"""Lojas da Fronteira backend integration tests (iteration 2).

Coverage focus for this iteration:
- Dev-login is now server-gated by ALLOW_DEV_LOGIN, NO X-Dev-Secret header required
- Delete account (DELETE /api/auth/me) removes user and clears favorites/reviews/sessions
- Regression: stores, products (+ retail categories), favorites, reviews, coupons,
  order with coupon (subtotal/discount/total), store open/close/heartbeat,
  vendor report, admin metrics/users, PDF.
"""
import io
import os
import uuid
import base64
import pytest
import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

STATE = {}
PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)

RETAIL_CATEGORIES = [
    "Eletrônicos", "Informática", "Celulares", "Perfumaria", "Moda",
    "Calçados", "Casa & Decoração", "Brinquedos", "Bebidas", "Alimentos",
    "Acessórios", "Outros",
]


def _login(role, email=None):
    email = email or f"TEST_{role}_{uuid.uuid4().hex[:6]}@feira.test"
    r = requests.post(f"{API}/auth/dev-login",
                      json={"email": email, "name": f"Test {role}", "role": role},
                      timeout=30)
    assert r.status_code == 200, f"dev-login failed for {role}: {r.status_code} {r.text}"
    data = r.json()
    return data["session_token"], data["user"]


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin():
    return _login("admin", "TEST_admin@feira.test")


@pytest.fixture(scope="module")
def cliente():
    return _login("cliente", "TEST_cliente@feira.test")


@pytest.fixture(scope="module")
def lojista():
    return _login("lojista", "TEST_lojista@feira.test")


