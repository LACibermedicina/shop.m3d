import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { AppState } from "react-native";
import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { storage } from "@/src/utils/storage";

type Ctx = {
  orders: any[];
  loading: boolean;
  newCount: number;
  refresh: () => Promise<void>;
  markSeen: () => void;
  storeOpen: boolean;
  savingOpen: boolean;
  toggleOpen: (v: boolean) => Promise<void>;
};

const VendorOrdersCtx = createContext<Ctx>(null as any);
export const useVendorOrders = () => useContext(VendorOrdersCtx);

const POLL_MS = 15000;
const HEARTBEAT_MS = 25000;

export function VendorOrdersProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastSeen, setLastSeen] = useState<number>(0);
  const [storeOpen, setStoreOpen] = useState(false);
  const [savingOpen, setSavingOpen] = useState(false);
  const seenKey = `vendor_orders_seen_${user?.user_id || "x"}`;
  const pollTimer = useRef<any>(null);
  const beatTimer = useRef<any>(null);
  const openRef = useRef(false);

  useEffect(() => {
    openRef.current = storeOpen;
  }, [storeOpen]);

  useEffect(() => {
    (async () => {
      const s = await storage.getItem<string>(seenKey, "0");
      setLastSeen(Number(s) || 0);
    })();
  }, [seenKey]);

  const refresh = useCallback(async () => {
    try {
      const data = await api.vendorOrders();
      setOrders(data);
    } catch {
      // ignore transient errors
    } finally {
      setLoading(false);
    }
  }, []);

  const loadStore = useCallback(async () => {
    if (!user?.store_id) return;
    try {
      const s = await api.store(user.store_id);
      setStoreOpen(!!s.is_open && !!s.online);
    } catch {}
  }, [user?.store_id]);

  const beat = useCallback(async () => {
    if (!openRef.current) return;
    try {
      await api.heartbeat();
    } catch {}
  }, []);

  useEffect(() => {
    if (!user || (user.role !== "lojista" && user.role !== "admin")) return;
    refresh();
    loadStore();
    pollTimer.current = setInterval(refresh, POLL_MS);
    beatTimer.current = setInterval(beat, HEARTBEAT_MS);
    const sub = AppState.addEventListener("change", (s) => {
      if (s === "active") {
        refresh();
        beat();
      }
    });
    return () => {
      if (pollTimer.current) clearInterval(pollTimer.current);
      if (beatTimer.current) clearInterval(beatTimer.current);
      sub.remove();
    };
  }, [user, refresh, loadStore, beat]);

  const toggleOpen = useCallback(async (v: boolean) => {
    setSavingOpen(true);
    try {
      await api.setStoreOpen(v);
      setStoreOpen(v);
      if (v) await api.heartbeat();
    } catch {
    } finally {
      setSavingOpen(false);
    }
  }, []);

  const newCount = orders.filter((o) => new Date(o.created_at).getTime() > lastSeen).length;

  const markSeen = useCallback(() => {
    const now = Date.now();
    setLastSeen(now);
    storage.setItem(seenKey, String(now));
  }, [seenKey]);

  return (
    <VendorOrdersCtx.Provider
      value={{ orders, loading, newCount, refresh, markSeen, storeOpen, savingOpen, toggleOpen }}
    >
      {children}
    </VendorOrdersCtx.Provider>
  );
}
