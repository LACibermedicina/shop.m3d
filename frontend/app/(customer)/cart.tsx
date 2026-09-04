import { useState, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  Modal,
  Linking,
  Platform,
  TextInput,
} from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";
import { api, fileUrl } from "@/src/api";
import { useCart, CartItem } from "@/src/cart";
import { useAuth } from "@/src/auth";
import { EmptyState, Button, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money } from "@/src/theme";

type CreatedOrder = {
  id: string;
  token: string;
  store_name: string;
  store_whatsapp: string;
  total: number;
  waUrl: string;
};

export default function Cart() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { user } = useAuth();
  const { items, setQty, remove, clear, total, count } = useCart();
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<CreatedOrder[] | null>(null);
  const [waConfigured, setWaConfigured] = useState(false);
  const [couponInput, setCouponInput] = useState<Record<string, string>>({});
  const [applied, setApplied] = useState<Record<string, { code: string; discount: number }>>({});
  const [applying, setApplying] = useState<string>("");
  const [custWhats, setCustWhats] = useState("");

  const applyCoupon = async (storeId: string, subtotal: number) => {
    const code = (couponInput[storeId] || "").trim();
    if (!code) return;
    setApplying(storeId);
    try {
      const r = await api.applyCoupon(storeId, code, subtotal);
      if (r.valid) {
        setApplied((p) => ({ ...p, [storeId]: { code: r.code, discount: r.discount } }));
        toast(`Cupom aplicado: -${money(r.discount)}`, "success");
      } else {
        setApplied((p) => {
          const n = { ...p };
          delete n[storeId];
          return n;
        });
        toast("Cupom inválido", "error");
      }
    } catch {
      toast("Falha ao validar cupom", "error");
    } finally {
      setApplying("");
    }
  };

  const removeCoupon = (storeId: string) => {
    setApplied((p) => {
      const n = { ...p };
      delete n[storeId];
      return n;
    });
    setCouponInput((p) => ({ ...p, [storeId]: "" }));
  };

  const totalDiscount = Object.values(applied).reduce((a, c) => a + c.discount, 0);
  const grandTotal = Math.max(total - totalDiscount, 0);

  useEffect(() => {
    api.whatsappStatus().then((r) => setWaConfigured(!!r.configured)).catch(() => {});
  }, []);

  useEffect(() => {
    if (user?.whatsapp) setCustWhats(user.whatsapp);
  }, [user?.whatsapp]);

  const sendOrder = async (o: CreatedOrder) => {
    if (waConfigured) {
      try {
        await api.sendOrderWhatsApp(o.id);
        toast("Pedido enviado ao lojista pelo WhatsApp!", "success");
        return;
      } catch {
        toast("Abrindo WhatsApp...", "info");
      }
    }
    Linking.openURL(o.waUrl);
  };

  const groups = items.reduce<Record<string, CartItem[]>>((acc, it) => {
    (acc[it.store_id] = acc[it.store_id] || []).push(it);
    return acc;
  }, {});

  const buildWa = (order: any, storeItems: CartItem[]) => {
    const pdf = api.pdfUrl(order.id, order.token);
    const lines = storeItems.map((i) => `• ${i.qty}x ${i.name} — ${money(i.price * i.qty)}`).join("\n");
    const text = `*Novo pedido — Lojas da Fronteira*\nLoja: ${order.store_name}\n\n${lines}\n\n*Total: ${money(
      order.total
    )}*\n\nLista em PDF: ${pdf}\nVer/editar pedido: ${pdf}`;
    const num = (order.store_whatsapp || "").replace(/\D/g, "");
    return `https://wa.me/${num}?text=${encodeURIComponent(text)}`;
  };

  const checkout = async () => {
    setBusy(true);
    try {
      const results: CreatedOrder[] = [];
      for (const storeId of Object.keys(groups)) {
        const storeItems = groups[storeId];
        const order = await api.createOrder({
          store_id: storeId,
          items: storeItems.map((i) => ({
            product_id: i.product_id,
            name: i.name,
            price: i.price,
            qty: i.qty,
          })),
          coupon_code: applied[storeId]?.code || "",
          customer_whatsapp: custWhats.trim(),
        });
        results.push({
          id: order.id,
          token: order.token,
          store_name: order.store_name,
          store_whatsapp: order.store_whatsapp,
          total: order.total,
          waUrl: buildWa(order, storeItems),
        });
      }
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      clear();
      setCreated(results);
    } catch (e: any) {
      toast(e.message || "Falha ao finalizar pedido", "error");
    } finally {
      setBusy(false);
    }
  };

  if (count === 0) {
    return (
      <View style={styles.container}>
        <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
          <Text style={styles.title}>Sacola</Text>
        </View>
        <EmptyState
          icon="bag-handle-outline"
          title="Sua sacola está vazia"
          subtitle="Adicione produtos das lojas para começar."
          action={<Button title="Explorar lojas" onPress={() => router.push("/(customer)")} testID="explore-button" />}
        />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.title}>Sacola</Text>
        <Text style={styles.subtitle}>{count} {count === 1 ? "item" : "itens"}</Text>
      </View>

      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 160 }}
        showsVerticalScrollIndicator={false}
      >
        {Object.keys(groups).map((storeId) => {
          const g = groups[storeId];
          const sub = g.reduce((a, i) => a + i.price * i.qty, 0);
          return (
            <View key={storeId} style={styles.group}>
              <View style={styles.groupHeader}>
                <Ionicons name="storefront" size={16} color={colors.brandPrimary} />
                <Text style={styles.groupName}>{g[0].store_name}</Text>
              </View>
              {g.map((it) => (
                <View key={it.product_id} style={styles.item} testID={`cart-item-${it.product_id}`}>
                  <Image
                    source={{ uri: fileUrl(it.image) || undefined }}
                    style={styles.itemImg}
                    contentFit="cover"
                  />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.itemName} numberOfLines={1}>
                      {it.name}
                    </Text>
                    <Text style={styles.itemPrice}>{money(it.price)}</Text>
                  </View>
                  <View style={styles.qtyRow}>
                    <Pressable
                      testID={`qty-minus-${it.product_id}`}
                      onPress={() => setQty(it.product_id, it.qty - 1)}
                      style={styles.qtyBtn}
                    >
                      <Ionicons name="remove" size={16} color={colors.onSurface} />
                    </Pressable>
                    <Text style={styles.qtyText}>{it.qty}</Text>
                    <Pressable
                      testID={`qty-plus-${it.product_id}`}
                      onPress={() => setQty(it.product_id, it.qty + 1)}
                      style={styles.qtyBtn}
                    >
                      <Ionicons name="add" size={16} color={colors.onSurface} />
                    </Pressable>
                  </View>
                </View>
              ))}
              <View style={styles.subRow}>
                <Text style={styles.subLabel}>Subtotal</Text>
                <Text style={styles.subValue}>{money(sub)}</Text>
              </View>
              {applied[storeId] ? (
                <View style={styles.couponApplied} testID={`coupon-applied-${storeId}`}>
                  <Ionicons name="pricetag" size={14} color={colors.success} />
                  <Text style={styles.couponAppliedText}>
                    {applied[storeId].code} — desconto {money(applied[storeId].discount)}
                  </Text>
                  <Pressable testID={`coupon-remove-${storeId}`} onPress={() => removeCoupon(storeId)}>
                    <Ionicons name="close-circle" size={18} color={colors.muted} />
                  </Pressable>
                </View>
              ) : (
                <View style={styles.couponRow}>
                  <TextInput
                    testID={`coupon-input-${storeId}`}
                    value={couponInput[storeId] || ""}
                    onChangeText={(t) => setCouponInput((p) => ({ ...p, [storeId]: t }))}
                    placeholder="Cupom de desconto"
                    placeholderTextColor={colors.muted}
                    autoCapitalize="characters"
                    style={styles.couponInput}
                  />
                  <Pressable
                    testID={`coupon-apply-${storeId}`}
                    onPress={() => applyCoupon(storeId, sub)}
                    style={styles.couponApply}
                    disabled={applying === storeId}
                  >
                    <Text style={styles.couponApplyText}>{applying === storeId ? "..." : "Aplicar"}</Text>
                  </Pressable>
                </View>
              )}
            </View>
          );
        })}
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.md }]}>
        <TextInput
          testID="customer-whatsapp-input"
          value={custWhats}
          onChangeText={setCustWhats}
          placeholder="Seu WhatsApp p/ confirmação (opcional)"
          placeholderTextColor={colors.muted}
          keyboardType="phone-pad"
          style={styles.custWhatsInput}
        />
        {totalDiscount > 0 && (
          <View style={styles.discountRow}>
            <Text style={styles.discountLabel}>Descontos</Text>
            <Text style={styles.discountValue}>- {money(totalDiscount)}</Text>
          </View>
        )}
        <View style={styles.totalRow}>
          <Text style={styles.totalLabel}>Total</Text>
          <Text style={styles.totalValue}>{money(grandTotal)}</Text>
        </View>
        <Button
          title="Finalizar Pedido"
          icon="logo-whatsapp"
          onPress={checkout}
          loading={busy}
          testID="checkout-button"
        />
      </View>

      <Modal visible={!!created} transparent animationType="slide" onRequestClose={() => setCreated(null)}>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, { paddingBottom: insets.bottom + spacing.lg }]}>
            <View style={styles.modalHandle} />
            <View style={styles.successIcon}>
              <Ionicons name="checkmark-circle" size={44} color={colors.success} />
            </View>
            <Text style={styles.modalTitle}>Pedido criado!</Text>
            <Text style={styles.modalSub}>Confirmação enviada a você, ao lojista e ao administrador.</Text>
            {created?.map((o) => (
              <View key={o.id} style={styles.orderRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.orderStore}>{o.store_name}</Text>
                  <Text style={styles.orderTotal}>{money(o.total)}</Text>
                </View>
                <Pressable
                  testID={`view-order-${o.id}`}
                  onPress={() => {
                    setCreated(null);
                    router.push(`/order/${o.id}?token=${o.token}`);
                  }}
                  style={styles.ghostBtn}
                >
                  <Ionicons name="eye-outline" size={18} color={colors.brandPrimary} />
                </Pressable>
                <Pressable
                  testID={`send-whatsapp-${o.id}`}
                  onPress={() => sendOrder(o)}
                  style={styles.waBtn}
                >
                  <Ionicons name="logo-whatsapp" size={18} color="#fff" />
                  <Text style={styles.waText}>Enviar</Text>
                </Pressable>
              </View>
            ))}
            <Button
              title="Concluir"
              variant="outline"
              onPress={() => {
                setCreated(null);
                router.push("/(customer)/orders");
              }}
              testID="done-button"
              style={{ marginTop: spacing.md }}
            />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  header: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  title: { fontSize: font["2xl"], fontWeight: "800", color: colors.onSurface },
  subtitle: { fontSize: font.base, color: colors.onSurfaceTertiary, marginTop: 2 },
  group: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.lg,
    ...shadow.card,
  },
  groupHeader: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm },
  groupName: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  item: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: spacing.sm },
  itemImg: { width: 48, height: 48, borderRadius: radius.sm, backgroundColor: colors.surfaceTertiary },
  itemName: { fontSize: font.base, fontWeight: "600", color: colors.onSurface },
  itemPrice: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
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
  subRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  subLabel: { fontSize: font.base, color: colors.onSurfaceTertiary },
  subValue: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  couponRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md },
  couponInput: {
    flex: 1,
    height: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    color: colors.onSurface,
    fontSize: font.base,
    backgroundColor: colors.surface,
  },
  couponApply: {
    paddingHorizontal: spacing.lg,
    height: 44,
    borderRadius: radius.md,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  couponApplyText: { color: colors.onBrandTertiary, fontWeight: "800", fontSize: font.base },
  couponApplied: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.md,
    backgroundColor: colors.brandTertiary,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  couponAppliedText: { flex: 1, fontSize: font.base, fontWeight: "700", color: colors.onBrandTertiary },
  discountRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.xs },
  custWhatsInput: {
    height: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    color: colors.onSurface,
    fontSize: font.base,
    backgroundColor: colors.surface,
    marginBottom: spacing.md,
  },
  discountLabel: { fontSize: font.base, color: colors.success },
  discountValue: { fontSize: font.base, fontWeight: "700", color: colors.success },
  footer: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: colors.surfaceSecondary,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    padding: spacing.lg,
    ...shadow.float,
  },
  totalRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.md },
  totalLabel: { fontSize: font.lg, color: colors.onSurfaceTertiary },
  totalValue: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface },
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  modalCard: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    padding: spacing.lg,
  },
  modalHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.borderStrong,
    alignSelf: "center",
    marginBottom: spacing.lg,
  },
  successIcon: { alignItems: "center", marginBottom: spacing.sm },
  modalTitle: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface, textAlign: "center" },
  modalSub: { fontSize: font.base, color: colors.onSurfaceTertiary, textAlign: "center", marginBottom: spacing.lg },
  orderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  orderStore: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  orderTotal: { fontSize: font.sm, color: colors.onSurfaceTertiary },
  ghostBtn: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  waBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: "#25D366",
    paddingHorizontal: spacing.md,
    height: 40,
    borderRadius: radius.sm,
  },
  waText: { color: "#fff", fontWeight: "700", fontSize: font.base },
});
