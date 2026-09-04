"""SHOP.M3D.pro imported-app smoke test (iteration N).

Validates the imported repo behaves end-to-end:
- Username/password login for the 4 seeded accounts (root, admin, lojista, cliente)
- /api/auth/me returns correct role for each token
- Public endpoints (/api/home, /api/stores, /api/whatsapp/status)
- Admin flows: /api/admin/metrics, /api/admin/users, /api/groups
- Vendor flows: create store (admin) -> create product (lojista) -> vendor/report
- Customer flows: /api/my/orders, /api/my/catalog-stores
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

SEEDED = {
    "root":    ("root",    "@0root",    "master"),
    "admin":   ("admin",   "@0admin",   "admin"),
    "lojista": ("lojista", "@0lojista", "lojista"),
    "cliente": ("cliente", "@0cliente", "cliente"),
}

STATE = {}


def _login(username, password):
    r = requests.post(f"{API}/auth/login",
                      json={"username": username, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {username} => {r.status_code} {r.text}"
    d = r.json()
    assert "session_token" in d and "user" in d
    return d["session_token"], d["user"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tokens():
    out = {}
    for key, (u, p, _role) in SEEDED.items():
        tok, user = _login(u, p)
        out[key] = {"token": tok, "user": user}
    return out


# -------------------- 1) LOGIN + /auth/me --------------------
class TestSeededLogin:
    def test_login_root_master(self):
        tok, u = _login("root", "@0root")
        assert u["role"] == "master"
        assert u["username"] == "root"

    def test_login_admin(self):
        tok, u = _login("admin", "@0admin")
        assert u["role"] == "admin"

    def test_login_lojista(self):
        tok, u = _login("lojista", "@0lojista")
        assert u["role"] == "lojista"

    def test_login_cliente(self):
        tok, u = _login("cliente", "@0cliente")
        assert u["role"] == "cliente"

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login",
                          json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401

    def test_login_missing_fields(self):
        r = requests.post(f"{API}/auth/login", json={"username": "admin"})
        assert r.status_code in (400, 422)

    def test_me_with_each_token(self, tokens):
        for key, expected in [
            ("root", "master"), ("admin", "admin"),
            ("lojista", "lojista"), ("cliente", "cliente"),
        ]:
            r = requests.get(f"{API}/auth/me", headers=_h(tokens[key]["token"]))
            assert r.status_code == 200, f"/auth/me {key} => {r.status_code} {r.text}"
            assert r.json()["role"] == expected

    def test_me_without_token(self):
        assert requests.get(f"{API}/auth/me").status_code == 401


# -------------------- 2) PUBLIC ENDPOINTS --------------------
class TestPublic:
    def test_home(self):
        r = requests.get(f"{API}/home", timeout=30)
        assert r.status_code == 200
        data = r.json()
        # Home should return object or list; sanity check structure
        assert isinstance(data, (dict, list))

    def test_list_stores(self):
        r = requests.get(f"{API}/stores", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_whatsapp_status(self):
        r = requests.get(f"{API}/whatsapp/status", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, dict)


# -------------------- 3) ADMIN FLOWS --------------------
class TestAdminFlows:
    def test_admin_metrics(self, tokens):
        r = requests.get(f"{API}/admin/metrics", headers=_h(tokens["admin"]["token"]))
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("stores", "products", "orders", "customers", "revenue"):
            assert k in d, f"missing metric key: {k}"

    def test_admin_users_as_master(self, tokens):
        # /api/admin/users for master returns ALL users; for non-master admin it
        # returns only lojistas of stores bound to that admin (may be empty).
        r = requests.get(f"{API}/admin/users", headers=_h(tokens["root"]["token"]))
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list) and len(users) >= 4
        roles = {u.get("role") for u in users}
        assert {"admin", "lojista", "cliente"}.issubset(roles)

    def test_admin_users_scoped_for_common_admin(self, tokens):
        # Sanity: seeded admin (not master) still returns 200 (list may be empty)
        r = requests.get(f"{API}/admin/users", headers=_h(tokens["admin"]["token"]))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_groups_public_get(self):
        r = requests.get(f"{API}/groups", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_cliente_forbidden_admin(self, tokens):
        r = requests.get(f"{API}/admin/metrics",
                         headers=_h(tokens["cliente"]["token"]))
        assert r.status_code == 403


# -------------------- 4) VENDOR FLOW (create store as admin, assign to lojista) --------------------
class TestVendorFlow:
    def test_admin_create_store_for_lojista(self, tokens):
        atok = tokens["admin"]["token"]
        luser = tokens["lojista"]["user"]
        payload = {
            "name": f"TEST_ShopM3D_Store_{uuid.uuid4().hex[:5]}",
            "description": "Loja de teste de importação",
            "logo": "",
            "whatsapp": "+5511999999999",
            "owner_user_id": luser["user_id"],
        }
        r = requests.post(f"{API}/stores", headers=_h(atok), json=payload)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["name"] == payload["name"]
        assert s["id"].startswith("store_")
        STATE["store_id"] = s["id"]

    def test_lojista_me_has_store(self, tokens):
        # After assignment, /auth/me for lojista should have store_id
        r = requests.get(f"{API}/auth/me",
                         headers=_h(tokens["lojista"]["token"]))
        assert r.status_code == 200
        j = r.json()
        assert j.get("store_id") == STATE["store_id"], j

    def test_lojista_create_product(self, tokens):
        tok = tokens["lojista"]["token"]
        r = requests.post(f"{API}/products", headers=_h(tok), json={
            "store_id": STATE["store_id"],
            "name": f"TEST_prod_{uuid.uuid4().hex[:4]}",
            "description": "produto teste",
            "price": 19.9,
            "category": "Eletrônicos",
            "image": "",
        })
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["price"] == 19.9
        assert p["store_id"] == STATE["store_id"]
        STATE["product_id"] = p["id"]

    def test_vendor_report(self, tokens):
        tok = tokens["lojista"]["token"]
        r = requests.get(f"{API}/vendor/report", headers=_h(tok))
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("daily", "weekly", "total", "orders"):
            assert k in d, f"missing key: {k}"
        assert isinstance(d["daily"], list) and len(d["daily"]) == 7


# -------------------- 5) CUSTOMER FLOW --------------------
class TestCustomerFlow:
    def test_my_orders(self, tokens):
        r = requests.get(f"{API}/my/orders",
                         headers=_h(tokens["cliente"]["token"]))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_my_catalog_stores(self, tokens):
        r = requests.get(f"{API}/my/catalog-stores",
                         headers=_h(tokens["cliente"]["token"]))
        assert r.status_code == 200
        assert isinstance(r.json(), (list, dict))


# -------------------- 6) CLEANUP --------------------
class TestCleanup:
    def test_cleanup_store_and_product(self, tokens):
        # Best-effort teardown, do not fail if endpoints don't allow deletion
        if STATE.get("product_id"):
            requests.delete(f"{API}/products/{STATE['product_id']}",
                            headers=_h(tokens["lojista"]["token"]))
        if STATE.get("store_id"):
            requests.delete(f"{API}/stores/{STATE['store_id']}",
                            headers=_h(tokens["admin"]["token"]))
