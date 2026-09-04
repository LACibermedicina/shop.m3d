import { useState, useCallback } from "react";
import { View, Text, StyleSheet, FlatList, Pressable, RefreshControl } from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api } from "@/src/api";
import { useI18n } from "@/src/i18n";
import { LangSelector } from "@/src/LangSelector";
import { Loading, EmptyState, ErrorState, StatusBadge } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money, gradients } from "@/src/theme";

export default function CustomerOrders() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { t } = useI18n();
  const [orders, setOrders] = useState<any[]>([]);
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.myOrders();
      setOrders(data);
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

  return (
    <View style={styles.container}>
      <LinearGradient colors={gradients.header} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.topBar}>
          <LangSelector variant="light" />
        </View>
        <Text style={styles.title}>{t("Meus pedidos")}</Text>
      </LinearGradient>
      {state === "loading" ? (
        <Loading />
      ) : state === "error" ? (
        <ErrorState onRetry={load} />
      ) : (
        <FlatList
          data={orders}
          keyExtractor={(o) => o.id}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 40 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.brandPrimary} />}
          ListEmptyComponent={
            <EmptyState icon="receipt-outline" title="Nenhum pedido ainda" subtitle="Seus pedidos aparecerão aqui." />
          }
          renderItem={({ item }) => (
            <Pressable
              testID={`order-card-${item.id}`}
              style={({ pressed }) => [styles.card, pressed && { opacity: 0.9 }]}
              onPress={() => router.push(`/order/${item.id}?token=${item.token}`)}
            >
              <View style={styles.cardTop}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.store}>{item.store_name}</Text>
                  <Text style={styles.meta}>
                    {item.items.length} {item.items.length === 1 ? "item" : "itens"} • {money(item.total)}
                  </Text>
                </View>
                <StatusBadge status={item.status} />
              </View>
              <View style={styles.cardBottom}>
                <Text style={styles.date}>{new Date(item.created_at).toLocaleString("pt-BR")}</Text>
                <Ionicons name="chevron-forward" size={18} color={colors.muted} />
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
  header: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    borderBottomLeftRadius: radius.xl,
    borderBottomRightRadius: radius.xl,
    ...shadow.card,
  },
  topBar: { flexDirection: "row", justifyContent: "flex-end", marginBottom: spacing.sm },
  title: { fontSize: font["2xl"], fontWeight: "800", color: "#fff" },
  card: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    ...shadow.card,
  },
  cardTop: { flexDirection: "row", alignItems: "center" },
  store: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  meta: { fontSize: font.base, color: colors.onSurfaceTertiary, marginTop: 2 },
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
});
