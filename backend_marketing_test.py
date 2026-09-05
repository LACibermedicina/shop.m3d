#!/usr/bin/env python3
"""
Backend API Tests for Marketing / Campanhas IA
Tests the new marketing endpoints with AI image generation.
"""
import requests
import sys
import time

# Backend base URL from frontend/.env
BASE_URL = "https://git-sync-40.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
CREDENTIALS = {
    "lojista": {
        "username": "lojista",
        "password": "@0lojista",
        "role": "lojista"
    },
    "cliente": {
        "username": "cliente",
        "password": "@0cliente",
        "role": "cliente"
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

def login(account_name):
    """Login and return token"""
    cred = CREDENTIALS[account_name]
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": cred["username"],
        "password": cred["password"]
    }, timeout=10)
    
    if resp.status_code != 200:
        print(f"{Colors.RED}Failed to login as {account_name}: {resp.status_code}{Colors.END}")
        return None
    
    data = resp.json()
    token = data.get("session_token")
    print(f"{Colors.GREEN}✓ Logged in as {account_name} (role={data.get('user', {}).get('role')}){Colors.END}")
    return token

def test_get_socials(token):
    """Test 1: GET /api/marketing/socials with lojista token"""
    resp = requests.get(f"{BASE_URL}/marketing/socials", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=10)
    
    if resp.status_code != 200:
        return log_test(
            "GET /api/marketing/socials (lojista)",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        ), None
    
    data = resp.json()
    
    # Check structure
    if "networks" not in data or "catalog" not in data:
        return log_test(
            "GET /api/marketing/socials (lojista)",
            False,
            f"Missing 'networks' or 'catalog' in response: {list(data.keys())}"
        ), None
    
    # Check catalog has 5 items
    catalog = data["catalog"]
    if len(catalog) != 5:
        return log_test(
            "GET /api/marketing/socials (lojista)",
            False,
            f"Expected 5 catalog items, got {len(catalog)}"
        ), None
    
    # Check catalog items have required keys
    required_keys = ["instagram_feed", "instagram_story", "tiktok", "pinterest", "facebook_feed"]
    catalog_keys = [item.get("key") for item in catalog]
    
    missing_keys = [k for k in required_keys if k not in catalog_keys]
    if missing_keys:
        return log_test(
            "GET /api/marketing/socials (lojista)",
            False,
            f"Missing catalog keys: {missing_keys}"
        ), None
    
    # Check each catalog item has required fields
    for item in catalog:
        required_fields = ["key", "label", "icon", "ratio", "w", "h"]
        missing_fields = [f for f in required_fields if f not in item]
        if missing_fields:
            return log_test(
                "GET /api/marketing/socials (lojista)",
                False,
                f"Catalog item {item.get('key')} missing fields: {missing_fields}"
            ), None
    
    return log_test(
        "GET /api/marketing/socials (lojista)",
        True,
        f"networks={len(data['networks'])}, catalog={len(catalog)} items with correct keys"
    ), data

def test_put_socials(token):
    """Test 2: PUT /api/marketing/socials"""
    body = {
        "networks": [
            {
                "network": "instagram_feed",
                "handle": "@minhaloja",
                "url": "https://instagram.com/minhaloja",
                "enabled": True
            }
        ]
    }
    
    resp = requests.put(f"{BASE_URL}/marketing/socials", headers={
        "Authorization": f"Bearer {token}"
    }, json=body, timeout=10)
    
    if resp.status_code != 200:
        return log_test(
            "PUT /api/marketing/socials",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        ), None
    
    data = resp.json()
    
    # Check response has networks
    if "networks" not in data:
        return log_test(
            "PUT /api/marketing/socials",
            False,
            "Missing 'networks' in response"
        ), None
    
    networks = data["networks"]
    if len(networks) != 1:
        return log_test(
            "PUT /api/marketing/socials",
            False,
            f"Expected 1 network, got {len(networks)}"
        ), None
    
    # Check network details
    net = networks[0]
    if net.get("network") != "instagram_feed":
        return log_test(
            "PUT /api/marketing/socials",
            False,
            f"Expected network=instagram_feed, got {net.get('network')}"
        ), None
    
    if net.get("handle") != "@minhaloja":
        return log_test(
            "PUT /api/marketing/socials",
            False,
            f"Expected handle=@minhaloja, got {net.get('handle')}"
        ), None
    
    if net.get("url") != "https://instagram.com/minhaloja":
        return log_test(
            "PUT /api/marketing/socials",
            False,
            f"Expected url=https://instagram.com/minhaloja, got {net.get('url')}"
        ), None
    
    if not net.get("enabled"):
        return log_test(
            "PUT /api/marketing/socials",
            False,
            f"Expected enabled=True, got {net.get('enabled')}"
        ), None
    
    return log_test(
        "PUT /api/marketing/socials",
        True,
        f"Updated: network={net['network']}, handle={net['handle']}, enabled={net['enabled']}"
    ), data

