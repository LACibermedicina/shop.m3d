import hmac, hashlib, json, time, requests

BASE = "https://mobile-preview-871.preview.emergentagent.com"
APP_SECRET = "33ad148123a77e050633a92d04c20a53"
VENDOR1 = "5545911110001"
VENDOR2 = "5545911110002"
CUSTOMER = "5545922220000"


def sign(raw): return "sha256=" + hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()


def dev_login(role):
    return requests.post(f"{BASE}/api/auth/dev-login",
                         json={"email": f"{role}@feira.test", "name": role.title(), "role": role}).json()["session_token"]


def webhook(sender, text=None):
    msg = {"id": f"wamid.{time.time_ns()}", "from": sender, "type": "text", "text": {"body": text}}
    payload = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"messages": [msg]}}]}]}
    raw = json.dumps(payload).encode()
    r = requests.post(f"{BASE}/api/webhooks/whatsapp", data=raw,
                      headers={"Content-Type": "application/json", "x-hub-signature-256": sign(raw)})
    time.sleep(0.3)
    return r


def ensure_store(ah, name, wa):
    for s in requests.get(f"{BASE}/api/stores").json():
        if s.get("name") == name:
            return s["id"]
    r = requests.post(f"{BASE}/api/stores", headers=ah,
                      json={"name": name, "whatsapp": wa, "description": "t", "admin_whatsapp": ""})
    return r.json()["id"]


def main():
    admin = dev_login("admin"); ah = {"Authorization": f"Bearer {admin}"}
    s1 = ensure_store(ah, "Eletro Fronteira", VENDOR1)
    s2 = ensure_store(ah, "Moda Fronteira", VENDOR2)
    print("stores", s1, s2)

    # vendor 1 registers products via WA
    webhook(VENDOR1, "Fone de ouvido bluetooth JBL, R$ 199,90")
    webhook(VENDOR1, "Carregador turbo USB-C 20W, R$ 89,90")
    # vendor 2 registers products
    webhook(VENDOR2, "Camiseta Polo azul masculina, R$ 79,90")
    # vendor commands
    print("abrir:", webhook(VENDOR1, "abrir loja").status_code)
    print("cupom:", webhook(VENDOR1, "criar cupom PROMO10 10%").status_code)
    print("pedidos:", webhook(VENDOR1, "quais pedidos eu tenho?").status_code)
    print("fechar:", webhook(VENDOR1, "fechar loja").status_code)

    # verify coupon + store open toggled
    cps = requests.get(f"{BASE}/api/stores/{s1}").json()
    print("store1 is_open after fechar:", cps.get("is_open"))

    # CUSTOMER flow (multi-store cart)
    webhook(CUSTOMER, "estou procurando um fone de ouvido bluetooth")
    webhook(CUSTOMER, "adicionar 1")
    webhook(CUSTOMER, "quero uma camiseta polo")
    webhook(CUSTOMER, "adicionar 1 duas unidades")
    webhook(CUSTOMER, "ver carrinho")
    webhook(CUSTOMER, "finalizar")
    # confirm create
    webhook(CUSTOMER, "sim")
    # confirm send
    webhook(CUSTOMER, "sim")

    time.sleep(1)
    log = requests.get(f"{BASE}/api/admin/wa-inbound", headers=ah).json()
    print("\n== wa-inbound (recent) ==")
    for e in log[:22]:
        who = "LOJA:" + e["store_name"] if e.get("store_name") else "CLIENTE"
        print(f"{who} | {e.get('intent')} -> {e.get('result')}")

    # verify orders created for both stores and sent
    orders = requests.get(f"{BASE}/api/admin/metrics", headers=ah).json()
    print("\nmetrics orders:", orders.get("orders"))


if __name__ == "__main__":
    main()
