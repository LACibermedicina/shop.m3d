import os
import re
import io
import json
import uuid
import base64
import random
import asyncio
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
from passlib.context import CryptContext
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
MASTER_EMAIL = os.environ.get("MASTER_EMAIL", "lucasmedicina86@gmail.com").strip().lower()

# WhatsApp Cloud API (optional — dormant until configured)
WA_ACCESS_TOKEN = os.environ.get("WA_ACCESS_TOKEN", "").strip()
WA_PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID", "").strip()
WA_VERIFY_TOKEN = os.environ.get("WA_VERIFY_TOKEN", "").strip()
META_APP_SECRET = os.environ.get("META_APP_SECRET", "").strip()
WA_API_VERSION = os.environ.get("WA_API_VERSION", "v25.0").strip()
WA_CONFIGURED = bool(WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID)
# Utility templates (used for business-initiated notifications OUTSIDE the 24h window).
# Leave empty until the templates are created & APPROVED on the WABA — when empty the
# hybrid delivery skips the template step and falls back to a manual wa.me link.
WA_TEMPLATE_LANG = os.environ.get("WA_TEMPLATE_LANG", "pt_BR").strip()
WA_TEMPLATE_ORDER = os.environ.get("WA_TEMPLATE_ORDER", "").strip()
WA_TEMPLATE_STATUS = os.environ.get("WA_TEMPLATE_STATUS", "").strip()
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


# ------------------------------------------------------------------ Password helpers
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return pwd_ctx.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return pwd_ctx.verify(raw, hashed or "")
    except Exception:
        return False


# ------------------------------------------------------------------ Models
class DevLogin(BaseModel):
    email: str
    name: Optional[str] = None
    role: str = "cliente"


class SessionReq(BaseModel):
    session_id: str


class LoginReq(BaseModel):
    username: str
    password: str


class StoreIn(BaseModel):
    name: str
    description: Optional[str] = ""
    logo: Optional[str] = ""
    whatsapp: str
    admin_whatsapp: Optional[str] = ""
    owner_user_id: Optional[str] = None
    admin_id: Optional[str] = None
    group_ids: Optional[List[str]] = None
    featured: Optional[bool] = False


class GroupIn(BaseModel):
    name: str
    description: Optional[str] = ""
    icon: Optional[str] = "pricetags"
    color: Optional[str] = "#4A7C59"


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
    available: bool = True


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


class InviteIn(BaseModel):
    store_id: str
    client_email: Optional[str] = ""


class CatalogItemIn(BaseModel):
    store_id: str
    product_id: str
    qty: int = 1
    note: Optional[str] = ""


class CatalogItemUpdate(BaseModel):
    qty: Optional[int] = None
    note: Optional[str] = None


class CartSend(BaseModel):
    item_ids: Optional[List[str]] = None  # None => all items in personal catalog
    notes: Optional[str] = ""
    customer_name: Optional[str] = ""
    customer_whatsapp: Optional[str] = ""


class TranslateReq(BaseModel):
    texts: List[str]
    target: str = "pt"
    source: Optional[str] = "pt"


class RoleUpdate(BaseModel):
    role: str
    store_id: Optional[str] = None
    admin_id: Optional[str] = None


class MasterUserIn(BaseModel):
    email: str
    name: Optional[str] = ""
    role: str = "cliente"
    admin_id: Optional[str] = None


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
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user


def require_role(*roles):
    async def checker(user=Depends(get_current_user)):
        if user["role"] == "master":
            return user
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Acesso negado")
        return user
    return checker


def is_master(user) -> bool:
    return user.get("role") == "master"


async def admin_store_ids(user) -> List[str]:
    """Store ids an admin manages (stores whose admin_id == admin's user_id)."""
    ids = await db.stores.distinct("id", {"admin_id": user["user_id"], "deleted": {"$ne": True}})
    return list(ids)


async def optional_user(authorization: Optional[str] = Header(None)):
    """Returns the user dict if a valid Bearer token is present, else None (no error)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        return None
    exp = sess.get("expires_at")
    if exp:
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return None
    return await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0, "password_hash": 0})


async def client_store_ids(user) -> List[str]:
    """Stores a client can access = stores that invited them (by user id or e-mail), not revoked."""
    if not user:
        return []
    email_l = (user.get("email") or "").lower()
    q = {"status": {"$ne": "revoked"},
         "$or": [{"client_user_id": user["user_id"]}, {"client_email": email_l}]}
    ids = await db.invites.distinct("store_id", q)
    return list(ids)


async def scoped_store_ids_for_viewer(user) -> Optional[List[str]]:
    """None means 'no restriction' (public/admin/vendor/master). List means restrict to these ids."""
    if not user or user.get("role") in ("admin", "master"):
        return None
    if user.get("role") == "lojista":
        return [user["store_id"]] if user.get("store_id") else []
    # cliente => invite-only
    return await client_store_ids(user)


async def upsert_user(email, name, picture):
    email_l = email.lower()
    existing = await db.users.find_one({"email": email_l})
    if existing:
        # keep master role in sync even for pre-existing accounts
        if email_l == MASTER_EMAIL and existing.get("role") != "master":
            await db.users.update_one({"user_id": existing["user_id"]}, {"$set": {"role": "master"}})
            existing["role"] = "master"
        return existing["user_id"], existing["role"], existing.get("store_id")
    if email_l == MASTER_EMAIL:
        role = "master"
    elif email_l in ADMIN_EMAILS:
        role = "admin"
    else:
        role = "cliente"
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
    if body.role not in ("admin", "lojista", "cliente", "master"):
        raise HTTPException(status_code=400, detail="Role inválida")
    email_l = body.email.lower()
    # o e-mail master sempre entra como master, independentemente do que for pedido
    role = "master" if email_l == MASTER_EMAIL else body.role
    existing = await db.users.find_one({"email": email_l})
    if existing:
        uid = existing["user_id"]
        await db.users.update_one({"user_id": uid}, {"$set": {"role": role}})
    else:
        uid = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({"user_id": uid, "email": email_l, "name": body.name or email_l.split("@")[0],
                                   "picture": "", "role": role, "store_id": None, "created_at": now_iso()})
    token = await create_session(uid)
    user = await db.users.find_one({"user_id": uid}, {"_id": 0})
    return {"session_token": token, "user": user}


@api.post("/auth/login")
async def auth_login(body: LoginReq):
    """Password login. Accepts username OR e-mail in the 'username' field."""
    ident = (body.username or "").strip().lower()
    if not ident or not body.password:
        raise HTTPException(status_code=400, detail="Informe usuário e senha")
    user = await db.users.find_one({"$or": [{"username": ident}, {"email": ident}]})
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")
    token = await create_session(user["user_id"])
    user = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
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
async def list_stores(group_id: str = Query(""), viewer=Depends(optional_user)):
    q = {"deleted": {"$ne": True}, "active": {"$ne": False}}
    restrict = await scoped_store_ids_for_viewer(viewer)
    if restrict is not None:
        q["id"] = {"$in": restrict}
    if group_id:
        q["group_ids"] = group_id
    stores = await db.stores.find(q, {"_id": 0}).to_list(500)
    for s in stores:
        s["product_count"] = await db.products.count_documents({"store_id": s["id"], "deleted": {"$ne": True}})
        s["online"] = store_online(s)
        s.update(await rating_summary(s["id"]))
    return stores


@api.get("/stores/{store_id}")
async def get_store(store_id: str, viewer=Depends(optional_user)):
    s = await db.stores.find_one({"id": store_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    restrict = await scoped_store_ids_for_viewer(viewer)
    if restrict is not None and store_id not in restrict:
        raise HTTPException(status_code=403, detail="Você precisa de um convite para acessar esta loja")
    s["online"] = store_online(s)
    s.update(await rating_summary(store_id))
    return s


@api.post("/stores")
async def create_store(body: StoreIn, user=Depends(require_role("admin"))):
    doc = body.dict()
    # admin comum: a loja pertence a ele; master pode atribuir a qualquer admin
    if is_master(user):
        doc["admin_id"] = body.admin_id or None
    else:
        doc["admin_id"] = user["user_id"]
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
    if user["role"] == "admin" and s.get("admin_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Esta loja não está vinculada a você")
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if user["role"] == "lojista":
        updates.pop("owner_user_id", None)
        updates.pop("admin_id", None)
    if user["role"] == "admin":
        # admin comum não pode transferir a loja para outro admin
        updates.pop("admin_id", None)
    await db.stores.update_one({"id": store_id}, {"$set": updates})
    if updates.get("owner_user_id"):
        await db.users.update_one({"user_id": updates["owner_user_id"]},
                                  {"$set": {"role": "lojista", "store_id": store_id}})
    return await db.stores.find_one({"id": store_id}, {"_id": 0})


@api.delete("/stores/{store_id}")
async def delete_store(store_id: str, user=Depends(require_role("admin"))):
    s = await db.stores.find_one({"id": store_id, "deleted": {"$ne": True}})
    if not s:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    if user["role"] == "admin" and s.get("admin_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Esta loja não está vinculada a você")
    await db.stores.update_one({"id": store_id}, {"$set": {"deleted": True}})
    return {"ok": True}


# ------------------------------------------------------------------ Products
SORT_MAP = {"recent": ("created_at", -1), "name": ("name", 1),
            "price_asc": ("price", 1), "price_desc": ("price", -1)}


@api.get("/stores/{store_id}/products")
async def store_products(store_id: str, sort: str = Query("recent"), category: str = Query(""),
                         viewer=Depends(optional_user)):
    restrict = await scoped_store_ids_for_viewer(viewer)
    if restrict is not None and store_id not in restrict:
        raise HTTPException(status_code=403, detail="Você precisa de um convite para acessar esta loja")
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
    if user["role"] == "admin" and body.store_id not in await admin_store_ids(user):
        raise HTTPException(status_code=403, detail="Loja não vinculada a você")
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
    if user["role"] == "admin" and p["store_id"] not in await admin_store_ids(user):
        raise HTTPException(status_code=403, detail="Loja não vinculada a você")
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
    if user["role"] == "admin" and p["store_id"] not in await admin_store_ids(user):
        raise HTTPException(status_code=403, detail="Loja não vinculada a você")
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


async def interpret_command(message: str, has_image: bool = False):
    """Classifica a intenção de uma mensagem de WhatsApp de LOJISTA e extrai dados."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    system = (
        "Você interpreta mensagens de WhatsApp que LOJISTAS enviam ao marketplace "
        "'Lojas da Fronteira' (Tríplice Fronteira). Classifique a INTENÇÃO e extraia dados. "
        "Responda SOMENTE com JSON válido no formato: "
        '{"intent": "criar|atualizar|desativar|catalogo|abrir_loja|fechar_loja|ver_pedidos|criar_cupom|ajuda|desconhecido", '
        '"alvo": string, "name": string, "price": number, "description": string, "category": string, '
        '"cupom_codigo": string, "cupom_valor": number, "cupom_tipo": "percent|fixed"}. '
        "intent=criar: cadastrar/adicionar um novo produto. "
        "intent=atualizar: mudar preço/nome/descrição de um item existente. "
        "intent=desativar: remover/desativar/esgotou/tirar um item. "
        "intent=catalogo: pediu o catálogo/lista/PDF dos produtos. "
        "intent=abrir_loja: quer abrir a loja / ficar online / começar a vender. "
        "intent=fechar_loja: quer fechar a loja / ficar offline / parar por hoje. "
        "intent=ver_pedidos: quer ver os pedidos recebidos / vendas do dia. "
        "intent=criar_cupom: quer criar um cupom de desconto (extraia cupom_codigo, cupom_valor e cupom_tipo; "
        "percent se falar em % ou porcentagem, fixed se falar em R$/reais). "
        "intent=ajuda: pediu ajuda/comandos. Caso contrário: desconhecido. "
        "alvo = nome do produto citado para atualizar/desativar (vazio se criar). "
        "name/price/description/category preenchidos quando intent=criar ou atualizar. "
        "price em reais (número, sem R$; 0 se ausente). "
        "category deve ser UMA de: Eletrônicos, Informática, Celulares, Perfumaria, Moda, "
        "Calçados, Casa & Decoração, Brinquedos, Bebidas, Alimentos, Acessórios, Outros. "
        "Nada além do JSON."
    )
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"wa-cmd-{uuid.uuid4().hex[:8]}",
                   system_message=system).with_model("gemini", "gemini-3-flash-preview")
    hint = " (a mensagem veio acompanhada de uma imagem do produto)" if has_image else ""
    try:
        resp = await chat.send_message(UserMessage(text=f"Mensagem: {message or '(sem texto)'}{hint}"))
    except Exception as e:
        logger.error(f"WA interpret error: {e}")
        return {"intent": "desconhecido"}
    text = resp if isinstance(resp, str) else str(resp)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"intent": "desconhecido"}
    try:
        data = json.loads(m.group(0))
    except Exception:
        return {"intent": "desconhecido"}
    return {
        "intent": str(data.get("intent", "desconhecido")).strip().lower(),
        "alvo": str(data.get("alvo", "")).strip(),
        "name": str(data.get("name", "")).strip(),
        "price": float(data.get("price", 0) or 0),
        "description": str(data.get("description", "")).strip(),
        "category": str(data.get("category", "Outros")).strip() or "Outros",
        "cupom_codigo": str(data.get("cupom_codigo", "")).strip(),
        "cupom_valor": float(data.get("cupom_valor", 0) or 0),
        "cupom_tipo": str(data.get("cupom_tipo", "percent")).strip().lower() or "percent",
    }