def test_get_socials_after_update(token):
    """Test 2b: GET /api/marketing/socials after PUT to verify changes"""
    resp = requests.get(f"{BASE_URL}/marketing/socials", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=10)
    
    if resp.status_code != 200:
        return log_test(
            "GET /api/marketing/socials after PUT",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        )
    
    data = resp.json()
    networks = data.get("networks", [])
    
    if len(networks) != 1:
        return log_test(
            "GET /api/marketing/socials after PUT",
            False,
            f"Expected 1 network, got {len(networks)}"
        )
    
    net = networks[0]
    if net.get("network") != "instagram_feed" or net.get("handle") != "@minhaloja":
        return log_test(
            "GET /api/marketing/socials after PUT",
            False,
            f"Network not persisted correctly: {net}"
        )
    
    return log_test(
        "GET /api/marketing/socials after PUT",
        True,
        f"Changes persisted: network={net['network']}, handle={net['handle']}"
    )

def test_create_campaign(token):
    """Test 3: POST /api/marketing/campaign with REAL AI image generation"""
    body = {
        "product_name": "Tenis Runner X",
        "product_details": "leve, corrida, amortecimento",
        "price": "R$ 299",
        "category": "Calcados",
        "networks": ["instagram_feed"],  # ONLY 1 network to limit cost/time
        "language": "pt",
        "tone": "esportivo"
    }
    
    print(f"{Colors.YELLOW}⏳ Creating campaign with AI image generation (may take 20-40s)...{Colors.END}")
    start_time = time.time()
    
    resp = requests.post(f"{BASE_URL}/marketing/campaign", headers={
        "Authorization": f"Bearer {token}"
    }, json=body, timeout=90)  # 90s timeout for AI generation
    
    elapsed = time.time() - start_time
    
    if resp.status_code != 200:
        return log_test(
            "POST /api/marketing/campaign (AI generation)",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:500]}"
        ), None
    
    data = resp.json()
    
    # Check required fields
    required_fields = ["id", "concept", "cover_path", "assets"]
    missing_fields = [f for f in required_fields if f not in data]
    if missing_fields:
        return log_test(
            "POST /api/marketing/campaign (AI generation)",
            False,
            f"Missing fields: {missing_fields}"
        ), None
    
    # Check concept is non-empty
    if not data.get("concept") or not data["concept"].strip():
        return log_test(
            "POST /api/marketing/campaign (AI generation)",
            False,
            "concept is empty"
        ), None
    
    # Check assets is a list with 1 item
    assets = data.get("assets", [])
    if not isinstance(assets, list) or len(assets) != 1:
        return log_test(
            "POST /api/marketing/campaign (AI generation)",
            False,
            f"Expected assets to be a list with 1 item, got {type(assets)} with {len(assets) if isinstance(assets, list) else 'N/A'} items"
        ), None
    
    # Check asset[0] has required fields
    asset = assets[0]
    required_asset_fields = ["image_path", "caption", "hashtags", "cta", "ratio", "w", "h"]
    missing_asset_fields = [f for f in required_asset_fields if f not in asset]
    if missing_asset_fields:
        return log_test(
            "POST /api/marketing/campaign (AI generation)",
            False,
            f"Asset missing fields: {missing_asset_fields}"
        ), None
    
    # Check image_path is non-empty
    if not asset.get("image_path") or not asset["image_path"].strip():
        return log_test(
            "POST /api/marketing/campaign (AI generation)",
            False,
            "asset image_path is empty"
        ), None
    
    # Check caption is non-empty
    if not asset.get("caption") or not asset["caption"].strip():
        return log_test(
            "POST /api/marketing/campaign (AI generation)",
            False,
            "asset caption is empty"
        ), None
    
    # Check hashtags is non-empty list
    hashtags = asset.get("hashtags", [])
    if not isinstance(hashtags, list) or len(hashtags) == 0:
        return log_test(
            "POST /api/marketing/campaign (AI generation)",
            False,
            f"Expected hashtags to be non-empty list, got {type(hashtags)} with {len(hashtags) if isinstance(hashtags, list) else 'N/A'} items"
        ), None
    
    # Check ratio, w, h
    if asset.get("ratio") != "4:5":
        return log_test(
            "POST /api/marketing/campaign (AI generation)",
            False,
            f"Expected ratio=4:5, got {asset.get('ratio')}"
        ), None
    
    if asset.get("w") != 1080:
        return log_test(
            "POST /api/marketing/campaign (AI generation)",
            False,
            f"Expected w=1080, got {asset.get('w')}"
        ), None
    
    if asset.get("h") != 1350:
        return log_test(
            "POST /api/marketing/campaign (AI generation)",
            False,
            f"Expected h=1350, got {asset.get('h')}"
        ), None
    
    return log_test(
        "POST /api/marketing/campaign (AI generation)",
        True,
        f"Campaign created in {elapsed:.1f}s: id={data['id']}, concept={data['concept'][:50]}..., image_path={asset['image_path']}, hashtags={len(hashtags)}"
    ), data

