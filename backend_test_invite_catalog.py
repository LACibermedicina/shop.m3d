#!/usr/bin/env python3
"""
Backend API Testing for Lojas da Fronteira - Invite-Only + Personal Catalog + Multi-Vendor Cart + AI Translation
Tests the NEW features: invite-only access, personal shopping catalog, multi-vendor cart send, and AI translation
"""

import requests
import json
import sys
from typing import Dict, Optional

# Backend URL - using localhost as specified in review request
BASE_URL = "http://localhost:8001/api"

# Test configuration
MASTER_EMAIL = "lucasmedicina86@gmail.com"
CLIENTE_EMAIL = "cli_inv@test.com"
CLIENTE_NONE_EMAIL = "cli_none@test.com"

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
        print(f"\n{'='*80}")
        print(f"Test Summary: {self.passed}/{total} passed ({100*self.passed//total if total > 0 else 0}%)")
        if self.failed > 0:
            print(f"\n{RED}Failed Tests:{RESET}")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*80}\n")
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
            "data": resp.json() if resp.content and 'application/json' in resp.headers.get('content-type', '') else {},
            "content": resp.content,
            "headers": dict(resp.headers),
            "success": resp.status_code == expected_status
        }
    except Exception as e:
        return {
            "error": str(e),
            "status_code": getattr(e.response, 'status_code', 0) if hasattr(e, 'response') else 0,
            "success": False
        }

def test_step_1_master_login(result: TestResult):
    """Step 1: Master dev-login with cliente role should become master"""
    print(f"\n{BLUE}=== Step 1: Master Dev-Login (Auto-Promotion) ==={RESET}")
    
    login = dev_login(MASTER_EMAIL, "cliente", "Master User")
    if "error" in login:
        result.add_fail("Step 1: Master dev-login", login["error"])
        return None
    
    if login.get("user", {}).get("role") != "master":
        result.add_fail("Step 1: Master auto-promotion", 
                       f"Expected role 'master', got '{login.get('user', {}).get('role')}'")
        return None
    
    result.add_pass("Step 1: Master dev-login (cliente -> master)")
    return login.get("token")

