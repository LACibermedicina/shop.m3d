import os
import re
import io
import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Header, Request, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import httpx
import requests

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("feira")

# ------------------------------------------------------------------ DB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
DEV_LOGIN_SECRET = os.environ.get("DEV_LOGIN_SECRET", "")
ADMIN_EMAILS = [e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()]

# ------------------------------------------------------------------ Storage
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "feira-online"
_storage_key = None


def init_storage():
    global _storage_key
    if _storage_key:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_LLM_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


# ------------------------------------------------------------------ App
app = FastAPI(title="Feira Online API")
api = APIRouter(prefix="/api")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix="id"):
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


# ------------------------------------------------------------------ Models
class DevLogin(BaseModel):
    email: str
    name: Optional[str] = None
    role: str = "cliente"


class SessionReq(BaseModel):
    session_id: str


class StoreIn(BaseModel):
    name: str
    description: Optional[str] = ""
    logo: Optional[str] = ""
    whatsapp: str
    owner_user_id: Optional[str] = None


class ProductIn(BaseModel):
    store_id: str
    name: str
    description: Optional[str] = ""
    price: float
    image: Optional[str] = ""


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    image: Optional[str] = None


class AIImportReq(BaseModel):
    message: str
    image: Optional[str] = ""  # storage path
    store_id: str


class OrderItem(BaseModel):
    product_id: str
    name: str
    price: float
    qty: int


class OrderIn(BaseModel):
    store_id: str
    items: List[OrderItem]
    customer_name: Optional[str] = ""
    notes: Optional[str] = ""


class OrderItemsUpdate(BaseModel):
    items: List[OrderItem]


class StatusUpdate(BaseModel):
    status: str


class RoleUpdate(BaseModel):
    role: str
    store_id: Optional[str] = None


# ------------------------------------------------------------------ Auth helpers
async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Não autenticado")
    token = authorization.split(" ", 1)[1].strip()
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Sessão inválida")
    exp = session.get("expires_at")
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Sessão expirada")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user


def require_role(*roles):
    async def checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Acesso negado")
        return user
    return checker


async def upsert_user(email, name, picture):
    email_l = email.lower()
    existing = await db.users.find_one({"email": email_l})
    if existing:
        return existing["user_id"], existing["role"], existing.get("store_id")
    role = "admin" if email_l in ADMIN_EMAILS else "cliente"
    uid = f"user_{uuid.uuid4().hex[:12]}"
    doc = {"user_id": uid, "email": email_l, "name": name or email_l.split("@")[0],
           "picture": picture or "", "role": role, "store_id": None, "created_at": now_iso()}
    await db.users.insert_one(doc)
    return uid, role, None


