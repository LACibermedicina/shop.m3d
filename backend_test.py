#!/usr/bin/env python3
"""
Backend API Tests for Password Authentication
Tests the new password login feature and existing public endpoints.
"""
import requests
import sys
import os

# Backend base URL from frontend/.env
BASE_URL = "https://98710137-4fd0-48f9-a67d-5c9ad5ac69d2.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
CREDENTIALS = {
    "root": {
        "username": "root",
        "email": "root@m3d.pro",
        "password": "@0root",
        "role": "master",
        "whatsapp": "5511920946954"
    },
    "admin": {
        "username": "admin",
        "email": "admin@m3d.pro",
        "password": "@0admin",
        "role": "admin",
        "whatsapp": "5511960708817"
    },
    "lojista": {
        "username": "lojista",
        "email": "lojista@m3d.pro",
        "password": "@0lojista",
        "role": "lojista",
        "whatsapp": "5511960708817"
    },
    "cliente": {
        "username": "cliente",
        "email": "cliente@m3d.pro",
        "password": "@0cliente",
        "role": "cliente",
        "whatsapp": "5511960708817"
    }
}

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def log_test(name, passed, details=""):
    status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
    print(f"{status} | {name}")
    if details:
        print(f"       {details}")
    return passed

def test_login_by_username(account_name):
    """Test 1: Login with username for all 4 accounts"""
    cred = CREDENTIALS[account_name]
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": cred["username"],
        "password": cred["password"]
    }, timeout=10)
    
    if resp.status_code != 200:
        return log_test(
            f"Login {account_name} by username",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        )
    
    data = resp.json()
    
    # Check session_token exists
    if "session_token" not in data:
        return log_test(
            f"Login {account_name} by username",
            False,
            "Missing session_token in response"
        )
    
    # Check user object
    if "user" not in data:
        return log_test(
            f"Login {account_name} by username",
            False,
            "Missing user object in response"
        )
    
    user = data["user"]
    
    # Check role
    if user.get("role") != cred["role"]:
        return log_test(
            f"Login {account_name} by username",
            False,
            f"Expected role={cred['role']}, got {user.get('role')}"
        )
    
    # Check whatsapp
    if user.get("whatsapp") != cred["whatsapp"]:
        return log_test(
            f"Login {account_name} by username",
            False,
            f"Expected whatsapp={cred['whatsapp']}, got {user.get('whatsapp')}"
        )
    
    # Check password_hash is NOT in response
    if "password_hash" in user:
        return log_test(
            f"Login {account_name} by username",
            False,
            "SECURITY: password_hash leaked in response!"
        )
    
    return log_test(
        f"Login {account_name} by username",
        True,
        f"role={user['role']}, whatsapp={user['whatsapp']}, token={data['session_token'][:20]}..."
    ), data["session_token"]

def test_login_by_email(account_name):
    """Test 3: Login with email"""
    cred = CREDENTIALS[account_name]
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": cred["email"],  # email in username field
        "password": cred["password"]
    }, timeout=10)
    
    if resp.status_code != 200:
        return log_test(
            f"Login {account_name} by email",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        )
    
    data = resp.json()
    user = data.get("user", {})
    
    # Check role
    if user.get("role") != cred["role"]:
        return log_test(
            f"Login {account_name} by email",
            False,
            f"Expected role={cred['role']}, got {user.get('role')}"
        )
    
    # Check password_hash is NOT in response
    if "password_hash" in user:
        return log_test(
            f"Login {account_name} by email",
            False,
            "SECURITY: password_hash leaked in response!"
        )
    
    return log_test(
        f"Login {account_name} by email",
        True,
        f"role={user['role']}"
    ), data["session_token"]

def test_wrong_password():
    """Test 4: Wrong password returns 401"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "cliente",
        "password": "wrongpassword"
    }, timeout=10)
    
    return log_test(
        "Wrong password returns 401",
        resp.status_code == 401,
        f"Got status {resp.status_code}"
    )

def test_unknown_user():
    """Test 4: Unknown user returns 401"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "nonexistent_user_12345",
        "password": "anypassword"
    }, timeout=10)
    
    return log_test(
        "Unknown user returns 401",
        resp.status_code == 401,
        f"Got status {resp.status_code}"
    )

