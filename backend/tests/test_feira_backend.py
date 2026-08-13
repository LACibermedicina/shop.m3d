"""Feira Online backend integration tests.

Covers:
- Auth: dev-login, me, logout, invalid dev secret
- Stores CRUD (admin) + list/get
- Products CRUD, sort, RBAC (lojista cross-store)
- AI import (Gemini)
- Upload + files (Object Storage)
- Orders create/get/edit/status + public token access + PDF
- Admin metrics, users, role assignment
- RBAC / auth negatives
"""
import io
import os
import uuid
import base64
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://bazaar-app-85.preview.emergentagent.com").rstrip("/")
DEV_SECRET = os.environ.get("DEV_LOGIN_SECRET", "feira-dev-secret-2026")
API = f"{BASE_URL}/api"

# Module shared state (avoid pytest attr hack; safe for -p no:xdist)
STATE = {}
STORE_KEY = "store_id"
PRODUCT_KEY = "product_id"
OTHER_STORE_KEY = "other_store_id"
ORDER_KEY = "order_id"
ORDER_TOKEN_KEY = "order_token"
UPLOAD_KEY = "upload_path"

# 1x1 PNG (real, with data) — valid PNG magic
PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)


def _login(role, email=None):
    email = email or f"TEST_{role}_{uuid.uuid4().hex[:6]}@feira.test"
    r = requests.post(f"{API}/auth/dev-login",
                      headers={"X-Dev-Secret": DEV_SECRET, "Content-Type": "application/json"},
                      json={"email": email, "name": f"Test {role}", "role": role}, timeout=30)
    assert r.status_code == 200, f"dev-login failed for {role}: {r.status_code} {r.text}"
    data = r.json()
    return data["session_token"], data["user"]


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin():
    tok, u = _login("admin", "TEST_admin@feira.test")
    return tok, u


@pytest.fixture(scope="module")
def cliente():
    tok, u = _login("cliente", "TEST_cliente@feira.test")
    return tok, u


@pytest.fixture(scope="module")
def lojista():
    # Note: assigned via store creation below
    tok, u = _login("lojista", "TEST_lojista@feira.test")
    return tok, u


# -------------------- AUTH --------------------
class TestAuth:
    def test_dev_login_bad_secret(self):
        r = requests.post(f"{API}/auth/dev-login",
                          headers={"X-Dev-Secret": "wrong"},
                          json={"email": "x@y.com", "role": "cliente"})
        assert r.status_code == 403

    def test_dev_login_invalid_role(self):
        r = requests.post(f"{API}/auth/dev-login",
                          headers={"X-Dev-Secret": DEV_SECRET},
                          json={"email": "x@y.com", "role": "hacker"})
        assert r.status_code == 400

    def test_me_requires_auth(self):
        assert requests.get(f"{API}/auth/me").status_code == 401

    def test_me_ok(self, admin):
        tok, u = admin
        r = requests.get(f"{API}/auth/me", headers=_h(tok))
        assert r.status_code == 200
        assert r.json()["email"] == u["email"]
        assert r.json()["role"] == "admin"

    def test_logout(self):
        tok, _ = _login("cliente", f"TEST_logout_{uuid.uuid4().hex[:6]}@feira.test")
        assert requests.post(f"{API}/auth/logout", headers=_h(tok)).status_code == 200
        # session invalidated
        assert requests.get(f"{API}/auth/me", headers=_h(tok)).status_code == 401


# -------------------- STORES --------------------
class TestStores:
    def test_cliente_cannot_create_store(self, cliente):
        tok, _ = cliente
        r = requests.post(f"{API}/stores", headers=_h(tok),
                          json={"name": "X", "whatsapp": "+5511999999999"})
        assert r.status_code == 403

    def test_unauth_cannot_create_store(self):
        r = requests.post(f"{API}/stores", json={"name": "X", "whatsapp": "+55"})
        assert r.status_code == 401

    def test_admin_create_store_and_assign_lojista(self, admin, lojista):
        atok, _ = admin
        _, luser = lojista
        payload = {"name": "TEST_Barraca_Verde", "description": "Frutas frescas",
                   "logo": "", "whatsapp": "+5511987654321",
                   "owner_user_id": luser["user_id"]}
        r = requests.post(f"{API}/stores", headers=_h(atok), json=payload)
        assert r.status_code == 200, r.text
        store = r.json()
        assert store["name"] == payload["name"]
        assert store["whatsapp"] == payload["whatsapp"]
        assert store["id"].startswith("store_")
        STATE[STORE_KEY] = store["id"]

        # GET verify persisted
        g = requests.get(f"{API}/stores/{store['id']}")
        assert g.status_code == 200
        assert g.json()["name"] == payload["name"]

        # Lojista should now be assigned
        me = requests.get(f"{API}/auth/me",
                          headers={"Authorization": f"Bearer {lojista[0]}"}).json()
        assert me["role"] == "lojista"
        assert me["store_id"] == store["id"]

    def test_list_stores(self):
        r = requests.get(f"{API}/stores")
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert STATE[STORE_KEY] in ids

    def test_update_store_admin(self, admin):
        atok, _ = admin
        r = requests.put(f"{API}/stores/{STATE[STORE_KEY]}", headers=_h(atok),
                         json={"name": "TEST_Barraca_Verde_2", "whatsapp": "+5511987654321",
                               "description": "Atualizada"})
        assert r.status_code == 200
        assert r.json()["name"] == "TEST_Barraca_Verde_2"