async def interpret_customer(message: str, has_image: bool = False):
    """Classifica a intenção de uma mensagem de WhatsApp de CLIENTE (carrinho/busca)."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    system = (
        "Você interpreta mensagens de WhatsApp que CLIENTES enviam ao marketplace "
        "'Lojas da Fronteira'. O cliente busca produtos, monta um carrinho e finaliza um pedido. "
        "Responda SOMENTE com JSON válido no formato: "
        '{"intent": "buscar|adicionar|remover|ver_carrinho|finalizar|confirmar|cancelar|ajuda|desconhecido", '
        '"query": string, "index": number, "qty": number, "sim": boolean}. '
        "intent=buscar: descreve/procura um produto que deseja (query = descrição do produto). "
        "intent=adicionar: quer adicionar um item da lista de resultados ao carrinho "
        "(index = número do item citado, qty = quantidade, padrão 1). "
        "intent=remover: quer remover um item do carrinho (index = número). "
        "intent=ver_carrinho: quer ver o carrinho / o PDF do pedido. "
        "intent=finalizar: quer fechar/finalizar o pedido. "
        "intent=confirmar: está respondendo sim/não a uma confirmação (sim=true se confirmou, false se recusou). "
        "intent=cancelar: quer cancelar/esvaziar o carrinho. "
        "intent=ajuda: pediu ajuda. Caso contrário: desconhecido. "
        "Se a mensagem for uma foto de produto sem texto claro, use intent=buscar. "
        "Nada além do JSON."
    )
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"wa-cli-{uuid.uuid4().hex[:8]}",
                   system_message=system).with_model("gemini", "gemini-3-flash-preview")
    hint = " (a mensagem veio com uma foto de um produto que o cliente procura)" if has_image else ""
    try:
        resp = await chat.send_message(UserMessage(text=f"Mensagem: {message or '(sem texto)'}{hint}"))
    except Exception as e:
        logger.error(f"WA customer interpret error: {e}")
        return {"intent": "buscar" if has_image else "desconhecido", "query": message}
    text = resp if isinstance(resp, str) else str(resp)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"intent": "desconhecido"}
    try:
        data = json.loads(m.group(0))
    except Exception:
        return {"intent": "desconhecido"}
    def _int(v):
        try:
            return int(float(v))
        except Exception:
            return 0
    return {
        "intent": str(data.get("intent", "desconhecido")).strip().lower(),
        "query": str(data.get("query", "")).strip(),
        "index": _int(data.get("index", 0)),
        "qty": max(1, _int(data.get("qty", 1)) or 1),
        "sim": bool(data.get("sim", False)),
    }


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
            if u and (u["role"] in ("admin", "master") or u["user_id"] == o["customer_user_id"]
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
        # pedidos criados via WhatsApp só aparecem após o cliente confirmar o envio
        q["sent_to_vendor"] = {"$ne": False}
    elif user["role"] == "admin":
        ids = await admin_store_ids(user)
        q["store_id"] = {"$in": ids}
    orders = await db.orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return orders


@api.put("/orders/{order_id}")
async def update_order_items(order_id: str, body: OrderItemsUpdate, user=Depends(get_current_user)):
    o = await db.orders.find_one({"id": order_id, "deleted": {"$ne": True}})
    if not o:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    is_vendor = user["role"] == "lojista" and user.get("store_id") == o["store_id"]
    is_admin = user["role"] in ("admin", "master")
    is_owner = user["user_id"] == o["customer_user_id"]
    if not (is_admin or is_vendor or (is_owner and o.get("editable"))):
        raise HTTPException(status_code=403, detail="Edição não permitida")
    total = round(sum(i.price * i.qty for i in body.items if getattr(i, "available", True)), 2)
    await db.orders.update_one({"id": order_id},
                               {"$set": {"items": [i.dict() for i in body.items], "total": total}})
    updated = await db.orders.find_one({"id": order_id}, {"_id": 0})
    # se o lojista/admin ajustou o pedido, avisa o cliente
    if (is_vendor or is_admin) and not is_owner:
        try:
            await notify_order(updated, "edited")
        except Exception as e:
            logger.warning(f"notify_order edited failed: {e}")
    return updated


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


def _wa_me(number: str, text: str) -> str:
    from urllib.parse import quote
    digits = re.sub(r"\D", "", number or "")
    if not digits:
        return ""
    return f"https://wa.me/{digits}?text={quote(text)}"


@api.get("/orders/{order_id}/wa-links")
async def order_wa_links(order_id: str, token: Optional[str] = Query(None),
                         authorization: Optional[str] = Header(None)):
    """Click-to-chat (wa.me) links to notify vendor or client via the WhatsApp app.
    Alternative delivery path when Cloud API sending is unavailable (SMB numbers)."""
    o = await db.orders.find_one({"id": order_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    authorized = bool(token and token == o["token"])
    if not authorized and authorization and authorization.startswith("Bearer "):
        sess = await db.user_sessions.find_one({"session_token": authorization.split(" ", 1)[1].strip()}, {"_id": 0})
        if sess:
            u = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
            if u and (u["role"] in ("admin", "master") or u["user_id"] == o["customer_user_id"]
                      or (u["role"] == "lojista" and u.get("store_id") == o["store_id"])):
                authorized = True
    if not authorized:
        raise HTTPException(status_code=403, detail="Acesso negado")
    store = await db.stores.find_one({"id": o["store_id"]}, {"_id": 0}) or {}
    link = _order_link(o)
    link_txt = f"\n{link}" if link else ""
    to_vendor = (f"*Pedido — {o['store_name']}*\nCliente: {o.get('customer_name','')}\n"
                 f"{_order_lines(o)}\nTotal: R$ {o['total']:.2f}{link_txt}")
    to_customer = (f"Olá {o.get('customer_name','')}! Sobre seu pedido em {o['store_name']}:\n"
                   f"{_order_lines(o)}\nTotal: R$ {o['total']:.2f}{link_txt}")
    return {
        # cliente abre para enviar o pedido ao lojista
        "vendor_link": _wa_me(store.get("whatsapp", ""), to_vendor),
        "vendor_number": re.sub(r"\D", "", store.get("whatsapp", "") or ""),
        # lojista abre para avisar o cliente
        "customer_link": _wa_me(o.get("customer_whatsapp", ""), to_customer),
        "customer_number": re.sub(r"\D", "", o.get("customer_whatsapp", "") or ""),
        "pdf": link,
    }


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


@api.get("/stores/{store_id}/catalog.pdf")
async def store_catalog_pdf(store_id: str):
    store = await db.stores.find_one({"id": store_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    products = await db.products.find(
        {"store_id": store_id, "deleted": {"$ne": True}}, {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    pdf = await run_in_threadpool(build_catalog_pdf, store, products)
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="catalogo-{store_id}.pdf"'})


def build_catalog_pdf(store, products):
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
           Paragraph(f"<b>Catálogo:</b> {store['name']}", h),
           Paragraph(f"<b>Itens ativos:</b> {len(products)}", h),
           Spacer(1, 10 * mm)]
    if not products:
        els.append(Paragraph("Nenhum produto cadastrado ainda.", h))
    else:
        data = [["Produto", "Categoria", "Preço"]]
        for p in products:
            data.append([p.get("name", ""), p.get("category", "Outros"),
                         f"R$ {float(p.get('price', 0) or 0):.2f}"])
        table = Table(data, colWidths=[90 * mm, 45 * mm, 35 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1C9BE")),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FDFBF7")]),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        els.append(table)
    doc.build(els)
    return buf.getvalue()


# ------------------------------------------------------------------ Busca global + Carrinho por WhatsApp
def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


async def search_products_global(query: str, limit: int = 8):
    """Busca produtos ativos em TODAS as lojas por similaridade simples de tokens."""
    q = _norm(query)
    tokens = [t for t in re.split(r"[^a-z0-9]+", q) if len(t) >= 3]
    prods = await db.products.find({"deleted": {"$ne": True}}, {"_id": 0}).to_list(5000)
    stores = await db.stores.find({"deleted": {"$ne": True}}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    smap = {s["id"]: s["name"] for s in stores}
    scored = []
    for p in prods:
        name = _norm(p.get("name", ""))
        desc = _norm(p.get("description", ""))
        cat = _norm(p.get("category", ""))
        score = 0
        for t in tokens:
            if t in name:
                score += 3
            if t in cat:
                score += 2
            if t in desc:
                score += 1
        if score > 0:
            p = dict(p)
            p["store_name"] = smap.get(p.get("store_id", ""), "—")
            p["_score"] = score
            scored.append(p)
    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[:limit]


async def _get_or_create_cart(sender: str):
    cart = await db.wa_carts.find_one({"customer_phone": sender, "status": "building"}, {"_id": 0})
    if cart:
        return cart
    user = await db.users.find_one({"whatsapp": {"$regex": f"{re.escape(sender[-10:])}$"}},
                                   {"_id": 0, "user_id": 1, "name": 1})
    cart = {
        "id": new_id("wcart"), "token": uuid.uuid4().hex, "customer_phone": sender,
        "customer_user_id": (user or {}).get("user_id", ""),
        "customer_name": (user or {}).get("name", ""),
        "items": [], "candidates": [], "status": "building", "pending_action": "",
        "order_ids": [], "created_at": now_iso(),
    }
    await db.wa_carts.insert_one(cart)
    cart.pop("_id", None)
    return cart


@api.get("/wa/cart/{cart_id}/pdf")
async def wa_cart_pdf(cart_id: str, token: str = Query(...)):
    cart = await db.wa_carts.find_one({"id": cart_id}, {"_id": 0})
    if not cart or cart.get("token") != token:
        raise HTTPException(status_code=404, detail="Carrinho não encontrado")
    pdf = await run_in_threadpool(build_cart_pdf, cart)
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="pedido-{cart_id}.pdf"'})


def build_cart_pdf(cart):
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
    sub = ParagraphStyle("s", parent=styles["Normal"], fontSize=13, textColor=brand, spaceBefore=8)
    els = [Paragraph("Lojas da Fronteira", title),
           Paragraph("<b>Pedido de compra (carrinho)</b>", h),
           Paragraph(f"<b>Cliente:</b> {cart.get('customer_name') or cart.get('customer_phone','')}", h),
           Spacer(1, 6 * mm)]
    # agrupa por loja
    groups = {}
    for it in cart.get("items", []):
        groups.setdefault((it.get("store_id"), it.get("store_name", "—")), []).append(it)
    grand = 0.0
    for (sid, sname), items in groups.items():
        els.append(Paragraph(f"Loja: {sname}", sub))
        data = [["Produto", "Qtd", "Preço", "Subtotal"]]
        stotal = 0.0
        for it in items:
            line = it["price"] * it["qty"]
            stotal += line
            data.append([it["name"], str(it["qty"]), f"R$ {it['price']:.2f}", f"R$ {line:.2f}"])
        data.append(["", "", "Subtotal", f"R$ {stotal:.2f}"])
        grand += stotal
        table = Table(data, colWidths=[80 * mm, 20 * mm, 35 * mm, 35 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1C9BE")),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        els.append(table)
    els.append(Spacer(1, 8 * mm))
    els.append(Paragraph(f"<b>TOTAL GERAL: R$ {grand:.2f}</b>", sub))
    doc.build(els)
    return buf.getvalue()


# ------------------------------------------------------------------ Admin
@api.get("/admin/metrics")
async def admin_metrics(user=Depends(require_role("admin"))):
    store_q = {"deleted": {"$ne": True}}
    if not is_master(user):
        ids = await admin_store_ids(user)
        store_q["id"] = {"$in": ids}
        prod_store_filter = {"$in": ids}
    else:
        prod_store_filter = None
    stores = await db.stores.count_documents(store_q)
    if prod_store_filter is None:
        products = await db.products.count_documents({"deleted": {"$ne": True}})
        order_docs = await db.orders.find({"deleted": {"$ne": True}}, {"_id": 0, "total": 1, "customer_user_id": 1}).to_list(5000)
        customers = await db.users.count_documents({"role": "cliente"})
    else:
        products = await db.products.count_documents({"deleted": {"$ne": True}, "store_id": prod_store_filter})
        order_docs = await db.orders.find({"deleted": {"$ne": True}, "store_id": prod_store_filter},
                                          {"_id": 0, "total": 1, "customer_user_id": 1}).to_list(5000)
        customers = len({o.get("customer_user_id") for o in order_docs if o.get("customer_user_id")})
    orders = len(order_docs)
    revenue = round(sum(o.get("total", 0) for o in order_docs), 2)
    return {"stores": stores, "products": products, "orders": orders,
            "customers": customers, "revenue": revenue}


@api.get("/admin/users")
async def admin_users(user=Depends(require_role("admin"))):
    if is_master(user):
        users = await db.users.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    else:
        # admin comum vê apenas os lojistas das lojas vinculadas a ele
        ids = await admin_store_ids(user)
        users = await db.users.find({"store_id": {"$in": ids}, "role": "lojista"}, {"_id": 0}
                                    ).sort("created_at", -1).to_list(1000)
    return users


@api.put("/admin/users/{user_id}/role")
async def set_role(user_id: str, body: RoleUpdate, user=Depends(require_role("master"))):
    # Somente o master altera papéis de clientes, lojistas e administradores.
    if body.role not in ("admin", "lojista", "cliente", "master"):
        raise HTTPException(status_code=400, detail="Role inválida")
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    updates = {"role": body.role, "store_id": body.store_id if body.role == "lojista" else None}
    await db.users.update_one({"user_id": user_id}, {"$set": updates})
    # opcional: vincular a loja do lojista a um admin
    if body.role == "lojista" and body.store_id and body.admin_id:
        await db.stores.update_one({"id": body.store_id}, {"$set": {"admin_id": body.admin_id}})
    return await db.users.find_one({"user_id": user_id}, {"_id": 0})


# ------------------------------------------------------------------ Master (super-admin)
@api.get("/master/overview")
async def master_overview(user=Depends(require_role("master"))):
    users = await db.users.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    stores = await db.stores.find({"deleted": {"$ne": True}}, {"_id": 0}).to_list(1000)
    counts = {"master": 0, "admin": 0, "lojista": 0, "cliente": 0}
    for u in users:
        counts[u.get("role", "cliente")] = counts.get(u.get("role", "cliente"), 0) + 1
    return {"users": users, "stores": stores, "counts": counts}


@api.post("/master/users")
async def master_create_user(body: MasterUserIn, user=Depends(require_role("master"))):
    if body.role not in ("admin", "lojista", "cliente", "master"):
        raise HTTPException(status_code=400, detail="Role inválida")
    email_l = body.email.strip().lower()
    if not email_l:
        raise HTTPException(status_code=400, detail="E-mail obrigatório")
    existing = await db.users.find_one({"email": email_l})
    role = "master" if email_l == MASTER_EMAIL else body.role
    if existing:
        await db.users.update_one({"user_id": existing["user_id"]}, {"$set": {"role": role}})
        uid = existing["user_id"]
    else:
        uid = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({"user_id": uid, "email": email_l,
                                   "name": body.name or email_l.split("@")[0], "picture": "",
                                   "role": role, "store_id": None, "created_at": now_iso()})
    return await db.users.find_one({"user_id": uid}, {"_id": 0})


@api.delete("/master/users/{user_id}")
async def master_delete_user(user_id: str, user=Depends(require_role("master"))):
    if user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="Você não pode excluir a si mesmo")
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if target and target.get("email") == MASTER_EMAIL:
        raise HTTPException(status_code=400, detail="A conta master não pode ser excluída")
    await db.user_sessions.delete_many({"user_id": user_id})
    await db.users.delete_one({"user_id": user_id})
    return {"ok": True}


@api.put("/master/stores/{store_id}/assign")
async def master_assign_store(store_id: str, body: dict, user=Depends(require_role("master"))):
    s = await db.stores.find_one({"id": store_id, "deleted": {"$ne": True}})
    if not s:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    await db.stores.update_one({"id": store_id}, {"$set": {"admin_id": body.get("admin_id") or None}})
    return await db.stores.find_one({"id": store_id}, {"_id": 0})


@api.get("/home")
async def home(viewer=Depends(optional_user)):
    q = {"deleted": {"$ne": True}, "active": {"$ne": False}}
    restrict = await scoped_store_ids_for_viewer(viewer)
    if restrict is not None:
        q["id"] = {"$in": restrict}
    stores = await db.stores.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
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
async def search(q: str = Query(""), viewer=Depends(optional_user)):
    q = q.strip()
    if not q:
        return {"stores": [], "products": []}
    restrict = await scoped_store_ids_for_viewer(viewer)
    rx = {"$regex": re.escape(q), "$options": "i"}
    sq = {"deleted": {"$ne": True}, "active": {"$ne": False}, "name": rx}
    if restrict is not None:
        sq["id"] = {"$in": restrict}
    stores = await db.stores.find(sq, {"_id": 0}).to_list(50)
    for s in stores:
        s["product_count"] = await db.products.count_documents(
            {"store_id": s["id"], "deleted": {"$ne": True}}
        )
        s["online"] = store_online(s)
        s.update(await rating_summary(s["id"]))
    active_q = {"deleted": {"$ne": True}, "active": {"$ne": False}}
    if restrict is not None:
        active_q["id"] = {"$in": restrict}
    active_ids = await db.stores.distinct("id", active_q)
    all_stores = await db.stores.find({"id": {"$in": active_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
    smap = {s["id"]: s["name"] for s in all_stores}
    products = await db.products.find(
        {"deleted": {"$ne": True}, "store_id": {"$in": active_ids},
         "$or": [{"name": rx}, {"description": rx}]}, {"_id": 0}
    ).to_list(50)
    for p in products:
        p["store_name"] = smap.get(p["store_id"], "")
    return {"stores": stores, "products": products}


# ------------------------------------------------------------------ Interest groups (áreas)
DEFAULT_GROUPS = [
    {"name": "Eletrônicos", "icon": "hardware-chip", "color": "#3A6EA5"},
    {"name": "Moda & Acessórios", "icon": "shirt", "color": "#C16E53"},
    {"name": "Beleza & Perfumaria", "icon": "sparkles", "color": "#B0568A"},
    {"name": "Casa & Decoração", "icon": "home", "color": "#4A7C59"},
    {"name": "Alimentos & Bebidas", "icon": "fast-food", "color": "#D48C46"},
    {"name": "Serviços", "icon": "construct", "color": "#6B7A8F"},
]


async def seed_groups():
    if await db.groups.count_documents({}) == 0:
        for g in DEFAULT_GROUPS:
            await db.groups.insert_one({"id": new_id("grp"), "name": g["name"], "description": "",
                                        "icon": g["icon"], "color": g["color"], "created_at": now_iso()})


# Fixed system accounts (username / password / role / whatsapp)
SEED_ACCOUNTS = [
    {"username": "root", "email": "root@m3d.pro", "name": "Root", "password": "@0root",
     "role": "master", "whatsapp": "5511920946954"},
    {"username": "admin", "email": "admin@m3d.pro", "name": "Administrador", "password": "@0admin",
     "role": "admin", "whatsapp": "5511960708817"},
    {"username": "lojista", "email": "lojista@m3d.pro", "name": "Lojista", "password": "@0lojista",
     "role": "lojista", "whatsapp": "5511960708817"},
    {"username": "cliente", "email": "cliente@m3d.pro", "name": "Cliente", "password": "@0cliente",
     "role": "cliente", "whatsapp": "5511960708817"},
]


async def seed_accounts():
    """Idempotent: ensures the fixed system accounts exist with the right role/password/whatsapp."""
    for acc in SEED_ACCOUNTS:
        existing = await db.users.find_one({"$or": [{"username": acc["username"]}, {"email": acc["email"]}]})
        fields = {
            "username": acc["username"],
            "email": acc["email"],
            "name": acc["name"],
            "role": acc["role"],
            "whatsapp": acc["whatsapp"],
            "password_hash": hash_password(acc["password"]),
        }
        if existing:
            await db.users.update_one({"user_id": existing["user_id"]}, {"$set": fields})
        else:
            fields.update({"user_id": f"user_{uuid.uuid4().hex[:12]}", "picture": "",
                           "store_id": None, "created_at": now_iso()})
            await db.users.insert_one(fields)


@api.get("/groups")
async def list_groups():
    groups = await db.groups.find({}, {"_id": 0}).sort("name", 1).to_list(200)
    for g in groups:
        g["store_count"] = await db.stores.count_documents(
            {"group_ids": g["id"], "deleted": {"$ne": True}, "active": {"$ne": False}})
    return groups


@api.post("/groups")
async def create_group(body: GroupIn, user=Depends(require_role("admin"))):
    doc = {"id": new_id("grp"), "name": body.name, "description": body.description or "",
           "icon": body.icon or "pricetags", "color": body.color or "#4A7C59", "created_at": now_iso()}
    await db.groups.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.put("/groups/{group_id}")
async def update_group(group_id: str, body: GroupIn, user=Depends(require_role("admin"))):
    await db.groups.update_one({"id": group_id}, {"$set": {
        "name": body.name, "description": body.description or "",
        "icon": body.icon or "pricetags", "color": body.color or "#4A7C59"}})
    return await db.groups.find_one({"id": group_id}, {"_id": 0})


@api.delete("/groups/{group_id}")
async def delete_group(group_id: str, user=Depends(require_role("admin"))):
    await db.groups.delete_one({"id": group_id})
    await db.stores.update_many({"group_ids": group_id}, {"$pull": {"group_ids": group_id}})
    return {"ok": True}


# ------------------------------------------------------------------ Invites (convite-only access)
async def _can_manage_store(user, store):
    if is_master(user):
        return True
    if user["role"] == "lojista" and user.get("store_id") == store["id"]:
        return True
    if user["role"] == "admin" and store.get("admin_id") == user["user_id"]:
        return True
    return False


@api.post("/invites")
async def create_invite(body: InviteIn, user=Depends(require_role("lojista", "admin"))):
    store = await db.stores.find_one({"id": body.store_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    if not await _can_manage_store(user, store):
        raise HTTPException(status_code=403, detail="Loja não vinculada a você")
    email_l = (body.client_email or "").strip().lower()
    doc = {"id": new_id("inv"), "token": uuid.uuid4().hex, "store_id": store["id"],
           "store_name": store["name"], "store_logo": store.get("logo", ""),
           "vendor_user_id": user["user_id"], "client_email": email_l,
           "client_user_id": None, "status": "pending", "created_at": now_iso(),
           "accepted_at": None}
    await db.invites.insert_one(doc)
    doc.pop("_id", None)
    base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else ""
    doc["link"] = f"{base}/invite/{doc['token']}" if base else f"/invite/{doc['token']}"
    # se houver e-mail, envia convite
    if email_l:
        try:
            html = (f'<table role="presentation" width="100%"><tr><td style="padding:24px;'
                    f'font-family:Arial,sans-serif;color:#1A1C19">'
                    f'<h2 style="color:#4A7C59">Convite — {escape(store["name"])}</h2>'
                    f'<p>Você foi convidado(a) a acessar o catálogo da loja <b>{escape(store["name"])}</b> '
                    f'no app Lojas da Fronteira.</p>'
                    f'<p><a href="{escape(doc["link"])}" style="background:#4A7C59;color:#fff;'
                    f'padding:10px 18px;border-radius:8px;text-decoration:none">Acessar catálogo</a></p>'
                    f'</td></tr></table>')
            await send_email(to=email_l, subject=f"Convite para {store['name']} — Lojas da Fronteira", html=html)
        except Exception as e:
            logger.warning(f"invite email failed: {e}")
    return doc


@api.get("/invites")
async def list_invites(user=Depends(require_role("lojista", "admin"))):
    if is_master(user):
        q = {}
    elif user["role"] == "lojista":
        q = {"store_id": user.get("store_id")}
    else:
        q = {"store_id": {"$in": await admin_store_ids(user)}}
    invites = await db.invites.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return invites


@api.delete("/invites/{invite_id}")
async def revoke_invite(invite_id: str, user=Depends(require_role("lojista", "admin"))):
    inv = await db.invites.find_one({"id": invite_id})
    if not inv:
        raise HTTPException(status_code=404, detail="Convite não encontrado")
    store = await db.stores.find_one({"id": inv["store_id"]}, {"_id": 0}) or {"id": inv["store_id"]}
    if not await _can_manage_store(user, store):
        raise HTTPException(status_code=403, detail="Acesso negado")
    await db.invites.update_one({"id": invite_id}, {"$set": {"status": "revoked"}})
    return {"ok": True}


@api.get("/invite/{token}")
async def get_invite(token: str):
    inv = await db.invites.find_one({"token": token}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Convite inválido")
    return {"store_id": inv["store_id"], "store_name": inv["store_name"],
            "store_logo": inv.get("store_logo", ""), "status": inv["status"]}


@api.post("/invite/{token}/accept")
async def accept_invite(token: str, user=Depends(get_current_user)):
    inv = await db.invites.find_one({"token": token})
    if not inv or inv["status"] == "revoked":
        raise HTTPException(status_code=404, detail="Convite inválido ou revogado")
    await db.invites.update_one({"token": token}, {"$set": {
        "client_user_id": user["user_id"], "status": "accepted",
        "accepted_at": now_iso(),
        "client_email": inv.get("client_email") or (user.get("email") or "").lower()}})
    return {"ok": True, "store_id": inv["store_id"], "store_name": inv["store_name"]}


@api.get("/my/catalog-stores")
async def my_catalog_stores(user=Depends(get_current_user)):
    ids = await client_store_ids(user)
    stores = await db.stores.find({"id": {"$in": ids}, "deleted": {"$ne": True}}, {"_id": 0}).to_list(500)
    for s in stores:
        s["product_count"] = await db.products.count_documents({"store_id": s["id"], "deleted": {"$ne": True}})
        s["online"] = store_online(s)
        s.update(await rating_summary(s["id"]))
    return stores


# ------------------------------------------------------------------ Personal shopping catalog
@api.post("/catalog")
async def add_catalog_item(body: CatalogItemIn, user=Depends(get_current_user)):
    allowed = await client_store_ids(user)
    if body.store_id not in allowed:
        raise HTTPException(status_code=403, detail="Você precisa de um convite para esta loja")
    p = await db.products.find_one({"id": body.product_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not p or p["store_id"] != body.store_id:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    store = await db.stores.find_one({"id": body.store_id}, {"_id": 0}) or {}
    doc = {"id": new_id("citem"), "client_user_id": user["user_id"], "store_id": body.store_id,
           "store_name": store.get("name", ""), "product_id": p["id"], "name": p["name"],
           "price": p.get("price", 0), "image": p.get("image", ""),
           "category": p.get("category", "Outros"), "qty": max(1, body.qty),
           "note": body.note or "", "added_at": now_iso()}
    # upsert por (cliente, produto): se já existe, soma quantidade
    existing = await db.catalog_items.find_one({"client_user_id": user["user_id"], "product_id": p["id"]})
    if existing:
        await db.catalog_items.update_one({"id": existing["id"]},
                                          {"$set": {"qty": existing.get("qty", 1) + max(1, body.qty),
                                                    "note": body.note or existing.get("note", "")}})
        return await db.catalog_items.find_one({"id": existing["id"]}, {"_id": 0})
    await db.catalog_items.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/catalog")
async def list_catalog(store_id: str = Query(""), category: str = Query(""),
                       q: str = Query(""), user=Depends(get_current_user)):
    query = {"client_user_id": user["user_id"]}
    if store_id:
        query["store_id"] = store_id
    if category and category != "Todos":
        query["category"] = category
    if q.strip():
        query["name"] = {"$regex": re.escape(q.strip()), "$options": "i"}
    items = await db.catalog_items.find(query, {"_id": 0}).sort("added_at", -1).to_list(2000)
    # metadados para filtros do cliente
    all_items = await db.catalog_items.find({"client_user_id": user["user_id"]}, {"_id": 0}).to_list(2000)
    stores_meta = {}
    cats = set()
    for it in all_items:
        stores_meta.setdefault(it["store_id"], {"store_id": it["store_id"], "store_name": it.get("store_name", ""), "count": 0})
        stores_meta[it["store_id"]]["count"] += 1
        cats.add(it.get("category", "Outros"))
    total = round(sum(i["price"] * i["qty"] for i in items), 2)
    return {"items": items, "total": total, "count": len(items),
            "stores": list(stores_meta.values()), "categories": sorted(cats)}


@api.put("/catalog/{item_id}")
async def update_catalog_item(item_id: str, body: CatalogItemUpdate, user=Depends(get_current_user)):
    it = await db.catalog_items.find_one({"id": item_id, "client_user_id": user["user_id"]})
    if not it:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    updates = {}
    if body.qty is not None:
        updates["qty"] = max(1, body.qty)
    if body.note is not None:
        updates["note"] = body.note
    if updates:
        await db.catalog_items.update_one({"id": item_id}, {"$set": updates})
    return await db.catalog_items.find_one({"id": item_id}, {"_id": 0})


@api.delete("/catalog/{item_id}")
async def delete_catalog_item(item_id: str, user=Depends(get_current_user)):
    await db.catalog_items.delete_one({"id": item_id, "client_user_id": user["user_id"]})
    return {"ok": True}


@api.get("/catalog/report.pdf")
async def catalog_report_pdf(store_id: str = Query(""), category: str = Query(""),
                             token: str = Query(""), authorization: Optional[str] = Header(None)):
    # resolve user from Bearer header OR ?token=<session_token> (para abrir no navegador)
    user = None
    tok = ""
    if authorization and authorization.startswith("Bearer "):
        tok = authorization.split(" ", 1)[1].strip()
    elif token:
        tok = token
    if tok:
        sess = await db.user_sessions.find_one({"session_token": tok}, {"_id": 0})
        if sess:
            user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    query = {"client_user_id": user["user_id"]}
    if store_id:
        query["store_id"] = store_id
    if category and category != "Todos":
        query["category"] = category
    items = await db.catalog_items.find(query, {"_id": 0}).sort("store_name", 1).to_list(2000)
    label_parts = []
    if store_id:
        s = await db.stores.find_one({"id": store_id}, {"_id": 0, "name": 1})
        label_parts.append(f"Loja: {(s or {}).get('name', store_id)}")
    if category and category != "Todos":
        label_parts.append(f"Categoria: {category}")
    pdf = await run_in_threadpool(build_catalog_report_pdf, user.get("name", "Cliente"),
                                  items, " · ".join(label_parts) or "Todos os itens")
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                             headers={"Content-Disposition": 'inline; filename="meu-catalogo.pdf"'})


@api.post("/catalog/send")
async def send_catalog_cart(body: CartSend, user=Depends(get_current_user)):
    query = {"client_user_id": user["user_id"]}
    if body.item_ids:
        query["id"] = {"$in": body.item_ids}
    items = await db.catalog_items.find(query, {"_id": 0}).to_list(2000)
    if not items:
        raise HTTPException(status_code=400, detail="Nenhum item selecionado")
    # agrupa por loja => 1 pedido (e 1 PDF) por lojista
    by_store: dict = {}
    for it in items:
        by_store.setdefault(it["store_id"], []).append(it)
    if body.customer_whatsapp:
        await db.users.update_one({"user_id": user["user_id"]},
                                  {"$set": {"whatsapp": body.customer_whatsapp.strip()}})
    created = []
    for sid, sitems in by_store.items():
        store = await db.stores.find_one({"id": sid, "deleted": {"$ne": True}}, {"_id": 0})
        if not store:
            continue
        order_items = [{"product_id": i["product_id"], "name": i["name"],
                        "price": i["price"], "qty": i["qty"]} for i in sitems]
        subtotal = round(sum(i["price"] * i["qty"] for i in sitems), 2)
        doc = {"id": new_id("order"), "token": uuid.uuid4().hex, "store_id": sid,
               "store_name": store["name"], "store_whatsapp": store.get("whatsapp", ""),
               "customer_user_id": user["user_id"],
               "customer_name": body.customer_name or user.get("name", ""),
               "items": order_items, "subtotal": subtotal, "discount": 0.0,
               "coupon_code": "", "total": subtotal, "notes": body.notes or "",
               "customer_whatsapp": (body.customer_whatsapp or "").strip(),
               "status": "novo", "editable": True, "deleted": False,
               "source": "catalog", "created_at": now_iso()}
        await db.orders.insert_one(doc)
        doc.pop("_id", None)
        try:
            await notify_order(doc, "created")
        except Exception as e:
            logger.warning(f"catalog send notify failed: {e}")
        base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else ""
        created.append({"order_id": doc["id"], "store_id": sid, "store_name": store["name"],
                        "total": subtotal,
                        "pdf": f"{base}/api/orders/{doc['id']}/pdf?token={doc['token']}" if base else ""})
    # remove itens enviados do catálogo pessoal
    sent_ids = [i["id"] for i in items]
    await db.catalog_items.delete_many({"id": {"$in": sent_ids}, "client_user_id": user["user_id"]})
    return {"ok": True, "orders": created,
            "message": f"{len(created)} pedido(s) enviados aos lojistas."}


def build_catalog_report_pdf(customer_name, items, filter_label):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors as rc
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    brand = rc.HexColor("#4A7C59")
    title = ParagraphStyle("t", parent=styles["Title"], textColor=brand, fontSize=22)
    h = ParagraphStyle("h", parent=styles["Normal"], fontSize=11, textColor=rc.HexColor("#4A4C48"))
    sh = ParagraphStyle("sh", parent=styles["Normal"], fontSize=13, textColor=brand, fontName="Helvetica-Bold")
    els = [Paragraph("Meu Catálogo de Compras", title),
           Paragraph(f"<b>Cliente:</b> {customer_name}", h),
           Paragraph(f"<b>Filtro:</b> {filter_label}", h), Spacer(1, 8 * mm)]
    groups: dict = {}
    for it in items:
        groups.setdefault(it.get("store_name", "Loja"), []).append(it)
    grand = 0.0
    for store_name, gitems in groups.items():
        els.append(Paragraph(f"🏪 {store_name}", sh))
        els.append(Spacer(1, 2 * mm))
        data = [["Produto", "Qtd", "Preço", "Subtotal"]]
        stotal = 0.0
        for it in gitems:
            line = it["price"] * it["qty"]
            stotal += line
            data.append([it["name"], str(it["qty"]), f"R$ {it['price']:.2f}", f"R$ {line:.2f}"])
        data.append(["", "", "Subtotal", f"R$ {stotal:.2f}"])
        grand += stotal
        t = Table(data, colWidths=[85 * mm, 18 * mm, 32 * mm, 33 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand),
            ("TEXTCOLOR", (0, 0), (-1, 0), rc.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), rc.HexColor("#E9F0EC")),
            ("GRID", (0, 0), (-1, -1), 0.5, rc.HexColor("#D1C9BE")),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [rc.white, rc.HexColor("#FDFBF7")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        els.append(t)
        els.append(Spacer(1, 6 * mm))
    els.append(Paragraph(f"<b>Total geral:</b> R$ {grand:.2f}", sh))
    doc.build(els)
    return buf.getvalue()


# ------------------------------------------------------------------ AI translation (PT/EN/ES)
LANG_NAMES = {"pt": "português brasileiro", "en": "English (US)", "es": "español latinoamericano"}


@api.post("/translate")
async def translate_texts(body: TranslateReq):
    target = body.target if body.target in LANG_NAMES else "pt"
    texts = [t for t in body.texts if isinstance(t, str) and t.strip()]
    if target == "pt" or not texts:
        return {"translations": {t: t for t in texts}}
    import hashlib
    result: dict = {}
    pending: List[str] = []
    for t in texts:
        key = f"{target}:{hashlib.sha1(t.encode('utf-8')).hexdigest()}"
        cached = await db.translations.find_one({"k": key}, {"_id": 0, "v": 1})
        if cached:
            result[t] = cached["v"]
        else:
            pending.append(t)
    if pending:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            system = (
                f"You are a professional localizer for a retail marketplace app of the Triple Frontier "
                f"(Foz do Iguaçu / Ciudad del Este / Puerto Iguazú). Translate each string to {LANG_NAMES[target]}. "
                f"Use natural, colloquial commercial tone as a local shopper would say it. Keep product/brand "
                f"names, emojis, numbers and currency intact. Return ONLY a valid JSON array of strings with the "
                f"SAME length and order as the input, no extra text."
            )
            chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"i18n-{uuid.uuid4().hex[:8]}",
                           system_message=system).with_model("gemini", "gemini-3-flash-preview")
            resp = await chat.send_message(UserMessage(text=json.dumps(pending, ensure_ascii=False)))
            raw = (resp or "").strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].replace("json", "", 1).strip()
            arr = json.loads(raw)
            if isinstance(arr, list) and len(arr) == len(pending):
                for src, tr in zip(pending, arr):
                    tr = str(tr)
                    result[src] = tr
                    key = f"{target}:{hashlib.sha1(src.encode('utf-8')).hexdigest()}"
                    await db.translations.update_one({"k": key}, {"$set": {"k": key, "v": tr}}, upsert=True)
            else:
                for src in pending:
                    result[src] = src
        except Exception as e:
            logger.warning(f"translate failed: {e}")
            for src in pending:
                result.setdefault(src, src)
    return {"translations": result}


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


def _wa_norm(number: str) -> str:
    return re.sub(r"\D", "", number or "")


async def wa_send_template(to: str, name: str, lang: str, body_params=None):
    """Send an APPROVED utility template. body_params -> ordered list for {{1}},{{2}}..."""
    template = {"name": name, "language": {"code": lang or WA_TEMPLATE_LANG or "pt_BR"}}
    if body_params:
        template["components"] = [{
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)} for p in body_params],
        }]
    return await wa_send({"to": _wa_norm(to), "type": "template", "template": template})


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


# ============================================================ MARKETING / CAMPANHAS IA
# Redes sociais suportadas + formato padrão de imagem por rede
SUPPORTED_NETWORKS = {
    "instagram_feed": {"label": "Instagram Feed", "icon": "logo-instagram", "ratio": "4:5", "w": 1080, "h": 1350, "base": "https://instagram.com/"},
    "instagram_story": {"label": "Instagram Stories/Reels", "icon": "logo-instagram", "ratio": "9:16", "w": 1080, "h": 1920, "base": "https://instagram.com/"},
    "tiktok": {"label": "TikTok", "icon": "logo-tiktok", "ratio": "9:16", "w": 1080, "h": 1920, "base": "https://tiktok.com/@"},
    "pinterest": {"label": "Pinterest", "icon": "logo-pinterest", "ratio": "2:3", "w": 1000, "h": 1500, "base": "https://pinterest.com/"},
    "facebook_feed": {"label": "Facebook Feed", "icon": "logo-facebook", "ratio": "1:1", "w": 1080, "h": 1080, "base": "https://facebook.com/"},
}


class SocialNetworkIn(BaseModel):
    network: str
    handle: Optional[str] = ""
    url: Optional[str] = ""
    enabled: Optional[bool] = True


class SocialsUpdate(BaseModel):
    networks: List[SocialNetworkIn] = []


STYLE_PRESETS = {
    "auto": {"label": "Automático", "icon": "sparkles-outline",
             "hint": ""},
    "minimalista": {"label": "Minimalista", "icon": "remove-outline",
                    "hint": "clean minimalist aesthetic, generous negative space, soft neutral palette, calm studio lighting, refined and elegant"},
    "luxo": {"label": "Luxo", "icon": "diamond-outline",
             "hint": "luxurious premium aesthetic, sophisticated, deep dark tones with gold accents, dramatic cinematic lighting, high-end editorial fashion look"},
    "vibrante": {"label": "Vibrante", "icon": "color-palette-outline",
                 "hint": "vibrant bold saturated colors, energetic and playful, dynamic composition, pop-art inspired, high contrast"},
    "natural": {"label": "Natural", "icon": "leaf-outline",
                "hint": "natural organic lifestyle scene, warm golden-hour daylight, earthy tones, authentic real-world environment, soft depth of field"},
    "tech": {"label": "Tecnológico", "icon": "hardware-chip-outline",
             "hint": "modern high-tech aesthetic, sleek surfaces, cool blue neon accents, futuristic clean environment, crisp reflections"},
}


class CampaignReq(BaseModel):
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    product_details: Optional[str] = None
    price: Optional[str] = None
    category: Optional[str] = None
    networks: Optional[List[str]] = None
    language: Optional[str] = "pt"
    tone: Optional[str] = None
    style: Optional[str] = "auto"


class TrackReq(BaseModel):
    network: str
    action: str  # "save" | "copy" | "open"


class ScheduleReq(BaseModel):
    network: str
    scheduled_at: str          # ISO datetime (UTC or with offset)
    whatsapp: Optional[str] = ""


class AssetTextUpdate(BaseModel):
    network: str
    caption: Optional[str] = ""
    hashtags: Optional[List[str]] = []
    cta: Optional[str] = ""


class AssetRegenReq(BaseModel):
    network: str
    distinct: Optional[bool] = False
    prompt: Optional[str] = None


class SuggestReq(BaseModel):
    network: str
    language: Optional[str] = "pt"


def _mkt_parse_json(text: str) -> dict:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t.strip())
    a, b = t.find("{"), t.rfind("}")
    if a >= 0 and b > a:
        t = t[a:b + 1]
    return json.loads(t)


def _cover_crop_bytes(src_bytes: bytes, w: int, h: int) -> bytes:
    """Resize-to-cover + center-crop to exact (w,h), return JPEG bytes."""
    from PIL import Image
    img = Image.open(io.BytesIO(src_bytes)).convert("RGB")
    sw, sh = img.size
    scale = max(w / sw, h / sh)
    nw, nh = max(w, round(sw * scale)), max(h, round(sh * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    img = img.crop((left, top, left + w, top + h))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


async def _mkt_generate_copy(product: dict, networks: list, language: str, tone: Optional[str]) -> dict:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    lang_name = {"pt": "português do Brasil", "en": "inglês", "es": "espanhol"}.get(language, "português do Brasil")
    net_labels = {k: SUPPORTED_NETWORKS[k]["label"] for k in networks}
    schema = {
        "concept_pt": "conceito criativo da campanha em 1-2 frases (sempre em português)",
        "image_prompt_en": "prompt fotográfico DETALHADO em INGLÊS para gerador de imagem por IA: cenário lifestyle imersivo, iluminação, ângulo de câmera, textura, atmosfera, composição vertical, produto centralizado e com margens, sem qualquer texto na imagem",
        "networks": {k: {"caption": "legenda persuasiva", "hashtags": ["#exemplo"], "cta": "chamada para ação"} for k in networks},
    }
    system = (
        "Você é diretor de criação e copywriter sênior de campanhas publicitárias imersivas "
        "para redes sociais e marketplaces. Use metodologia AIDA, gatilhos mentais e CTA claro. "
        f"Os textos comerciais devem estar em {lang_name}. "
        "Responda ESTRITAMENTE com um JSON válido (sem markdown, sem comentários)."
    )
    prompt = (
        f"Produto: {product.get('name','')}\n"
        f"Detalhes: {product.get('details','')}\n"
        f"Categoria: {product.get('category','')}\n"
        f"Preço: {product.get('price','')}\n"
        f"Tom desejado: {tone or 'moderno, aspiracional'}\n"
        f"Redes-alvo: {net_labels}\n\n"
        "Para CADA rede, crie uma legenda única e adaptada ao público, com 4 a 8 hashtags e um CTA.\n"
        f"Preencha os valores mantendo exatamente estas chaves: {json.dumps(schema, ensure_ascii=False)}"
    )
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"mkt-{uuid.uuid4().hex[:8]}",
                   system_message=system).with_model("gemini", "gemini-3-flash-preview")
    resp = await chat.send_message(UserMessage(text=prompt))
    return _mkt_parse_json(resp)


async def _mkt_generate_image(prompt_en: str, ref_bytes: Optional[bytes] = None) -> Optional[bytes]:
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"mktimg-{uuid.uuid4().hex[:8]}",
                   system_message="You are a world-class commercial advertising photographer and art director.")
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
    full_prompt = (prompt_en or "").strip() + \
        " Ultra photorealistic commercial advertising photography, 8k, sharp focus, professional color grading, vertical composition, subject centered with generous margins, no text, no watermark."
    if ref_bytes:
        b64 = base64.b64encode(ref_bytes).decode("utf-8")
        msg = UserMessage(text=full_prompt + " Feature the exact product shown in the reference image.",
                          file_contents=[ImageContent(b64)])
    else:
        msg = UserMessage(text=full_prompt)
    _text, images = await chat.send_message_multimodal_response(msg)
    if not images:
        return None
    return base64.b64decode(images[0]["data"])


@api.get("/marketing/socials")
async def marketing_get_socials(user=Depends(require_role("lojista", "admin"))):
    catalog = [{"key": k, "label": v["label"], "icon": v["icon"], "ratio": v["ratio"],
                "w": v["w"], "h": v["h"]} for k, v in SUPPORTED_NETWORKS.items()]
    styles = [{"key": k, "label": v["label"], "icon": v["icon"]} for k, v in STYLE_PRESETS.items()]
    return {"networks": user.get("social_networks") or [], "catalog": catalog, "styles": styles}


@api.put("/marketing/socials")
async def marketing_put_socials(body: SocialsUpdate, user=Depends(require_role("lojista", "admin"))):
    nets = [{"network": n.network, "handle": (n.handle or "").strip(),
             "url": (n.url or "").strip(), "enabled": bool(n.enabled)}
            for n in body.networks if n.network in SUPPORTED_NETWORKS]
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"social_networks": nets}})
    return {"networks": nets}


@api.post("/marketing/campaign")
async def marketing_create_campaign(body: CampaignReq, user=Depends(require_role("lojista", "admin"))):
    # 1) Resolve product info (cadastrado ou manual)
    if body.product_id:
        p = await db.products.find_one({"id": body.product_id}, {"_id": 0})
        if not p:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        product = {"name": p.get("name", ""), "details": p.get("description", ""),
                   "category": p.get("category", ""), "price": f"R$ {float(p.get('price', 0)):.2f}",
                   "image": p.get("image", "")}
    else:
        if not (body.product_name or "").strip():
            raise HTTPException(status_code=400, detail="Informe um produto ou as informações do item")
        product = {"name": body.product_name.strip(), "details": (body.product_details or "").strip(),
                   "category": (body.category or "").strip(), "price": (body.price or "").strip(), "image": ""}

    # 2) Redes-alvo (subset das do lojista; padrão = habilitadas ou todas)
    networks = [n for n in (body.networks or []) if n in SUPPORTED_NETWORKS]
    if not networks:
        socials = user.get("social_networks") or []
        networks = [s["network"] for s in socials if s.get("enabled") and s.get("network") in SUPPORTED_NETWORKS]
    if not networks:
        networks = list(SUPPORTED_NETWORKS.keys())

    # 3) Copy (textos por rede)
    try:
        data = await _mkt_generate_copy(product, networks, body.language or "pt", body.tone)
    except Exception as e:
        logger.warning(f"marketing copy failed: {e}")
        raise HTTPException(status_code=502, detail="Falha ao gerar os textos da campanha. Tente novamente.")
    image_prompt = (data.get("image_prompt_en") or "").strip() or (
        f"High-end commercial lifestyle photograph of {product['name']} in an aspirational real-world setting, "
        "soft natural lighting, depth of field")
    style = (body.style or "auto").strip().lower()
    if style not in STYLE_PRESETS:
        style = "auto"
    style_hint = STYLE_PRESETS[style]["hint"]
    if style_hint:
        image_prompt = f"{image_prompt}. Visual style: {style_hint}."

    # 4) Imagem base por IA (usa a foto real do produto como referência, se houver)
    ref = None
    if product.get("image"):
        try:
            ref, _ = await run_in_threadpool(get_object, product["image"])
        except Exception:
            ref = None
    try:
        base_img = await _mkt_generate_image(image_prompt, ref)
    except Exception as e:
        logger.warning(f"marketing image failed: {e}")
        base_img = None
    if not base_img:
        raise HTTPException(status_code=502, detail="Não foi possível gerar a imagem. Tente novamente.")

    # 5) Recorta para o formato de cada rede + salva no storage
    handles = {s.get("network"): s for s in (user.get("social_networks") or [])}
    assets = []
    for nk in networks:
        cfg = SUPPORTED_NETWORKS[nk]
        try:
            variant = await run_in_threadpool(_cover_crop_bytes, base_img, cfg["w"], cfg["h"])
            path = f"{APP_NAME}/campaigns/{user['user_id']}/{uuid.uuid4().hex}.jpg"
            await run_in_threadpool(put_object, path, variant, "image/jpeg")
        except Exception as e:
            logger.warning(f"marketing asset {nk} failed: {e}")
            continue
        nc = (data.get("networks") or {}).get(nk) or {}
        hh = handles.get(nk) or {}
        assets.append({
            "network": nk, "label": cfg["label"], "icon": cfg["icon"], "ratio": cfg["ratio"],
            "w": cfg["w"], "h": cfg["h"], "image_path": path, "image_prompt": image_prompt,
            "caption": nc.get("caption", ""), "hashtags": nc.get("hashtags") or [], "cta": nc.get("cta", ""),
            "profile_url": (hh.get("url") or hh.get("handle") or ""),
            "stats": {"saves": 0, "copies": 0, "opens": 0},
        })
    if not assets:
        raise HTTPException(status_code=502, detail="Falha ao montar os formatos da campanha.")

    doc = {"id": new_id("camp"), "owner_id": user["user_id"], "store_id": user.get("store_id"),
           "product_name": product["name"], "concept": data.get("concept_pt", ""),
           "image_prompt": image_prompt, "ref_image_path": product.get("image", ""),
           "style": style, "cover_path": assets[0]["image_path"],
           "assets": assets, "created_at": now_iso()}
    await db.campaigns.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/marketing/campaigns")
async def marketing_list_campaigns(user=Depends(require_role("lojista", "admin"))):
    q = {} if is_master(user) else {"owner_id": user["user_id"]}
    return await db.campaigns.find(q, {"_id": 0, "assets": 0, "image_prompt": 0}).sort("created_at", -1).to_list(50)


@api.get("/marketing/campaigns/{cid}")
async def marketing_get_campaign(cid: str, user=Depends(require_role("lojista", "admin"))):
    c = await db.campaigns.find_one({"id": cid}, {"_id": 0})
    if not c or (not is_master(user) and c.get("owner_id") != user["user_id"]):
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    return c


@api.delete("/marketing/campaigns/{cid}")
async def marketing_delete_campaign(cid: str, user=Depends(require_role("lojista", "admin"))):
    c = await db.campaigns.find_one({"id": cid})
    if not c or (not is_master(user) and c.get("owner_id") != user["user_id"]):
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    await db.campaigns.delete_one({"id": cid})
    return {"ok": True}


_VARIATION_HINTS = [
    "an alternative creative concept with a completely different scene and setting",
    "a different camera angle with a fresh background and mood",
    "a new art direction with a different color palette and composition",
    "a different time of day and lighting for a distinct atmosphere",
    "a unique lifestyle context with different props and environment",
    "a bold minimalist studio composition with dramatic lighting",
]


async def _mkt_find_campaign_asset(cid: str, network: str, user):
    c = await db.campaigns.find_one({"id": cid})
    if not c or (not is_master(user) and c.get("owner_id") != user["user_id"]):
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    if network not in SUPPORTED_NETWORKS:
        raise HTTPException(status_code=400, detail="Rede inválida")
    assets = c.get("assets") or []
    asset = next((a for a in assets if a.get("network") == network), None)
    if not asset:
        raise HTTPException(status_code=404, detail="Formato não encontrado nesta campanha")
    return c, assets, asset


@api.put("/marketing/campaigns/{cid}/asset")
async def marketing_update_asset(cid: str, body: AssetTextUpdate,
                                 user=Depends(require_role("lojista", "admin"))):
    _c, assets, asset = await _mkt_find_campaign_asset(cid, body.network, user)
    asset["caption"] = (body.caption or "").strip()
    asset["hashtags"] = [h.strip() for h in (body.hashtags or []) if h and h.strip()]
    asset["cta"] = (body.cta or "").strip()
    await db.campaigns.update_one({"id": cid}, {"$set": {"assets": assets}})
    return asset


@api.post("/marketing/campaigns/{cid}/asset/regenerate")
async def marketing_regen_asset(cid: str, body: AssetRegenReq,
                                user=Depends(require_role("lojista", "admin"))):
    c, assets, asset = await _mkt_find_campaign_asset(cid, body.network, user)
    cfg = SUPPORTED_NETWORKS[body.network]
    base_prompt = (body.prompt or "").strip() or asset.get("image_prompt") or c.get("image_prompt") or (
        f"High-end commercial lifestyle photograph of {c.get('product_name','')} in an aspirational setting")
    prompt = base_prompt
    if body.distinct:
        prompt = f"{base_prompt}. Reimagine it as {random.choice(_VARIATION_HINTS)}, keeping the same product."

    ref = None
    rp = c.get("ref_image_path")
    if rp:
        try:
            ref, _ = await run_in_threadpool(get_object, rp)
        except Exception:
            ref = None
    try:
        img = await _mkt_generate_image(prompt, ref)
    except Exception as e:
        logger.warning(f"marketing regen image failed: {e}")
        raise HTTPException(status_code=502, detail="Não foi possível gerar a imagem. Tente novamente.")
    if not img:
        raise HTTPException(status_code=502, detail="Não foi possível gerar a imagem. Tente novamente.")

    variant = await run_in_threadpool(_cover_crop_bytes, img, cfg["w"], cfg["h"])
    path = f"{APP_NAME}/campaigns/{user['user_id']}/{uuid.uuid4().hex}.jpg"
    await run_in_threadpool(put_object, path, variant, "image/jpeg")

    old_path = asset.get("image_path")
    asset["image_path"] = path
    if (body.prompt or "").strip():
        asset["image_prompt"] = body.prompt.strip()
    upd = {"assets": assets}
    if c.get("cover_path") == old_path:
        upd["cover_path"] = path
    await db.campaigns.update_one({"id": cid}, {"$set": upd})
    return asset


@api.post("/marketing/campaigns/{cid}/suggest")
async def marketing_suggest_copy(cid: str, body: SuggestReq,
                                 user=Depends(require_role("lojista", "admin"))):
    c, _assets, _asset = await _mkt_find_campaign_asset(cid, body.network, user)
    cfg = SUPPORTED_NETWORKS[body.network]
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    lang_name = {"pt": "português do Brasil", "en": "inglês", "es": "espanhol"}.get(body.language or "pt", "português do Brasil")
    system = (
        "Você é copywriter sênior de marketing digital. Crie a MELHOR legenda possível "
        f"para {cfg['label']} usando metodologia AIDA e gatilhos mentais, no idioma {lang_name}. "
        "Responda ESTRITAMENTE com JSON válido, sem markdown."
    )
    schema = {"caption": "legenda persuasiva e adequada à rede", "hashtags": ["#exemplo"], "cta": "chamada para ação"}
    prompt = (
        f"Produto/campanha: {c.get('product_name','')}\n"
        f"Conceito criativo: {c.get('concept','')}\n"
        f"Rede-alvo: {cfg['label']} (formato {cfg['ratio']})\n\n"
        "Sugira a melhor legenda para maximizar engajamento e conversão, com 4 a 8 hashtags e um CTA claro.\n"
        f"Preencha exatamente estas chaves: {json.dumps(schema, ensure_ascii=False)}"
    )
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"mktsug-{uuid.uuid4().hex[:8]}",
                   system_message=system).with_model("gemini", "gemini-3-flash-preview")
    try:
        resp = await chat.send_message(UserMessage(text=prompt))
        data = _mkt_parse_json(resp)
    except Exception as e:
        logger.warning(f"marketing suggest failed: {e}")
        raise HTTPException(status_code=502, detail="Falha ao gerar sugestão. Tente novamente.")
    return {"caption": data.get("caption", ""), "hashtags": data.get("hashtags") or [], "cta": data.get("cta", "")}


@api.post("/marketing/campaigns/{cid}/asset/track")
async def marketing_track_asset(cid: str, body: TrackReq,
                                user=Depends(require_role("lojista", "admin"))):
    action = (body.action or "").strip().lower()
    field = {"save": "saves", "copy": "copies", "open": "opens"}.get(action)
    if not field:
        raise HTTPException(status_code=400, detail="Ação inválida")
    _c, assets, asset = await _mkt_find_campaign_asset(cid, body.network, user)
    stats = asset.get("stats") or {"saves": 0, "copies": 0, "opens": 0}
    stats[field] = int(stats.get(field, 0)) + 1
    asset["stats"] = stats
    await db.campaigns.update_one({"id": cid}, {"$set": {"assets": assets}})
    return asset


@api.get("/marketing/campaigns/{cid}/kit.zip")
async def marketing_campaign_kit(cid: str, token: str = Query(""),
                                 authorization: Optional[str] = Header(None)):
    tok = ""
    if authorization and authorization.startswith("Bearer "):
        tok = authorization.split(" ", 1)[1].strip()
    elif token:
        tok = token
    user = None
    if tok:
        sess = await db.user_sessions.find_one({"session_token": tok}, {"_id": 0})
        if sess:
            user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0, "password_hash": 0})
    if not user or user.get("role") not in ("lojista", "admin", "master"):
        raise HTTPException(status_code=401, detail="Não autenticado")
    c = await db.campaigns.find_one({"id": cid}, {"_id": 0})
    if not c or (not is_master(user) and c.get("owner_id") != user["user_id"]):
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    import zipfile
    buf = io.BytesIO()
    txt_lines = [f"CAMPANHA: {c.get('product_name','')}", f"Conceito: {c.get('concept','')}", ""]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for a in (c.get("assets") or []):
            nk = a.get("network")
            try:
                content, _ct = await run_in_threadpool(get_object, a.get("image_path"))
                zf.writestr(f"{nk}.jpg", content)
            except Exception:
                pass
            tags = " ".join(a.get("hashtags") or [])
            txt_lines += [
                f"===== {a.get('label', nk)} ({a.get('ratio','')}) =====",
                a.get("caption", ""), "", tags, "",
                f"CTA: {a.get('cta','')}", "", "",
            ]
        zf.writestr("legendas.txt", "\n".join(txt_lines))
    buf.seek(0)
    fname = re.sub(r"[^a-zA-Z0-9]+", "-", c.get("product_name", "campanha")).strip("-").lower() or "campanha"
    return StreamingResponse(io.BytesIO(buf.read()), media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="kit-{fname}.zip"'})


# --------------------------------------------------- Agendamento de publicações
def _parse_dt(s: str):
    try:
        dt = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


@api.post("/marketing/campaigns/{cid}/schedule")
async def marketing_schedule_post(cid: str, body: ScheduleReq,
                                  user=Depends(require_role("lojista", "admin"))):
    c, _assets, asset = await _mkt_find_campaign_asset(cid, body.network, user)
    dt = _parse_dt(body.scheduled_at)
    if not dt:
        raise HTTPException(status_code=400, detail="Data/hora inválida")
    if dt <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Escolha uma data/hora no futuro")
    wa = (body.whatsapp or "").strip() or (user.get("whatsapp") or "").strip()
    if not wa:
        raise HTTPException(status_code=400, detail="Informe um número de WhatsApp para o lembrete")
    doc = {
        "id": new_id("sched"), "owner_id": user["user_id"], "campaign_id": cid,
        "network": body.network, "network_label": SUPPORTED_NETWORKS[body.network]["label"],
        "product_name": c.get("product_name", ""), "caption": asset.get("caption", ""),
        "hashtags": asset.get("hashtags") or [], "image_path": asset.get("image_path", ""),
        "target_whatsapp": wa, "scheduled_at": dt.isoformat(), "status": "pending",
        "created_at": now_iso(), "sent_at": None, "error": "",
    }
    await db.scheduled_posts.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/marketing/schedule")
async def marketing_list_schedule(user=Depends(require_role("lojista", "admin"))):
    q = {} if is_master(user) else {"owner_id": user["user_id"]}
    items = await db.scheduled_posts.find(q, {"_id": 0}).sort("scheduled_at", 1).to_list(200)
    return {"items": items, "whatsapp_configured": WA_CONFIGURED}


@api.delete("/marketing/schedule/{sid}")
async def marketing_cancel_schedule(sid: str, user=Depends(require_role("lojista", "admin"))):
    sp = await db.scheduled_posts.find_one({"id": sid})
    if not sp or (not is_master(user) and sp.get("owner_id") != user["user_id"]):
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    await db.scheduled_posts.update_one({"id": sid}, {"$set": {"status": "cancelled"}})
    return {"ok": True}


async def _send_scheduled_post(sp: dict):
    to = re.sub(r"\D", "", sp.get("target_whatsapp") or "")
    if not to:
        return False, "Número de WhatsApp ausente"
    net_label = sp.get("network_label") or sp.get("network", "")
    tags = " ".join(sp.get("hashtags") or [])
    text = (f"⏰ *Hora de publicar!*\n\n"
            f"Campanha: {sp.get('product_name', '')}\nRede: {net_label}\n\n"
            f"{sp.get('caption', '')}\n\n{tags}").strip()
    await wa_send({"to": to, "type": "text", "text": {"body": text}})
    base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else ""
    if base and sp.get("image_path"):
        try:
            link = f"{base}/api/files/{sp['image_path']}"
            await wa_send({"to": to, "type": "image",
                           "image": {"link": link, "caption": f"Arte para {net_label}"}})
        except Exception:
            pass
    return True, ""


async def _marketing_scheduler_loop():
    await asyncio.sleep(10)
    while True:
        try:
            now = datetime.now(timezone.utc)
            due = await db.scheduled_posts.find({"status": "pending"}, {"_id": 0}).to_list(100)
            for sp in due:
                dt = _parse_dt(sp.get("scheduled_at", ""))
                if not dt or dt > now:
                    continue
                if not WA_CONFIGURED:
                    continue  # aguarda credenciais da WhatsApp API
                try:
                    ok, err = await _send_scheduled_post(sp)
                    upd = {"status": "sent" if ok else "failed", "sent_at": now_iso()}
                    if not ok:
                        upd["error"] = err
                    await db.scheduled_posts.update_one({"id": sp["id"]}, {"$set": upd})
                except Exception as e:
                    await db.scheduled_posts.update_one(
                        {"id": sp["id"]}, {"$set": {"status": "failed", "error": str(e)[:300]}})
        except Exception as e:
            logger.warning(f"marketing scheduler loop error: {e}")
        await asyncio.sleep(60)


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


def _digits(s):
    return (s or "").replace(" ", "").replace("+", "").replace("-", "")


async def wa_reply(to: str, text: str):
    if not (WA_CONFIGURED and to):
        return
    try:
        await wa_send({"to": _digits(to), "type": "text", "text": {"body": text}})
    except Exception as e:
        logger.warning(f"WA reply failed: {e}")


async def wa_send_document(to: str, link: str, filename: str, caption: str = ""):
    if not (WA_CONFIGURED and to and link):
        return
    try:
        await wa_send({"to": _digits(to), "type": "document",
                       "document": {"link": link, "filename": filename, "caption": caption}})
    except Exception as e:
        logger.warning(f"WA document failed: {e}")


def _match_number(candidate: str, sender: str) -> bool:
    c = _digits(candidate)
    return bool(c) and bool(sender) and (c.endswith(sender[-10:]) or sender.endswith(c[-10:]))


async def _find_store_for_sender(sender: str):
    stores = await db.stores.find({"deleted": {"$ne": True}}, {"_id": 0}).to_list(1000)
    for s in stores:
        if _match_number(s.get("whatsapp"), sender):
            return s
    return None


async def _find_product_in_store(store_id: str, query: str):
    if not query:
        return None
    prods = await db.products.find({"store_id": store_id, "deleted": {"$ne": True}}, {"_id": 0}).to_list(1000)
    ql = query.strip().lower()
    for p in prods:
        if p.get("name", "").strip().lower() == ql:
            return p
    for p in prods:
        nm = p.get("name", "").strip().lower()
        if nm and (ql in nm or nm in ql):
            return p
    return None


HELP_TEXT = (
    "🛍️ *Lojas da Fronteira* — comandos do lojista:\n\n"
    "• *Cadastrar*: envie a descrição do produto (com foto, se quiser). "
    "Ex: _Camiseta Polo azul, R$ 79,90_\n"
    "• *Atualizar*: _atualizar Camiseta Polo para R$ 69,90_\n"
    "• *Desativar*: _desativar Camiseta Polo_\n"
    "• *Catálogo em PDF*: envie _catálogo_\n"
    "• *Abrir/Fechar loja*: _abrir loja_ / _fechar loja_\n"
    "• *Ver pedidos*: envie _pedidos_\n"
    "• *Criar cupom*: _criar cupom PROMO10 10%_\n"
    "• *Ajuda*: envie _ajuda_"
)


async def _record_inbound(sender, store, text, intent, result):
    await db.wa_inbound.insert_one({
        "id": new_id("wain"), "from": sender,
        "store_id": (store or {}).get("id", ""), "store_name": (store or {}).get("name", ""),
        "text": text, "intent": intent, "result": result, "created_at": now_iso(),
    })


async def _process_inbound(msg: dict):
    mid = msg.get("id")
    if not mid or await db.whatsapp_events.find_one({"message_id": mid}):
        return
    sender = _digits(msg.get("from"))
    await db.whatsapp_events.insert_one({"message_id": mid, "created_at": now_iso(), "from": sender})

    text = (msg.get("text") or {}).get("body", "") or ""
    image_path = ""
    image = msg.get("image")
    has_image = bool(image and image.get("id"))
    if has_image:
        try:
            image_path = await _download_wa_media(image["id"])
        except Exception as e:
            logger.warning(f"WA media download failed: {e}")
        text = text or image.get("caption", "")

    store = await _find_store_for_sender(sender)
    if store:
        await _handle_vendor(store, sender, text, image_path, has_image)
    elif ROOT_WHATSAPP and _match_number(ROOT_WHATSAPP, sender):
        await wa_reply(sender, "👑 Número de administrador reconhecido. A gestão de lojas, "
                               "usuários e métricas é feita pelo aplicativo Lojas da Fronteira.")
        await _record_inbound(sender, None, text, "admin", "superadmin reconhecido")
    else:
        await _handle_customer(sender, text, image_path, has_image)


async def _handle_vendor(store, sender, text, image_path, has_image):
    cmd = await interpret_command(text, has_image)
    intent = cmd.get("intent", "desconhecido")

    if intent == "ajuda":
        await wa_reply(sender, HELP_TEXT)
        await _record_inbound(sender, store, text, "ajuda", "ajuda enviada")
        return

    if intent == "abrir_loja":
        await db.stores.update_one({"id": store["id"]}, {"$set": {"is_open": True, "last_seen": now_iso()}})
        await wa_reply(sender, f"🟢 *{store['name']}* está ABERTA. Boas vendas!")
        await _record_inbound(sender, store, text, "abrir_loja", "loja aberta")
        return

    if intent == "fechar_loja":
        await db.stores.update_one({"id": store["id"]}, {"$set": {"is_open": False}})
        await wa_reply(sender, f"⚪ *{store['name']}* está FECHADA.")
        await _record_inbound(sender, store, text, "fechar_loja", "loja fechada")
        return

    if intent == "ver_pedidos":
        orders = await db.orders.find({"store_id": store["id"], "deleted": {"$ne": True}},
                                      {"_id": 0}).sort("created_at", -1).to_list(10)
        if not orders:
            await wa_reply(sender, "Você ainda não recebeu pedidos.")
        else:
            lines = [f"• {o['id'][-6:]} — {o.get('customer_name', 'cliente')} — "
                     f"R$ {o['total']:.2f} ({o['status']})" for o in orders]
            await wa_reply(sender, "🧾 *Últimos pedidos da sua loja:*\n" + "\n".join(lines))
        await _record_inbound(sender, store, text, "ver_pedidos", f"{len(orders)} pedidos")
        return

    if intent == "criar_cupom":
        code = (cmd.get("cupom_codigo") or "").strip().upper()
        val = cmd.get("cupom_valor") or 0
        ctype = "fixed" if cmd.get("cupom_tipo") == "fixed" else "percent"
        if not code or val <= 0:
            await wa_reply(sender, "Para criar um cupom informe o código e o valor. "
                                   "Ex: _criar cupom PROMO10 10%_")
            await _record_inbound(sender, store, text, "criar_cupom", "dados insuficientes")
            return
        await db.coupons.update_one(
            {"store_id": store["id"], "code": code},
            {"$set": {"id": new_id("cpn"), "store_id": store["id"], "code": code, "type": ctype,
                      "value": val, "active": True, "deleted": False, "created_at": now_iso()}},
            upsert=True)
        desc = f"{val:.0f}%" if ctype == "percent" else f"R$ {val:.2f}"
        await wa_reply(sender, f"🎟️ Cupom *{code}* criado ({desc} de desconto).")
        await _record_inbound(sender, store, text, "criar_cupom", f"cupom {code}")
        return

    if intent == "catalogo":
        base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else ""
        if base:
            link = f"{base}/api/stores/{store['id']}/catalog.pdf"
            await wa_send_document(sender, link, f"catalogo-{store['name']}.pdf",
                                   f"Catálogo de {store['name']}")
            await wa_reply(sender, "📄 Aqui está o catálogo atualizado da sua loja.")
        else:
            await wa_reply(sender, "Não foi possível gerar o catálogo agora.")
        await _record_inbound(sender, store, text, "catalogo", "catálogo enviado")
        return

    if intent in ("atualizar", "desativar"):
        target = cmd.get("alvo") or cmd.get("name")
        prod = await _find_product_in_store(store["id"], target)
        if not prod:
            await wa_reply(sender, f"Não encontrei o produto \"{target}\" na sua loja. "
                                   "Envie *catálogo* para ver os itens cadastrados.")
            await _record_inbound(sender, store, text, intent, f"produto não encontrado: {target}")
            return
        if intent == "desativar":
            await db.products.update_one({"id": prod["id"]}, {"$set": {"deleted": True}})
            await wa_reply(sender, f"✅ Produto *{prod['name']}* foi desativado do catálogo.")
            await _record_inbound(sender, store, text, "desativar", f"desativado: {prod['name']}")
            return
        updates = {}
        if cmd.get("price"):
            updates["price"] = cmd["price"]
        if cmd.get("name") and cmd["name"].strip().lower() != prod.get("name", "").strip().lower():
            updates["name"] = cmd["name"]
        if cmd.get("description"):
            updates["description"] = cmd["description"]
        if cmd.get("category") and cmd["category"] != "Outros":
            updates["category"] = cmd["category"]
        if not updates:
            await wa_reply(sender, "Não entendi o que atualizar. Ex: _atualizar "
                                   f"{prod['name']} para R$ 49,90_")
            await _record_inbound(sender, store, text, "atualizar", "sem alterações claras")
            return
        await db.products.update_one({"id": prod["id"]}, {"$set": updates})
        parts = []
        if "price" in updates: parts.append(f"preço R$ {updates['price']:.2f}")
        if "name" in updates: parts.append(f"nome '{updates['name']}'")
        if "description" in updates: parts.append("descrição")
        if "category" in updates: parts.append(f"categoria {updates['category']}")
        await wa_reply(sender, f"✅ *{prod['name']}* atualizado: {', '.join(parts)}.")
        await _record_inbound(sender, store, text, "atualizar", f"atualizado: {prod['name']}")
        return

    if intent == "criar" or has_image:
        if has_image:
            parsed = await extract_product(text, image_path)
        elif cmd.get("name"):
            parsed = cmd
        else:
            parsed = await extract_product(text, image_path)
        name = parsed.get("name") or "Produto"
        doc = {"id": new_id("prod"), "store_id": store["id"], "name": name,
               "description": parsed.get("description", ""),
               "price": float(parsed.get("price", 0) or 0), "image": image_path,
               "category": parsed.get("category", "Outros"),
               "deleted": False, "created_at": now_iso(), "source": "whatsapp"}
        await db.products.insert_one(doc)
        await wa_reply(sender, f"✅ Produto cadastrado: *{name}* — R$ {doc['price']:.2f} "
                               f"({doc['category']}).\nEnvie *catálogo* para conferir.")
        await _record_inbound(sender, store, text, "criar", f"criado: {name}")
        return

    await wa_reply(sender, "Não entendi 🤔\n\n" + HELP_TEXT)
    await _record_inbound(sender, store, text, "desconhecido", "ajuda enviada")


CUSTOMER_HELP = (
    "🛒 *Lojas da Fronteira* — comprar pelo WhatsApp:\n\n"
    "• *Procurar*: descreva o produto (ou envie uma foto). Ex: _tênis de corrida nº 42_\n"
    "• *Adicionar*: _adicionar 2_ (item 2 da lista) — pode dizer a quantidade\n"
    "• *Ver carrinho*: envie _carrinho_\n"
    "• *Remover*: _remover 1_\n"
    "• *Finalizar*: envie _finalizar_ e confirme com *SIM*\n"
    "• *Ajuda*: envie _ajuda_"
)


def _cart_link(cart):
    base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else ""
    return f"{base}/api/wa/cart/{cart['id']}/pdf?token={cart['token']}" if base else ""


async def _reply_cart(sender, cart):
    items = cart.get("items", [])
    lines = [f"{i+1}. {it['qty']}x {it['name']} — {it['store_name']} — "
             f"R$ {it['price'] * it['qty']:.2f}" for i, it in enumerate(items)]
    total = sum(it["price"] * it["qty"] for it in items)
    await wa_reply(sender, "🛒 *Seu carrinho:*\n" + "\n".join(lines) + f"\n\n*Total: R$ {total:.2f}*")
    link = _cart_link(cart)
    if link:
        await wa_send_document(sender, link, f"carrinho-{cart['id']}.pdf", "Seu carrinho em PDF")


async def _create_orders_from_cart(cart):
    groups = {}
    for it in cart.get("items", []):
        groups.setdefault(it["store_id"], []).append(it)
    order_ids = []
    for sid, items in groups.items():
        store = await db.stores.find_one({"id": sid}, {"_id": 0}) or {}
        subtotal = round(sum(i["price"] * i["qty"] for i in items), 2)
        doc = {"id": new_id("order"), "token": uuid.uuid4().hex, "store_id": sid,
               "store_name": store.get("name", items[0].get("store_name", "")),
               "store_whatsapp": store.get("whatsapp", ""),
               "customer_user_id": cart.get("customer_user_id", ""),
               "customer_name": cart.get("customer_name", "") or cart.get("customer_phone", ""),
               "items": [{"product_id": i["product_id"], "name": i["name"],
                          "price": i["price"], "qty": i["qty"]} for i in items],
               "subtotal": subtotal, "discount": 0.0, "coupon_code": "", "total": subtotal,
               "notes": "", "customer_whatsapp": cart.get("customer_phone", ""),
               "status": "novo", "editable": True, "deleted": False, "created_at": now_iso(),
               "source": "whatsapp", "general_order_id": cart["id"], "sent_to_vendor": False}
        await db.orders.insert_one(doc)
        order_ids.append(doc["id"])
    await db.wa_carts.update_one({"id": cart["id"]}, {"$set": {"order_ids": order_ids}})
    return order_ids


async def _send_cart_orders(cart):
    doc = await db.wa_carts.find_one({"id": cart["id"]}, {"_id": 0}) or {}
    n = 0
    for oid in doc.get("order_ids", []):
        o = await db.orders.find_one({"id": oid, "deleted": {"$ne": True}}, {"_id": 0})
        if not o:
            continue
        try:
            await notify_order(o, "created")
        except Exception as e:
            logger.warning(f"cart notify failed: {e}")
        await db.orders.update_one({"id": oid}, {"$set": {"sent_to_vendor": True}})
        n += 1
    return n


async def _handle_customer(sender, text, image_path, has_image):
    cart = await _get_or_create_cart(sender)
    low = _norm(text)
    affirm = low in {"sim", "s", "confirmar", "confirmo", "ok", "pode", "isso", "claro",
                     "confirmado", "quero"} or low.startswith("sim")
    negate = low in {"nao", "n", "cancelar", "cancela", "depois", "espera", "espere"} or low.startswith("nao")

    pending = cart.get("pending_action", "")
    if pending == "confirm_create":
        if affirm:
            await _create_orders_from_cart(cart)
            await db.wa_carts.update_one({"id": cart["id"]}, {"$set": {"pending_action": "confirm_send"}})
            link = _cart_link(cart)
            if link:
                await wa_send_document(sender, link, f"pedido-{cart['id']}.pdf", "Seu pedido")
            await wa_reply(sender, "✅ Pedido criado! Confirma o *envio aos lojistas*? "
                                   "Responda *SIM* para enviar.")
            await _record_inbound(sender, None, text, "confirmar", "pedido criado")
        elif negate:
            await db.wa_carts.update_one({"id": cart["id"]}, {"$set": {"pending_action": ""}})
            await wa_reply(sender, "Ok! Seu carrinho continua salvo. "
                                   "Envie *finalizar* quando quiser fechar.")
            await _record_inbound(sender, None, text, "confirmar", "criação recusada")
        else:
            await wa_reply(sender, "Responda *SIM* para criar o pedido ou *não* para continuar comprando.")
        return

    if pending == "confirm_send":
        if affirm:
            n = await _send_cart_orders(cart)
            await db.wa_carts.update_one({"id": cart["id"]}, {"$set": {"status": "sent", "pending_action": ""}})
            await wa_reply(sender, f"🚀 Enviado! {n} loja(s) receberam seus pedidos. "
                                   "Cada lojista vê apenas os itens da própria loja. Obrigado pela compra!")
            await _record_inbound(sender, None, text, "confirmar", f"enviado a {n} lojas")
        elif negate:
            await db.wa_carts.update_one({"id": cart["id"]}, {"$set": {"pending_action": ""}})
            await wa_reply(sender, "Ok! Os pedidos foram criados mas *não* enviados aos lojistas. "
                                   "Envie *finalizar* novamente para enviar depois.")
            await _record_inbound(sender, None, text, "confirmar", "envio recusado")
        else:
            await wa_reply(sender, "Responda *SIM* para enviar aos lojistas ou *não* para enviar depois.")
        return

    cmd = await interpret_customer(text, has_image)
    intent = cmd.get("intent", "desconhecido")

    if intent == "ajuda":
        await wa_reply(sender, CUSTOMER_HELP)
        await _record_inbound(sender, None, text, "ajuda", "ajuda cliente")
        return

    if intent == "cancelar":
        await db.wa_carts.update_one({"id": cart["id"]}, {"$set": {"items": [], "pending_action": ""}})
        await wa_reply(sender, "🗑️ Carrinho esvaziado.")
        await _record_inbound(sender, None, text, "cancelar", "carrinho limpo")
        return

    if intent == "buscar" or (has_image and intent in ("desconhecido", "buscar")):
        query = cmd.get("query") or text
        if has_image:
            try:
                desc = await extract_product(text or "", image_path)
                query = " ".join([desc.get("name", ""), desc.get("category", ""),
                                  desc.get("description", "")]).strip() or query
            except Exception:
                pass
        results = await search_products_global(query, 8)
        if not results:
            await wa_reply(sender, f"Não encontrei produtos para \"{query}\". "
                                   "Tente descrever de outro jeito 🙂")
            await _record_inbound(sender, None, text, "buscar", f"0 resultados: {query}")
            return
        cand = [{"product_id": p["id"], "store_id": p["store_id"], "store_name": p["store_name"],
                 "name": p["name"], "price": float(p.get("price", 0) or 0)} for p in results]
        await db.wa_carts.update_one({"id": cart["id"]}, {"$set": {"candidates": cand}})
        lines = [f"{i+1}. {c['name']} — {c['store_name']} — R$ {c['price']:.2f}"
                 for i, c in enumerate(cand)]
        await wa_reply(sender, "🔎 *Encontrei estas opções:*\n" + "\n".join(lines) +
                       "\n\nEnvie *adicionar 2* para colocar o item 2 no carrinho "
                       "(pode indicar a quantidade, ex: _adicionar 2 x3_).")
        await _record_inbound(sender, None, text, "buscar", f"{len(cand)} resultados: {query}")
        return

    if intent == "adicionar":
        cand = cart.get("candidates", [])
        idx = cmd.get("index", 0)
        if not cand:
            await wa_reply(sender, "Primeiro descreva ou envie a foto do produto que procura 🙂")
            return
        if idx < 1 or idx > len(cand):
            await wa_reply(sender, f"Escolha um número de 1 a {len(cand)}.")
            return
        c = cand[idx - 1]
        qty = cmd.get("qty", 1)
        items = cart.get("items", [])
        for it in items:
            if it["product_id"] == c["product_id"]:
                it["qty"] += qty
                break
        else:
            items.append({**c, "qty": qty})
        await db.wa_carts.update_one({"id": cart["id"]}, {"$set": {"items": items}})
        total = sum(i["price"] * i["qty"] for i in items)
        await wa_reply(sender, f"🛒 Adicionado: {qty}x {c['name']}.\n"
                               f"Carrinho: {len(items)} item(ns) — total R$ {total:.2f}.\n"
                               "Envie *carrinho* para ver ou *finalizar* para fechar.")
        await _record_inbound(sender, None, text, "adicionar", f"{qty}x {c['name']}")
        return

    if intent == "remover":
        items = cart.get("items", [])
        idx = cmd.get("index", 0)
        if idx < 1 or idx > len(items):
            await wa_reply(sender, "Envie *carrinho* para ver os números e depois *remover N*.")
            return
        removed = items.pop(idx - 1)
        await db.wa_carts.update_one({"id": cart["id"]}, {"$set": {"items": items}})
        await wa_reply(sender, f"Removido: {removed['name']}.")
        await _record_inbound(sender, None, text, "remover", removed["name"])
        return

    if intent == "ver_carrinho":
        if not cart.get("items"):
            await wa_reply(sender, "Seu carrinho está vazio. Descreva um produto para começar 🙂")
            return
        await _reply_cart(sender, cart)
        await _record_inbound(sender, None, text, "ver_carrinho", f"{len(cart['items'])} itens")
        return

    if intent == "finalizar":
        if not cart.get("items"):
            await wa_reply(sender, "Seu carrinho está vazio.")
            return
        await _reply_cart(sender, cart)
        await db.wa_carts.update_one({"id": cart["id"]}, {"$set": {"pending_action": "confirm_create"}})
        await wa_reply(sender, "Deseja *criar* este pedido? Responda *SIM* para confirmar.")
        await _record_inbound(sender, None, text, "finalizar", "aguardando confirmação")
        return

    await wa_reply(sender, "Não entendi 🤔\n\n" + CUSTOMER_HELP)
    await _record_inbound(sender, None, text, "desconhecido", "ajuda cliente")


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
    prev = await db.stores.find_one({"id": sid}, {"_id": 0, "is_open": 1})
    was_open = bool((prev or {}).get("is_open"))
    updates = {"is_open": body.is_open}
    if body.is_open:
        updates["last_seen"] = now_iso()
    await db.stores.update_one({"id": sid}, {"$set": updates})
    s = await db.stores.find_one({"id": sid}, {"_id": 0})
    if body.is_open and not was_open:
        try:
            await notify_store_open(s)
        except Exception as e:
            logger.warning(f"notify_store_open failed: {e}")
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


async def _record(order_id, target, channel, to, body, status, subject="", store_id="", wa_link=""):
    await db.notifications.insert_one({
        "id": new_id("ntf"), "order_id": order_id, "store_id": store_id, "target": target,
        "channel": channel, "to": to, "subject": subject, "body": body, "status": status,
        "wa_link": wa_link, "created_at": now_iso(),
    })


async def _wa_or_sim(order_id, target, to, body, store_id="", template=None):
    """Hybrid WhatsApp delivery (approved plan C):
    1) free-form text  -> works INSIDE the 24h customer-service window        [status=sent]
    2) approved utility template -> works OUTSIDE the window (if configured)   [status=template]
    3) manual wa.me link -> safety net so a notification is never lost         [status=link]
    When WhatsApp isn't configured at all we still return an actionable link   [status=simulated].
    """
    if not to:
        return
    wa_link = _wa_me(to, body)
    if WA_CONFIGURED:
        # 1) free-form session message
        try:
            await wa_send({"to": _wa_norm(to), "type": "text", "text": {"body": body}})
            await _record(order_id, target, "whatsapp", to, body, "sent", store_id=store_id, wa_link=wa_link)
            return
        except Exception as e:
            logger.warning(f"WA text failed ({target}): {e}")
        # 2) approved utility template (business-initiated, out-of-window)
        if template and template.get("name"):
            try:
                await wa_send_template(to, template["name"], template.get("lang", WA_TEMPLATE_LANG),
                                       template.get("params"))
                await _record(order_id, target, "whatsapp", to, body, "template",
                              store_id=store_id, wa_link=wa_link)
                return
            except Exception as e:
                logger.warning(f"WA template failed ({target}): {e}")
    # 3) safety net: manual click-to-chat link (nothing is lost)
    await _record(order_id, target, "whatsapp", to, body,
                  "link" if wa_link else "simulated", store_id=store_id, wa_link=wa_link)


async def notify_order(o, kind):
    """kind: 'created' | 'status'. Notifica lojista + admin (WhatsApp) e cliente (WhatsApp ou e-mail)."""
    store = await db.stores.find_one({"id": o["store_id"]}, {"_id": 0}) or {}
    link = _order_link(o)
    link_txt = f"\nLink do pedido (PDF): {link}" if link else ""
    if kind == "created":
        head = f"🆕 Novo pedido — {o['store_name']}"
    elif kind == "edited":
        head = f"✏️ Pedido ajustado pelo lojista — {o['store_name']}"
    else:
        head = f"🔔 Pedido atualizado ({o.get('status','')}) — {o['store_name']}"
    base_body = (f"{head}\nCliente: {o.get('customer_name','')}\n{_order_lines(o)}\n"
                 f"Total: R$ {o['total']:.2f}{link_txt}")
    # Template de utilidade (fallback fora da janela de 24h). Desativado enquanto o
    # WA_TEMPLATE_* não estiver definido (aguarda criação/aprovação na Meta).
    _cust = o.get("customer_name", "") or "cliente"
    _total = f"R$ {o['total']:.2f}"
    _link = link or "-"
    tmpl_order = ({"name": WA_TEMPLATE_ORDER, "lang": WA_TEMPLATE_LANG,
                   "params": [_cust, o["store_name"], _total, _link]}
                  if WA_TEMPLATE_ORDER else None)
    tmpl_status = ({"name": WA_TEMPLATE_STATUS, "lang": WA_TEMPLATE_LANG,
                    "params": [_cust, o["store_name"], o.get("status", "atualizado"), _link]}
                   if WA_TEMPLATE_STATUS else None)
    tmpl = tmpl_order if kind in ("created", "edited") else tmpl_status
    # Lojista
    await _wa_or_sim(o["id"], "lojista", store.get("whatsapp", ""), base_body, o["store_id"], template=tmpl)
    # Administrador responsável (whatsapp da loja) ou root
    admin_to = store.get("admin_whatsapp") or ROOT_WHATSAPP
    await _wa_or_sim(o["id"], "admin", admin_to, base_body, o["store_id"], template=tmpl)
    # Cliente: WhatsApp se houver, senão e-mail
    cust_wa = o.get("customer_whatsapp") or ""
    if kind == "created":
        cust_body = (f"✅ Pedido confirmado em {o['store_name']}!\n{_order_lines(o)}\n"
                     f"Total: R$ {o['total']:.2f}{link_txt}\nObrigado pela compra!")
        subj = "Seu pedido foi confirmado — Lojas da Fronteira"
    elif kind == "edited":
        cust_body = (f"✏️ O lojista ajustou seu pedido em {o['store_name']}.\n{_order_lines(o)}\n"
                     f"Novo total: R$ {o['total']:.2f}{link_txt}")
        subj = f"Seu pedido foi ajustado — {o['store_name']}"
    else:
        cust_body = (f"🔔 Seu pedido em {o['store_name']} agora está: {o.get('status','')}.{link_txt}")
        subj = f"Atualização do seu pedido ({o.get('status','')}) — Lojas da Fronteira"
    if cust_wa:
        await _wa_or_sim(o["id"], "cliente", cust_wa, cust_body, o["store_id"], template=tmpl)
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
                await _record(o["id"], "cliente", "email", email, cust_body, "sent", subj, o["store_id"])
            except Exception as e:
                logger.warning(f"Email notify failed: {e}")
                await _record(o["id"], "cliente", "email", email, cust_body, "failed", subj, o["store_id"])


async def notify_store_open(store):
    favs = await db.favorites.find({"store_id": store["id"]}, {"_id": 0, "user_id": 1}).to_list(3000)
    body = f"🟢 {store['name']} abriu agora! Aproveite para comprar."
    subj = f"{store['name']} abriu agora — Lojas da Fronteira"
    for f in favs:
        u = await db.users.find_one({"user_id": f["user_id"]}, {"_id": 0, "whatsapp": 1, "email": 1})
        if not u:
            continue
        if u.get("whatsapp"):
            await _wa_or_sim(f"open_{store['id']}", "cliente", u["whatsapp"], body, store["id"])
        elif u.get("email"):
            html = (f'<table role="presentation" width="100%"><tr><td style="padding:24px;'
                    f'font-family:Arial,sans-serif;color:#1A1C19"><h2 style="color:#4A7C59">'
                    f'{escape(store["name"])} abriu agora!</h2>'
                    f'<p>Sua loja favorita está aberta. Aproveite para comprar.</p></td></tr></table>')
            try:
                await send_email(to=u["email"], subject=subj, html=html)
                await _record(f"open_{store['id']}", "cliente", "email", u["email"], body, "sent", subj, store["id"])
            except Exception as e:
                logger.warning(f"open notify email failed: {e}")


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


@api.post("/orders/{order_id}/resend")
async def resend_order(order_id: str, user=Depends(get_current_user)):
    o = await db.orders.find_one({"id": order_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    ok = (user["role"] == "admin" or user["user_id"] == o["customer_user_id"]
          or (user["role"] == "lojista" and user.get("store_id") == o["store_id"]))
    if not ok:
        raise HTTPException(status_code=403, detail="Acesso negado")
    await notify_order(o, "status")
    return {"ok": True}


@api.put("/auth/whatsapp")
async def set_my_whatsapp(body: dict, user=Depends(get_current_user)):
    wa = str(body.get("whatsapp", "")).strip()
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"whatsapp": wa}})
    return await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})


@api.get("/admin/notifications")
async def admin_notifications(store_id: str = Query(""), status: str = Query(""),
                              user=Depends(require_role("admin"))):
    q = {}
    if store_id:
        q["store_id"] = store_id
    if status:
        q["status"] = status
    notifs = await db.notifications.find(q, {"_id": 0}).sort("created_at", -1).to_list(300)
    stores = await db.stores.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    smap = {s["id"]: s["name"] for s in stores}
    for n in notifs:
        n["store_name"] = smap.get(n.get("store_id", ""), "—")
    return notifs


@api.get("/admin/wa-inbound")
async def admin_wa_inbound(user=Depends(require_role("admin"))):
    return await db.wa_inbound.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)


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
        await db.users.create_index("username", unique=True, sparse=True)
        await db.campaigns.create_index("owner_id")
        await db.campaigns.create_index("created_at")
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
    try:
        await seed_groups()
    except Exception as e:
        logger.warning(f"seed groups failed: {e}")
    try:
        await seed_accounts()
        logger.info("system accounts seeded")
    except Exception as e:
        logger.warning(f"seed accounts failed: {e}")
    try:
        asyncio.create_task(_marketing_scheduler_loop())
        logger.info("marketing scheduler started")
    except Exception as e:
        logger.warning(f"scheduler start failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    client.close()
