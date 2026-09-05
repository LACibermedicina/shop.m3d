import hmac, hashlib, json, time, requests

BASE = "https://git-sync-40.preview.emergentagent.com"
APP_SECRET = "33ad148123a77e050633a92d04c20a53"
SENDER = "5511977778888"


def sign(raw: bytes) -> str:
    return "sha256=" + hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()


def dev_login(role):
    r = requests.post(f"{BASE}/api/auth/dev-login",
                      json={"email": f"{role}@feira.test", "name": role.title(), "role": role})
    r.raise_for_status()
    return r.json()["session_token"]


def webhook(text=None, image_id=None, caption=None):
    msg = {"id": f"wamid.{time.time_ns()}", "from": SENDER, "type": "text"}
    if text is not None:
        msg["type"] = "text"; msg["text"] = {"body": text}
    if image_id:
        msg["type"] = "image"; msg["image"] = {"id": image_id, "caption": caption or ""}
    payload = {"object": "whatsapp_business_account",
               "entry": [{"changes": [{"value": {"messages": [msg]}}]}]}
    raw = json.dumps(payload).encode()
    r = requests.post(f"{BASE}/api/webhooks/whatsapp", data=raw,
                      headers={"Content-Type": "application/json",
                               "x-hub-signature-256": sign(raw)})
    print("webhook", r.status_code, r.text)
    return r


def main():
    admin = dev_login("admin")
    ah = {"Authorization": f"Bearer {admin}"}

    # ensure a test store with our sender's whatsapp
    stores = requests.get(f"{BASE}/api/stores")
    print("stores status", stores.status_code)
    store_id = None
    if stores.status_code == 200:
        for s in stores.json():
            if s.get("name") == "Loja Teste WA":
                store_id = s["id"]; break
    if not store_id:
        r = requests.post(f"{BASE}/api/stores", headers=ah,
                          json={"name": "Loja Teste WA", "whatsapp": SENDER,
                                "description": "teste", "admin_whatsapp": ""})
        print("create store", r.status_code, r.text[:200])
        store_id = r.json().get("id")
    print("store_id", store_id)

    # 1) help
    webhook(text="ajuda")
    # 2) create product
    webhook(text="Camiseta Polo azul tamanho M, R$ 79,90")
    # 3) catalog
    webhook(text="catálogo")
    # 4) update price
    webhook(text="atualizar Camiseta Polo para R$ 69,90")
    # 5) deactivate
    webhook(text="desativar Camiseta Polo")

    time.sleep(1)
    log = requests.get(f"{BASE}/api/admin/wa-inbound", headers=ah)
    print("\n== wa-inbound log ==")
    for e in log.json()[:10]:
        print(e.get("intent"), "->", e.get("result"))

    # catalog pdf
    pdf = requests.get(f"{BASE}/api/stores/{store_id}/catalog.pdf")
    print("\ncatalog.pdf", pdf.status_code, pdf.headers.get("content-type"), len(pdf.content), "bytes")


if __name__ == "__main__":
    main()