# -------------------- AUTH (server-gated dev-login) --------------------
class TestAuth:
    def test_dev_login_no_secret_works(self):
        # No header — ALLOW_DEV_LOGIN=true on preview
        r = requests.post(f"{API}/auth/dev-login",
                          json={"email": f"TEST_noheader_{uuid.uuid4().hex[:6]}@feira.test",
                                "role": "cliente", "name": "n"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "session_token" in d and "user" in d
        assert d["user"]["role"] == "cliente"

    def test_dev_login_invalid_role(self):
        r = requests.post(f"{API}/auth/dev-login",
                          json={"email": "x@y.com", "role": "hacker"})
        assert r.status_code == 400

    def test_dev_login_all_roles(self):
        for role in ("admin", "lojista", "cliente"):
            tok, u = _login(role, f"TEST_role_{role}_{uuid.uuid4().hex[:6]}@feira.test")
            assert u["role"] == role
            me = requests.get(f"{API}/auth/me", headers=_h(tok))
            assert me.status_code == 200
            assert me.json()["role"] == role

    def test_me_requires_auth(self):
        assert requests.get(f"{API}/auth/me").status_code == 401

    def test_logout(self):
        tok, _ = _login("cliente", f"TEST_logout_{uuid.uuid4().hex[:6]}@feira.test")
        assert requests.post(f"{API}/auth/logout", headers=_h(tok)).status_code == 200
        assert requests.get(f"{API}/auth/me", headers=_h(tok)).status_code == 401


# -------------------- DELETE ACCOUNT --------------------
class TestDeleteAccount:
    def test_delete_account_requires_auth(self):
        assert requests.delete(f"{API}/auth/me").status_code == 401

    def test_delete_account_removes_user_and_data(self):
        # Create user + a store to favorite + a review, then DELETE /auth/me
        # Create a store via admin
        atok, _ = _login("admin", f"TEST_admin_del_{uuid.uuid4().hex[:6]}@feira.test")
        s = requests.post(f"{API}/stores", headers=_h(atok),
                          json={"name": f"TEST_DeleteStore_{uuid.uuid4().hex[:4]}",
                                "whatsapp": "+5511900000000", "description": ""}).json()
        # Create cliente
        ctok, cuser = _login("cliente", f"TEST_del_{uuid.uuid4().hex[:6]}@feira.test")
        # Add favorite
        assert requests.post(f"{API}/favorites/{s['id']}", headers=_h(ctok)).status_code == 200
        assert requests.get(f"{API}/my/favorite-ids", headers=_h(ctok)).json() == [s["id"]]
        # Add review
        rv = requests.post(f"{API}/stores/{s['id']}/reviews", headers=_h(ctok),
                           json={"rating": 5, "comment": "Ótimo"})
        assert rv.status_code == 200
        # Delete account
        r = requests.delete(f"{API}/auth/me", headers=_h(ctok))
        assert r.status_code == 200
        assert r.json().get("ok") is True
        # Session invalidated -> 401
        assert requests.get(f"{API}/auth/me", headers=_h(ctok)).status_code == 401
        # Reviews for that user should be gone
        rj = requests.get(f"{API}/stores/{s['id']}/reviews").json()
        reviews = rj.get("reviews", []) if isinstance(rj, dict) else rj
        assert not any(x.get("user_id") == cuser["user_id"] for x in reviews)


# -------------------- STORES --------------------
class TestStores:
    def test_admin_create_and_assign_lojista(self, admin, lojista):
        atok, _ = admin
        _, luser = lojista
        payload = {"name": f"TEST_Barraca_{uuid.uuid4().hex[:4]}",
                   "description": "Loja de varejo",
                   "logo": "", "whatsapp": "+5511987654321",
                   "owner_user_id": luser["user_id"]}
        r = requests.post(f"{API}/stores", headers=_h(atok), json=payload)
        assert r.status_code == 200, r.text
        store = r.json()
        assert store["name"] == payload["name"]
        assert store["id"].startswith("store_")
        STATE["store_id"] = store["id"]

    def test_list_stores(self):
        r = requests.get(f"{API}/stores")
        assert r.status_code == 200
        assert STATE["store_id"] in [s["id"] for s in r.json()]

    def test_cliente_cannot_create_store(self, cliente):
        tok, _ = cliente
        r = requests.post(f"{API}/stores", headers=_h(tok),
                          json={"name": "X", "whatsapp": "+55"})
        assert r.status_code == 403


# -------------------- PRODUCTS + RETAIL CATEGORIES --------------------
class TestProducts:
    def test_lojista_create_products_all_categories(self, lojista):
        tok, _ = lojista
        me = requests.get(f"{API}/auth/me", headers=_h(tok)).json()
        assert me["store_id"] == STATE["store_id"]
        ids = []
        for i, cat in enumerate(RETAIL_CATEGORIES):
            r = requests.post(f"{API}/products", headers=_h(tok),
                              json={"store_id": STATE["store_id"],
                                    "name": f"TEST_prod_{cat}_{i}",
                                    "description": "", "price": 10.0 + i,
                                    "category": cat, "image": ""})
            assert r.status_code == 200, r.text
            p = r.json()
            assert p["category"] == cat
            ids.append(p["id"])
        STATE["product_ids"] = ids
        STATE["product_id"] = ids[0]

    def test_filter_products_by_category(self):
        # Pick a distinct category and verify only those come back
        cat = "Perfumaria"
        r = requests.get(f"{API}/stores/{STATE['store_id']}/products?category={cat}")
        assert r.status_code == 200
        got = r.json()
        assert len(got) >= 1
        for p in got:
            assert p["category"] == cat

    def test_list_sort_price_asc(self):
        r = requests.get(f"{API}/stores/{STATE['store_id']}/products?sort=price_asc")
        assert r.status_code == 200
        prices = [p["price"] for p in r.json() if p["name"].startswith("TEST_prod_")]
        assert prices == sorted(prices)


# -------------------- FAVORITES --------------------
class TestFavorites:
    def test_favorite_flow(self, cliente):
        tok, _ = cliente
        sid = STATE["store_id"]
        # add
        assert requests.post(f"{API}/favorites/{sid}", headers=_h(tok)).status_code == 200
        assert sid in requests.get(f"{API}/my/favorite-ids", headers=_h(tok)).json()
        favs = requests.get(f"{API}/my/favorites", headers=_h(tok)).json()
        assert any(s["id"] == sid for s in favs)
        # remove
        assert requests.delete(f"{API}/favorites/{sid}", headers=_h(tok)).status_code == 200
        assert sid not in requests.get(f"{API}/my/favorite-ids", headers=_h(tok)).json()


# -------------------- REVIEWS --------------------
class TestReviews:
    def test_add_review_and_avg(self, cliente):
        tok, _ = cliente
        sid = STATE["store_id"]
        r = requests.post(f"{API}/stores/{sid}/reviews", headers=_h(tok),
                          json={"rating": 5, "comment": "Excelente atendimento"})
        assert r.status_code == 200, r.text
        # list
        rl = requests.get(f"{API}/stores/{sid}/reviews")
        assert rl.status_code == 200
        rlj = rl.json()
        reviews = rlj.get("reviews", []) if isinstance(rlj, dict) else rlj
        assert any(rv["rating"] == 5 for rv in reviews)
        # rating aggregated in list response
        if isinstance(rlj, dict):
            assert rlj.get("review_count", rlj.get("rating_count", 0)) >= 1
            assert rlj.get("avg_rating", rlj.get("rating_avg", 0)) >= 5.0


# -------------------- COUPONS + ORDER WITH COUPON --------------------
class TestCoupons:
    def test_create_list_apply_coupon(self, lojista):
        tok, _ = lojista
        code = f"TEST{uuid.uuid4().hex[:5].upper()}"
        # create 10% coupon
        r = requests.post(f"{API}/coupons", headers=_h(tok),
                          json={"store_id": STATE["store_id"], "code": code,
                                "type": "percent", "value": 10})
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["code"] == code and c["type"] == "percent"
        STATE["coupon_id"] = c["id"]
        STATE["coupon_code"] = code
        # list
        lst = requests.get(f"{API}/vendor/coupons", headers=_h(tok)).json()
        assert any(x["code"] == code for x in lst)
        # apply
        a = requests.post(f"{API}/coupons/apply", headers=_h(tok),
                          json={"store_id": STATE["store_id"], "code": code, "subtotal": 100.0})
        assert a.status_code == 200
        aj = a.json()
        assert aj["valid"] is True and aj["discount"] == 10.0 and aj["total"] == 90.0

    def test_order_with_coupon(self, cliente):
        tok, _ = cliente
        code = STATE["coupon_code"]
        pid = STATE["product_id"]
        items = [{"product_id": pid, "name": "TEST_prod", "price": 10.0, "qty": 5}]
        r = requests.post(f"{API}/orders", headers=_h(tok),
                          json={"store_id": STATE["store_id"], "items": items,
                                "customer_name": "Cliente Teste",
                                "coupon_code": code})
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["subtotal"] == 50.0
        assert o["discount"] == 5.0
        assert o["total"] == 45.0
        assert o["coupon_code"] == code
        STATE["order_id"] = o["id"]
        STATE["order_token"] = o["token"]

    def test_delete_coupon(self, lojista):
        tok, _ = lojista
        r = requests.delete(f"{API}/coupons/{STATE['coupon_id']}", headers=_h(tok))
        assert r.status_code == 200
        # apply should now be invalid
        a = requests.post(f"{API}/coupons/apply", headers=_h(tok),
                          json={"store_id": STATE["store_id"], "code": STATE["coupon_code"],
                                "subtotal": 100.0}).json()
        assert a["valid"] is False


# -------------------- ORDER PDF --------------------
class TestOrderPDF:
    def test_pdf_download(self):
        r = requests.get(
            f"{API}/orders/{STATE['order_id']}/pdf?token={STATE['order_token']}",
            timeout=30)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF"


# -------------------- STORE OPEN / HEARTBEAT --------------------
class TestStorePresence:
    def test_set_open_and_heartbeat(self, lojista):
        tok, _ = lojista
        # Open
        r = requests.put(f"{API}/vendor/store/open", headers=_h(tok),
                         json={"is_open": True})
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["is_open"] is True
        assert "online" in s
        # Heartbeat
        hb = requests.post(f"{API}/vendor/heartbeat", headers=_h(tok))
        assert hb.status_code == 200
        hbj = hb.json()
        assert hbj["is_open"] is True
        assert hbj["online"] is True
        # Store listing should now reflect
        listed = requests.get(f"{API}/stores").json()
        mine = next(x for x in listed if x["id"] == STATE["store_id"])
        assert mine.get("online") is True or mine.get("is_open") is True
        # Close
        r2 = requests.put(f"{API}/vendor/store/open", headers=_h(tok),
                          json={"is_open": False})
        assert r2.status_code == 200 and r2.json()["is_open"] is False


# -------------------- VENDOR REPORT --------------------
class TestVendorReport:
    def test_vendor_report(self, lojista):
        tok, _ = lojista
        r = requests.get(f"{API}/vendor/report", headers=_h(tok))
        assert r.status_code == 200
        d = r.json()
        for k in ("daily", "weekly", "total", "orders"):
            assert k in d
        assert isinstance(d["daily"], list) and len(d["daily"]) == 7
        assert isinstance(d["weekly"], list) and len(d["weekly"]) == 4
        assert d["orders"] >= 1


# -------------------- ADMIN --------------------
class TestAdmin:
    def test_metrics(self, admin):
        tok, _ = admin
        r = requests.get(f"{API}/admin/metrics", headers=_h(tok))
        assert r.status_code == 200
        d = r.json()
        for k in ("stores", "products", "orders", "customers", "revenue"):
            assert k in d
        assert d["stores"] >= 1

    def test_users(self, admin):
        tok, _ = admin
        r = requests.get(f"{API}/admin/users", headers=_h(tok))
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()]
        assert "test_admin@feira.test" in emails

    def test_cliente_forbidden(self, cliente):
        tok, _ = cliente
        assert requests.get(f"{API}/admin/metrics", headers=_h(tok)).status_code == 403


# -------------------- UPLOAD (regression) --------------------
class TestUpload:
    def test_upload_and_fetch(self, lojista):
        tok, _ = lojista
        img_bytes = base64.b64decode(PNG_B64)
        files = {"file": ("t.png", io.BytesIO(img_bytes), "image/png")}
        r = requests.post(f"{API}/upload", headers={"Authorization": f"Bearer {tok}"},
                          files=files, timeout=60)
        assert r.status_code == 200, r.text
        path = r.json()["path"]
        g = requests.get(f"{API}/files/{path}", timeout=30)
        assert g.status_code == 200
        assert g.content[:8].startswith(b"\x89PNG")
