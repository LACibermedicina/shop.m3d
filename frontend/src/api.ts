import { storage } from "@/src/utils/storage";

const BASE = process.env.EXPO_PUBLIC_BACKEND_URL;
const TOKEN_KEY = "feira_session_token";

let memToken: string | null = null;

export async function setToken(token: string | null) {
  memToken = token;
  if (token) await storage.secureSet(TOKEN_KEY, token);
  else await storage.secureRemove(TOKEN_KEY);
}

export async function loadToken(): Promise<string | null> {
  if (memToken) return memToken;
  const t = await storage.secureGet<string>(TOKEN_KEY, "");
  memToken = t || null;
  return memToken;
}

export function fileUrl(path?: string | null): string | null {
  if (!path) return null;
  return `${BASE}/api/files/${path}`;
}

type Opts = {
  method?: string;
  body?: any;
  auth?: boolean;
  headers?: Record<string, string>;
};

export async function apiRequest<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const { method = "GET", body, auth = true, headers = {} } = opts;
  const h: Record<string, string> = { "Content-Type": "application/json", ...headers };
  if (auth) {
    const t = await loadToken();
    if (t) h["Authorization"] = `Bearer ${t}`;
  }
  const res = await fetch(`${BASE}/api${path}`, {
    method,
    headers: h,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = "Erro na requisição";
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch {}
    const err: any = new Error(detail);
    err.status = res.status;
    throw err;
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return (await res.text()) as any;
}

export async function uploadImage(uri: string): Promise<string> {
  const t = await loadToken();
  const form = new FormData();
  const name = `photo_${Date.now()}.jpg`;
  // native shape (works in Expo Go / device). Web preview also accepts blob below.
  // @ts-ignore
  if (typeof window !== "undefined" && window.location && uri.startsWith("blob:")) {
    const blob = await (await fetch(uri)).blob();
    form.append("file", blob, name);
  } else {
    // @ts-ignore
    form.append("file", { uri, name, type: "image/jpeg" });
  }
  const res = await fetch(`${BASE}/api/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${t}` },
    body: form,
  });
  if (!res.ok) throw new Error("Falha no upload");
  const j = await res.json();
  return j.path;
}