# -------------------- PRODUCTS --------------------
class TestProducts:
    def test_lojista_create_product(self, lojista):
        tok, _ = lojista
        # refresh user to pick assigned store
        me = requests.get(f"{API}/auth/me", headers=_h(tok)).json()
        assert me["store_id"] == STATE[STORE_KEY]
        r = requests.post(f"{API}/products", headers=_h(tok),
                          json={"store_id": STATE[STORE_KEY], "name": "TEST_Banana",
                                "description": "Doce", "price": 5.5, "image": ""})
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["name"] == "TEST_Banana" and p["price"] == 5.5
        STATE[PRODUCT_KEY] = p["id"]

        # 2nd product for sort tests
        r2 = requests.post(f"{API}/products", headers=_h(tok),
                           json={"store_id": STATE[STORE_KEY], "name": "TEST_Abacaxi",
                                 "description": "", "price": 12.0, "image": ""})
        assert r2.status_code == 200

    def test_list_products_sort_name(self):
        r = requests.get(f"{API}/stores/{STATE[STORE_KEY]}/products?sort=name")
        assert r.status_code == 200
        names = [p["name"] for p in r.json() if p["name"].startswith("TEST_")]
        assert names == sorted(names)

    def test_list_products_sort_price_asc(self):
        r = requests.get(f"{API}/stores/{STATE[STORE_KEY]}/products?sort=price_asc")
        prices = [p["price"] for p in r.json() if p["name"].startswith("TEST_")]
        assert prices == sorted(prices)

    def test_lojista_cannot_manage_other_store(self, admin, lojista):
        atok, _ = admin
        # create another store, unowned
        r = requests.post(f"{API}/stores", headers=_h(atok),
                          json={"name": "TEST_OtherStore", "whatsapp": "+5500", "description": "", "logo": ""})
        other_store = r.json()["id"]
        STATE[OTHER_STORE_KEY] = other_store

        ltok, _ = lojista
        r = requests.post(f"{API}/products", headers=_h(ltok),
                          json={"store_id": other_store, "name": "hack", "price": 1})
        assert r.status_code == 403

    def test_update_product(self, lojista):
        tok, _ = lojista
        r = requests.put(f"{API}/products/{STATE[PRODUCT_KEY]}", headers=_h(tok),
                         json={"price": 6.0})
        assert r.status_code == 200
        assert r.json()["price"] == 6.0


# -------------------- UPLOAD --------------------
class TestUpload:
    def test_upload_and_fetch(self, lojista):
        tok, _ = lojista
        img_bytes = base64.b64decode(PNG_B64)
        files = {"file": ("t.png", io.BytesIO(img_bytes), "image/png")}
        r = requests.post(f"{API}/upload", headers={"Authorization": f"Bearer {tok}"},
                          files=files, timeout=60)
        assert r.status_code == 200, r.text
        path = r.json()["path"]
        assert path
        STATE[UPLOAD_KEY] = path
        # public fetch
        g = requests.get(f"{API}/files/{path}", timeout=30)
        assert g.status_code == 200
        assert g.content[:8].startswith(b"\x89PNG")


