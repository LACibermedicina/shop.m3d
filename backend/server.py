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
ALLOW_DEV_LOGIN = os.environ.get("ALLOW_DEV_LOGIN", "").strip().lower() == "true"
ADMIN_EMAILS = [e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()]

# WhatsApp Cloud API (optional — dormant until configured)
WA_ACCESS_TOKEN = os.environ.get("WA_ACCESS_TOKEN", "").strip()
WA_PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID", "").strip()
WA_VERIFY_TOKEN = os.environ.get("WA_VERIFY_TOKEN", "").strip()
META_APP_SECRET = os.environ.get("META_APP_SECRET", "").strip()
WA_API_VERSION = os.environ.get("WA_API_VERSION", "v25.0").strip()
WA_CONFIGURED = bool(WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID)
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip()
ONLINE_WINDOW = 60  # segundos sem heartbeat até a loja ser considerada offline
ROOT_WHATSAPP = os.environ.get("ROOT_WHATSAPP", "").strip()
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMERGENT_EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Lojas da Fronteira")

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
    admin_whatsapp: Optional[str] = ""
    owner_user_id: Optional[str] = None
    featured: Optional[bool] = False


class SendWhatsApp(BaseModel):
    order_id: str


class ProductIn(BaseModel):
    store_id: str
    name: str
    description: Optional[str] = ""
    price: float
    image: Optional[str] = ""
    category: Optional[str] = "Outros"


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    image: Optional[str] = None
    category: Optional[str] = None


class ReviewIn(BaseModel):
    rating: int
    comment: Optional[str] = ""


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
    coupon_code: Optional[str] = ""
    customer_whatsapp: Optional[str] = ""


class StoreOpen(BaseModel):
    is_open: bool


class CouponIn(BaseModel):
    store_id: str
    code: str
    type: str = "percent"  # "percent" | "fixed"
    value: float


class CouponApply(BaseModel):
    store_id: str
    code: str
    subtotal: float


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
async def dev_login(body: DevLogin):
    # Server-only gate. Disabled in production unless ALLOW_DEV_LOGIN=true.
    if not ALLOW_DEV_LOGIN:
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


@api.delete("/auth/me")
async def delete_account(user=Depends(get_current_user)):
    uid = user["user_id"]
    await db.user_sessions.delete_many({"user_id": uid})
    await db.favorites.delete_many({"user_id": uid})
    await db.reviews.delete_many({"user_id": uid})
    await db.users.delete_one({"user_id": uid})
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
def store_online(s: dict) -> bool:
    if not s.get("is_open"):
        return False
    ls = s.get("last_seen")
    if not ls:
        return False
    try:
        t = datetime.fromisoformat(ls)
    except Exception:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() < ONLINE_WINDOW


async def rating_summary(store_id: str):
    revs = await db.reviews.find({"store_id": store_id}, {"_id": 0, "rating": 1}).to_list(2000)
    if not revs:
        return {"avg_rating": 0.0, "review_count": 0}
    avg = round(sum(r["rating"] for r in revs) / len(revs), 1)
    return {"avg_rating": avg, "review_count": len(revs)}


@api.get("/stores")
async def list_stores():
    stores = await db.stores.find({"deleted": {"$ne": True}, "active": {"$ne": False}}, {"_id": 0}).to_list(500)
    for s in stores:
        s["product_count"] = await db.products.count_documents({"store_id": s["id"], "deleted": {"$ne": True}})
        s["online"] = store_online(s)
        s.update(await rating_summary(s["id"]))
    return stores