export const api = {
  me: () => apiRequest("/auth/me"),
  logout: () => apiRequest("/auth/logout", { method: "POST" }),
  session: (session_id: string) =>
    apiRequest("/auth/session", { method: "POST", body: { session_id }, auth: false }),
  devLogin: (email: string, role: string) =>
    apiRequest("/auth/dev-login", {
      method: "POST",
      body: { email, role, name: email.split("@")[0] },
      auth: false,
    }),
  deleteAccount: () => apiRequest("/auth/me", { method: "DELETE" }),
  orderNotifications: (id: string, token?: string) =>
    apiRequest(`/orders/${id}/notifications${token ? `?token=${token}` : ""}`),
  resendOrder: (id: string) => apiRequest(`/orders/${id}/resend`, { method: "POST" }),
  setMyWhatsapp: (whatsapp: string) =>
    apiRequest("/auth/whatsapp", { method: "PUT", body: { whatsapp } }),
  adminNotifications: (storeId = "", status = "") =>
    apiRequest(`/admin/notifications?store_id=${encodeURIComponent(storeId)}&status=${encodeURIComponent(status)}`),
  adminWaInbound: () => apiRequest("/admin/wa-inbound"),

  stores: () => apiRequest("/stores", { auth: false }),
  home: () => apiRequest("/home", { auth: false }),
  search: (q: string) => apiRequest(`/search?q=${encodeURIComponent(q)}`, { auth: false }),
  whatsappStatus: () => apiRequest("/whatsapp/status", { auth: false }),
  sendOrderWhatsApp: (orderId: string) =>
    apiRequest("/orders/send-whatsapp", { method: "POST", body: { order_id: orderId } }),
  store: (id: string) => apiRequest(`/stores/${id}`, { auth: false }),
  createStore: (b: any) => apiRequest("/stores", { method: "POST", body: b }),
  updateStore: (id: string, b: any) => apiRequest(`/stores/${id}`, { method: "PUT", body: b }),
  deleteStore: (id: string) => apiRequest(`/stores/${id}`, { method: "DELETE" }),

  products: (storeId: string, sort = "recent", category = "") =>
    apiRequest(`/stores/${storeId}/products?sort=${sort}${category ? `&category=${encodeURIComponent(category)}` : ""}`, { auth: false }),
  reviews: (storeId: string) => apiRequest(`/stores/${storeId}/reviews`, { auth: false }),
  addReview: (storeId: string, rating: number, comment: string) =>
    apiRequest(`/stores/${storeId}/reviews`, { method: "POST", body: { rating, comment } }),
  favoriteIds: () => apiRequest("/my/favorite-ids"),
  favorites: () => apiRequest("/my/favorites"),
  addFavorite: (storeId: string) => apiRequest(`/favorites/${storeId}`, { method: "POST" }),
  removeFavorite: (storeId: string) => apiRequest(`/favorites/${storeId}`, { method: "DELETE" }),
  vendorReport: () => apiRequest("/vendor/report"),
  setStoreOpen: (isOpen: boolean) =>
    apiRequest("/vendor/store/open", { method: "PUT", body: { is_open: isOpen } }),
  heartbeat: () => apiRequest("/vendor/heartbeat", { method: "POST" }),
  createCoupon: (b: any) => apiRequest("/coupons", { method: "POST", body: b }),
  vendorCoupons: () => apiRequest("/vendor/coupons"),
  deleteCoupon: (id: string) => apiRequest(`/coupons/${id}`, { method: "DELETE" }),
  applyCoupon: (storeId: string, code: string, subtotal: number) =>
    apiRequest("/coupons/apply", { method: "POST", body: { store_id: storeId, code, subtotal } }),
  createProduct: (b: any) => apiRequest("/products", { method: "POST", body: b }),
  updateProduct: (id: string, b: any) => apiRequest(`/products/${id}`, { method: "PUT", body: b }),
  deleteProduct: (id: string) => apiRequest(`/products/${id}`, { method: "DELETE" }),
  aiImport: (b: any) => apiRequest("/products/ai-import", { method: "POST", body: b }),

  createOrder: (b: any) => apiRequest("/orders", { method: "POST", body: b }),
  order: (id: string, token?: string) =>
    apiRequest(`/orders/${id}${token ? `?token=${token}` : ""}`),
  myOrders: () => apiRequest("/my/orders"),
  vendorOrders: () => apiRequest("/vendor/orders"),
  updateOrderItems: (id: string, items: any[]) =>
    apiRequest(`/orders/${id}`, { method: "PUT", body: { items } }),
  updateOrderStatus: (id: string, status: string) =>
    apiRequest(`/orders/${id}/status`, { method: "PUT", body: { status } }),
  pdfUrl: (id: string, token: string) =>
    `${BASE}/api/orders/${id}/pdf?token=${token}`,

  metrics: () => apiRequest("/admin/metrics"),
  users: () => apiRequest("/admin/users"),
  setUserRole: (id: string, role: string, storeId?: string | null, adminId?: string | null) =>
    apiRequest(`/admin/users/${id}/role`, { method: "PUT", body: { role, store_id: storeId, admin_id: adminId ?? null } }),
  // Master (super-admin) endpoints
  masterOverview: () => apiRequest("/master/overview"),
  masterCreateUser: (email: string, role: string, name?: string) =>
    apiRequest("/master/users", { method: "POST", body: { email, role, name } }),
  masterDeleteUser: (id: string) => apiRequest(`/master/users/${id}`, { method: "DELETE" }),
  masterAssignStore: (storeId: string, adminId: string | null) =>
    apiRequest(`/master/stores/${storeId}/assign`, { method: "PUT", body: { admin_id: adminId } }),

  // Invites
  createInvite: (storeId: string, clientEmail?: string) =>
    apiRequest("/invites", { method: "POST", body: { store_id: storeId, client_email: clientEmail || "" } }),
  invites: () => apiRequest("/invites"),
  revokeInvite: (id: string) => apiRequest(`/invites/${id}`, { method: "DELETE" }),
  getInvite: (token: string) => apiRequest(`/invite/${token}`, { auth: false }),
  acceptInvite: (token: string) => apiRequest(`/invite/${token}/accept`, { method: "POST" }),
  catalogStores: () => apiRequest("/my/catalog-stores"),

  // Personal shopping catalog
  addCatalogItem: (storeId: string, productId: string, qty = 1, note = "") =>
    apiRequest("/catalog", { method: "POST", body: { store_id: storeId, product_id: productId, qty, note } }),
  catalog: (storeId = "", category = "", q = "") =>
    apiRequest(`/catalog?store_id=${encodeURIComponent(storeId)}&category=${encodeURIComponent(category)}&q=${encodeURIComponent(q)}`),
  updateCatalogItem: (id: string, qty?: number, note?: string) =>
    apiRequest(`/catalog/${id}`, { method: "PUT", body: { qty, note } }),
  removeCatalogItem: (id: string) => apiRequest(`/catalog/${id}`, { method: "DELETE" }),
  sendCatalog: (itemIds: string[] | null, notes = "", customerName = "", customerWhatsapp = "") =>
    apiRequest("/catalog/send", { method: "POST", body: { item_ids: itemIds, notes, customer_name: customerName, customer_whatsapp: customerWhatsapp } }),
  catalogReportUrl: async (storeId = "", category = "") => {
    const t = await loadToken();
    return `${BASE}/api/catalog/report.pdf?store_id=${encodeURIComponent(storeId)}&category=${encodeURIComponent(category)}&token=${encodeURIComponent(t || "")}`;
  },

  // Translation
  translate: (texts: string[], target: string) =>
    apiRequest("/translate", { method: "POST", body: { texts, target }, auth: false }),
};