# -------------------- AI IMPORT --------------------
class TestAI:
    def test_ai_import_text(self, lojista):
        tok, _ = lojista
        msg = "Bom dia! Tenho tomate italiano super fresco, direto do sítio. R$ 8,90 o quilo."
        r = requests.post(f"{API}/products/ai-import", headers=_h(tok),
                          json={"store_id": STATE[STORE_KEY], "message": msg, "image": ""}, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "name" in d and "price" in d and "description" in d
        assert isinstance(d["price"], (int, float))
        # Sanity: expected price near 8.90
        assert 8.0 <= d["price"] <= 10.0 or d["price"] == 0

    def test_ai_import_rbac(self, cliente):
        tok, _ = cliente
        r = requests.post(f"{API}/products/ai-import", headers=_h(tok),
                          json={"store_id": STATE[STORE_KEY], "message": "x", "image": ""})
        assert r.status_code == 403


# -------------------- ORDERS --------------------
class TestOrders:
    def test_create_order(self, cliente):
        tok, _ = cliente
        items = [{"product_id": STATE[PRODUCT_KEY], "name": "TEST_Banana", "price": 6.0, "qty": 3}]
        r = requests.post(f"{API}/orders", headers=_h(tok),
                          json={"store_id": STATE[STORE_KEY], "items": items,
                                "customer_name": "Cliente Teste", "notes": "sem cebola"})
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["total"] == 18.0
        assert o["status"] == "novo" and o["editable"] is True
        assert o["token"]
        STATE[ORDER_KEY] = o["id"]
        STATE[ORDER_TOKEN_KEY] = o["token"]

    def test_get_order_by_token_public(self):
        r = requests.get(f"{API}/orders/{STATE[ORDER_KEY]}?token={STATE[ORDER_TOKEN_KEY]}")
        assert r.status_code == 200
        assert r.json()["id"] == STATE[ORDER_KEY]

    def test_get_order_bad_token_forbidden(self):
        r = requests.get(f"{API}/orders/{STATE[ORDER_KEY]}?token=nope")
        assert r.status_code == 403

    def test_my_orders(self, cliente):
        tok, _ = cliente
        r = requests.get(f"{API}/my/orders", headers=_h(tok))
        assert r.status_code == 200
        assert any(o["id"] == STATE[ORDER_KEY] for o in r.json())

    def test_vendor_orders(self, lojista):
        tok, _ = lojista
        r = requests.get(f"{API}/vendor/orders", headers=_h(tok))
        assert r.status_code == 200
        assert any(o["id"] == STATE[ORDER_KEY] for o in r.json())

    def test_update_order_items(self, cliente):
        tok, _ = cliente
        new_items = [{"product_id": STATE[PRODUCT_KEY], "name": "TEST_Banana", "price": 6.0, "qty": 5}]
        r = requests.put(f"{API}/orders/{STATE[ORDER_KEY]}", headers=_h(tok),
                         json={"items": new_items})
        assert r.status_code == 200
        assert r.json()["total"] == 30.0

    def test_update_status_vendor(self, lojista):
        tok, _ = lojista
        r = requests.put(f"{API}/orders/{STATE[ORDER_KEY]}/status", headers=_h(tok),
                         json={"status": "confirmado"})
        assert r.status_code == 200
        assert r.json()["status"] == "confirmado"
        assert r.json()["editable"] is False

    def test_pdf(self):
        r = requests.get(f"{API}/orders/{STATE[ORDER_KEY]}/pdf?token={STATE[ORDER_TOKEN_KEY]}", timeout=30)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF"


# -------------------- ADMIN --------------------
class TestAdmin:
    def test_admin_metrics(self, admin):
        tok, _ = admin
        r = requests.get(f"{API}/admin/metrics", headers=_h(tok))
        assert r.status_code == 200
        d = r.json()
        for k in ("stores", "products", "orders", "customers", "revenue"):
            assert k in d
        assert d["stores"] >= 1 and d["orders"] >= 1

    def test_admin_users(self, admin):
        tok, _ = admin
        r = requests.get(f"{API}/admin/users", headers=_h(tok))
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()]
        assert "test_admin@feira.test" in emails

    def test_cliente_forbidden_admin(self, cliente):
        tok, _ = cliente
        assert requests.get(f"{API}/admin/metrics", headers=_h(tok)).status_code == 403

    def test_set_role(self, admin):
        atok, _ = admin
        # Create a fresh user
        _, u = _login("cliente", f"TEST_promote_{uuid.uuid4().hex[:6]}@feira.test")
        r = requests.put(f"{API}/admin/users/{u['user_id']}/role", headers=_h(atok),
                         json={"role": "lojista", "store_id": STATE[STORE_KEY]})
        assert r.status_code == 200
        assert r.json()["role"] == "lojista"
        assert r.json()["store_id"] == STATE[STORE_KEY]


# -------------------- CLEANUP --------------------
class TestCleanup:
    def test_delete_store_admin(self, admin):
        tok, _ = admin
        assert requests.delete(f"{API}/stores/{STATE[OTHER_STORE_KEY]}",
                               headers=_h(tok)).status_code == 200
        # Deleted store hidden from list
        listed = [s["id"] for s in requests.get(f"{API}/stores").json()]
        assert STATE[OTHER_STORE_KEY] not in listed
