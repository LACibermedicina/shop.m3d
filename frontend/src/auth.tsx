import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { Platform } from "react-native";
import * as WebBrowser from "expo-web-browser";
import * as Linking from "expo-linking";
import { api, setToken, loadToken } from "@/src/api";

WebBrowser.maybeCompleteAuthSession();

export type User = {
  user_id: string;
  email: string;
  name: string;
  picture?: string;
  role: "admin" | "lojista" | "cliente";
  store_id?: string | null;
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  loginGoogle: () => Promise<void>;
  devLogin: (email: string, role: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  deleteAccount: () => Promise<void>;
};

const Ctx = createContext<AuthCtx>(null as any);
export const useAuth = () => useContext(Ctx);

const processed = new Set<string>();

function extractSessionId(url?: string | null): string | null {
  if (!url) return null;
  const m = url.match(/[?#&]session_id=([^&#]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const exchange = useCallback(async (sessionId: string) => {
    if (processed.has(sessionId)) return;
    processed.add(sessionId);
    try {
      const res = await api.session(sessionId);
      await setToken(res.session_token);
      setUser(res.user);
    } catch (e) {
      console.log("session exchange failed", e);
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const t = await loadToken();
      if (!t) {
        setUser(null);
        return;
      }
      const u = await api.me();
      setUser(u);
    } catch {
      await setToken(null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      // Web: parse session_id from URL first
      if (Platform.OS === "web" && typeof window !== "undefined") {
        const sid = extractSessionId(window.location.hash) || extractSessionId(window.location.search);
        if (sid) {
          await exchange(sid);
          try {
            const url = new URL(window.location.href);
            url.hash = "";
            url.searchParams.delete("session_id");
            window.history.replaceState(window.history.state, "", url.toString());
          } catch {}
          setLoading(false);
          return;
        }
      } else {
        const initial = await Linking.getInitialURL();
        const sid = extractSessionId(initial);
        if (sid) {
          await exchange(sid);
          setLoading(false);
          return;
        }
      }
      await refresh();
      setLoading(false);
    })();

    const sub = Linking.addEventListener("url", async ({ url }) => {
      const sid = extractSessionId(url);
      if (sid) {
        setLoading(true);
        await exchange(sid);
        setLoading(false);
      }
    });
    return () => sub.remove();
  }, []);

  const loginGoogle = useCallback(async () => {
    const redirectUrl =
      Platform.OS === "web" && typeof window !== "undefined"
        ? window.location.origin + "/"
        : Linking.createURL("");
    const authUrl = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
    if (Platform.OS === "web" && typeof window !== "undefined") {
      window.location.href = authUrl;
      return;
    }
    const result = await WebBrowser.openAuthSessionAsync(authUrl, redirectUrl);
    let url: string | null = (result as any)?.url ?? null;
    if (!url) url = await Linking.getInitialURL();
    const sid = extractSessionId(url);
    if (sid) {
      setLoading(true);
      await exchange(sid);
      setLoading(false);
    }
  }, [exchange]);

  const devLogin = useCallback(async (email: string, role: string) => {
    const res = await api.devLogin(email, role);
    await setToken(res.session_token);
    setUser(res.user);
  }, []);

  const deleteAccount = useCallback(async () => {
    try {
      await api.deleteAccount();
    } catch {}
    await setToken(null);
    setUser(null);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {}
    await setToken(null);
    setUser(null);
  }, []);

  return (
    <Ctx.Provider value={{ user, loading, loginGoogle, devLogin, logout, refresh, deleteAccount }}>
      {children}
    </Ctx.Provider>
  );
}