@api.get("/stores/{store_id}")
async def get_store(store_id: str):
    s = await db.stores.find_one({"id": store_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    s["online"] = store_online(s)
    s.update(await rating_summary(store_id))
    return s


@api.post("/stores")
async def create_store(body: StoreIn, user=Depends(require_role("admin"))):
    doc = body.dict()
    doc.update({"id": new_id("store"), "active": True, "deleted": False,
                "is_open": False, "last_seen": None, "created_at": now_iso()})
    await db.stores.insert_one(doc)
    if doc.get("owner_user_id"):
        await db.users.update_one({"user_id": doc["owner_user_id"]},
                                  {"$set": {"role": "lojista", "store_id": doc["id"]}})
    return await db.stores.find_one({"id": doc["id"]}, {"_id": 0})


@api.put("/stores/{store_id}")
async def update_store(store_id: str, body: StoreIn, user=Depends(require_role("admin", "lojista"))):
    s = await db.stores.find_one({"id": store_id, "deleted": {"$ne": True}})
    if not s:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
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
async def store_products(store_id: str, sort: str = Query("recent"), category: str = Query("")):
    field, direction = SORT_MAP.get(sort, ("created_at", -1))
    q = {"store_id": store_id, "deleted": {"$ne": True}}
    if category and category != "Todos":
        q["category"] = category
    products = await db.products.find(q, {"_id": 0}).sort(field, direction).to_list(1000)
    return products


@api.get("/stores/{store_id}/reviews")
async def list_reviews(store_id: str):
    revs = await db.reviews.find({"store_id": store_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    summary = await rating_summary(store_id)
    return {"reviews": revs, **summary}


@api.post("/stores/{store_id}/reviews")
async def add_review(store_id: str, body: ReviewIn, user=Depends(get_current_user)):
    if body.rating < 1 or body.rating > 5:
        raise HTTPException(status_code=400, detail="Nota deve ser de 1 a 5")
    doc = {"id": new_id("rev"), "store_id": store_id, "user_id": user["user_id"],
           "user_name": user.get("name", ""), "rating": body.rating,
           "comment": (body.comment or "").strip(), "created_at": now_iso()}
    await db.reviews.update_one({"store_id": store_id, "user_id": user["user_id"]},
                               {"$set": doc}, upsert=True)
    return doc


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
        "Você extrai dados de produtos de mensagens de WhatsApp de lojistas da Tríplice Fronteira "
        "(comércio varejista de Foz do Iguaçu / Ciudad del Este). "
        "Responda SOMENTE com JSON válido no formato: "
        '{\"name\": string, \"price\": number, \"description\": string, \"category\": string}. '
        "price em reais (número, sem R$). Se não houver preço, use 0. "
        "category deve ser UMA de: Eletrônicos, Informática, Celulares, Perfumaria, Moda, "
        "Calçados, Casa & Decoração, Brinquedos, Bebidas, Alimentos, Acessórios, Outros. "
        "Escolha a categoria de varejo que melhor descreve o produto. "
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
            "description": str(data.get("description", "")).strip(),
            "category": str(data.get("category", "Outros")).strip() or "Outros"}


# ------------------------------------------------------------------ Orders
def order_public(o):
    o.pop("_id", None)
    return o


@api.post("/orders")
async def create_order(body: OrderIn, user=Depends(get_current_user)):
    store = await db.stores.find_one({"id": body.store_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    subtotal = round(sum(i.price * i.qty for i in body.items), 2)
    discount = 0.0
    coupon_code = ""
    if body.coupon_code:
        coupon = await db.coupons.find_one(
            {"store_id": body.store_id, "code": body.coupon_code.strip().upper(),
             "active": {"$ne": False}, "deleted": {"$ne": True}}, {"_id": 0})
        if coupon:
            discount = calc_discount(coupon, subtotal)
            coupon_code = coupon["code"]
    total = round(max(subtotal - discount, 0), 2)
    doc = {
        "id": new_id("order"), "token": uuid.uuid4().hex, "store_id": body.store_id,
        "store_name": store["name"], "store_whatsapp": store["whatsapp"],
        "customer_user_id": user["user_id"],
        "customer_name": body.customer_name or user.get("name", ""),
        "items": [i.dict() for i in body.items], "subtotal": subtotal,
        "discount": discount, "coupon_code": coupon_code, "total": total, "notes": body.notes,
        "customer_whatsapp": (body.customer_whatsapp or "").strip(),
        "status": "novo", "editable": True, "deleted": False, "created_at": now_iso(),
    }
    await db.orders.insert_one(doc)
    doc.pop("_id", None)
    if body.customer_whatsapp:
        await db.users.update_one({"user_id": user["user_id"]},
                                  {"$set": {"whatsapp": body.customer_whatsapp.strip()}})
    try:
        await notify_order(doc, "created")
    except Exception as e:
        logger.warning(f"notify_order created failed: {e}")
    doc["confirmation"] = "Pedido criado! Avisos enviados ao lojista, administrador e a você."
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
    updated = await db.orders.find_one({"id": order_id}, {"_id": 0})
    try:
        await notify_order(updated, "status")
    except Exception as e:
        logger.warning(f"notify_order status failed: {e}")
    return updated


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
    els = [Paragraph("Lojas da Fronteira", title),
           Paragraph(f"<b>Loja:</b> {o['store_name']}", h),
           Paragraph(f"<b>Cliente:</b> {o.get('customer_name','')}", h),
           Paragraph(f"<b>Pedido:</b> {o['id']}", h),
           Paragraph(f"<b>Status:</b> {o['status']}", h),
           Spacer(1, 10 * mm)]
    data = [["Produto", "Qtd", "Preço", "Subtotal"]]
    for it in o["items"]:
        data.append([it["name"], str(it["qty"]), f"R$ {it['price']:.2f}",
                     f"R$ {it['price'] * it['qty']:.2f}"])
    if o.get("discount"):
        data.append(["", "", "Subtotal", f"R$ {o.get('subtotal', o['total']):.2f}"])
        cc = f" ({o.get('coupon_code')})" if o.get("coupon_code") else ""
        data.append(["", "", f"Desconto{cc}", f"- R$ {o['discount']:.2f}"])
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


@api.get("/home")
async def home():
    stores = await db.stores.find(
        {"deleted": {"$ne": True}, "active": {"$ne": False}}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    for s in stores:
        s["product_count"] = await db.products.count_documents(
            {"store_id": s["id"], "deleted": {"$ne": True}}
        )
        s["online"] = store_online(s)
        s.update(await rating_summary(s["id"]))
    featured = [s for s in stores if s.get("featured")]
    if not featured:
        featured = stores[:6]
    store_ids = [s["id"] for s in stores]
    smap = {s["id"]: s["name"] for s in stores}
    prods = await db.products.find(
        {"store_id": {"$in": store_ids}, "deleted": {"$ne": True}}, {"_id": 0}
    ).sort("created_at", -1).to_list(12)
    for p in prods:
        p["store_name"] = smap.get(p["store_id"], "")
    return {"featured_stores": featured, "new_products": prods}


@api.get("/search")
async def search(q: str = Query("")):
    q = q.strip()
    if not q:
        return {"stores": [], "products": []}
    rx = {"$regex": re.escape(q), "$options": "i"}
    stores = await db.stores.find(
        {"deleted": {"$ne": True}, "active": {"$ne": False}, "name": rx}, {"_id": 0}
    ).to_list(50)
    for s in stores:
        s["product_count"] = await db.products.count_documents(
            {"store_id": s["id"], "deleted": {"$ne": True}}
        )
        s["online"] = store_online(s)
        s.update(await rating_summary(s["id"]))
    active_ids = await db.stores.distinct("id", {"deleted": {"$ne": True}, "active": {"$ne": False}})
    all_stores = await db.stores.find({"id": {"$in": active_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
    smap = {s["id"]: s["name"] for s in all_stores}
    products = await db.products.find(
        {"deleted": {"$ne": True}, "store_id": {"$in": active_ids},
         "$or": [{"name": rx}, {"description": rx}]}, {"_id": 0}
    ).to_list(50)
    for p in products:
        p["store_name"] = smap.get(p["store_id"], "")
    return {"stores": stores, "products": products}


# ------------------------------------------------------------------ WhatsApp Cloud API
@api.get("/whatsapp/status")
async def whatsapp_status():
    return {"configured": WA_CONFIGURED}


async def wa_send(payload: dict):
    url = f"https://graph.facebook.com/{WA_API_VERSION}/{WA_PHONE_NUMBER_ID}/messages"
    async with httpx.AsyncClient(timeout=20) as hc:
        r = await hc.post(url, headers={"Authorization": f"Bearer {WA_ACCESS_TOKEN}"},
                          json={"messaging_product": "whatsapp", "recipient_type": "individual", **payload})
    if r.status_code >= 400:
        logger.error(f"WA send error {r.status_code}: {r.text}")
        raise HTTPException(status_code=502, detail="Falha ao enviar pelo WhatsApp")
    return r.json()


@api.post("/orders/send-whatsapp")
async def send_order_whatsapp(body: SendWhatsApp, user=Depends(get_current_user)):
    if not WA_CONFIGURED:
        raise HTTPException(status_code=400, detail="WhatsApp oficial não configurado")
    o = await db.orders.find_one({"id": body.order_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    num = (o["store_whatsapp"] or "").replace(" ", "").replace("+", "")
    lines = "\n".join([f"• {i['qty']}x {i['name']} — R$ {i['price'] * i['qty']:.2f}" for i in o["items"]])
    text = (f"*Novo pedido — Lojas da Fronteira*\nCliente: {o.get('customer_name','')}\n\n{lines}\n\n"
            f"*Total: R$ {o['total']:.2f}*")
    result = await wa_send({"to": num, "type": "text", "text": {"body": text}})
    base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else ""
    if base:
        pdf_link = f"{base}/api/orders/{o['id']}/pdf?token={o['token']}"
        await wa_send({"to": num, "type": "document",
                       "document": {"link": pdf_link, "filename": f"pedido-{o['id']}.pdf",
                                    "caption": "Lista do pedido em PDF"}})
    await db.orders.update_one({"id": o["id"]}, {"$set": {"whatsapp_sent": True}})
    return {"ok": True, "result": result}


@api.get("/webhooks/whatsapp")
async def wa_verify(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == WA_VERIFY_TOKEN and WA_VERIFY_TOKEN:
        challenge = params.get("hub.challenge", "")
        return int(challenge) if challenge.isdigit() else challenge
    raise HTTPException(status_code=403, detail="verification failed")


def _valid_wa_signature(raw: bytes, header: Optional[str]) -> bool:
    if not META_APP_SECRET:
        return True  # signature check disabled if secret not set
    if not header or not header.startswith("sha256="):
        return False
    import hmac, hashlib
    expected = hmac.new(META_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:], expected)


@api.post("/webhooks/whatsapp")
async def wa_webhook(request: Request):
    raw = await request.body()
    if not _valid_wa_signature(raw, request.headers.get("x-hub-signature-256")):
        raise HTTPException(status_code=403, detail="bad signature")
    payload = json.loads(raw or b"{}")
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                try:
                    await _process_inbound(msg)
                except Exception as e:
                    logger.error(f"inbound process error: {e}")
    return {"ok": True}


async def _process_inbound(msg: dict):
    mid = msg.get("id")
    if not mid or await db.whatsapp_events.find_one({"message_id": mid}):
        return
    await db.whatsapp_events.insert_one({"message_id": mid, "created_at": now_iso(), "from": msg.get("from")})
    sender = (msg.get("from") or "").replace("+", "")
    # match a store by whatsapp number (last 10-11 digits)
    stores = await db.stores.find({"deleted": {"$ne": True}}, {"_id": 0}).to_list(1000)
    store = None
    for s in stores:
        digits = (s.get("whatsapp") or "").replace(" ", "").replace("+", "")
        if digits and (digits.endswith(sender[-10:]) or sender.endswith(digits[-10:])):
            store = s
            break
    if not store:
        logger.warning(f"WA inbound from unknown store number {sender}")
        return
    text = (msg.get("text") or {}).get("body", "")
    image_path = ""
    image = msg.get("image")
    if image and image.get("id"):
        try:
            image_path = await _download_wa_media(image["id"])
        except Exception as e:
            logger.warning(f"WA media download failed: {e}")
        text = text or image.get("caption", "")
    parsed = await extract_product(text, image_path)
    doc = {"id": new_id("prod"), "store_id": store["id"], "name": parsed["name"] or "Produto",
           "description": parsed["description"], "price": parsed["price"], "image": image_path,
           "category": parsed.get("category", "Outros"),
           "deleted": False, "created_at": now_iso(), "source": "whatsapp"}
    await db.products.insert_one(doc)
    logger.info(f"WA product created for store {store['id']}: {doc['name']}")


async def _download_wa_media(media_id: str) -> str:
    async with httpx.AsyncClient(timeout=30) as hc:
        meta = await hc.get(f"https://graph.facebook.com/{WA_API_VERSION}/{media_id}",
                           headers={"Authorization": f"Bearer {WA_ACCESS_TOKEN}"})
        meta.raise_for_status()
        info = meta.json()
        blob = await hc.get(info["url"], headers={"Authorization": f"Bearer {WA_ACCESS_TOKEN}"})
        blob.raise_for_status()
    ct = info.get("mime_type", "image/jpeg")
    ext = "png" if "png" in ct else "jpg"
    path = f"{APP_NAME}/whatsapp/{uuid.uuid4().hex}.{ext}"
    await run_in_threadpool(put_object, path, blob.content, ct)
    return path


# ------------------------------------------------------------------ Favorites
@api.get("/my/favorite-ids")
async def my_favorite_ids(user=Depends(get_current_user)):
    favs = await db.favorites.find({"user_id": user["user_id"]}, {"_id": 0, "store_id": 1}).to_list(1000)
    return [f["store_id"] for f in favs]


@api.get("/my/favorites")
async def my_favorites(user=Depends(get_current_user)):
    favs = await db.favorites.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(1000)
    ids = [f["store_id"] for f in favs]
    stores = await db.stores.find({"id": {"$in": ids}, "deleted": {"$ne": True}}, {"_id": 0}).to_list(1000)
    for s in stores:
        s["product_count"] = await db.products.count_documents({"store_id": s["id"], "deleted": {"$ne": True}})
        s.update(await rating_summary(s["id"]))
    return stores


@api.post("/favorites/{store_id}")
async def add_favorite(store_id: str, user=Depends(get_current_user)):
    await db.favorites.update_one(
        {"user_id": user["user_id"], "store_id": store_id},
        {"$set": {"user_id": user["user_id"], "store_id": store_id, "created_at": now_iso()}},
        upsert=True)
    return {"ok": True}


@api.delete("/favorites/{store_id}")
async def remove_favorite(store_id: str, user=Depends(get_current_user)):
    await db.favorites.delete_one({"user_id": user["user_id"], "store_id": store_id})
    return {"ok": True}


# ------------------------------------------------------------------ Vendor report
@api.get("/vendor/report")
async def vendor_report(user=Depends(require_role("lojista", "admin"))):
    q = {"deleted": {"$ne": True}, "status": {"$ne": "cancelado"}}
    if user["role"] == "lojista":
        if not user.get("store_id"):
            return {"daily": [], "weekly": [], "total": 0, "orders": 0}
        q["store_id"] = user["store_id"]
    orders = await db.orders.find(q, {"_id": 0, "total": 1, "created_at": 1}).to_list(10000)

    def as_date(o):
        try:
            return datetime.fromisoformat(o["created_at"]).date()
        except Exception:
            return None

    now = datetime.now(timezone.utc)
    daily = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        total = sum(o["total"] for o in orders if as_date(o) == day)
        daily.append({"label": day.strftime("%d/%m"), "value": round(total, 2)})
    weekly = []
    for w in range(3, -1, -1):
        start = (now - timedelta(days=now.weekday() + 7 * w)).date()
        end = start + timedelta(days=6)
        total = sum(o["total"] for o in orders if as_date(o) and start <= as_date(o) <= end)
        weekly.append({"label": start.strftime("%d/%m"), "value": round(total, 2)})
    total_rev = round(sum(o["total"] for o in orders), 2)
    return {"daily": daily, "weekly": weekly, "total": total_rev, "orders": len(orders)}


# ------------------------------------------------------------------ Store presence (aberta/fechada)
async def _vendor_store(user):
    if user["role"] == "admin":
        return None
    if not user.get("store_id"):
        raise HTTPException(status_code=400, detail="Nenhuma loja vinculada")
    return user["store_id"]


@api.put("/vendor/store/open")
async def set_store_open(body: StoreOpen, user=Depends(require_role("lojista"))):
    sid = user.get("store_id")
    if not sid:
        raise HTTPException(status_code=400, detail="Nenhuma loja vinculada")
    updates = {"is_open": body.is_open}
    if body.is_open:
        updates["last_seen"] = now_iso()
    await db.stores.update_one({"id": sid}, {"$set": updates})
    s = await db.stores.find_one({"id": sid}, {"_id": 0})
    s["online"] = store_online(s)
    return s


@api.post("/vendor/heartbeat")
async def heartbeat(user=Depends(require_role("lojista"))):
    sid = user.get("store_id")
    if not sid:
        return {"online": False}
    await db.stores.update_one({"id": sid}, {"$set": {"last_seen": now_iso()}})
    s = await db.stores.find_one({"id": sid}, {"_id": 0})
    return {"online": store_online(s), "is_open": bool(s.get("is_open"))}


# ------------------------------------------------------------------ Coupons
def calc_discount(coupon: dict, subtotal: float) -> float:
    if coupon.get("type") == "fixed":
        return round(min(float(coupon.get("value", 0)), subtotal), 2)
    return round(subtotal * float(coupon.get("value", 0)) / 100.0, 2)


@api.post("/coupons")
async def create_coupon(body: CouponIn, user=Depends(require_role("lojista", "admin"))):
    if user["role"] == "lojista" and user.get("store_id") != body.store_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    if body.type not in ("percent", "fixed"):
        raise HTTPException(status_code=400, detail="Tipo inválido")
    if body.value <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero")
    code = body.code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Informe o código")
    doc = {"id": new_id("coup"), "store_id": body.store_id, "code": code,
           "type": body.type, "value": round(body.value, 2), "active": True,
           "deleted": False, "created_at": now_iso()}
    await db.coupons.update_one(
        {"store_id": body.store_id, "code": code},
        {"$set": doc}, upsert=True)
    return await db.coupons.find_one({"store_id": body.store_id, "code": code}, {"_id": 0})


@api.get("/vendor/coupons")
async def vendor_coupons(user=Depends(require_role("lojista", "admin"))):
    q = {"deleted": {"$ne": True}}
    if user["role"] == "lojista":
        if not user.get("store_id"):
            return []
        q["store_id"] = user["store_id"]
    return await db.coupons.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.delete("/coupons/{coupon_id}")
async def delete_coupon(coupon_id: str, user=Depends(require_role("lojista", "admin"))):
    c = await db.coupons.find_one({"id": coupon_id})
    if not c:
        raise HTTPException(status_code=404, detail="Cupom não encontrado")
    if user["role"] == "lojista" and user.get("store_id") != c["store_id"]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    await db.coupons.update_one({"id": coupon_id}, {"$set": {"deleted": True}})
    return {"ok": True}


@api.post("/coupons/apply")
async def apply_coupon(body: CouponApply, user=Depends(get_current_user)):
    coupon = await db.coupons.find_one(
        {"store_id": body.store_id, "code": body.code.strip().upper(),
         "active": {"$ne": False}, "deleted": {"$ne": True}}, {"_id": 0})
    if not coupon:
        return {"valid": False, "detail": "Cupom inválido"}
    discount = calc_discount(coupon, body.subtotal)
    return {"valid": True, "code": coupon["code"], "type": coupon["type"],
            "value": coupon["value"], "discount": discount,
            "total": round(max(body.subtotal - discount, 0), 2)}


# ------------------------------------------------------------------ Notifications (WhatsApp sim + Email real)
import ipaddress
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls = set(), []
    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms in email")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError("Email links must be absolute https")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError("Unsafe URL in email")


async def send_email(*, to: str, subject: str, html: str) -> Optional[str]:
    if not EMERGENT_EMAIL_KEY:
        return None
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    async with httpx.AsyncClient(timeout=30) as hc:
        resp = await hc.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                             headers={"X-Email-Key": EMERGENT_EMAIL_KEY}, json=payload)
    resp.raise_for_status()
    return resp.json().get("id")


def _order_lines(o):
    return "\n".join([f"- {i['qty']}x {i['name']} (R$ {i['price'] * i['qty']:.2f})" for i in o["items"]])


def _order_link(o):
    base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else ""
    return f"{base}/api/orders/{o['id']}/pdf?token={o['token']}" if base else ""


async def _record(order_id, target, channel, to, body, status, subject=""):
    await db.notifications.insert_one({
        "id": new_id("ntf"), "order_id": order_id, "target": target, "channel": channel,
        "to": to, "subject": subject, "body": body, "status": status, "created_at": now_iso(),
    })


async def _wa_or_sim(order_id, target, to, body):
    if not to:
        return
    if WA_CONFIGURED:
        try:
            await wa_send({"to": to.replace(" ", "").replace("+", ""), "type": "text", "text": {"body": body}})
            await _record(order_id, target, "whatsapp", to, body, "sent")
            return
        except Exception as e:
            logger.warning(f"WA notify failed: {e}")
    await _record(order_id, target, "whatsapp", to, body, "simulated")


async def notify_order(o, kind):
    """kind: 'created' | 'status'. Notifica lojista + admin (WhatsApp) e cliente (WhatsApp ou e-mail)."""
    store = await db.stores.find_one({"id": o["store_id"]}, {"_id": 0}) or {}
    link = _order_link(o)
    link_txt = f"\nLink do pedido (PDF): {link}" if link else ""
    if kind == "created":
        head = f"🆕 Novo pedido — {o['store_name']}"
    else:
        head = f"🔔 Pedido atualizado ({o.get('status','')}) — {o['store_name']}"
    base_body = (f"{head}\nCliente: {o.get('customer_name','')}\n{_order_lines(o)}\n"
                 f"Total: R$ {o['total']:.2f}{link_txt}")
    # Lojista
    await _wa_or_sim(o["id"], "lojista", store.get("whatsapp", ""), base_body)
    # Administrador responsável (whatsapp da loja) ou root
    admin_to = store.get("admin_whatsapp") or ROOT_WHATSAPP
    await _wa_or_sim(o["id"], "admin", admin_to, base_body)
    # Cliente: WhatsApp se houver, senão e-mail
    cust_wa = o.get("customer_whatsapp") or ""
    if kind == "created":
        cust_body = (f"✅ Pedido confirmado em {o['store_name']}!\n{_order_lines(o)}\n"
                     f"Total: R$ {o['total']:.2f}{link_txt}\nObrigado pela compra!")
        subj = "Seu pedido foi confirmado — Lojas da Fronteira"
    else:
        cust_body = (f"🔔 Seu pedido em {o['store_name']} agora está: {o.get('status','')}.{link_txt}")
        subj = f"Atualização do seu pedido ({o.get('status','')}) — Lojas da Fronteira"
    if cust_wa:
        await _wa_or_sim(o["id"], "cliente", cust_wa, cust_body)
    else:
        email = None
        u = await db.users.find_one({"user_id": o["customer_user_id"]}, {"_id": 0, "email": 1})
        email = (u or {}).get("email")
        if email:
            link_html = (f'<p><a href="{escape(link)}">Ver pedido (PDF)</a></p>' if link else "")
            html = (f'<table role="presentation" width="100%"><tr><td style="padding:24px;'
                    f'font-family:Arial,sans-serif;color:#1A1C19">'
                    f'<h2 style="color:#4A7C59;margin:0 0 12px">{escape(subj)}</h2>'
                    f'<p>Olá {escape(o.get("customer_name","") or "cliente")},</p>'
                    f'<p>{escape(cust_body)}</p>{link_html}'
                    f'<p style="font-size:12px;color:#888">Enviado por {escape(EMAIL_FROM_NAME)}. '
                    f'Nunca pedimos senha ou dados de cartão por e-mail.</p></td></tr></table>')
            try:
                await send_email(to=email, subject=subj, html=html)
                await _record(o["id"], "cliente", "email", email, cust_body, "sent", subj)
            except Exception as e:
                logger.warning(f"Email notify failed: {e}")
                await _record(o["id"], "cliente", "email", email, cust_body, "failed", subj)


@api.get("/orders/{order_id}/notifications")
async def order_notifications(order_id: str, token: Optional[str] = Query(None),
                              authorization: Optional[str] = Header(None)):
    o = await db.orders.find_one({"id": order_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    allowed = bool(token and token == o["token"])
    if not allowed and authorization and authorization.startswith("Bearer "):
        sess = await db.user_sessions.find_one({"session_token": authorization.split(" ", 1)[1].strip()}, {"_id": 0})
        if sess:
            u = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
            allowed = u and (u["role"] == "admin" or u["user_id"] == o["customer_user_id"]
                             or (u["role"] == "lojista" and u.get("store_id") == o["store_id"]))
    if not allowed:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return await db.notifications.find({"order_id": order_id}, {"_id": 0}).sort("created_at", 1).to_list(200)


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
        await db.reviews.create_index([("store_id", 1), ("user_id", 1)], unique=True)
        await db.favorites.create_index([("user_id", 1), ("store_id", 1)], unique=True)
        await db.coupons.create_index([("store_id", 1), ("code", 1)], unique=True)
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
