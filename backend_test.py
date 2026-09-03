#!/usr/bin/env python3
"""
Backend API Testing for Lojas da Fronteira - Role-Based Permission Model
Tests master auto-promotion, admin restrictions, store ownership, and product scoping
"""

import requests
import json
import sys
from typing import Dict, Optional

# Backend URL - using the public URL from environment
BASE_URL = "https://mobile-preview-871.preview.emergentagent.com/api"

# Test configuration
MASTER_EMAIL = "lucasmedicina86@gmail.com"
ADMIN1_EMAIL = "admin1@test.com"
ADMIN2_EMAIL = "admin2@test.com"
VENDOR_EMAIL = "vend1@test.com"

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_pass(self, test_name: str):
        self.passed += 1
        print(f"{GREEN}✓{RESET} {test_name}")
    
    def add_fail(self, test_name: str, reason: str):
        self.failed += 1
        error_msg = f"{test_name}: {reason}"
        self.errors.append(error_msg)
        print(f"{RED}✗{RESET} {test_name}")
        print(f"  {RED}Reason: {reason}{RESET}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Test Summary: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"\n{RED}Failed Tests:{RESET}")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}\n")
        return self.failed == 0

def dev_login(email: str, role: str, name: str = "") -> Dict:
    """Login using dev-login endpoint"""
    url = f"{BASE_URL}/auth/dev-login"
    payload = {"email": email, "role": role, "name": name or email.split("@")[0]}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            "token": data.get("session_token"),
            "user": data.get("user"),
            "status_code": resp.status_code
        }
    except Exception as e:
        return {"error": str(e), "status_code": getattr(e.response, 'status_code', 0) if hasattr(e, 'response') else 0}

def api_call(method: str, endpoint: str, token: Optional[str] = None, 
             json_data: Optional[Dict] = None, expected_status: int = 200) -> Dict:
    """Make an API call with optional authentication"""
    url = f"{BASE_URL}{endpoint}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=json_data, timeout=10)
        elif method == "PUT":
            resp = requests.put(url, headers=headers, json=json_data, timeout=10)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=10)
        else:
            return {"error": f"Unsupported method: {method}"}
        
        return {
            "status_code": resp.status_code,
            "data": resp.json() if resp.content else {},
            "success": resp.status_code == expected_status
        }
    except Exception as e:
        return {
            "error": str(e),
            "status_code": getattr(e.response, 'status_code', 0) if hasattr(e, 'response') else 0,
            "success": False
        }

def test_master_auto_promotion(result: TestResult):
    """Test 1: Master auto-promotion by email"""
    print(f"\n{BLUE}=== Test 1: Master Auto-Promotion ==={RESET}")
    
    # Test 1a: Master email with cliente role should return master
    print("\n1a. Master email with 'cliente' role should auto-promote to 'master'")
    login = dev_login(MASTER_EMAIL, "cliente", "Master User")
    if "error" in login:
        result.add_fail("Master auto-promotion (cliente->master)", login["error"])
    elif login.get("user", {}).get("role") != "master":
        result.add_fail("Master auto-promotion (cliente->master)", 
                       f"Expected role 'master', got '{login.get('user', {}).get('role')}'")
    else:
        result.add_pass("Master auto-promotion (cliente->master)")
    
    # Test 1b: Master email with master role should work
    print("\n1b. Master email with 'master' role should work")
    login = dev_login(MASTER_EMAIL, "master", "Master User")
    if "error" in login:
        result.add_fail("Master login with master role", login["error"])
    elif login.get("user", {}).get("role") != "master":
        result.add_fail("Master login with master role", 
                       f"Expected role 'master', got '{login.get('user', {}).get('role')}'")
    else:
        result.add_pass("Master login with master role")
    
    # Test 1c: Non-master email with master role should work
    print("\n1c. Non-master email with 'master' role should work")
    login = dev_login("other@test.com", "master", "Other Master")
    if "error" in login:
        result.add_fail("Non-master email with master role", login["error"])
    elif login.get("user", {}).get("role") != "master":
        result.add_fail("Non-master email with master role", 
                       f"Expected role 'master', got '{login.get('user', {}).get('role')}'")
    else:
        result.add_pass("Non-master email with master role")
    
    return login.get("token") if "error" not in login else None