async def create_session(user_id):
    token = f"st_{uuid.uuid4().hex}{uuid.uuid4().hex}"
    await db.user_sessions.insert_one({
        "session_token": token, "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    })
    return token


# ------------------------------------------------------------------ Auth routes
@api.post("/auth/session")
async def auth_session(body: SessionReq):
    async with httpx.AsyncClient(timeout=30) as hc:
        r = await hc.get("https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                         headers={"X-Session-ID": body.session_id})
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Sessão inválida")
    data = r.json()
    uid, role, store_id = await upsert_user(data["email"], data.get("name"), data.get("picture"))
    token = await create_session(uid)
    user = await db.users.find_one({"user_id": uid}, {"_id": 0})
    return {"session_token": token, "user": user}


@api.post("/auth/dev-login")
async def dev_login(body: DevLogin, x_dev_secret: Optional[str] = Header(None)):
    if not DEV_LOGIN_SECRET or x_dev_secret != DEV_LOGIN_SECRET:
        raise HTTPException(status_code=403, detail="Dev login desabilitado")
    if body.role not in ("admin", "lojista", "cliente"):
        raise HTTPException(status_code=400, detail="Role inválida")
    email_l = body.email.lower()
    existing = await db.users.find_one({"email": email_l})
    if existing:
        uid = existing["user_id"]
        await db.users.update_one({"user_id": uid}, {"$set": {"role": body.role}})
    else:
        uid = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({"user_id": uid, "email": email_l, "name": body.name or email_l.split("@")[0],
                                   "picture": "", "role": body.role, "store_id": None, "created_at": now_iso()})
    token = await create_session(uid)
    user = await db.users.find_one({"user_id": uid}, {"_id": 0})
    return {"session_token": token, "user": user}


@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user


@api.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        await db.user_sessions.delete_many({"session_token": token})
    return {"ok": True}


# ------------------------------------------------------------------ Upload / Files
@api.post("/upload")
async def upload(file: UploadFile = File(...), user=Depends(get_current_user)):
    ext = (file.filename or "img").split(".")[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    path = f"{APP_NAME}/uploads/{user['user_id']}/{uuid.uuid4().hex}.{ext}"
    data = await file.read()
    ct = file.content_type or "image/jpeg"
    await run_in_threadpool(put_object, path, data, ct)
    return {"path": path}


@api.get("/files/{path:path}")
async def files(path: str):
    try:
        content, ct = await run_in_threadpool(get_object, path)
    except Exception:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return StreamingResponse(io.BytesIO(content), media_type=ct)


# ------------------------------------------------------------------ Stores
@api.get("/stores")
async def list_stores():
    stores = await db.stores.find({"deleted": {"$ne": True}, "active": {"$ne": False}}, {"_id": 0}).to_list(500)
    for s in stores:
        s["product_count"] = await db.products.count_documents({"store_id": s["id"], "deleted": {"$ne": True}})
    return stores


@api.get("/stores/{store_id}")
async def get_store(store_id: str):
    s = await db.stores.find_one({"id": store_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Barraca não encontrada")
    return s


@api.post("/stores")
async def create_store(body: StoreIn, user=Depends(require_role("admin"))):
    doc = body.dict()
    doc.update({"id": new_id("store"), "active": True, "deleted": False, "created_at": now_iso()})
    await db.stores.insert_one(doc)
    if doc.get("owner_user_id"):
        await db.users.update_one({"user_id": doc["owner_user_id"]},
                                  {"$set": {"role": "lojista", "store_id": doc["id"]}})
    return await db.stores.find_one({"id": doc["id"]}, {"_id": 0})


@api.put("/stores/{store_id}")
async def update_store(store_id: str, body: StoreIn, user=Depends(require_role("admin", "lojista"))):
    s = await db.stores.find_one({"id": store_id, "deleted": {"$ne": True}})
    if not s:
        raise HTTPException(status_code=404, detail="Barraca não encontrada")
    if user["role"] == "lojista" and user.get("store_id") != store_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if user["role"] == "lojista":
        updates.pop("owner_user_id", None)
    await db.stores.update_one({"id": store_id}, {"$set": updates})
    if updates.get("owner_user_id"):
        await db.users.update_one({"user_id": updates["owner_user_id"]},
                                  {"$set": {"role": "lojista", "store_id": store_id}})
    return await db.stores.find_one({"id": store_id}, {"_id": 0})


@api.delete("/stores/{store_id}")
async def delete_store(store_id: str, user=Depends(require_role("admin"))):
    await db.stores.update_one({"id": store_id}, {"$set": {"deleted": True}})
    return {"ok": True}


# ------------------------------------------------------------------ Products
SORT_MAP = {"recent": ("created_at", -1), "name": ("name", 1),
            "price_asc": ("price", 1), "price_desc": ("price", -1)}


@api.get("/stores/{store_id}/products")
async def store_products(store_id: str, sort: str = Query("recent")):
    field, direction = SORT_MAP.get(sort, ("created_at", -1))
    products = await db.products.find({"store_id": store_id, "deleted": {"$ne": True}},
                                      {"_id": 0}).sort(field, direction).to_list(1000)
    return products


@api.post("/products")
async def create_product(body: ProductIn, user=Depends(require_role("admin", "lojista"))):
    if user["role"] == "lojista" and user.get("store_id") != body.store_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    doc = body.dict()
    doc.update({"id": new_id("prod"), "deleted": False, "created_at": now_iso()})
    await db.products.insert_one(doc)
    return await db.products.find_one({"id": doc["id"]}, {"_id": 0})


@api.put("/products/{product_id}")
async def update_product(product_id: str, body: ProductUpdate, user=Depends(require_role("admin", "lojista"))):
    p = await db.products.find_one({"id": product_id, "deleted": {"$ne": True}})
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    if user["role"] == "lojista" and user.get("store_id") != p["store_id"]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    updates = {k: v for k, v in body.dict().items() if v is not None}
    await db.products.update_one({"id": product_id}, {"$set": updates})
    return await db.products.find_one({"id": product_id}, {"_id": 0})


@api.delete("/products/{product_id}")
async def delete_product(product_id: str, user=Depends(require_role("admin", "lojista"))):
    p = await db.products.find_one({"id": product_id})
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    if user["role"] == "lojista" and user.get("store_id") != p["store_id"]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    await db.products.update_one({"id": product_id}, {"$set": {"deleted": True}})
    return {"ok": True}


@api.post("/products/ai-import")
async def ai_import(body: AIImportReq, user=Depends(require_role("admin", "lojista"))):
    if user["role"] == "lojista" and user.get("store_id") != body.store_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    parsed = await extract_product(body.message, body.image)
    return parsed


async def extract_product(message: str, image_path: str = ""):
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    system = (
        "Você extrai dados de produtos de mensagens de WhatsApp de feirantes brasileiros. "
        "Responda SOMENTE com JSON válido no formato: "
        '{\"name\": string, \"price\": number, \"description\": string}. '
        "price em reais (número, sem R$). Se não houver preço, use 0. "
        "name curto. description resumida. Nada além do JSON."
    )
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"ai-import-{uuid.uuid4().hex[:8]}",
                   system_message=system).with_model("gemini", "gemini-3-flash-preview")
    file_contents = []
    if image_path:
        try:
            content, _ = await run_in_threadpool(get_object, image_path)
            import base64
            file_contents = [ImageContent(image_base64=base64.b64encode(content).decode())]
        except Exception as e:
            logger.warning(f"AI image load failed: {e}")
    um = UserMessage(text=f"Mensagem do feirante: {message}", file_contents=file_contents or None)
    try:
        resp = await chat.send_message(um)
    except Exception as e:
        logger.error(f"AI extract error: {e}")
        raise HTTPException(status_code=502, detail="Falha ao processar com IA")
    text = resp if isinstance(resp, str) else str(resp)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise HTTPException(status_code=502, detail="IA não retornou dados válidos")
    try:
        data = json.loads(m.group(0))
    except Exception:
        raise HTTPException(status_code=502, detail="IA não retornou JSON válido")
    return {"name": str(data.get("name", "")).strip(),
            "price": float(data.get("price", 0) or 0),
            "description": str(data.get("description", "")).strip()}


# ------------------------------------------------------------------ Orders
def order_public(o):
    o.pop("_id", None)
    return o


@api.post("/orders")
async def create_order(body: OrderIn, user=Depends(get_current_user)):
    store = await db.stores.find_one({"id": body.store_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not store:
        raise HTTPException(status_code=404, detail="Barraca não encontrada")
    total = round(sum(i.price * i.qty for i in body.items), 2)
    doc = {
        "id": new_id("order"), "token": uuid.uuid4().hex, "store_id": body.store_id,
        "store_name": store["name"], "store_whatsapp": store["whatsapp"],
        "customer_user_id": user["user_id"],
        "customer_name": body.customer_name or user.get("name", ""),
        "items": [i.dict() for i in body.items], "total": total, "notes": body.notes,
        "status": "novo", "editable": True, "deleted": False, "created_at": now_iso(),
    }
    await db.orders.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/orders/{order_id}")
async def get_order(order_id: str, token: Optional[str] = Query(None),
                    authorization: Optional[str] = Header(None)):
    o = await db.orders.find_one({"id": order_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if token and token == o["token"]:
        return o
    # otherwise require auth + ownership
    if authorization and authorization.startswith("Bearer "):
        sess = await db.user_sessions.find_one({"session_token": authorization.split(" ", 1)[1].strip()}, {"_id": 0})
        if sess:
            u = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
            if u and (u["role"] == "admin" or u["user_id"] == o["customer_user_id"]
                      or (u["role"] == "lojista" and u.get("store_id") == o["store_id"])):
                return o
    raise HTTPException(status_code=403, detail="Acesso negado")


@api.get("/my/orders")
async def my_orders(user=Depends(get_current_user)):
    orders = await db.orders.find({"customer_user_id": user["user_id"], "deleted": {"$ne": True}},
                                  {"_id": 0}).sort("created_at", -1).to_list(500)
    return orders


@api.get("/vendor/orders")
async def vendor_orders(user=Depends(require_role("lojista", "admin"))):
    q = {"deleted": {"$ne": True}}
    if user["role"] == "lojista":
        if not user.get("store_id"):
            return []
        q["store_id"] = user["store_id"]
    orders = await db.orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return orders


@api.put("/orders/{order_id}")
async def update_order_items(order_id: str, body: OrderItemsUpdate, user=Depends(get_current_user)):
    o = await db.orders.find_one({"id": order_id, "deleted": {"$ne": True}})
    if not o:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    is_vendor = user["role"] == "lojista" and user.get("store_id") == o["store_id"]
    is_admin = user["role"] == "admin"
    is_owner = user["user_id"] == o["customer_user_id"]
    if not (is_admin or is_vendor or (is_owner and o.get("editable"))):
        raise HTTPException(status_code=403, detail="Edição não permitida")
    total = round(sum(i.price * i.qty for i in body.items), 2)
    await db.orders.update_one({"id": order_id},
                               {"$set": {"items": [i.dict() for i in body.items], "total": total}})
    return await db.orders.find_one({"id": order_id}, {"_id": 0})


@api.put("/orders/{order_id}/status")
async def update_order_status(order_id: str, body: StatusUpdate, user=Depends(require_role("lojista", "admin"))):
    o = await db.orders.find_one({"id": order_id, "deleted": {"$ne": True}})
    if not o:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if user["role"] == "lojista" and user.get("store_id") != o["store_id"]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    editable = body.status in ("novo", "editando")
    await db.orders.update_one({"id": order_id}, {"$set": {"status": body.status, "editable": editable}})
    return await db.orders.find_one({"id": order_id}, {"_id": 0})


@api.get("/orders/{order_id}/pdf")
async def order_pdf(order_id: str, token: str = Query(...)):
    o = await db.orders.find_one({"id": order_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not o or o["token"] != token:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    pdf = await run_in_threadpool(build_pdf, o)
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="pedido-{order_id}.pdf"'})


def build_pdf(o):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    brand = colors.HexColor("#4A7C59")
    title = ParagraphStyle("t", parent=styles["Title"], textColor=brand, fontSize=22)
    h = ParagraphStyle("h", parent=styles["Normal"], fontSize=11, textColor=colors.HexColor("#4A4C48"))
    els = [Paragraph("Feira Online", title),
           Paragraph(f"<b>Barraca:</b> {o['store_name']}", h),
           Paragraph(f"<b>Cliente:</b> {o.get('customer_name','')}", h),
           Paragraph(f"<b>Pedido:</b> {o['id']}", h),
           Paragraph(f"<b>Status:</b> {o['status']}", h),
           Spacer(1, 10 * mm)]
    data = [["Produto", "Qtd", "Preço", "Subtotal"]]
    for it in o["items"]:
        data.append([it["name"], str(it["qty"]), f"R$ {it['price']:.2f}",
                     f"R$ {it['price'] * it['qty']:.2f}"])
    data.append(["", "", "Total", f"R$ {o['total']:.2f}"])
    table = Table(data, colWidths=[80 * mm, 20 * mm, 35 * mm, 35 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brand),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E9F0EC")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1C9BE")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#FDFBF7")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    els.append(table)
    if o.get("notes"):
        els.append(Spacer(1, 8 * mm))
        els.append(Paragraph(f"<b>Observações:</b> {o['notes']}", h))
    doc.build(els)
    return buf.getvalue()


# ------------------------------------------------------------------ Admin
@api.get("/admin/metrics")
async def admin_metrics(user=Depends(require_role("admin"))):
    stores = await db.stores.count_documents({"deleted": {"$ne": True}})
    products = await db.products.count_documents({"deleted": {"$ne": True}})
    orders = await db.orders.count_documents({"deleted": {"$ne": True}})
    customers = await db.users.count_documents({"role": "cliente"})
    order_docs = await db.orders.find({"deleted": {"$ne": True}}, {"_id": 0, "total": 1}).to_list(5000)
    revenue = round(sum(o.get("total", 0) for o in order_docs), 2)
    return {"stores": stores, "products": products, "orders": orders,
            "customers": customers, "revenue": revenue}


@api.get("/admin/users")
async def admin_users(user=Depends(require_role("admin"))):
    users = await db.users.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return users


@api.put("/admin/users/{user_id}/role")
async def set_role(user_id: str, body: RoleUpdate, user=Depends(require_role("admin"))):
    if body.role not in ("admin", "lojista", "cliente"):
        raise HTTPException(status_code=400, detail="Role inválida")
    updates = {"role": body.role, "store_id": body.store_id if body.role == "lojista" else None}
    await db.users.update_one({"user_id": user_id}, {"$set": updates})
    return await db.users.find_one({"user_id": user_id}, {"_id": 0})


@api.get("/")
async def root():
    return {"message": "Feira Online API"}


app.include_router(api)

app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.users.create_index("user_id", unique=True)
        await db.user_sessions.create_index("session_token", unique=True)
        await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)
        await db.stores.create_index("id", unique=True)
        await db.products.create_index("store_id")
        await db.orders.create_index("id", unique=True)
    except Exception as e:
        logger.warning(f"index error: {e}")
    try:
        await run_in_threadpool(init_storage)
        logger.info("storage initialized")
    except Exception as e:
        logger.warning(f"storage init failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    client.close()
