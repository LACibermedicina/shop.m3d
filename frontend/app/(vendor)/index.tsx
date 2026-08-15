import { useCallback, useRef } from "react";
import { View, Text, StyleSheet, FlatList, Pressable, RefreshControl } from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useAuth } from "@/src/auth";
import { useVendorOrders } from "@/src/vendorOrders";
import { Loading, EmptyState, StatusBadge } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money } from "@/src/theme";

export default function VendorOrders() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const { orders, loading, newCount, refresh, markSeen } = useVendorOrders();
  const seenTimer = useRef<any>(null);

  useFocusEffect(
    useCallback(() => {
      refresh();
      // clear the "new" badge shortly after the vendor views the list
      seenTimer.current = setTimeout(markSeen, 1500);
      return () => seenTimer.current && clearTimeout(seenTimer.current);
    }, [refresh, markSeen])
  );

  const onRefresh = async () => {
    await refresh();
  };

  const active = orders.filter((o) => ["novo", "editando", "pronto"].includes(o.status)).length;
  const revenue = orders.filter((o) => o.status !== "cancelado").reduce((a, o) => a + o.total, 0);

  const header = (
    <View>
      {newCount > 0 && (
        <View style={styles.alertBanner} testID="new-orders-banner">
          <Ionicons name="notifications" size={18} color="#fff" />
          <Text style={styles.alertText}>
            {newCount} {newCount === 1 ? "novo pedido chegou!" : "novos pedidos chegaram!"}
          </Text>
        </View>
      )}
      <View style={styles.metrics}>
        <View style={styles.metricCard}>
          <Text style={styles.metricValue}>{active}</Text>
          <Text style={styles.metricLabel}>Pedidos ativos</Text>
        </View>
        <View style={styles.metricCard}>
          <Text style={styles.metricValue}>{money(revenue)}</Text>
          <Text style={styles.metricLabel}>Faturamento</Text>
        </View>
      </View>
    </View>
  );

  if (!user?.store_id) {
    return (
      <View style={styles.container}>
        <View style={[styles.headerBar, { paddingTop: insets.top + spacing.sm }]}>
          <Text style={styles.title}>Pedidos</Text>
        </View>
        <EmptyState
          icon="storefront-outline"
          title="Nenhuma loja vinculada"
          subtitle="Peça ao administrador para vincular sua conta a uma loja."
        />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={[styles.headerBar, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.title}>Pedidos</Text>
      </View>
      {loading ? (
        <Loading />
      ) : (
        <FlatList
          data={orders}
          keyExtractor={(o) => o.id}
          ListHeaderComponent={header}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 40 }}
          refreshControl={<RefreshControl refreshing={false} onRefresh={onRefresh} tintColor={colors.brandPrimary} />}
          ListEmptyComponent={
            <EmptyState icon="cube-outline" title="Nenhum pedido no momento" subtitle="Os pedidos dos clientes aparecerão aqui." />
          }
          renderItem={({ item }) => (
            <Pressable
              testID={`vendor-order-${item.id}`}
              style={({ pressed }) => [styles.card, pressed && { opacity: 0.9 }]}
              onPress={() => router.push(`/order/${item.id}?token=${item.token}`)}
            >
              <View style={styles.rowBetween}>
                <Text style={styles.customer}>{item.customer_name || "Cliente"}</Text>
                <StatusBadge status={item.status} />
              </View>
              <Text style={styles.meta}>
                {item.items.length} {item.items.length === 1 ? "item" : "itens"} • {money(item.total)}
              </Text>
              <View style={styles.cardBottom}>
                <Text style={styles.date}>{new Date(item.created_at).toLocaleString("pt-BR")}</Text>
                <View style={styles.manageBtn}>
                  <Text style={styles.manageText}>Gerenciar</Text>
                  <Ionicons name="chevron-forward" size={16} color={colors.brandPrimary} />
                </View>
              </View>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  headerBar: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  title: { fontSize: font["2xl"], fontWeight: "800", color: colors.onSurface },
  metrics: { flexDirection: "row", gap: spacing.md, marginBottom: spacing.lg },
  alertBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.brandSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  alertText: { color: "#fff", fontSize: font.base, fontWeight: "700" },
  metricCard: {
    flex: 1,
    backgroundColor: colors.brandTertiary,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  metricValue: { fontSize: font.xl, fontWeight: "800", color: colors.onBrandTertiary },
  metricLabel: { fontSize: font.sm, color: colors.onBrandTertiary, marginTop: 2 },
  card: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    ...shadow.card,
  },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  customer: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  meta: { fontSize: font.base, color: colors.onSurfaceTertiary, marginTop: 4 },
  cardBottom: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  date: { fontSize: font.sm, color: colors.muted },
  manageBtn: { flexDirection: "row", alignItems: "center", gap: 2 },
  manageText: { fontSize: font.base, fontWeight: "700", color: colors.brandPrimary },
});
