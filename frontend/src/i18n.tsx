import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";
import { storage } from "@/src/utils/storage";
import { api } from "@/src/api";

export type Lang = "pt" | "en" | "es";
export const LANGS: { key: Lang; label: string; flag: string }[] = [
  { key: "pt", label: "PT", flag: "🇧🇷" },
  { key: "en", label: "EN", flag: "🇺🇸" },
  { key: "es", label: "ES", flag: "🇪🇸" },
];

const KEY = "feira_lang_v1";

// Curated static overrides for common UI terms (instant + high quality).
const STATIC: Record<Exclude<Lang, "pt">, Record<string, string>> = {
  en: {
    "Início": "Home",
    "Catálogo": "Catalog",
    "Meu Catálogo": "My Catalog",
    "Pedidos": "Orders",
    "Perfil": "Profile",
    "Sacola": "Bag",
    "Lojas": "Stores",
    "Usuários": "Users",
    "Métricas": "Metrics",
    "Buscar lojas ou produtos": "Search stores or products",
    "Buscar no meu catálogo": "Search my catalog",
    "Todos": "All",
    "Todas as lojas": "All stores",
    "Destaques da fronteira": "Border highlights",
    "Enviar aos lojistas": "Send to vendors",
    "Gerar PDF": "Generate PDF",
    "Meus pedidos": "My orders",
    "Sair": "Log out",
    "Entrar": "Sign in",
    "Aceitar convite": "Accept invitation",
    "Convidar cliente": "Invite customer",
    "Total": "Total",
    "Total geral": "Grand total",
    "Enviar": "Send",
    "Cancelar": "Cancel",
    "Salvar": "Save",
    "Remover": "Remove",
    "Filtrar por loja": "Filter by store",
    "Todas": "All",
    "Categoria": "Category",
    "itens": "items",
    "produtos": "products",
    "produto": "product",
    "Aberta": "Open",
    "Fechada": "Closed",
    "Recentes": "Recent",
    "Nome": "Name",
    "Menor preço": "Lowest price",
    "Maior preço": "Highest price",
    "Ver meu catálogo": "View my catalog",
    "adicionado ao meu catálogo": "added to my catalog",
    "Novidades": "New arrivals",
    "Suas lojas favoritas": "Your favorite stores",
    "Convidar clientes": "Invite customers",
    "Gerar convite": "Generate invite",
    "Compartilhar link": "Share link",
    "Seu catálogo está vazio": "Your catalog is empty",
    "Compre de quem entende, na sua rede de confiança": "Buy from people who get it, in your trusted network",
    "Compre nas lojas da Tríplice Fronteira": "Shop from Triple Frontier stores",
    "Tríplice Fronteira · compre sem sair de casa": "Triple Frontier · shop from home",
  },
  es: {
    "Início": "Inicio",
    "Catálogo": "Catálogo",
    "Meu Catálogo": "Mi Catálogo",
    "Pedidos": "Pedidos",
    "Perfil": "Perfil",
    "Sacola": "Bolsa",
    "Lojas": "Tiendas",
    "Usuários": "Usuarios",
    "Métricas": "Métricas",
    "Buscar lojas ou produtos": "Buscar tiendas o productos",
    "Buscar no meu catálogo": "Buscar en mi catálogo",
    "Todos": "Todos",
    "Todas as lojas": "Todas las tiendas",
    "Destaques da fronteira": "Destacados de la frontera",
    "Enviar aos lojistas": "Enviar a los vendedores",
    "Gerar PDF": "Generar PDF",
    "Meus pedidos": "Mis pedidos",
    "Sair": "Salir",
    "Entrar": "Ingresar",
    "Aceitar convite": "Aceptar invitación",
    "Convidar cliente": "Invitar cliente",
    "Total": "Total",
    "Total geral": "Total general",
    "Enviar": "Enviar",
    "Cancelar": "Cancelar",
    "Salvar": "Guardar",
    "Remover": "Quitar",
    "Filtrar por loja": "Filtrar por tienda",
    "Todas": "Todas",
    "Categoria": "Categoría",
    "itens": "ítems",
    "produtos": "productos",
    "produto": "producto",
    "Aberta": "Abierta",
    "Fechada": "Cerrada",
    "Recentes": "Recientes",
    "Nome": "Nombre",
    "Menor preço": "Menor precio",
    "Maior preço": "Mayor precio",
    "Ver meu catálogo": "Ver mi catálogo",
    "adicionado ao meu catálogo": "agregado a mi catálogo",
    "Novidades": "Novedades",
    "Suas lojas favoritas": "Tus tiendas favoritas",
    "Convidar clientes": "Invitar clientes",
    "Gerar convite": "Generar invitación",
    "Compartilhar link": "Compartir enlace",
    "Seu catálogo está vazio": "Tu catálogo está vacío",
    "Compre de quem entende, na sua rede de confiança": "Compra de quien entiende, en tu red de confianza",
    "Compre nas lojas da Tríplice Fronteira": "Compra en las tiendas de la Triple Frontera",
    "Tríplice Fronteira · compre sem sair de casa": "Triple Frontera · compra desde casa",
  },
};

type Ctx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (pt: string) => string;
  ready: boolean;
};

const I18nCtx = createContext<Ctx>(null as any);
export const useI18n = () => useContext(I18nCtx);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("pt");
  const [ready, setReady] = useState(false);
  const [cache, setCache] = useState<Record<string, Record<string, string>>>({ en: {}, es: {} });
  const pending = useRef<Set<string>>(new Set());
  const timer = useRef<any>(null);

  useEffect(() => {
    (async () => {
      const saved = await storage.getItem<string>(KEY, "pt");
      if (saved === "en" || saved === "es" || saved === "pt") setLangState(saved);
      setReady(true);
    })();
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    storage.setItem(KEY, l);
  }, []);

  const flush = useCallback(
    (target: Exclude<Lang, "pt">) => {
      const texts = Array.from(pending.current);
      pending.current = new Set();
      if (texts.length === 0) return;
      api
        .translate(texts, target)
        .then((res: any) => {
          const tr = res?.translations || {};
          setCache((prev) => ({ ...prev, [target]: { ...prev[target], ...tr } }));
        })
        .catch(() => {});
    },
    []
  );

  const t = useCallback(
    (pt: string): string => {
      if (!pt || lang === "pt") return pt;
      const target = lang as Exclude<Lang, "pt">;
      const stat = STATIC[target]?.[pt];
      if (stat) return stat;
      const cached = cache[target]?.[pt];
      if (cached) return cached;
      // enqueue for AI translation (batched)
      if (!pending.current.has(pt)) {
        pending.current.add(pt);
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => flush(target), 250);
      }
      return pt; // fallback while translating
    },
    [lang, cache, flush]
  );

  return <I18nCtx.Provider value={{ lang, setLang, t, ready }}>{children}</I18nCtx.Provider>;
}