def test_get_image(image_path):
    """Test 4: GET /api/files/{image_path}"""
    resp = requests.get(f"{BASE_URL}/files/{image_path}", timeout=30)
    
    if resp.status_code != 200:
        return log_test(
            "GET /api/files/{image_path}",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        )
    
    # Check content-type
    content_type = resp.headers.get("Content-Type", "")
    if "image/jpeg" not in content_type and "image/jpg" not in content_type:
        return log_test(
            "GET /api/files/{image_path}",
            False,
            f"Expected content-type image/jpeg, got {content_type}"
        )
    
    # Check size > 10KB
    size = len(resp.content)
    if size < 10240:  # 10KB
        return log_test(
            "GET /api/files/{image_path}",
            False,
            f"Expected size > 10KB, got {size} bytes"
        )
    
    return log_test(
        "GET /api/files/{image_path}",
        True,
        f"Image retrieved: content-type={content_type}, size={size} bytes ({size/1024:.1f}KB)"
    )

def test_list_campaigns(token):
    """Test 5: GET /api/marketing/campaigns"""
    resp = requests.get(f"{BASE_URL}/marketing/campaigns", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=10)
    
    if resp.status_code != 200:
        return log_test(
            "GET /api/marketing/campaigns (list)",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        ), None
    
    data = resp.json()
    
    if not isinstance(data, list):
        return log_test(
            "GET /api/marketing/campaigns (list)",
            False,
            f"Expected list, got {type(data)}"
        ), None
    
    if len(data) == 0:
        return log_test(
            "GET /api/marketing/campaigns (list)",
            False,
            "Expected at least 1 campaign, got 0"
        ), None
    
    # Check first campaign has cover_path but NOT assets
    campaign = data[0]
    if "cover_path" not in campaign:
        return log_test(
            "GET /api/marketing/campaigns (list)",
            False,
            "Campaign missing cover_path"
        ), None
    
    if "assets" in campaign:
        return log_test(
            "GET /api/marketing/campaigns (list)",
            False,
            "Campaign should NOT include assets array in list view"
        ), None
    
    return log_test(
        "GET /api/marketing/campaigns (list)",
        True,
        f"Found {len(data)} campaigns, first has cover_path, no assets array"
    ), data

