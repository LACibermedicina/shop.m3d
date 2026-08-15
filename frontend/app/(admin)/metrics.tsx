import { useState, useCallback } from "react";
import { View, Text, StyleSheet, ScrollView, RefreshControl } from "react-native";
import { useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api } from "@/src/api";
import { Loading, ErrorState } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money } from "@/src/theme";

const CARDS = [
  { key: "revenue", label: "Faturamento", icon: "cash-outline", color: colors.brandPrimary, isMoney: true },
  { key: "orders", label: "Pedidos", icon: "receipt-outline", color: colors.brandSecondary },
  { key: "stores", label: "Barracas", icon: "business-outline", color: colors.success },
  { key: "products", label: "Produtos", icon: "pricetags-outline", color: colors.warning },
  { key: "customers", label: "Clientes", icon: "people-outline", color: colors.info },
];

export default function AdminMetrics() {
  const insets = useSafeAreaInsets();
  const [metrics, setMetrics] = useState<any>(null);
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.metrics();
      setMetrics(data);
      setState("done");
    } catch {
      setState("error");
    }
  }, []);

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
});
