import { useState, useCallback } from "react";
import { View, Text, StyleSheet, ScrollView, RefreshControl } from "react-native";
import { useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Loading, EmptyState, ErrorState } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money } from "@/src/theme";

type Point = { label: string; value: number };

function BarChart({ data, accent }: { data: Point[]; accent: string }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <View style={styles.chart}>
      {data.map((d, i) => {
        const h = Math.max((d.value / max) * 120, d.value > 0 ? 6 : 2);
        return (
          <View key={i} style={styles.barCol} testID={`bar-${i}`}>
            {d.value > 0 && <Text style={styles.barValue}>{d.value >= 1000 ? `${(d.value / 1000).toFixed(1)}k` : d.value.toFixed(0)}</Text>}
            <View style={[styles.bar, { height: h, backgroundColor: d.value > 0 ? accent : colors.border }]} />
            <Text style={styles.barLabel}>{d.label}</Text>
          </View>
        );
      })}
    </View>
  );
}

export default function VendorReport() {
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const [data, setData] = useState<any>(null);
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.vendorReport();
      setData(r);
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

  if (!user?.store_id) {
    return (
      <View style={styles.container}>
        <View style={[styles.headerBar, { paddingTop: insets.top + spacing.sm }]}>
          <Text style={styles.title}>Vendas</Text>
        </View>
        <EmptyState icon="stats-chart-outline" title="Nenhuma loja vinculada" subtitle="Peça ao administrador para vincular sua conta." />
      </View>
    );
  }

  if (state === "loading") return <Loading />;
  if (state === "error") return <ErrorState onRetry={load} />;

  const avgTicket = data.orders > 0 ? data.total / data.orders : 0;

  return (
    <View style={styles.container}>
      <View style={[styles.headerBar, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.title}>Vendas</Text>
        <Text style={styles.subtitle}>Acompanhe o seu faturamento</Text>
      </View>
      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 40 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.brandPrimary} />}
      >
        <View style={styles.summaryRow}>
          <View style={[styles.sumCard, { backgroundColor: colors.brandPrimary }]}>
            <Ionicons name="cash-outline" size={20} color="#fff" />
            <Text style={styles.sumValue}>{money(data.total)}</Text>
            <Text style={styles.sumLabel}>Faturamento total</Text>
          </View>
          <View style={styles.sumColumn}>
            <View style={styles.miniCard}>
              <Text style={styles.miniValue}>{data.orders}</Text>
              <Text style={styles.miniLabel}>Pedidos</Text>
            </View>
            <View style={styles.miniCard}>
              <Text style={styles.miniValue}>{money(avgTicket)}</Text>
              <Text style={styles.miniLabel}>Ticket médio</Text>
            </View>
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.chartTitle}>Faturamento por dia (7 dias)</Text>
          <BarChart data={data.daily} accent={colors.brandPrimary} />
        </View>

        <View style={styles.card}>
          <Text style={styles.chartTitle}>Faturamento por semana (4 semanas)</Text>
          <BarChart data={data.weekly} accent={colors.brandSecondary} />
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
  summaryRow: { flexDirection: "row", gap: spacing.md, marginBottom: spacing.lg },
  sumCard: {
    flex: 1,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.xs,
    justifyContent: "center",
    ...shadow.card,
  },
  sumValue: { fontSize: font.xl, fontWeight: "800", color: "#fff" },
  sumLabel: { fontSize: font.sm, color: "rgba(255,255,255,0.85)" },
  sumColumn: { flex: 1, gap: spacing.md },
  miniCard: {
    flex: 1,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
    justifyContent: "center",
    ...shadow.card,
  },
  miniValue: { fontSize: font.lg, fontWeight: "800", color: colors.onSurface },
  miniLabel: { fontSize: font.sm, color: colors.onSurfaceTertiary },
  card: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    ...shadow.card,
  },
  chartTitle: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface, marginBottom: spacing.lg },
  chart: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", height: 170, gap: spacing.xs },
  barCol: { flex: 1, alignItems: "center", justifyContent: "flex-end", gap: spacing.xs },
  bar: { width: "72%", borderRadius: radius.sm, minHeight: 2 },
  barValue: { fontSize: 10, color: colors.onSurfaceTertiary, fontWeight: "600" },
  barLabel: { fontSize: 10, color: colors.muted, marginTop: 2 },
});