def test_get_campaign_detail(token, campaign_id):
    """Test 6: GET /api/marketing/campaigns/{id}"""
    resp = requests.get(f"{BASE_URL}/marketing/campaigns/{campaign_id}", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=10)
    
    if resp.status_code != 200:
        return log_test(
            "GET /api/marketing/campaigns/{id} (detail)",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        ), None
    
    data = resp.json()
    
    # Check has assets array
    if "assets" not in data:
        return log_test(
            "GET /api/marketing/campaigns/{id} (detail)",
            False,
            "Campaign detail missing assets array"
        ), None
    
    assets = data.get("assets", [])
    if not isinstance(assets, list) or len(assets) == 0:
        return log_test(
            "GET /api/marketing/campaigns/{id} (detail)",
            False,
            f"Expected assets to be non-empty list, got {type(assets)} with {len(assets) if isinstance(assets, list) else 'N/A'} items"
        ), None
    
    return log_test(
        "GET /api/marketing/campaigns/{id} (detail)",
        True,
        f"Campaign detail includes assets array with {len(assets)} items"
    ), data

def test_delete_campaign(token, campaign_id):
    """Test 7: DELETE /api/marketing/campaigns/{id}"""
    resp = requests.delete(f"{BASE_URL}/marketing/campaigns/{campaign_id}", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=10)
    
    if resp.status_code != 200:
        return log_test(
            "DELETE /api/marketing/campaigns/{id}",
            False,
            f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        )
    
    data = resp.json()
    if not data.get("ok"):
        return log_test(
            "DELETE /api/marketing/campaigns/{id}",
            False,
            f"Expected ok=true, got {data}"
        )
    
    return log_test(
        "DELETE /api/marketing/campaigns/{id}",
        True,
        f"Campaign deleted: {campaign_id}"
    )

def test_get_deleted_campaign(token, campaign_id):
    """Test 7b: GET /api/marketing/campaigns/{id} after delete -> 404"""
    resp = requests.get(f"{BASE_URL}/marketing/campaigns/{campaign_id}", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=10)
    
    if resp.status_code != 404:
        return log_test(
            "GET deleted campaign returns 404",
            False,
            f"Expected 404, got {resp.status_code}"
        )
    
    return log_test(
        "GET deleted campaign returns 404",
        True,
        f"Deleted campaign correctly returns 404"
    )

def test_cliente_get_socials(token):
    """Test 8a: Cliente cannot access GET /api/marketing/socials (403)"""
    resp = requests.get(f"{BASE_URL}/marketing/socials", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=10)
    
    if resp.status_code != 403:
        return log_test(
            "Cliente GET /api/marketing/socials returns 403",
            False,
            f"Expected 403, got {resp.status_code}"
        )
    
    return log_test(
        "Cliente GET /api/marketing/socials returns 403",
        True,
        "Permission check passed"
    )

def test_cliente_create_campaign(token):
    """Test 8b: Cliente cannot access POST /api/marketing/campaign (403)"""
    body = {
        "product_name": "Test Product",
        "networks": ["instagram_feed"]
    }
    
    resp = requests.post(f"{BASE_URL}/marketing/campaign", headers={
        "Authorization": f"Bearer {token}"
    }, json=body, timeout=10)
    
    if resp.status_code != 403:
        return log_test(
            "Cliente POST /api/marketing/campaign returns 403",
            False,
            f"Expected 403, got {resp.status_code}"
        )
    
    return log_test(
        "Cliente POST /api/marketing/campaign returns 403",
        True,
        "Permission check passed"
    )

def test_create_campaign_no_product(token):
    """Test 9: POST /api/marketing/campaign with no product_id and no product_name -> 400"""
    body = {}  # Empty body
    
    resp = requests.post(f"{BASE_URL}/marketing/campaign", headers={
        "Authorization": f"Bearer {token}"
    }, json=body, timeout=10)
    
    if resp.status_code != 400:
        return log_test(
            "POST campaign with empty body returns 400",
            False,
            f"Expected 400, got {resp.status_code}"
        )
    
    return log_test(
        "POST campaign with empty body returns 400",
        True,
        "Validation check passed"
    )

