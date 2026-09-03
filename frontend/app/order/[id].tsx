import { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  TextInput,
  Linking,
} from "react-native";
import { useLocalSearchParams, useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Loading, ErrorState, Button, StatusBadge, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money } from "@/src/theme";

const VENDOR_STATUSES = [
  { key: "novo", label: "Novo" },
  { key: "editando", label: "Editando" },
  { key: "pronto", label: "Pronto" },
  { key: "entregue", label: "Entregue" },
  { key: "cancelado", label: "Cancelado" },
];

export default function OrderDetail() {
  const { id, token } = useLocalSearchParams<{ id: string; token?: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { user } = useAuth();
  const [order, setOrder] = useState<any>(null);
  const [items, setItems] = useState<any[]>([]);
  const [notifs, setNotifs] = useState<any[]>([]);
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const o = await api.order(id, token);
      setOrder(o);
      setItems(o.items);
      try {
        setNotifs(await api.orderNotifications(id, token));
      } catch {}
      setState("done");
    } catch {
      setState("error");
    }
  }, [id, token]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  if (state === "loading") return <Loading />;
  if (state === "error") return <ErrorState onRetry={load} />;

  const isVendor = user?.role === "lojista" && user?.store_id === order.store_id;
  const isAdmin = user?.role === "admin" || user?.role === "master";
  const isOwner = user?.user_id === order.customer_user_id;
  const canEdit = isVendor || isAdmin || (isOwner && order.editable);

  const total = items.reduce((a, i) => a + i.price * i.qty, 0);

  const changeQty = (pid: string, delta: number) => {
    setItems((prev) =>
      prev
        .map((i) => (i.product_id === pid ? { ...i, qty: Math.max(0, i.qty + delta) } : i))
        .filter((i) => i.qty > 0)
    );
  };

  const changePrice = (pid: string, value: string) => {
    const num = parseFloat(value.replace(",", ".").replace(/[^0-9.]/g, "")) || 0;
    setItems((prev) => prev.map((i) => (i.product_id === pid ? { ...i, price: num } : i)));
  };

  const canPrice = isVendor || isAdmin;

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.updateOrderItems(id, items);
      setOrder(updated);
      setItems(updated.items);
      toast("Pedido atualizado", "success");
    } catch (e: any) {
      toast(e.message || "Falha ao salvar", "error");
    } finally {
      setSaving(false);
    }
  };

  const setStatus = async (status: string) => {
    try {
      const updated = await api.updateOrderStatus(id, status);
      setOrder(updated);
      toast(`Status: ${status}`, "success");
    } catch (e: any) {
      toast(e.message || "Falha", "error");
    }
  };

  const openPdf = () => Linking.openURL(api.pdfUrl(order.id, order.token));

  const resend = async () => {
    try {
      await api.resendOrder(id);
      setNotifs(await api.orderNotifications(id, token));
      toast("Avisos reenviados", "success");
    } catch (e: any) {
      toast(e.message || "Falha ao reenviar", "error");
    }
  };

  const dirty = JSON.stringify(items) !== JSON.stringify(order.items);

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Pressable testID="order-back" onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Pedido</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 160 }}>
        <View style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.store}>{order.store_name}</Text>
            <StatusBadge status={order.status} />
          </View>
          <Text style={styles.meta}>Cliente: {order.customer_name || "—"}</Text>
          <Text style={styles.meta}>#{order.id}</Text>
        </View>

        <Text style={styles.sectionTitle}>Itens</Text>
        <View style={styles.card}>
          {items.map((it, idx) => (
            <View
              key={it.product_id}
              style={[styles.item, idx > 0 && styles.itemBorder]}
              testID={`order-item-${it.product_id}`}
            >
              <View style={{ flex: 1 }}>
                <Text style={styles.itemName}>{it.name}</Text>
                {canPrice ? (
                  <View style={styles.priceEditRow}>
                    <Text style={styles.priceCurrency}>R$</Text>
                    <TextInput
                      testID={`order-price-${it.product_id}`}
                      value={String(it.price)}
                      onChangeText={(v) => changePrice(it.product_id, v)}
                      keyboardType="decimal-pad"
                      style={styles.priceInput}
                    />
                  </View>
                ) : (
                  <Text style={styles.itemPrice}>{money(it.price)}</Text>
                )}
              </View>
              {canEdit ? (
                <View style={styles.qtyRow}>
                  <Pressable
                    testID={`order-minus-${it.product_id}`}
                    onPress={() => changeQty(it.product_id, -1)}
                    style={styles.qtyBtn}
                  >
                    <Ionicons name="remove" size={16} color={colors.onSurface} />
                  </Pressable>
                  <Text style={styles.qtyText}>{it.qty}</Text>
                  <Pressable
                    testID={`order-plus-${it.product_id}`}
                    onPress={() => changeQty(it.product_id, 1)}
                    style={styles.qtyBtn}
                  >
                    <Ionicons name="add" size={16} color={colors.onSurface} />
                  </Pressable>
                </View>
              ) : (
                <Text style={styles.qtyStatic}>x{it.qty}</Text>
              )}
            </View>
          ))}
          <View style={styles.totalRow}>
            <Text style={styles.totalLabel}>Total</Text>
            <Text style={styles.totalValue}>{money(order.discount ? Math.max(total - order.discount, 0) : total)}</Text>
          </View>
          {!!order.discount && (
            <Text style={styles.couponNote}>
              Inclui desconto do cupom {order.coupon_code} (-{money(order.discount)})
            </Text>
          )}
        </View>

        {canEdit && dirty && (
          <Button title="Salvar alterações" onPress={save} loading={saving} testID="save-order-button" />
        )}

        {(isVendor || isAdmin) && (
          <>
            <Text style={styles.sectionTitle}>Status</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.statusRow}>
              {VENDOR_STATUSES.map((s) => (
                <Pressable
                  key={s.key}
                  testID={`status-${s.key}`}
                  onPress={() => setStatus(s.key)}
                  style={[styles.statusChip, order.status === s.key && styles.statusChipActive]}
                >
                  <Text
                    style={[styles.statusChipText, order.status === s.key && { color: "#fff", fontWeight: "700" }]}
                  >
                    {s.label}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          </>
        )}

        <View style={{ height: spacing.lg }} />
        {notifs.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Avisos enviados</Text>
            {notifs.map((n, i) => (
              <View key={i} style={styles.notifRow} testID={`notif-${i}`}>
                <Ionicons
                  name={n.channel === "email" ? "mail-outline" : "logo-whatsapp"}
                  size={16}
                  color={n.channel === "email" ? colors.brandSecondary : "#25D366"}
                />
                <Text style={styles.notifText} numberOfLines={1}>
                  {n.target} • {n.to || "—"}
                </Text>
                <Text style={[styles.notifStatus, { color: n.status === "sent" ? colors.success : n.status === "failed" ? colors.error : colors.warning }]}>
                  {n.status === "sent" ? "enviado" : n.status === "failed" ? "falhou" : "simulado"}
                </Text>
              </View>
            ))}
          </View>
        )}
        {!!user && (
          <Button title="Reenviar aviso (WhatsApp/e-mail)" icon="paper-plane-outline" variant="secondary" onPress={resend} testID="resend-order-button" style={{ marginBottom: spacing.md }} />
        )}
        <Button title="Abrir PDF do pedido" icon="document-text-outline" variant="outline" onPress={openPdf} testID="open-pdf-button" />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surfaceTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  title: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface },
  card: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    ...shadow.card,
  },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  store: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface },
  meta: { fontSize: font.base, color: colors.onSurfaceTertiary, marginTop: 4 },
  sectionTitle: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface, marginBottom: spacing.sm },
  item: { flexDirection: "row", alignItems: "center", paddingVertical: spacing.md },
  itemBorder: { borderTopWidth: 1, borderTopColor: colors.divider },
  itemName: { fontSize: font.base, fontWeight: "600", color: colors.onSurface },
  itemPrice: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  priceEditRow: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 4 },
  priceCurrency: { fontSize: font.sm, color: colors.onSurfaceTertiary, fontWeight: "700" },
  priceInput: {
    minWidth: 70,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    fontSize: font.base,
    color: colors.onSurface,
    backgroundColor: colors.surface,
  },
  qtyRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  qtyBtn: {
    width: 30,
    height: 30,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  qtyText: { fontSize: font.base, fontWeight: "700", color: colors.onSurface, minWidth: 20, textAlign: "center" },
  qtyStatic: { fontSize: font.base, fontWeight: "700", color: colors.onSurfaceTertiary },
  totalRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.sm,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  totalLabel: { fontSize: font.lg, color: colors.onSurfaceTertiary },
  totalValue: { fontSize: font.xl, fontWeight: "800", color: colors.brandPrimary },
  couponNote: { fontSize: font.sm, color: colors.success, marginTop: spacing.xs, fontWeight: "600" },
  notifRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingVertical: spacing.sm, borderTopWidth: 1, borderTopColor: colors.divider },
  notifText: { flex: 1, fontSize: font.sm, color: colors.onSurfaceTertiary },
  notifStatus: { fontSize: font.sm, fontWeight: "700" },
  statusRow: { gap: spacing.sm, paddingBottom: spacing.md },
  statusChip: {
    height: 40,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
    alignItems: "center",
    justifyContent: "center",
  },
  statusChipActive: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  statusChipText: { fontSize: font.base, color: colors.onSurfaceTertiary },
});
