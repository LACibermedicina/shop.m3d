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
};

const VendorOrdersCtx = createContext<Ctx>(null as any);
export const useVendorOrders = () => useContext(VendorOrdersCtx);

const POLL_MS = 15000;

export function VendorOrdersProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastSeen, setLastSeen] = useState<number>(0);
  const seenKey = `vendor_orders_seen_${user?.user_id || "x"}`;
  const timer = useRef<any>(null);

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

  useEffect(() => {
    if (!user || (user.role !== "lojista" && user.role !== "admin")) return;
    refresh();
    timer.current = setInterval(refresh, POLL_MS);
    const sub = AppState.addEventListener("change", (s) => {
      if (s === "active") refresh();
    });
    return () => {
      if (timer.current) clearInterval(timer.current);
      sub.remove();
    };
  }, [user, refresh]);

  const newCount = orders.filter((o) => {
    const t = new Date(o.created_at).getTime();
    return t > lastSeen;
  }).length;

  const markSeen = useCallback(() => {
    const now = Date.now();
    setLastSeen(now);
    storage.setItem(seenKey, String(now));
  }, [seenKey]);

  return (
    <VendorOrdersCtx.Provider value={{ orders, loading, newCount, refresh, markSeen }}>
      {children}
    </VendorOrdersCtx.Provider>
  );
}