def test_missing_fields():
    """Test 4: Missing fields returns 400"""
    # Missing password
    resp1 = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "cliente"
    }, timeout=10)
    
    # Missing username
    resp2 = requests.post(f"{BASE_URL}/auth/login", json={
        "password": "test"
    }, timeout=10)
    
    # Empty username
    resp3 = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "",
        "password": "test"
    }, timeout=10)
    
    passed = resp1.status_code == 400 and resp2.status_code == 400 and resp3.status_code == 400
    
    return log_test(
        "Missing fields returns 400",
        passed,
        f"Missing password: {resp1.status_code}, Missing username: {resp2.status_code}, Empty username: {resp3.status_code}"
    )

def test_auth_me(token):
    """Test 5: GET /api/auth/me with token"""
    resp = requests.get(f"{BASE_URL}/auth/me", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=10)
    
    if resp.status_code != 200:
        return log_test(
            "GET /api/auth/me with token",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        )
    
    user = resp.json()
    
    # Check password_hash is NOT in response
    if "password_hash" in user:
        return log_test(
            "GET /api/auth/me with token",
            False,
            "SECURITY: password_hash leaked in /auth/me response!"
        )
    
    return log_test(
        "GET /api/auth/me with token",
        True,
        f"role={user.get('role')}, email={user.get('email')}"
    )

def test_master_overview(master_token):
    """Test 6: Master can access /api/master/overview"""
    resp = requests.get(f"{BASE_URL}/master/overview", headers={
        "Authorization": f"Bearer {master_token}"
    }, timeout=10)
    
    if resp.status_code != 200:
        return log_test(
            "Master access to /api/master/overview",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        )
    
    data = resp.json()
    
    # Check response structure
    if "users" not in data or "stores" not in data or "counts" not in data:
        return log_test(
            "Master access to /api/master/overview",
            False,
            f"Missing expected fields in response: {list(data.keys())}"
        )
    
    return log_test(
        "Master access to /api/master/overview",
        True,
        f"users={len(data['users'])}, stores={len(data['stores'])}, counts={data['counts']}"
    )

def test_cliente_cannot_access_master(cliente_token):
    """Test 6: Cliente cannot access master endpoints (403)"""
    resp = requests.get(f"{BASE_URL}/master/overview", headers={
        "Authorization": f"Bearer {cliente_token}"
    }, timeout=10)
    
    return log_test(
        "Cliente cannot access /api/master/overview (403)",
        resp.status_code == 403,
        f"Got status {resp.status_code}"
    )

def test_dev_login_disabled():
    """Test 7: Dev-login is disabled (403)"""
    resp = requests.post(f"{BASE_URL}/auth/dev-login", json={
        "email": "test@example.com",
        "role": "cliente"
    }, timeout=10)
    
    return log_test(
        "Dev-login disabled (403)",
        resp.status_code == 403,
        f"Got status {resp.status_code}"
    )

def test_public_endpoint(endpoint_name, endpoint_path):
    """Test 8: Public endpoints still work"""
    resp = requests.get(f"{BASE_URL}{endpoint_path}", timeout=10)
    
    return log_test(
        f"Public endpoint {endpoint_name}",
        resp.status_code == 200,
        f"Got status {resp.status_code}"
    )

def test_seed_idempotency():
    """Test 9: Seed is idempotent - login again still works"""
    # Login root again
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "root",
        "password": "@0root"
    }, timeout=10)
    
    if resp.status_code != 200:
        return log_test(
            "Seed idempotency (login root again)",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        )
    
    data = resp.json()
    user = data.get("user", {})
    
    # Verify still master
    if user.get("role") != "master":
        return log_test(
            "Seed idempotency (login root again)",
            False,
            f"Expected role=master, got {user.get('role')}"
        )
    
    return log_test(
        "Seed idempotency (login root again)",
        True,
        "Root still logs in as master"
    )