def test_master_capabilities(result: TestResult, master_token: str):
    """Test 2: Master capabilities"""
    print(f"\n{BLUE}=== Test 2: Master Capabilities ==={RESET}")
    
    # Test 2a: GET /master/overview
    print("\n2a. GET /api/master/overview should return 200 with users, stores, counts")
    resp = api_call("GET", "/master/overview", master_token)
    if not resp.get("success"):
        result.add_fail("GET /master/overview", 
                       f"Status {resp.get('status_code')}, expected 200")
    elif not all(k in resp.get("data", {}) for k in ["users", "stores", "counts"]):
        result.add_fail("GET /master/overview", 
                       "Missing required fields: users, stores, or counts")
    else:
        result.add_pass("GET /master/overview")
    
    # Test 2b: POST /master/users - create vendor
    print("\n2b. POST /api/master/users to create vendor")
    resp = api_call("POST", "/master/users", master_token, 
                   {"email": VENDOR_EMAIL, "role": "lojista", "name": "Vendor 1"})
    vendor_user_id = None
    if not resp.get("success"):
        result.add_fail("POST /master/users (create vendor)", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        vendor_user_id = resp.get("data", {}).get("user_id")
        result.add_pass("POST /master/users (create vendor)")
    
    # Test 2c: PUT /admin/users/{user_id}/role - master can change roles
    print("\n2c. PUT /api/admin/users/{user_id}/role - master can change to admin")
    if vendor_user_id:
        resp = api_call("PUT", f"/admin/users/{vendor_user_id}/role", master_token,
                       {"role": "admin"})
        if not resp.get("success"):
            result.add_fail("PUT /admin/users/{id}/role (master)", 
                           f"Status {resp.get('status_code')}, expected 200")
        elif resp.get("data", {}).get("role") != "admin":
            result.add_fail("PUT /admin/users/{id}/role (master)", 
                           f"Role not updated, got '{resp.get('data', {}).get('role')}'")
        else:
            result.add_pass("PUT /admin/users/{id}/role (master)")
    else:
        result.add_fail("PUT /admin/users/{id}/role (master)", 
                       "Skipped - no vendor user created")
    
    # Test 2d: DELETE /master/users - delete non-master user
    print("\n2d. DELETE /api/master/users/{user_id} - delete non-master user")
    if vendor_user_id:
        resp = api_call("DELETE", f"/master/users/{vendor_user_id}", master_token)
        if not resp.get("success"):
            result.add_fail("DELETE /master/users (non-master)", 
                           f"Status {resp.get('status_code')}, expected 200")
        else:
            result.add_pass("DELETE /master/users (non-master)")
    else:
        result.add_fail("DELETE /master/users (non-master)", 
                       "Skipped - no vendor user created")
    
    # Test 2e: DELETE /master/users - attempt to delete master's own account
    print("\n2e. DELETE /api/master/users/{own_id} should return 400")
    # Get master's user_id
    resp = api_call("GET", "/auth/me", master_token)
    if resp.get("success"):
        master_user_id = resp.get("data", {}).get("user_id")
        resp = api_call("DELETE", f"/master/users/{master_user_id}", master_token, 
                       expected_status=400)
        if resp.get("status_code") != 400:
            result.add_fail("DELETE /master/users (self)", 
                           f"Expected 400, got {resp.get('status_code')}")
        else:
            result.add_pass("DELETE /master/users (self) - correctly blocked")
    else:
        result.add_fail("DELETE /master/users (self)", 
                       "Could not get master user_id")

def test_admin_restrictions(result: TestResult):
    """Test 3: Admin restrictions"""
    print(f"\n{BLUE}=== Test 3: Admin Restrictions ==={RESET}")
    
    # Create admin1
    print("\n3a. Create admin1 via dev-login")
    login = dev_login(ADMIN1_EMAIL, "admin", "Admin One")
    if "error" in login:
        result.add_fail("Create admin1", login["error"])
        return None, None
    
    admin1_token = login.get("token")
    admin1_user_id = login.get("user", {}).get("user_id")
    
    if login.get("user", {}).get("role") != "admin":
        result.add_fail("Create admin1", 
                       f"Expected role 'admin', got '{login.get('user', {}).get('role')}'")
        return None, None
    else:
        result.add_pass("Create admin1")
    
    # Test 3b: Admin cannot change roles
    print("\n3b. Admin PUT /api/admin/users/{id}/role should return 403")
    # Create a test user first
    test_login = dev_login("testuser@test.com", "cliente", "Test User")
    if "error" not in test_login:
        test_user_id = test_login.get("user", {}).get("user_id")
        resp = api_call("PUT", f"/admin/users/{test_user_id}/role", admin1_token,
                       {"role": "lojista"}, expected_status=403)
        if resp.get("status_code") != 403:
            result.add_fail("Admin PUT /admin/users/{id}/role (should be 403)", 
                           f"Expected 403, got {resp.get('status_code')}")
        else:
            result.add_pass("Admin PUT /admin/users/{id}/role - correctly blocked (403)")
    else:
        result.add_fail("Admin PUT /admin/users/{id}/role", 
                       "Could not create test user")
    
    # Test 3c: Admin GET /admin/metrics should return 200 but scoped
    print("\n3c. Admin GET /api/admin/metrics should return 200 (scoped)")
    resp = api_call("GET", "/admin/metrics", admin1_token)
    if not resp.get("success"):
        result.add_fail("Admin GET /admin/metrics", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        # Should show 0 stores initially since none linked to admin1
        stores_count = resp.get("data", {}).get("stores", -1)
        result.add_pass(f"Admin GET /admin/metrics (stores: {stores_count})")
    
    # Test 3d: Admin GET /admin/users should return 200 (empty initially)
    print("\n3d. Admin GET /api/admin/users should return 200 (empty initially)")
    resp = api_call("GET", "/admin/users", admin1_token)
    if not resp.get("success"):
        result.add_fail("Admin GET /admin/users", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        users = resp.get("data", [])
        result.add_pass(f"Admin GET /admin/users (returned {len(users)} users)")
    
    return admin1_token, admin1_user_id

def test_store_ownership(result: TestResult, admin1_token: str, admin1_user_id: str):
    """Test 4: Store ownership by admin_id"""
    print(f"\n{BLUE}=== Test 4: Store Ownership (admin_id) ==={RESET}")
    
    # Test 4a: Admin1 creates Loja A
    print("\n4a. Admin1 POST /api/stores - should set admin_id to admin1's user_id")
    resp = api_call("POST", "/stores", admin1_token,
                   {"name": "Loja A", "whatsapp": "5545999999999", "description": "Test Store A"})
    loja_a_id = None
    if not resp.get("success"):
        result.add_fail("Admin1 create Loja A", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        loja_a_id = resp.get("data", {}).get("id")
        returned_admin_id = resp.get("data", {}).get("admin_id")
        if returned_admin_id != admin1_user_id:
            result.add_fail("Admin1 create Loja A (admin_id check)", 
                           f"Expected admin_id={admin1_user_id}, got {returned_admin_id}")
        else:
            result.add_pass("Admin1 create Loja A (admin_id correctly set)")
    
    # Test 4b: Create admin2 and Loja B
    print("\n4b. Create admin2 and Loja B")
    login = dev_login(ADMIN2_EMAIL, "admin", "Admin Two")
    if "error" in login:
        result.add_fail("Create admin2", login["error"])
        return loja_a_id, None, None, None
    
    admin2_token = login.get("token")
    admin2_user_id = login.get("user", {}).get("user_id")
    result.add_pass("Create admin2")
    
    resp = api_call("POST", "/stores", admin2_token,
                   {"name": "Loja B", "whatsapp": "5545888888888", "description": "Test Store B"})
    loja_b_id = None
    if not resp.get("success"):
        result.add_fail("Admin2 create Loja B", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        loja_b_id = resp.get("data", {}).get("id")
        returned_admin_id = resp.get("data", {}).get("admin_id")
        if returned_admin_id != admin2_user_id:
            result.add_fail("Admin2 create Loja B (admin_id check)", 
                           f"Expected admin_id={admin2_user_id}, got {returned_admin_id}")
        else:
            result.add_pass("Admin2 create Loja B (admin_id correctly set)")
    
    # Test 4c: Admin1 tries to update Loja B (should fail with 403)
    print("\n4c. Admin1 PUT /api/stores/{Loja B id} should return 403")
    if loja_b_id:
        resp = api_call("PUT", f"/stores/{loja_b_id}", admin1_token,
                       {"name": "Loja B Modified", "whatsapp": "5545888888888"}, 
                       expected_status=403)
        if resp.get("status_code") != 403:
            result.add_fail("Admin1 update Loja B (should be 403)", 
                           f"Expected 403, got {resp.get('status_code')}")
        else:
            result.add_pass("Admin1 update Loja B - correctly blocked (403)")
    else:
        result.add_fail("Admin1 update Loja B", "Loja B not created")
    
    # Test 4d: Admin1 tries to delete Loja B (should fail with 403)
    print("\n4d. Admin1 DELETE /api/stores/{Loja B id} should return 403")
    if loja_b_id:
        resp = api_call("DELETE", f"/stores/{loja_b_id}", admin1_token, 
                       expected_status=403)
        if resp.get("status_code") != 403:
            result.add_fail("Admin1 delete Loja B (should be 403)", 
                           f"Expected 403, got {resp.get('status_code')}")
        else:
            result.add_pass("Admin1 delete Loja B - correctly blocked (403)")
    else:
        result.add_fail("Admin1 delete Loja B", "Loja B not created")
    
    # Test 4e: Admin1 GET /admin/metrics should count only Loja A
    print("\n4e. Admin1 GET /api/admin/metrics should count 1 store (Loja A)")
    resp = api_call("GET", "/admin/metrics", admin1_token)
    if not resp.get("success"):
        result.add_fail("Admin1 metrics after Loja A", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        stores_count = resp.get("data", {}).get("stores", -1)
        if stores_count != 1:
            result.add_fail("Admin1 metrics store count", 
                           f"Expected 1 store, got {stores_count}")
        else:
            result.add_pass("Admin1 metrics shows 1 store (Loja A only)")
    
    return loja_a_id, loja_b_id, admin2_token, admin2_user_id

def test_store_reassignment(result: TestResult, master_token: str, admin1_token: str, 
                           admin1_user_id: str, loja_b_id: str):
    """Test 4f: Master reassigns Loja B to admin1"""
    print(f"\n{BLUE}=== Test 4f: Master Store Reassignment ==={RESET}")
    
    if not loja_b_id:
        result.add_fail("Master reassign Loja B", "Loja B not available")
        return
    
    # Master reassigns Loja B to admin1
    print("\n4f. Master PUT /api/master/stores/{Loja B id}/assign to admin1")
    resp = api_call("PUT", f"/master/stores/{loja_b_id}/assign", master_token,
                   {"admin_id": admin1_user_id})
    if not resp.get("success"):
        result.add_fail("Master reassign Loja B to admin1", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        result.add_pass("Master reassign Loja B to admin1")
    
    # Admin1 metrics should now show 2 stores
    print("\n4g. Admin1 GET /api/admin/metrics should now count 2 stores")
    resp = api_call("GET", "/admin/metrics", admin1_token)
    if not resp.get("success"):
        result.add_fail("Admin1 metrics after reassignment", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        stores_count = resp.get("data", {}).get("stores", -1)
        if stores_count != 2:
            result.add_fail("Admin1 metrics after reassignment", 
                           f"Expected 2 stores, got {stores_count}")
        else:
            result.add_pass("Admin1 metrics shows 2 stores after reassignment")

def test_product_scoping(result: TestResult, admin2_token: str, loja_a_id: str, loja_b_id: str):
    """Test 5: Product scoping"""
    print(f"\n{BLUE}=== Test 5: Product Scoping ==={RESET}")
    
    if not loja_a_id or not loja_b_id:
        result.add_fail("Product scoping test", "Required stores not available")
        return
    
    # Note: After reassignment, Loja B belongs to admin1, not admin2
    # So admin2 should NOT be able to create products for Loja B
    print("\n5a. Admin2 POST /api/products for Loja B (not owned) should return 403")
    resp = api_call("POST", "/products", admin2_token,
                   {"store_id": loja_b_id, "name": "Test Product", 
                    "description": "Test", "price": 99.99, "category": "Outros"},
                   expected_status=403)
    if resp.get("status_code") != 403:
        result.add_fail("Admin2 create product for non-owned store", 
                       f"Expected 403, got {resp.get('status_code')}")
    else:
        result.add_pass("Admin2 create product for non-owned store - correctly blocked (403)")

def test_public_endpoints(result: TestResult):
    """Test 6: Public endpoints work without auth"""
    print(f"\n{BLUE}=== Test 6: Public Endpoints (No Auth) ==={RESET}")
    
    # Test 6a: GET /stores
    print("\n6a. GET /api/stores (public)")
    resp = api_call("GET", "/stores")
    if not resp.get("success"):
        result.add_fail("GET /stores (public)", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        result.add_pass("GET /stores (public)")
    
    # Test 6b: GET /home
    print("\n6b. GET /api/home (public)")
    resp = api_call("GET", "/home")
    if not resp.get("success"):
        result.add_fail("GET /home (public)", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        result.add_pass("GET /home (public)")
    
    # Test 6c: GET /whatsapp/status
    print("\n6c. GET /api/whatsapp/status (public)")
    resp = api_call("GET", "/whatsapp/status")
    if not resp.get("success"):
        result.add_fail("GET /whatsapp/status (public)", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        data = resp.get("data", {})
        if "configured" not in data:
            result.add_fail("GET /whatsapp/status (public)", 
                           "Missing 'configured' field")
        else:
            result.add_pass(f"GET /whatsapp/status (configured: {data.get('configured')})")

def main():
    print(f"\n{BLUE}{'='*60}")
    print("Backend API Testing - Role-Based Permission Model")
    print(f"Backend URL: {BASE_URL}")
    print(f"{'='*60}{RESET}\n")
    
    result = TestResult()
    
    # Test 1: Master auto-promotion
    master_token = test_master_auto_promotion(result)
    if not master_token:
        print(f"\n{RED}CRITICAL: Could not obtain master token. Aborting remaining tests.{RESET}")
        result.summary()
        return 1
    
    # Test 2: Master capabilities
    test_master_capabilities(result, master_token)
    
    # Test 3: Admin restrictions
    admin1_token, admin1_user_id = test_admin_restrictions(result)
    if not admin1_token:
        print(f"\n{RED}CRITICAL: Could not create admin1. Aborting store tests.{RESET}")
        result.summary()
        return 1
    
    # Test 4: Store ownership
    loja_a_id, loja_b_id, admin2_token, admin2_user_id = test_store_ownership(
        result, admin1_token, admin1_user_id)
    
    # Test 4f-g: Store reassignment
    if loja_b_id:
        test_store_reassignment(result, master_token, admin1_token, 
                               admin1_user_id, loja_b_id)
    
    # Test 5: Product scoping
    if admin2_token:
        test_product_scoping(result, admin2_token, loja_a_id, loja_b_id)
    
    # Test 6: Public endpoints
    test_public_endpoints(result)
    
    # Summary
    success = result.summary()
    return 0 if success else 1

def test_order_editing_regression():
    """
    Regression test for ORDER EDITING + client notification
    Tests:
    1. Master creates store and product
    2. Invite and accept as cliente
    3. Create order as cliente
    4. Edit order as master (change items, price, qty)
    5. Verify client notification was recorded
    6. Test permission (other cliente cannot edit)
    7. Test status change (pronto = not editable)
    8. Test GET order as master and as owner cliente
    """
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}ORDER EDITING REGRESSION TEST{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    result = TestResult()
    
    # Step 1: Master dev-login
    print(f"\n{YELLOW}Step 1: Master login{RESET}")
    master_login = dev_login(MASTER_EMAIL, "master", "Master User")
    if "error" in master_login:
        result.add_fail("Master login", master_login["error"])
        result.summary()
        return 1
    
    master_token = master_login["token"]
    master_user = master_login["user"]
    result.add_pass(f"Master login (email={MASTER_EMAIL}, role={master_user.get('role')})")
    
    # Step 2: Create store
    print(f"\n{YELLOW}Step 2: Create store{RESET}")
    store_data = {"name": "EditReg Store", "whatsapp": "5545000000099"}
    store_resp = api_call("POST", "/stores", master_token, store_data)
    if not store_resp.get("success"):
        result.add_fail("Create store", f"Status {store_resp.get('status_code')}, {store_resp.get('error', '')}")
        result.summary()
        return 1
    
    store_id = store_resp["data"]["id"]
    admin_id = store_resp["data"].get("admin_id")
    result.add_pass(f"Create store (id={store_id}, admin_id={admin_id})")
    
    # Step 3: Create product
    print(f"\n{YELLOW}Step 3: Create product{RESET}")
    product_data = {"store_id": store_id, "name": "Widget", "price": 100, "category": "Outros"}
    product_resp = api_call("POST", "/products", master_token, product_data)
    if not product_resp.get("success"):
        result.add_fail("Create product", f"Status {product_resp.get('status_code')}, {product_resp.get('error', '')}")
        result.summary()
        return 1
    
    product_id = product_resp["data"]["id"]
    result.add_pass(f"Create product (id={product_id}, name=Widget, price=100)")
    
    # Step 4: Invite a client
    print(f"\n{YELLOW}Step 4: Invite client{RESET}")
    client_email = "editreg_cli@test.com"
    invite_data = {"store_id": store_id, "client_email": client_email}
    invite_resp = api_call("POST", "/invites", master_token, invite_data)
    if not invite_resp.get("success"):
        result.add_fail("Create invite", f"Status {invite_resp.get('status_code')}, {invite_resp.get('error', '')}")
        result.summary()
        return 1
    
    invite_token = invite_resp["data"]["token"]
    result.add_pass(f"Create invite (token={invite_token[:16]}...)")
    
    # Step 5: Cliente dev-login and accept invite
    print(f"\n{YELLOW}Step 5: Cliente login and accept invite{RESET}")
    cliente_login = dev_login(client_email, "cliente", "Edit Reg Cliente")
    if "error" in cliente_login:
        result.add_fail("Cliente login", cliente_login["error"])
        result.summary()
        return 1
    
    cliente_token = cliente_login["token"]
    result.add_pass(f"Cliente login (email={client_email})")
    
    # Accept invite
    accept_resp = api_call("POST", f"/invite/{invite_token}/accept", cliente_token)
    if not accept_resp.get("success"):
        result.add_fail("Accept invite", f"Status {accept_resp.get('status_code')}, {accept_resp.get('error', '')}")
        result.summary()
        return 1
    result.add_pass("Accept invite")
    
    # Step 6: Add product to catalog
    print(f"\n{YELLOW}Step 6: Add product to catalog{RESET}")
    catalog_data = {"store_id": store_id, "product_id": product_id, "qty": 3}
    catalog_resp = api_call("POST", "/catalog", cliente_token, catalog_data)
    if not catalog_resp.get("success"):
        result.add_fail("Add to catalog", f"Status {catalog_resp.get('status_code')}, {catalog_resp.get('error', '')}")
        result.summary()
        return 1
    result.add_pass("Add product to catalog (qty=3)")
    
    # Step 7: Send catalog to create order
    print(f"\n{YELLOW}Step 7: Send catalog to create order{RESET}")
    send_data = {"item_ids": None, "customer_whatsapp": "5545999990000"}
    send_resp = api_call("POST", "/catalog/send", cliente_token, send_data)
    if not send_resp.get("success"):
        result.add_fail("Send catalog", f"Status {send_resp.get('status_code')}, {send_resp.get('error', '')}")
        result.summary()
        return 1
    
    orders = send_resp["data"].get("orders", [])
    if not orders:
        result.add_fail("Send catalog", "No orders created")
        result.summary()
        return 1
    
    order_id = orders[0]["order_id"]
    original_total = orders[0]["total"]
    result.add_pass(f"Create order (id={order_id}, total={original_total})")
    
    # Get the full order to get the token
    get_order_resp = api_call("GET", f"/orders/{order_id}", cliente_token)
    if not get_order_resp.get("success"):
        result.add_fail("Get order details", f"Status {get_order_resp.get('status_code')}")
        result.summary()
        return 1
    order_token = get_order_resp["data"]["token"]
    
    # Step 8: EDIT ORDER AS MASTER
    print(f"\n{YELLOW}Step 8: Edit order as master{RESET}")
    edit_data = {
        "items": [
            {"product_id": product_id, "name": "Widget", "price": 80, "qty": 2}
        ]
    }
    edit_resp = api_call("PUT", f"/orders/{order_id}", master_token, edit_data)
    if not edit_resp.get("success"):
        result.add_fail("Edit order as master", f"Status {edit_resp.get('status_code')}, {edit_resp.get('error', '')}")
        result.summary()
        return 1
    
    edited_order = edit_resp["data"]
    edited_total = edited_order.get("total")
    if edited_total != 160:
        result.add_fail("Edit order total", f"Expected 160, got {edited_total}")
    else:
        result.add_pass(f"Edit order as master (new total={edited_total}, expected=160)")
    
    # Step 9: GET notifications for the order (as cliente)
    print(f"\n{YELLOW}Step 9: Get order notifications{RESET}")
    notif_resp = api_call("GET", f"/orders/{order_id}/notifications", cliente_token)
    if not notif_resp.get("success"):
        result.add_fail("Get notifications", f"Status {notif_resp.get('status_code')}, {notif_resp.get('error', '')}")
        result.summary()
        return 1
    
    notifications = notif_resp["data"]
    if not isinstance(notifications, list):
        result.add_fail("Get notifications", f"Expected list, got {type(notifications)}")
        result.summary()
        return 1
    
    # Check for cliente notification (edited)
    cliente_notifs = [n for n in notifications if n.get("target") == "cliente"]
    if not cliente_notifs:
        result.add_fail("Cliente notification", "No cliente notifications found")
    else:
        # Check if any notification is for edit (body contains "ajustado" or "ajustou")
        edit_notifs = [n for n in cliente_notifs if "ajust" in n.get("body", "").lower()]
        if not edit_notifs:
            result.add_fail("Edit notification", f"No edit notification found. Found {len(cliente_notifs)} cliente notifications")
        else:
            notif = edit_notifs[0]
            channel = notif.get("channel")
            result.add_pass(f"Cliente edit notification recorded (channel={channel}, target=cliente)")
    
    # Step 10: PERMISSION TEST - other cliente cannot edit
    print(f"\n{YELLOW}Step 10: Permission test - other cliente cannot edit{RESET}")
    other_cliente_login = dev_login("other_cli@test.com", "cliente", "Other Cliente")
    if "error" in other_cliente_login:
        result.add_fail("Other cliente login", other_cliente_login["error"])
    else:
        other_cliente_token = other_cliente_login["token"]
        result.add_pass("Other cliente login")
        
        # Try to edit order as other cliente
        forbidden_resp = api_call("PUT", f"/orders/{order_id}", other_cliente_token, edit_data, expected_status=403)
        if forbidden_resp.get("status_code") == 403:
            result.add_pass("Other cliente cannot edit order (403)")
        else:
            result.add_fail("Permission check", f"Expected 403, got {forbidden_resp.get('status_code')}")
    
    # Step 11: STATUS TEST - change status to "pronto" (not editable)
    print(f"\n{YELLOW}Step 11: Status test - change to 'pronto'{RESET}")
    status_data = {"status": "pronto"}
    status_resp = api_call("PUT", f"/orders/{order_id}/status", master_token, status_data)
    if not status_resp.get("success"):
        result.add_fail("Change status to pronto", f"Status {status_resp.get('status_code')}, {status_resp.get('error', '')}")
    else:
        updated_order = status_resp["data"]
        if updated_order.get("status") != "pronto":
            result.add_fail("Status update", f"Expected 'pronto', got {updated_order.get('status')}")
        elif updated_order.get("editable") != False:
            result.add_fail("Editable flag", f"Expected False, got {updated_order.get('editable')}")
        else:
            result.add_pass(f"Status changed to 'pronto', editable={updated_order.get('editable')}")
    
    # Step 12: GET order as master
    print(f"\n{YELLOW}Step 12: GET order as master{RESET}")
    get_master_resp = api_call("GET", f"/orders/{order_id}", master_token)
    if get_master_resp.get("status_code") == 200:
        result.add_pass("Master can view order (200)")
    else:
        result.add_fail("Master view order", f"Expected 200, got {get_master_resp.get('status_code')}")
    
    # Step 13: GET order as owner cliente
    print(f"\n{YELLOW}Step 13: GET order as owner cliente{RESET}")
    get_cliente_resp = api_call("GET", f"/orders/{order_id}", cliente_token)
    if get_cliente_resp.get("status_code") == 200:
        result.add_pass("Owner cliente can view order (200)")
    else:
        result.add_fail("Cliente view order", f"Expected 200, got {get_cliente_resp.get('status_code')}")
    
    # Summary
    success = result.summary()
    return 0 if success else 1

if __name__ == "__main__":
    # Check if we should run the regression test
    if len(sys.argv) > 1 and sys.argv[1] == "order-edit-regression":
        sys.exit(test_order_editing_regression())
    else:
        sys.exit(main())
