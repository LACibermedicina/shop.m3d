import { useState, useCallback } from "react";
import { View, Text, StyleSheet, ScrollView, RefreshControl } from "react-native";
import { useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api } from "@/src/api";
import { Loading, ErrorState, Chip } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money } from "@/src/theme";

const CARDS = [
  { key: "revenue", label: "Faturamento", icon: "cash-outline", color: colors.brandPrimary, isMoney: true },
  { key: "orders", label: "Pedidos", icon: "receipt-outline", color: colors.brandSecondary },
  { key: "stores", label: "Lojas", icon: "business-outline", color: colors.success },
  { key: "products", label: "Produtos", icon: "pricetags-outline", color: colors.warning },
  { key: "customers", label: "Clientes", icon: "people-outline", color: colors.info },
];

export default function AdminMetrics() {
  const insets = useSafeAreaInsets();
  const [metrics, setMetrics] = useState<any>(null);
  const [notifs, setNotifs] = useState<any[]>([]);
  const [waLog, setWaLog] = useState<any[]>([]);
  const [nStatus, setNStatus] = useState("");
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [refreshing, setRefreshing] = useState(false);

  const loadNotifs = useCallback(async (status = nStatus) => {
    try {
      setNotifs(await api.adminNotifications("", status));
    } catch {}
  }, [nStatus]);

  const load = useCallback(async () => {
    try {
      const data = await api.metrics();
      setMetrics(data);
      await loadNotifs("");
      try { setWaLog(await api.adminWaInbound()); } catch {}
      setState("done");
    } catch {
      setState("error");
    }
  }, [loadNotifs]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  if (state === "loading") return <Loading />;
  if (state === "error") return <ErrorState onRetry={load} />;

  return (
    <View style={styles.container}>
      <View style={[styles.headerBar, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.title}>Métricas</Text>
        <Text style={styles.subtitle}>Visão geral das lojas</Text>
      </View>
      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 40 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.brandPrimary} />}
      >
        <View style={styles.hero}>
          <Text style={styles.heroLabel}>Faturamento total</Text>
          <Text style={styles.heroValue}>{money(metrics.revenue)}</Text>
          <View style={styles.heroFooter}>
            <Ionicons name="trending-up" size={16} color="#fff" />
            <Text style={styles.heroFooterText}>{metrics.orders} pedidos registrados</Text>
          </View>
        </View>

        <View style={styles.grid}>
          {CARDS.filter((c) => c.key !== "revenue").map((c) => (
            <View key={c.key} style={styles.card} testID={`metric-${c.key}`}>
              <View style={[styles.iconWrap, { backgroundColor: c.color + "22" }]}>
                <Ionicons name={c.icon as any} size={22} color={c.color} />
              </View>
              <Text style={styles.cardValue}>{metrics[c.key]}</Text>
              <Text style={styles.cardLabel}>{c.label}</Text>
            </View>
          ))}
        </View>

        <View style={styles.notifHeader}>
          <Text style={styles.notifTitle}>Avisos enviados</Text>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
          {[["", "Todos"], ["sent", "Enviados"], ["simulated", "Simulados"], ["failed", "Falhas"]].map(([v, l]) => (
            <Chip key={v} testID={`notif-filter-${v || "all"}`} label={l} active={nStatus === v} onPress={() => { setNStatus(v); loadNotifs(v); }} />
          ))}
        </ScrollView>
        {notifs.length === 0 ? (
          <Text style={styles.notifEmpty}>Nenhum aviso ainda.</Text>
        ) : (
          notifs.slice(0, 60).map((n, i) => (
            <View key={i} style={styles.notifCard} testID={`admin-notif-${i}`}>
              <Ionicons name={n.channel === "email" ? "mail-outline" : "logo-whatsapp"} size={16} color={n.channel === "email" ? colors.brandSecondary : "#25D366"} />
              <View style={{ flex: 1 }}>
                <Text style={styles.notifStore} numberOfLines={1}>{n.store_name} • {n.target}</Text>
                <Text style={styles.notifTo} numberOfLines={1}>{n.to || "—"}</Text>
              </View>
              <Text style={[styles.notifStat, { color: n.status === "sent" ? colors.success : n.status === "failed" ? colors.error : colors.warning }]}>
                {n.status === "sent" ? "enviado" : n.status === "failed" ? "falhou" : "simulado"}
              </Text>
            </View>
          ))
        )}

        <View style={styles.notifHeader}>
          <Text style={styles.notifTitle}>Comandos por WhatsApp</Text>
          <Text style={styles.subtitle}>Cadastros e alterações recebidos no número root</Text>
        </View>
        {waLog.length === 0 ? (
          <Text style={styles.notifEmpty}>Nenhum comando recebido ainda.</Text>
        ) : (
          waLog.slice(0, 60).map((w, i) => {
            const map: any = {
              criar: ["add-circle-outline", colors.success],
              atualizar: ["create-outline", colors.info],
              desativar: ["trash-outline", colors.error],
              catalogo: ["document-text-outline", colors.brandSecondary],
              ajuda: ["help-circle-outline", colors.warning],
              desconhecido: ["ellipse-outline", colors.onSurfaceTertiary],
            };
            const [icon, color] = map[w.intent] || map.desconhecido;
            return (
              <View key={i} style={styles.notifCard} testID={`admin-wa-${i}`}>
                <Ionicons name={icon} size={16} color={color} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.notifStore} numberOfLines={1}>
                    {(w.store_name || "—")} • {w.from}
                  </Text>
                  <Text style={styles.notifTo} numberOfLines={1}>{w.result || w.text}</Text>
                </View>
                <Text style={[styles.notifStat, { color }]}>{w.intent}</Text>
              </View>
            );
          })
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  headerBar: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  title: { fontSize: font["2xl"], fontWeight: "800", color: colors.onSurface },
  subtitle: { fontSize: font.base, color: colors.onSurfaceTertiary, marginTop: 2 },
  hero: {
    backgroundColor: colors.brandPrimary,
    borderRadius: radius.lg,
    padding: spacing.xl,
    marginBottom: spacing.lg,
    ...shadow.card,
  },
  heroLabel: { fontSize: font.base, color: "rgba(255,255,255,0.85)" },
  heroValue: { fontSize: font["3xl"], fontWeight: "800", color: "#fff", marginTop: spacing.xs },
  heroFooter: { flexDirection: "row", alignItems: "center", gap: spacing.xs, marginTop: spacing.md },
  heroFooterText: { fontSize: font.sm, color: "rgba(255,255,255,0.85)" },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  card: {
    width: "47.5%",
    flexGrow: 1,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    ...shadow.card,
  },
  iconWrap: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
  },
  cardValue: { fontSize: font["2xl"], fontWeight: "800", color: colors.onSurface },
  cardLabel: { fontSize: font.base, color: colors.onSurfaceTertiary, marginTop: 2 },
  notifHeader: { marginTop: spacing.xl, marginBottom: spacing.sm },
  notifTitle: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface },
  filterRow: { gap: spacing.sm, paddingBottom: spacing.md },
  notifEmpty: { fontSize: font.base, color: colors.onSurfaceTertiary, paddingVertical: spacing.md },
  notifCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    ...shadow.card,
  },
  notifStore: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  notifTo: { fontSize: font.sm, color: colors.onSurfaceTertiary },
  notifStat: { fontSize: font.sm, fontWeight: "700" },
});