def main():
    print(f"\n{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BLUE}Backend API Tests - Password Authentication{Colors.END}")
    print(f"{Colors.BLUE}Base URL: {BASE_URL}{Colors.END}")
    print(f"{Colors.BLUE}{'='*70}{Colors.END}\n")
    
    passed = 0
    failed = 0
    tokens = {}
    
    # Test 1 & 2: Login all 4 accounts by username
    print(f"\n{Colors.YELLOW}Test Group 1 & 2: Login by username (all 4 accounts){Colors.END}")
    for account in ["root", "admin", "lojista", "cliente"]:
        result = test_login_by_username(account)
        if isinstance(result, tuple):
            success, token = result
            if success:
                passed += 1
                tokens[account] = token
            else:
                failed += 1
        else:
            if result:
                passed += 1
            else:
                failed += 1
    
    # Test 3: Login by email
    print(f"\n{Colors.YELLOW}Test Group 3: Login by email{Colors.END}")
    result = test_login_by_email("root")
    if isinstance(result, tuple):
        success, token = result
        if success:
            passed += 1
            if "root" not in tokens:
                tokens["root"] = token
        else:
            failed += 1
    else:
        if result:
            passed += 1
        else:
            failed += 1
    
    # Test 4: Error cases
    print(f"\n{Colors.YELLOW}Test Group 4: Error handling{Colors.END}")
    if test_wrong_password():
        passed += 1
    else:
        failed += 1
    
    if test_unknown_user():
        passed += 1
    else:
        failed += 1
    
    if test_missing_fields():
        passed += 1
    else:
        failed += 1
    
    # Test 5: /auth/me
    print(f"\n{Colors.YELLOW}Test Group 5: Token usage on /api/auth/me{Colors.END}")
    if "root" in tokens:
        if test_auth_me(tokens["root"]):
            passed += 1
        else:
            failed += 1
    else:
        log_test("GET /api/auth/me with token", False, "No root token available")
        failed += 1
    
    # Test 6: Master access and cliente restriction
    print(f"\n{Colors.YELLOW}Test Group 6: Role-based access control{Colors.END}")
    if "root" in tokens:
        if test_master_overview(tokens["root"]):
            passed += 1
        else:
            failed += 1
    else:
        log_test("Master access to /api/master/overview", False, "No root token available")
        failed += 1
    
    if "cliente" in tokens:
        if test_cliente_cannot_access_master(tokens["cliente"]):
            passed += 1
        else:
            failed += 1
    else:
        log_test("Cliente cannot access /api/master/overview (403)", False, "No cliente token available")
        failed += 1
    
    # Test 7: Dev-login disabled
    print(f"\n{Colors.YELLOW}Test Group 7: Dev-login disabled{Colors.END}")
    if test_dev_login_disabled():
        passed += 1
    else:
        failed += 1
    
    # Test 8: Public endpoints
    print(f"\n{Colors.YELLOW}Test Group 8: Public endpoints{Colors.END}")
    public_endpoints = [
        ("GET /api/home", "/home"),
        ("GET /api/stores", "/stores"),
        ("GET /api/groups", "/groups"),
        ("GET /api/whatsapp/status", "/whatsapp/status")
    ]
    
    for name, path in public_endpoints:
        if test_public_endpoint(name, path):
            passed += 1
        else:
            failed += 1
    
    # Test 9: Seed idempotency
    print(f"\n{Colors.YELLOW}Test Group 9: Seed idempotency{Colors.END}")
    if test_seed_idempotency():
        passed += 1
    else:
        failed += 1
    
    # Summary
    total = passed + failed
    print(f"\n{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BLUE}Test Summary{Colors.END}")
    print(f"{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"Total: {total} | {Colors.GREEN}Passed: {passed}{Colors.END} | {Colors.RED}Failed: {failed}{Colors.END}")
    
    if failed == 0:
        print(f"\n{Colors.GREEN}✓ All tests passed!{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}✗ {failed} test(s) failed{Colors.END}\n")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted by user{Colors.END}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.END}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
