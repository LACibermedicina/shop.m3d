import { useCallback, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  RefreshControl,
  Switch,
  Modal,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { useI18n } from "@/src/i18n";
import { LangSelector } from "@/src/LangSelector";
import { useVendorOrders } from "@/src/vendorOrders";
import { Loading, EmptyState, StatusBadge, Button, Field, Chip, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money, gradients } from "@/src/theme";

export default function VendorOrders() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { user } = useAuth();
  const { t } = useI18n();
  const { orders, loading, newCount, refresh, markSeen, storeOpen, savingOpen, toggleOpen } =
    useVendorOrders();
  const seenTimer = useRef<any>(null);

  const [couponOpen, setCouponOpen] = useState(false);
  const [coupons, setCoupons] = useState<any[]>([]);
  const [cCode, setCCode] = useState("");
  const [cType, setCType] = useState("percent");
  const [cValue, setCValue] = useState("");
  const [cSaving, setCSaving] = useState(false);

  const openCoupons = async () => {
    setCouponOpen(true);
    try {
      setCoupons(await api.vendorCoupons());
    } catch {}
  };

  const addCoupon = async () => {
    if (!cCode.trim() || !cValue) {
      toast("Preencha código e valor", "info");
      return;
    }
    setCSaving(true);
    try {
      await api.createCoupon({
        store_id: user!.store_id,
        code: cCode,
        type: cType,
        value: parseFloat(cValue.replace(",", ".")) || 0,
      });
      setCCode("");
      setCValue("");
      setCoupons(await api.vendorCoupons());
      toast("Cupom salvo", "success");
    } catch (e: any) {
      toast(e.message || "Falha ao salvar cupom", "error");
    } finally {
      setCSaving(false);
    }
  };

  const removeCoupon = async (id: string) => {
    try {
      await api.deleteCoupon(id);
      setCoupons((prev) => prev.filter((c) => c.id !== id));
    } catch {
      toast("Falha ao remover", "error");
    }
  };

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

  const [clientFilter, setClientFilter] = useState<string>("");
  const clientNames = Array.from(
    new Map((orders || []).map((o: any) => [o.customer_user_id, o.customer_name || "Cliente"])).entries()
  ).map(([uid, name]) => ({ uid, name }));
  const shownOrders = clientFilter ? orders.filter((o: any) => o.customer_user_id === clientFilter) : orders;

  const active = orders.filter((o) => ["novo", "editando", "pronto"].includes(o.status)).length;
  const revenue = orders.filter((o) => o.status !== "cancelado").reduce((a, o) => a + o.total, 0);

  const header = (
    <View>
      <View style={styles.controlCard}>
        <View style={styles.openRow}>
          <View style={[styles.dot, { backgroundColor: storeOpen ? colors.success : colors.muted }]} />
          <View style={{ flex: 1 }}>
            <Text style={styles.openTitle}>{storeOpen ? "Loja aberta" : "Loja fechada"}</Text>
            <Text style={styles.openHint}>Aberta enquanto o app estiver ativo no seu celular</Text>
          </View>
          <Switch
            testID="store-open-switch"
            value={storeOpen}
            onValueChange={toggleOpen}
            disabled={savingOpen}
            trackColor={{ true: colors.success, false: colors.borderStrong }}
            thumbColor="#fff"
          />
        </View>
        <Pressable testID="manage-coupons-button" onPress={openCoupons} style={styles.couponBtn}>
          <Ionicons name="pricetag-outline" size={16} color={colors.brandPrimary} />
          <Text style={styles.couponBtnText}>Gerenciar cupons</Text>
        </Pressable>
        <Pressable testID="vendor-invite-button" onPress={() => router.push("/invites")} style={styles.couponBtn}>
          <Ionicons name="person-add-outline" size={16} color={colors.brandPrimary} />
          <Text style={styles.couponBtnText}>Convidar clientes</Text>
        </Pressable>
      </View>
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
      {clientNames.length > 0 && (
        <View>
          <Text style={styles.groupLabel}>{t("Filtrar por cliente")}</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.clientRow}>
            <Chip label={t("Todos")} active={!clientFilter} onPress={() => setClientFilter("")} testID="client-all" />
            {clientNames.map((c) => (
              <Chip
                key={c.uid}
                testID={`client-${c.uid}`}
                label={c.name}
                active={clientFilter === c.uid}
                onPress={() => setClientFilter(c.uid)}
              />
            ))}
          </ScrollView>
        </View>
      )}
    </View>
  );

  const couponModal = (
    <Modal visible={couponOpen} transparent animationType="slide" onRequestClose={() => setCouponOpen(false)}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.modalOverlay}>
        <View style={[styles.modalCard, { paddingBottom: insets.bottom + spacing.lg }]}>
          <View style={styles.modalHandle} />
          <View style={styles.modalTitleRow}>
            <Text style={styles.modalTitle}>Cupons de desconto</Text>
            <Pressable testID="close-coupons" onPress={() => setCouponOpen(false)}>
              <Ionicons name="close" size={24} color={colors.onSurfaceTertiary} />
            </Pressable>
          </View>
          <ScrollView keyboardShouldPersistTaps="handled">
            <View style={styles.couponForm}>
              <Field testID="coupon-code" label="Código" value={cCode} onChangeText={setCCode} placeholder="Ex: FRONTEIRA10" autoCapitalize="characters" />
              <View style={styles.typeRow}>
                <Chip testID="coupon-type-percent" label="Percentual (%)" active={cType === "percent"} onPress={() => setCType("percent")} />
                <Chip testID="coupon-type-fixed" label="Valor fixo (R$)" active={cType === "fixed"} onPress={() => setCType("fixed")} />
              </View>
              <View style={{ height: spacing.md }} />
              <Field
                testID="coupon-value"
                label={cType === "percent" ? "Desconto (%)" : "Desconto (R$)"}
                value={cValue}
                onChangeText={setCValue}
                placeholder={cType === "percent" ? "10" : "5,00"}
                keyboardType="decimal-pad"
              />
              <Button title="Criar cupom" onPress={addCoupon} loading={cSaving} testID="create-coupon-button" />
            </View>
            <Text style={styles.couponsHead}>Seus cupons</Text>
            {coupons.length === 0 ? (
              <Text style={styles.openHint}>Nenhum cupom criado ainda.</Text>
            ) : (
              coupons.map((c) => (
                <View key={c.id} style={styles.couponRow} testID={`coupon-${c.id}`}>
                  <View style={styles.couponTag}>
                    <Ionicons name="pricetag" size={14} color={colors.brandPrimary} />
                    <Text style={styles.couponCode}>{c.code}</Text>
                  </View>
                  <Text style={styles.couponVal}>
                    {c.type === "percent" ? `${c.value}% off` : `${money(c.value)} off`}
                  </Text>
                  <Pressable testID={`delete-coupon-${c.id}`} onPress={() => removeCoupon(c.id)} style={styles.couponDel}>
                    <Ionicons name="trash-outline" size={18} color={colors.error} />
                  </Pressable>
                </View>
              ))
            )}
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );

  if (!user?.store_id) {
    return (
      <View style={styles.container}>
        <LinearGradient colors={gradients.header} style={[styles.headerBar, { paddingTop: insets.top + spacing.sm }]}>
          <Text style={styles.title}>{t("Pedidos")}</Text>
        </LinearGradient>
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
      <LinearGradient colors={gradients.header} style={[styles.headerBar, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.topBar}>
          <LangSelector variant="light" />
        </View>
        <Text style={styles.title}>{t("Pedidos")}</Text>
      </LinearGradient>
      {loading ? (
        <Loading />
      ) : (
        <FlatList
          data={shownOrders}
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
      {couponModal}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  headerBar: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    borderBottomLeftRadius: radius.xl,
    borderBottomRightRadius: radius.xl,
    ...shadow.card,
  },
  topBar: { flexDirection: "row", justifyContent: "flex-end", marginBottom: spacing.sm },
  groupLabel: { fontSize: font.sm, fontWeight: "700", color: colors.onSurfaceTertiary, marginTop: spacing.md, marginBottom: spacing.xs },
  clientRow: { gap: spacing.sm, paddingBottom: spacing.sm },
  title: { fontSize: font["2xl"], fontWeight: "800", color: "#fff" },
  metrics: { flexDirection: "row", gap: spacing.md, marginBottom: spacing.lg },
  controlCard: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    ...shadow.card,
  },
  openRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  dot: { width: 12, height: 12, borderRadius: 6 },
  openTitle: { fontSize: font.lg, fontWeight: "800", color: colors.onSurface },
  openHint: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  couponBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    marginTop: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: colors.brandTertiary,
  },
  couponBtnText: { fontSize: font.base, fontWeight: "700", color: colors.brandPrimary },
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  modalCard: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    padding: spacing.lg,
    maxHeight: "88%",
  },
  modalHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.borderStrong,
    alignSelf: "center",
    marginBottom: spacing.md,
  },
  modalTitleRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.lg },
  modalTitle: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface },
  couponForm: { marginBottom: spacing.lg },
  typeRow: { flexDirection: "row", gap: spacing.sm },
  couponsHead: { fontSize: font.lg, fontWeight: "800", color: colors.onSurface, marginBottom: spacing.sm },
  couponRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    ...shadow.card,
  },
  couponTag: { flexDirection: "row", alignItems: "center", gap: spacing.xs, flex: 1 },
  couponCode: { fontSize: font.base, fontWeight: "800", color: colors.onSurface, letterSpacing: 0.5 },
  couponVal: { fontSize: font.base, fontWeight: "700", color: colors.brandPrimary },
  couponDel: {
    width: 36,
    height: 36,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
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
