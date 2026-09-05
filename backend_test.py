#!/usr/bin/env python3
"""
Backend test for WhatsApp hybrid delivery + notification status recording
Tests the fallback behavior when WhatsApp Cloud API fails with error #133010
"""
import requests
import json
import sys
from typing import Dict, Any, Optional

# Backend URL from frontend/.env
BASE_URL = "https://f7497c82-899f-4f48-913d-9bb1aa940d02.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
CREDENTIALS = {
    "master": {"username": "root", "password": "@0root"},
    "admin": {"username": "admin", "password": "@0admin"},
    "lojista": {"username": "lojista", "password": "@0lojista"},
    "cliente": {"username": "cliente", "password": "@0cliente"},
}

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tokens = {}
        self.test_data = {}
        
    def log(self, msg: str, level: str = "INFO"):
        prefix = {
            "INFO": "ℹ️",
            "PASS": "✅",
            "FAIL": "❌",
            "WARN": "⚠️",
        }.get(level, "•")
        print(f"{prefix} {msg}")
        
    def login(self, role: str) -> Optional[str]:
        """Login and return token"""
        creds = CREDENTIALS.get(role)
        if not creds:
            self.log(f"No credentials for role {role}", "FAIL")
            return None
            
        try:
            resp = requests.post(
                f"{BASE_URL}/auth/login",
                json=creds,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("session_token")
                self.tokens[role] = token
                self.log(f"Login {role} successful (role={data.get('role')})", "PASS")
                return token
            else:
                self.log(f"Login {role} failed: {resp.status_code} {resp.text}", "FAIL")
                return None
        except Exception as e:
            self.log(f"Login {role} exception: {e}", "FAIL")
            return None
            
    def api_call(self, method: str, endpoint: str, token: Optional[str] = None, 
                 json_data: Optional[Dict] = None, params: Optional[Dict] = None) -> tuple:
        """Make API call and return (status_code, response_data)"""
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        url = f"{BASE_URL}{endpoint}"
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, params=params, timeout=15)
            elif method == "POST":
                resp = requests.post(url, headers=headers, json=json_data, timeout=15)
            elif method == "PUT":
                resp = requests.put(url, headers=headers, json=json_data, timeout=15)
            elif method == "DELETE":
                resp = requests.delete(url, headers=headers, timeout=15)
            else:
                return (0, {"error": f"Unknown method {method}"})
                
            try:
                data = resp.json()
            except:
                data = {"text": resp.text}
            return (resp.status_code, data)
        except Exception as e:
            return (0, {"error": str(e)})
            
    def assert_equal(self, actual, expected, msg: str):
        """Assert equality"""
        if actual == expected:
            self.passed += 1
            self.log(f"{msg}: {actual} == {expected}", "PASS")
            return True
        else:
            self.failed += 1
            self.log(f"{msg}: {actual} != {expected}", "FAIL")
            return False
            
    def assert_true(self, condition, msg: str):
        """Assert true"""
        if condition:
            self.passed += 1
            self.log(f"{msg}", "PASS")
            return True
        else:
            self.failed += 1
            self.log(f"{msg} - FAILED", "FAIL")
            return False
            
    def assert_in(self, item, container, msg: str):
        """Assert item in container"""
        if item in container:
            self.passed += 1
            self.log(f"{msg}: '{item}' found", "PASS")
            return True
        else:
            self.failed += 1
            self.log(f"{msg}: '{item}' NOT found in {container}", "FAIL")
            return False
            
    def test_whatsapp_hybrid_delivery(self):
        """
        Test WhatsApp hybrid delivery + notification status recording
        Expected: status='link' with non-empty wa_link (because Cloud API fails with #133010)
        """
        self.log("=" * 80)
        self.log("TEST: WhatsApp Hybrid Delivery + Notification Status Recording")
        self.log("=" * 80)
        
        # Step 1: Login as master
        self.log("\n[Step 1] Login as master (root)")
        master_token = self.login("master")
        if not master_token:
            self.log("Cannot proceed without master token", "FAIL")
            return
            
        # Step 2: Create a store with whatsapp number
        self.log("\n[Step 2] Create store with WhatsApp number")
        store_data = {
            "name": "Loja WA Test",
            "whatsapp": "5545999990001",
            "category": "Geral",
            "description": "Test store for WhatsApp notifications"
        }
        status, resp = self.api_call("POST", "/stores", master_token, store_data)
        if status == 200:
            store_id = resp.get("id")
            self.test_data["store_id"] = store_id
            self.log(f"Store created: {store_id}", "PASS")
        else:
            self.log(f"Store creation failed: {status} {resp}", "FAIL")
            self.failed += 1
            return
            
        # Step 3: Create a product
        self.log("\n[Step 3] Create product for the store")
        product_data = {
            "store_id": store_id,
            "name": "Produto WA",
            "price": 50.0,
            "category": "Teste",
            "description": "Test product"
        }
        status, resp = self.api_call("POST", "/products", master_token, product_data)
        if status == 200:
            product_id = resp.get("id")
            self.test_data["product_id"] = product_id
            self.log(f"Product created: {product_id}", "PASS")
        else:
            self.log(f"Product creation failed: {status} {resp}", "FAIL")
            self.failed += 1
            return
            
        # Step 4: Create an order with customer_whatsapp to trigger notifications
        self.log("\n[Step 4] Create order with customer_whatsapp to trigger notifications")
        order_data = {
            "store_id": store_id,
            "items": [
                {
                    "product_id": product_id,
                    "name": "Produto WA",
                    "price": 50.0,
                    "qty": 2
                }
            ],
            "customer_name": "Cliente Teste WA",
            "customer_whatsapp": "5545988887777",
            "notes": "Test order for WhatsApp hybrid delivery"
        }
        status, resp = self.api_call("POST", "/orders", master_token, order_data)
        if status == 200:
            order_id = resp.get("id")
            order_token = resp.get("token")
            self.test_data["order_id"] = order_id
            self.test_data["order_token"] = order_token
            self.log(f"Order created: {order_id}, token: {order_token}", "PASS")
            self.log(f"Order total: R$ {resp.get('total')}", "INFO")
        else:
            self.log(f"Order creation failed: {status} {resp}", "FAIL")
            self.failed += 1
            return
            
        # Step 5: GET /api/orders/{order_id}/notifications
        self.log("\n[Step 5] GET /api/orders/{order_id}/notifications")
        status, notifications = self.api_call("GET", f"/orders/{order_id}/notifications", master_token)
        
        if status != 200:
            self.log(f"Failed to get notifications: {status} {notifications}", "FAIL")
            self.failed += 1
            return
            
        self.log(f"Retrieved {len(notifications)} notifications", "INFO")
        
        # Analyze notifications
        self.log("\n[Step 5a] Analyze notification records")
        targets_found = set()
        whatsapp_notifications = []
        
        for notif in notifications:
            target = notif.get("target")
            channel = notif.get("channel")
            status_val = notif.get("status")
            wa_link = notif.get("wa_link", "")
            to = notif.get("to", "")
            
            targets_found.add(target)
            
            self.log(f"  Notification: target={target}, channel={channel}, status={status_val}, "
                    f"to={to}, wa_link={'YES' if wa_link else 'NO'}", "INFO")
            
            if channel == "whatsapp":
                whatsapp_notifications.append(notif)
                
        # Assert: There should be notifications for lojista, admin, and cliente
        self.log("\n[Step 5b] Verify notification targets")
        self.assert_in("lojista", targets_found, "Notification for 'lojista' exists")
        self.assert_in("admin", targets_found, "Notification for 'admin' exists")
        self.assert_in("cliente", targets_found, "Notification for 'cliente' exists")
        
        # Assert: For WhatsApp notifications, status should be "link" (NOT "sent"/"template")
        self.log("\n[Step 5c] Verify WhatsApp notification status and wa_link")
        for notif in whatsapp_notifications:
            target = notif.get("target")
            status_val = notif.get("status")
            wa_link = notif.get("wa_link", "")
            
            # Status should be "link" because Cloud API fails with #133010
            self.assert_equal(status_val, "link", 
                            f"WhatsApp notification for '{target}' has status='link'")
            
            # wa_link must be non-empty and start with https://wa.me/
            self.assert_true(bool(wa_link), 
                           f"WhatsApp notification for '{target}' has non-empty wa_link")
            self.assert_true(wa_link.startswith("https://wa.me/"), 
                           f"WhatsApp notification for '{target}' wa_link starts with 'https://wa.me/'")
            
            if wa_link:
                self.log(f"  wa_link for {target}: {wa_link[:80]}...", "INFO")
                
        # Step 6: GET /api/orders/{order_id}/wa-links
        self.log("\n[Step 6] GET /api/orders/{order_id}/wa-links")
        status, wa_links = self.api_call("GET", f"/orders/{order_id}/wa-links", master_token)
        
        if status == 200:
            vendor_link = wa_links.get("vendor_link", "")
            customer_link = wa_links.get("customer_link", "")
            pdf = wa_links.get("pdf", "")
            
            self.assert_true(bool(vendor_link), "vendor_link is non-empty")
            self.assert_true(vendor_link.startswith("https://wa.me/"), 
                           "vendor_link starts with 'https://wa.me/'")
            
            self.assert_true(bool(customer_link), "customer_link is non-empty")
            self.assert_true(customer_link.startswith("https://wa.me/"), 
                           "customer_link starts with 'https://wa.me/'")
            
            self.log(f"  vendor_link: {vendor_link[:80]}...", "INFO")
            self.log(f"  customer_link: {customer_link[:80]}...", "INFO")
            if pdf:
                self.log(f"  pdf: {pdf}", "INFO")
        else:
            self.log(f"Failed to get wa-links: {status} {wa_links}", "FAIL")
            self.failed += 1
            
    def test_regression_endpoints(self):
        """Test regression: confirm existing endpoints still work"""
        self.log("\n" + "=" * 80)
        self.log("TEST: Regression - Existing Endpoints")
        self.log("=" * 80)
        
        # GET /api/whatsapp/status
        self.log("\n[Regression 1] GET /api/whatsapp/status")
        status, resp = self.api_call("GET", "/whatsapp/status")
        if status == 200:
            configured = resp.get("configured")
            self.assert_equal(configured, True, "WhatsApp configured=true")
        else:
            self.log(f"GET /api/whatsapp/status failed: {status} {resp}", "FAIL")
            self.failed += 1
            
        # GET /api/home
        self.log("\n[Regression 2] GET /api/home")
        status, resp = self.api_call("GET", "/home")
        self.assert_equal(status, 200, "GET /api/home returns 200")
        
        # GET /api/stores
        self.log("\n[Regression 3] GET /api/stores")
        status, resp = self.api_call("GET", "/stores")
        self.assert_equal(status, 200, "GET /api/stores returns 200")
        
        # GET /api/groups
        self.log("\n[Regression 4] GET /api/groups")
        status, resp = self.api_call("GET", "/groups")
        self.assert_equal(status, 200, "GET /api/groups returns 200")
        
    def test_webhook_verification(self):
        """Test webhook verification endpoint"""
        self.log("\n" + "=" * 80)
        self.log("TEST: Webhook Verification")
        self.log("=" * 80)
        
        # Correct verify_token
        self.log("\n[Webhook 1] GET /api/webhooks/whatsapp with CORRECT verify_token")
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "shopm3d_wa_verify_2025_9f4c2a",
            "hub.challenge": "PING"
        }
        status, resp = self.api_call("GET", "/webhooks/whatsapp", params=params)
        if status == 200:
            # Response should be the challenge value
            challenge_returned = resp if isinstance(resp, str) else resp.get("text", "")
            self.assert_true("PING" in str(challenge_returned), 
                           "Webhook returns challenge 'PING' on correct verify_token")
        else:
            self.log(f"Webhook verification failed: {status} {resp}", "FAIL")
            self.failed += 1
            
        # Wrong verify_token
        self.log("\n[Webhook 2] GET /api/webhooks/whatsapp with WRONG verify_token")
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "PING"
        }
        status, resp = self.api_call("GET", "/webhooks/whatsapp", params=params)
        self.assert_equal(status, 403, "Webhook returns 403 on wrong verify_token")
        
    def run_all_tests(self):
        """Run all tests"""
        self.log("Starting WhatsApp Hybrid Delivery Backend Tests")
        self.log(f"Backend URL: {BASE_URL}")
        self.log("")
        
        try:
            self.test_whatsapp_hybrid_delivery()
            self.test_regression_endpoints()
            self.test_webhook_verification()
        except Exception as e:
            self.log(f"Test suite exception: {e}", "FAIL")
            import traceback
            traceback.print_exc()
            
        # Summary
        self.log("\n" + "=" * 80)
        self.log("TEST SUMMARY")
        self.log("=" * 80)
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        self.log(f"Total tests: {total}")
        self.log(f"Passed: {self.passed} ✅")
        self.log(f"Failed: {self.failed} ❌")
        self.log(f"Pass rate: {pass_rate:.1f}%")
        
        if self.failed == 0:
            self.log("\n🎉 ALL TESTS PASSED!", "PASS")
            return 0
        else:
            self.log(f"\n⚠️  {self.failed} TEST(S) FAILED", "FAIL")
            return 1

if __name__ == "__main__":
    runner = TestRunner()
    exit_code = runner.run_all_tests()
    sys.exit(exit_code)