def main():
    print(f"\n{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BLUE}Backend API Tests - Marketing / Campanhas IA{Colors.END}")
    print(f"{Colors.BLUE}Base URL: {BASE_URL}{Colors.END}")
    print(f"{Colors.BLUE}{'='*70}{Colors.END}\n")
    
    passed = 0
    failed = 0
    
    # Login
    print(f"\n{Colors.YELLOW}Logging in...{Colors.END}")
    lojista_token = login("lojista")
    cliente_token = login("cliente")
    
    if not lojista_token or not cliente_token:
        print(f"\n{Colors.RED}Failed to login. Aborting tests.{Colors.END}\n")
        return 1
    
    # Test 1: GET /api/marketing/socials
    print(f"\n{Colors.YELLOW}Test 1: GET /api/marketing/socials{Colors.END}")
    result = test_get_socials(lojista_token)
    if isinstance(result, tuple):
        success, data = result
        if success:
            passed += 1
        else:
            failed += 1
    else:
        if result:
            passed += 1
        else:
            failed += 1
    
    # Test 2: PUT /api/marketing/socials
    print(f"\n{Colors.YELLOW}Test 2: PUT /api/marketing/socials{Colors.END}")
    result = test_put_socials(lojista_token)
    if isinstance(result, tuple):
        success, data = result
        if success:
            passed += 1
        else:
            failed += 1
    else:
        if result:
            passed += 1
        else:
            failed += 1
    
    # Test 2b: GET after PUT
    if test_get_socials_after_update(lojista_token):
        passed += 1
    else:
        failed += 1
    
    # Test 3: POST /api/marketing/campaign (AI generation)
    print(f"\n{Colors.YELLOW}Test 3: POST /api/marketing/campaign (REAL AI image generation){Colors.END}")
    result = test_create_campaign(lojista_token)
    campaign_data = None
    if isinstance(result, tuple):
        success, campaign_data = result
        if success:
            passed += 1
        else:
            failed += 1
    else:
        if result:
            passed += 1
        else:
            failed += 1
    
    # Test 4: GET /api/files/{image_path}
    if campaign_data and campaign_data.get("assets"):
        print(f"\n{Colors.YELLOW}Test 4: GET /api/files/{{image_path}}{Colors.END}")
        image_path = campaign_data["assets"][0]["image_path"]
        if test_get_image(image_path):
            passed += 1
        else:
            failed += 1
    else:
        log_test("GET /api/files/{image_path}", False, "No campaign data available")
        failed += 1
    
    # Test 5: GET /api/marketing/campaigns (list)
    print(f"\n{Colors.YELLOW}Test 5: GET /api/marketing/campaigns (list){Colors.END}")
    result = test_list_campaigns(lojista_token)
    campaigns_list = None
    if isinstance(result, tuple):
        success, campaigns_list = result
        if success:
            passed += 1
        else:
            failed += 1
    else:
        if result:
            passed += 1
        else:
            failed += 1
    
    # Test 6: GET /api/marketing/campaigns/{id} (detail)
    if campaign_data:
        print(f"\n{Colors.YELLOW}Test 6: GET /api/marketing/campaigns/{{id}} (detail){Colors.END}")
        campaign_id = campaign_data["id"]
        result = test_get_campaign_detail(lojista_token, campaign_id)
        if isinstance(result, tuple):
            success, data = result
            if success:
                passed += 1
            else:
                failed += 1
        else:
            if result:
                passed += 1
            else:
                failed += 1
    else:
        log_test("GET /api/marketing/campaigns/{id} (detail)", False, "No campaign data available")
        failed += 1
    
    # Test 7: DELETE /api/marketing/campaigns/{id}
    if campaign_data:
        print(f"\n{Colors.YELLOW}Test 7: DELETE /api/marketing/campaigns/{{id}}{Colors.END}")
        campaign_id = campaign_data["id"]
        if test_delete_campaign(lojista_token, campaign_id):
            passed += 1
        else:
            failed += 1
        
        # Test 7b: GET after delete -> 404
        if test_get_deleted_campaign(lojista_token, campaign_id):
            passed += 1
        else:
            failed += 1
    else:
        log_test("DELETE /api/marketing/campaigns/{id}", False, "No campaign data available")
        failed += 1
        log_test("GET deleted campaign returns 404", False, "No campaign data available")
        failed += 1
    
    # Test 8: Permission checks with cliente token
    print(f"\n{Colors.YELLOW}Test 8: Permission checks (cliente token){Colors.END}")
    if test_cliente_get_socials(cliente_token):
        passed += 1
    else:
        failed += 1
    
    if test_cliente_create_campaign(cliente_token):
        passed += 1
    else:
        failed += 1
    
    # Test 9: POST campaign with empty body
    print(f"\n{Colors.YELLOW}Test 9: POST campaign with empty body (validation){Colors.END}")
    if test_create_campaign_no_product(lojista_token):
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
