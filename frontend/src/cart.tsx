import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { storage } from "@/src/utils/storage";

export type CartItem = {
  product_id: string;
  name: string;
  price: number;
  image?: string;
  qty: number;
  store_id: string;
  store_name: string;
  store_whatsapp: string;
};

type CartCtx = {
  items: CartItem[];
  add: (item: Omit<CartItem, "qty">) => void;
  setQty: (product_id: string, qty: number) => void;
  remove: (product_id: string) => void;
  clear: () => void;
  clearStore: (store_id: string) => void;
  count: number;
  total: number;
};

const Ctx = createContext<CartCtx>(null as any);
export const useCart = () => useContext(Ctx);
const KEY = "feira_cart_v1";

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);

  useEffect(() => {
    (async () => {
      const saved = await storage.getItem<string>(KEY, "");
      if (saved) {
        try {
          setItems(JSON.parse(saved));
        } catch {}
      }
    })();
  }, []);

  const persist = useCallback((next: CartItem[]) => {
    setItems(next);
    storage.setItem(KEY, JSON.stringify(next));
  }, []);

  const add = useCallback(
    (item: Omit<CartItem, "qty">) => {
      setItems((prev) => {
        const idx = prev.findIndex((i) => i.product_id === item.product_id);
        let next;
        if (idx >= 0) {
          next = [...prev];
          next[idx] = { ...next[idx], qty: next[idx].qty + 1 };
        } else {
          next = [...prev, { ...item, qty: 1 }];
        }
        storage.setItem(KEY, JSON.stringify(next));
        return next;
      });
    },
    []
  );

  const setQty = useCallback((product_id: string, qty: number) => {
    setItems((prev) => {
      let next = prev.map((i) => (i.product_id === product_id ? { ...i, qty } : i));
      next = next.filter((i) => i.qty > 0);
      storage.setItem(KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const remove = useCallback((product_id: string) => {
    setItems((prev) => {
      const next = prev.filter((i) => i.product_id !== product_id);
      storage.setItem(KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const clear = useCallback(() => persist([]), [persist]);
  const clearStore = useCallback(
    (store_id: string) =>
      setItems((prev) => {
        const next = prev.filter((i) => i.store_id !== store_id);
        storage.setItem(KEY, JSON.stringify(next));
        return next;
      }),
    []
  );

  const count = items.reduce((a, i) => a + i.qty, 0);
  const total = items.reduce((a, i) => a + i.qty * i.price, 0);

  return (
    <Ctx.Provider value={{ items, add, setQty, remove, clear, clearStore, count, total }}>
      {children}
    </Ctx.Provider>
  );
}