def test_step_2_create_stores(result: TestResult, master_token: str):
    """Step 2: As master, create two stores (Loja X INV and Loja Y INV)"""
    print(f"\n{BLUE}=== Step 2: Create Stores (Loja X INV, Loja Y INV) ==={RESET}")
    
    # Create Loja X INV
    resp = api_call("POST", "/stores", master_token,
                   {"name": "Loja X INV", "whatsapp": "5545999990001", "description": "Invite-only store X"})
    if not resp.get("success"):
        result.add_fail("Step 2a: Create Loja X INV", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
        return None, None
    
    store_x_id = resp.get("data", {}).get("id")
    admin_id_x = resp.get("data", {}).get("admin_id")
    
    # admin_id field should be present (can be None for master-created stores)
    if "admin_id" not in resp.get("data", {}):
        result.add_fail("Step 2a: Loja X INV admin_id check", "admin_id field not present in response")
    else:
        result.add_pass(f"Step 2a: Create Loja X INV (id={store_x_id}, admin_id={admin_id_x})")
    
    # Create Loja Y INV
    resp = api_call("POST", "/stores", master_token,
                   {"name": "Loja Y INV", "whatsapp": "5545999990002", "description": "Invite-only store Y"})
    if not resp.get("success"):
        result.add_fail("Step 2b: Create Loja Y INV", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
        return store_x_id, None
    
    store_y_id = resp.get("data", {}).get("id")
    admin_id_y = resp.get("data", {}).get("admin_id")
    
    # admin_id field should be present (can be None for master-created stores)
    if "admin_id" not in resp.get("data", {}):
        result.add_fail("Step 2b: Loja Y INV admin_id check", "admin_id field not present in response")
    else:
        result.add_pass(f"Step 2b: Create Loja Y INV (id={store_y_id}, admin_id={admin_id_y})")
    
    return store_x_id, store_y_id

def test_step_3_create_products(result: TestResult, master_token: str, store_x_id: str, store_y_id: str):
    """Step 3: As master, create products for both stores"""
    print(f"\n{BLUE}=== Step 3: Create Products ==={RESET}")
    
    # Create product for Loja X
    resp = api_call("POST", "/products", master_token,
                   {"store_id": store_x_id, "name": "Prod X1", "price": 10, "category": "Outros", "description": "Product X1"})
    if not resp.get("success"):
        result.add_fail("Step 3a: Create Prod X1", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
        return None, None
    
    product_x_id = resp.get("data", {}).get("id")
    result.add_pass(f"Step 3a: Create Prod X1 (id={product_x_id})")
    
    # Create product for Loja Y
    resp = api_call("POST", "/products", master_token,
                   {"store_id": store_y_id, "name": "Prod Y1", "price": 20, "category": "Outros", "description": "Product Y1"})
    if not resp.get("success"):
        result.add_fail("Step 3b: Create Prod Y1", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
        return product_x_id, None
    
    product_y_id = resp.get("data", {}).get("id")
    result.add_pass(f"Step 3b: Create Prod Y1 (id={product_y_id})")
    
    return product_x_id, product_y_id

def test_step_4_cliente_before_invite(result: TestResult, store_x_id: str, store_y_id: str):
    """Step 4: Cliente login and verify NO access to invite-only stores BEFORE invite"""
    print(f"\n{BLUE}=== Step 4: Cliente Access BEFORE Invite ==={RESET}")
    
    # Cliente dev-login
    login = dev_login(CLIENTE_EMAIL, "cliente", "Cliente Test")
    if "error" in login:
        result.add_fail("Step 4a: Cliente dev-login", login["error"])
        return None
    
    cliente_token = login.get("token")
    result.add_pass("Step 4a: Cliente dev-login")
    
    # GET /stores as cliente - should NOT contain SX or SY (invite-only)
    resp = api_call("GET", "/stores", cliente_token)
    if not resp.get("success"):
        result.add_fail("Step 4b: GET /stores as cliente", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        stores = resp.get("data", [])
        store_ids = [s.get("id") for s in stores]
        if store_x_id in store_ids or store_y_id in store_ids:
            result.add_fail("Step 4b: GET /stores (invite-only check)", 
                           f"Stores should NOT contain {store_x_id} or {store_y_id} before invite")
        else:
            result.add_pass("Step 4b: GET /stores - invite-only stores NOT visible")
    
    # GET /stores/{store_x_id} as cliente - should return 403
    resp = api_call("GET", f"/stores/{store_x_id}", cliente_token, expected_status=403)
    if resp.get("status_code") != 403:
        result.add_fail("Step 4c: GET /stores/{SX} before invite", 
                       f"Expected 403, got {resp.get('status_code')}")
    else:
        result.add_pass("Step 4c: GET /stores/{SX} - correctly blocked (403)")
    
    # GET /home as cliente - featured_stores should not contain SX/SY
    resp = api_call("GET", "/home", cliente_token)
    if not resp.get("success"):
        result.add_fail("Step 4d: GET /home as cliente", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        featured = resp.get("data", {}).get("featured_stores", [])
        featured_ids = [s.get("id") for s in featured]
        if store_x_id in featured_ids or store_y_id in featured_ids:
            result.add_fail("Step 4d: GET /home (featured check)", 
                           f"Featured stores should NOT contain {store_x_id} or {store_y_id}")
        else:
            result.add_pass("Step 4d: GET /home - invite-only stores NOT in featured")
    
    return cliente_token

def test_step_5_create_invites(result: TestResult, master_token: str, store_x_id: str, store_y_id: str):
    """Step 5: As master, create invites for cliente"""
    print(f"\n{BLUE}=== Step 5: Create Invites ==={RESET}")
    
    # Create invite for Loja X
    resp = api_call("POST", "/invites", master_token,
                   {"store_id": store_x_id, "client_email": CLIENTE_EMAIL})
    if not resp.get("success"):
        result.add_fail("Step 5a: Create invite for Loja X", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
        return None, None
    
    token_sx = resp.get("data", {}).get("token")
    link_sx = resp.get("data", {}).get("link")
    
    if not token_sx or not link_sx:
        result.add_fail("Step 5a: Invite for Loja X", "Missing token or link in response")
        return None, None
    
    result.add_pass(f"Step 5a: Create invite for Loja X (token={token_sx[:16]}...)")
    
    # Create invite for Loja Y
    resp = api_call("POST", "/invites", master_token,
                   {"store_id": store_y_id, "client_email": CLIENTE_EMAIL})
    if not resp.get("success"):
        result.add_fail("Step 5b: Create invite for Loja Y", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
        return token_sx, None
    
    token_sy = resp.get("data", {}).get("token")
    result.add_pass(f"Step 5b: Create invite for Loja Y (token={token_sy[:16]}...)")
    
    return token_sx, token_sy

def test_step_6_public_invite_view(result: TestResult, token_sx: str):
    """Step 6: Public GET /invite/{token} should return 200 with store_name"""
    print(f"\n{BLUE}=== Step 6: Public Invite View ==={RESET}")
    
    resp = api_call("GET", f"/invite/{token_sx}", None)
    if not resp.get("success"):
        result.add_fail("Step 6: GET /invite/{token} (public)", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
        return
    
    store_name = resp.get("data", {}).get("store_name")
    if not store_name:
        result.add_fail("Step 6: GET /invite/{token}", "Missing store_name in response")
    else:
        result.add_pass(f"Step 6: GET /invite/{{token}} - store_name={store_name}")

def test_step_7_accept_invites(result: TestResult, cliente_token: str, token_sx: str, token_sy: str, 
                               store_x_id: str, store_y_id: str):
    """Step 7: As cliente, accept invites and verify access"""
    print(f"\n{BLUE}=== Step 7: Accept Invites & Verify Access ==={RESET}")
    
    # Accept invite for Loja X
    resp = api_call("POST", f"/invite/{token_sx}/accept", cliente_token)
    if not resp.get("success"):
        result.add_fail("Step 7a: Accept invite for Loja X", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
    else:
        result.add_pass("Step 7a: Accept invite for Loja X")
    
    # Accept invite for Loja Y
    resp = api_call("POST", f"/invite/{token_sy}/accept", cliente_token)
    if not resp.get("success"):
        result.add_fail("Step 7b: Accept invite for Loja Y", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
    else:
        result.add_pass("Step 7b: Accept invite for Loja Y")
    
    # GET /my/catalog-stores should now contain SX and SY
    resp = api_call("GET", "/my/catalog-stores", cliente_token)
    if not resp.get("success"):
        result.add_fail("Step 7c: GET /my/catalog-stores", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        stores = resp.get("data", [])
        store_ids = [s.get("id") for s in stores]
        if store_x_id not in store_ids or store_y_id not in store_ids:
            result.add_fail("Step 7c: GET /my/catalog-stores", 
                           f"Expected stores {store_x_id} and {store_y_id}, got {store_ids}")
        else:
            result.add_pass(f"Step 7c: GET /my/catalog-stores - contains SX and SY ({len(stores)} stores)")
    
    # GET /stores/{store_x_id} should now return 200
    resp = api_call("GET", f"/stores/{store_x_id}", cliente_token)
    if not resp.get("success"):
        result.add_fail("Step 7d: GET /stores/{SX} after invite", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        result.add_pass("Step 7d: GET /stores/{SX} - now accessible (200)")

def test_step_8_add_to_catalog(result: TestResult, cliente_token: str, store_x_id: str, store_y_id: str,
                               product_x_id: str, product_y_id: str):
    """Step 8: As cliente, add items to personal catalog and test access control"""
    print(f"\n{BLUE}=== Step 8: Add to Personal Catalog ==={RESET}")
    
    # Add Prod X1 to catalog (qty=2)
    resp = api_call("POST", "/catalog", cliente_token,
                   {"store_id": store_x_id, "product_id": product_x_id, "qty": 2})
    if not resp.get("success"):
        result.add_fail("Step 8a: Add Prod X1 to catalog", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
    else:
        result.add_pass("Step 8a: Add Prod X1 to catalog (qty=2)")
    
    # Add Prod Y1 to catalog (qty=1)
    resp = api_call("POST", "/catalog", cliente_token,
                   {"store_id": store_y_id, "product_id": product_y_id, "qty": 1})
    if not resp.get("success"):
        result.add_fail("Step 8b: Add Prod Y1 to catalog", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
    else:
        result.add_pass("Step 8b: Add Prod Y1 to catalog (qty=1)")
    
    # Test access control: try to add to a random store (should fail with 403)
    resp = api_call("POST", "/catalog", cliente_token,
                   {"store_id": "some_random_id", "product_id": product_x_id, "qty": 1},
                   expected_status=403)
    if resp.get("status_code") != 403:
        result.add_fail("Step 8c: Access control test (random store)", 
                       f"Expected 403, got {resp.get('status_code')}")
    else:
        result.add_pass("Step 8c: Access control - correctly blocked (403)")
    
    # GET /catalog - should have 2 items with total, count, stores, categories
    resp = api_call("GET", "/catalog", cliente_token)
    if not resp.get("success"):
        result.add_fail("Step 8d: GET /catalog", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        data = resp.get("data", {})
        items = data.get("items", [])
        total = data.get("total")
        count = data.get("count")
        stores = data.get("stores", [])
        categories = data.get("categories", [])
        
        if len(items) != 2:
            result.add_fail("Step 8d: GET /catalog (items count)", 
                           f"Expected 2 items, got {len(items)}")
        elif total is None or count is None or not stores or not categories:
            result.add_fail("Step 8d: GET /catalog (fields check)", 
                           f"Missing fields: total={total}, count={count}, stores={len(stores)}, categories={len(categories)}")
        else:
            result.add_pass(f"Step 8d: GET /catalog - 2 items, total={total}, count={count}, {len(stores)} stores, {len(categories)} categories")
    
    # GET /catalog?store_id={store_x_id} - should return exactly 1 item
    resp = api_call("GET", f"/catalog?store_id={store_x_id}", cliente_token)
    if not resp.get("success"):
        result.add_fail("Step 8e: GET /catalog?store_id=SX", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        items = resp.get("data", {}).get("items", [])
        if len(items) != 1:
            result.add_fail("Step 8e: GET /catalog?store_id=SX", 
                           f"Expected 1 item, got {len(items)}")
        else:
            result.add_pass("Step 8e: GET /catalog?store_id=SX - exactly 1 item")

def test_step_9_catalog_pdf(result: TestResult, cliente_token: str):
    """Step 9: GET /catalog/report.pdf should return PDF"""
    print(f"\n{BLUE}=== Step 9: Catalog PDF Report ==={RESET}")
    
    resp = api_call("GET", "/catalog/report.pdf", cliente_token)
    if not resp.get("success"):
        result.add_fail("Step 9: GET /catalog/report.pdf", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
    else:
        content_type = resp.get("headers", {}).get("content-type", "")
        if "application/pdf" not in content_type:
            result.add_fail("Step 9: GET /catalog/report.pdf (content-type)", 
                           f"Expected application/pdf, got {content_type}")
        else:
            result.add_pass(f"Step 9: GET /catalog/report.pdf - PDF returned ({len(resp.get('content', b''))} bytes)")

def test_step_10_send_catalog(result: TestResult, cliente_token: str, master_token: str):
    """Step 10: POST /catalog/send to create orders and verify catalog cleared"""
    print(f"\n{BLUE}=== Step 10: Send Catalog (Multi-Vendor Cart) ==={RESET}")
    
    # POST /catalog/send with empty body (all items)
    resp = api_call("POST", "/catalog/send", cliente_token, {})
    if not resp.get("success"):
        result.add_fail("Step 10a: POST /catalog/send", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
        return
    
    orders = resp.get("data", {}).get("orders", [])
    if len(orders) != 2:
        result.add_fail("Step 10a: POST /catalog/send (orders count)", 
                       f"Expected 2 orders (one per store), got {len(orders)}")
    else:
        # Check each order has order_id, store_name, total, pdf link
        all_valid = True
        for i, order in enumerate(orders):
            if not all(k in order for k in ["order_id", "store_name", "total", "pdf"]):
                result.add_fail(f"Step 10a: Order {i+1} missing fields", 
                               f"Order: {order}")
                all_valid = False
                break
        
        if all_valid:
            result.add_pass(f"Step 10a: POST /catalog/send - 2 orders created with all fields")
    
    # GET /catalog after send - should be empty (cleared)
    resp = api_call("GET", "/catalog", cliente_token)
    if not resp.get("success"):
        result.add_fail("Step 10b: GET /catalog after send", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        items = resp.get("data", {}).get("items", [])
        if len(items) != 0:
            result.add_fail("Step 10b: GET /catalog after send (cleared check)", 
                           f"Expected 0 items (cleared), got {len(items)}")
        else:
            result.add_pass("Step 10b: GET /catalog after send - cleared (0 items)")

def test_step_11_vendor_orders(result: TestResult, master_token: str):
    """Step 11: As master, GET /vendor/orders should include the newly created orders"""
    print(f"\n{BLUE}=== Step 11: Vendor Orders ==={RESET}")
    
    resp = api_call("GET", "/vendor/orders", master_token)
    if not resp.get("success"):
        result.add_fail("Step 11: GET /vendor/orders", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        orders = resp.get("data", [])
        # We expect at least 2 orders (the ones we just created)
        # Note: There might be more from previous tests
        if len(orders) < 2:
            result.add_fail("Step 11: GET /vendor/orders (count)", 
                           f"Expected at least 2 orders, got {len(orders)}")
        else:
            result.add_pass(f"Step 11: GET /vendor/orders - {len(orders)} orders (includes newly created)")

def test_step_12_translation(result: TestResult):
    """Step 12: POST /translate for Spanish, English, and Portuguese"""
    print(f"\n{BLUE}=== Step 12: AI Translation ==={RESET}")
    
    test_texts = ["Meus pedidos", "Adicionar ao carrinho"]
    
    # Test Spanish translation
    resp = api_call("POST", "/translate", None, {"texts": test_texts, "target": "es"})
    if not resp.get("success"):
        result.add_fail("Step 12a: POST /translate (Spanish)", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
    else:
        translations = resp.get("data", {}).get("translations", [])
        if len(translations) != len(test_texts):
            result.add_fail("Step 12a: POST /translate (Spanish count)", 
                           f"Expected {len(test_texts)} translations, got {len(translations)}")
        else:
            result.add_pass(f"Step 12a: POST /translate (Spanish) - {translations}")
    
    # Test English translation
    resp = api_call("POST", "/translate", None, {"texts": test_texts, "target": "en"})
    if not resp.get("success"):
        result.add_fail("Step 12b: POST /translate (English)", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
    else:
        translations = resp.get("data", {}).get("translations", [])
        if len(translations) != len(test_texts):
            result.add_fail("Step 12b: POST /translate (English count)", 
                           f"Expected {len(test_texts)} translations, got {len(translations)}")
        else:
            result.add_pass(f"Step 12b: POST /translate (English) - {translations}")
    
    # Test Portuguese (should return same strings unchanged)
    resp = api_call("POST", "/translate", None, {"texts": test_texts, "target": "pt"})
    if not resp.get("success"):
        result.add_fail("Step 12c: POST /translate (Portuguese)", 
                       f"Status {resp.get('status_code')}, expected 200. Error: {resp.get('data')}")
    else:
        translations = resp.get("data", {}).get("translations", {})
        # API returns dict format, check if all texts are unchanged
        all_unchanged = all(translations.get(t) == t for t in test_texts)
        if not all_unchanged:
            result.add_fail("Step 12c: POST /translate (Portuguese unchanged)", 
                           f"Expected unchanged, got {translations}")
        else:
            result.add_pass(f"Step 12c: POST /translate (Portuguese) - unchanged")

def test_step_13_negative_access(result: TestResult, store_x_id: str):
    """Step 13: Different cliente without invite should NOT have access"""
    print(f"\n{BLUE}=== Step 13: Negative Test (No Invite) ==={RESET}")
    
    # Login as different cliente
    login = dev_login(CLIENTE_NONE_EMAIL, "cliente", "Cliente None")
    if "error" in login:
        result.add_fail("Step 13a: Cliente (no invite) dev-login", login["error"])
        return
    
    cliente_none_token = login.get("token")
    result.add_pass("Step 13a: Cliente (no invite) dev-login")
    
    # GET /my/catalog-stores should be empty
    resp = api_call("GET", "/my/catalog-stores", cliente_none_token)
    if not resp.get("success"):
        result.add_fail("Step 13b: GET /my/catalog-stores (no invite)", 
                       f"Status {resp.get('status_code')}, expected 200")
    else:
        stores = resp.get("data", [])
        if len(stores) != 0:
            result.add_fail("Step 13b: GET /my/catalog-stores (no invite)", 
                           f"Expected 0 stores, got {len(stores)}")
        else:
            result.add_pass("Step 13b: GET /my/catalog-stores (no invite) - empty")
    
    # GET /stores/{store_x_id} should return 403
    resp = api_call("GET", f"/stores/{store_x_id}", cliente_none_token, expected_status=403)
    if resp.get("status_code") != 403:
        result.add_fail("Step 13c: GET /stores/{SX} (no invite)", 
                       f"Expected 403, got {resp.get('status_code')}")
    else:
        result.add_pass("Step 13c: GET /stores/{SX} (no invite) - correctly blocked (403)")

def main():
    print(f"\n{BLUE}{'='*80}")
    print("Backend API Testing - Invite-Only + Personal Catalog + Multi-Vendor + Translation")
    print(f"Backend URL: {BASE_URL}")
    print(f"{'='*80}{RESET}\n")
    
    result = TestResult()
    
    # Step 1: Master login
    master_token = test_step_1_master_login(result)
    if not master_token:
        print(f"\n{RED}CRITICAL: Could not obtain master token. Aborting.{RESET}")
        result.summary()
        return 1
    
    # Step 2: Create stores
    store_x_id, store_y_id = test_step_2_create_stores(result, master_token)
    if not store_x_id or not store_y_id:
        print(f"\n{RED}CRITICAL: Could not create stores. Aborting.{RESET}")
        result.summary()
        return 1
    
    # Step 3: Create products
    product_x_id, product_y_id = test_step_3_create_products(result, master_token, store_x_id, store_y_id)
    if not product_x_id or not product_y_id:
        print(f"\n{RED}CRITICAL: Could not create products. Aborting.{RESET}")
        result.summary()
        return 1
    
    # Step 4: Cliente before invite
    cliente_token = test_step_4_cliente_before_invite(result, store_x_id, store_y_id)
    if not cliente_token:
        print(f"\n{RED}CRITICAL: Could not login as cliente. Aborting.{RESET}")
        result.summary()
        return 1
    
    # Step 5: Create invites
    token_sx, token_sy = test_step_5_create_invites(result, master_token, store_x_id, store_y_id)
    if not token_sx or not token_sy:
        print(f"\n{RED}CRITICAL: Could not create invites. Aborting.{RESET}")
        result.summary()
        return 1
    
    # Step 6: Public invite view
    test_step_6_public_invite_view(result, token_sx)
    
    # Step 7: Accept invites
    test_step_7_accept_invites(result, cliente_token, token_sx, token_sy, store_x_id, store_y_id)
    
    # Step 8: Add to catalog
    test_step_8_add_to_catalog(result, cliente_token, store_x_id, store_y_id, product_x_id, product_y_id)
    
    # Step 9: Catalog PDF
    test_step_9_catalog_pdf(result, cliente_token)
    
    # Step 10: Send catalog
    test_step_10_send_catalog(result, cliente_token, master_token)
    
    # Step 11: Vendor orders
    test_step_11_vendor_orders(result, master_token)
    
    # Step 12: Translation
    test_step_12_translation(result)
    
    # Step 13: Negative test
    test_step_13_negative_access(result, store_x_id)
    
    # Summary
    success = result.summary()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
