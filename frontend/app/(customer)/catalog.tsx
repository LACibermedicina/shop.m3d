import { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  ScrollView,
  Modal,
  Linking,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";
import { api, fileUrl } from "@/src/api";
import { useI18n } from "@/src/i18n";
import { LangSelector } from "@/src/LangSelector";
import { Loading, EmptyState, ErrorState, Button, Field, Chip, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money, gradients } from "@/src/theme";
import { PRODUCT_PLACEHOLDER } from "@/src/images";

export default function PersonalCatalog() {
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const router = useRouter();
  const { t } = useI18n();

  const [data, setData] = useState<any>({ items: [], total: 0, count: 0, stores: [], categories: [] });
  const [storeFilter, setStoreFilter] = useState("");
  const [catFilter, setCatFilter] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [sendOpen, setSendOpen] = useState(false);
  const [whats, setWhats] = useState("");
  const [notes, setNotes] = useState("");
  const [sending, setSending] = useState(false);

  const load = useCallback(
    async (sf = storeFilter, cf = catFilter) => {
      try {
        const res = await api.catalog(sf, cf);
        setData(res);
        // por padrão, todos os itens visíveis ficam selecionados
        setSelected(new Set(res.items.map((i: any) => i.id)));
        setState("done");
      } catch {
        setState("error");
      }
    },
    [storeFilter, catFilter]
  );

  useFocusEffect(
    useCallback(() => {
      load();
    }, [])
  );

  const applyStore = async (sid: string) => {
    const next = storeFilter === sid ? "" : sid;
    setStoreFilter(next);
    setState("loading");
    await load(next, catFilter);
  };
  const applyCat = async (c: string) => {
    const next = catFilter === c || c === "Todos" ? "" : c;
    setCatFilter(next);
    setState("loading");
    await load(storeFilter, next);
  };

  const toggleSelect = (id: string) => {
    Haptics.selectionAsync();
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  };

  const changeQty = async (item: any, delta: number) => {
    const q = Math.max(1, (item.qty || 1) + delta);
    setData((d: any) => ({ ...d, items: d.items.map((i: any) => (i.id === item.id ? { ...i, qty: q } : i)) }));
    try {
      await api.updateCatalogItem(item.id, q);
    } catch {}
  };

  const removeItem = async (item: any) => {
    setData((d: any) => ({ ...d, items: d.items.filter((i: any) => i.id !== item.id) }));
    try {
      await api.removeCatalogItem(item.id);
      toast(t("Item removido"), "info");
    } catch {}
  };

  const openPdf = async () => {
    try {
      const url = await api.catalogReportUrl(storeFilter, catFilter);
      Linking.openURL(url);
    } catch {
      toast("Falha ao gerar PDF", "error");
    }
  };

  const doSend = async () => {
    const ids = Array.from(selected);
    if (ids.length === 0) {
      toast(t("Selecione ao menos um item"), "info");
      return;
    }
    setSending(true);
    try {
      const res = await api.sendCatalog(ids, notes, "", whats);
      setSendOpen(false);
      setWhats("");
      setNotes("");
      const n = res?.orders?.length || 0;
      toast(`${n} ${t("pedido(s) enviado(s) aos lojistas")}`, "success");
      await load();
      router.push("/(customer)/orders");
    } catch (e: any) {
      toast(e.message || "Falha ao enviar", "error");
    } finally {
      setSending(false);
    }
  };

  const selectedTotal = data.items
    .filter((i: any) => selected.has(i.id))
    .reduce((a: number, i: any) => a + i.price * i.qty, 0);

  const cats = ["Todos", ...(data.categories || [])];

  const header = (
    <LinearGradient
      colors={gradients.header}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={[styles.header, { paddingTop: insets.top + spacing.sm }]}
    >
      <View style={styles.topBar}>
        <LangSelector variant="light" />
      </View>
      <View style={styles.brandRow}>
        <View style={styles.brandBadge}>
          <Ionicons name="albums" size={20} color="#fff" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.hello}>{t("Meu Catálogo")}</Text>
          <Text style={styles.subtitle}>
            {data.count} {t("itens")} · {money(data.total)}
          </Text>
        </View>
      </View>
    </LinearGradient>
  );

  const filters = (
    <View style={{ paddingTop: spacing.md }}>
      <Text style={styles.filterLabel}>{t("Filtrar por loja")}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
        <Chip label={t("Todas")} active={!storeFilter} onPress={() => applyStore("")} testID="cat-store-all" />
        {(data.stores || []).map((s: any) => (
          <Chip
            key={s.store_id}
            testID={`cat-store-${s.store_id}`}
            label={`${s.store_name} (${s.count})`}
            active={storeFilter === s.store_id}
            onPress={() => applyStore(s.store_id)}
          />
        ))}
      </ScrollView>
      <Text style={styles.filterLabel}>{t("Categoria")}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
        {cats.map((c: string) => (
          <Chip
            key={c}
            testID={`cat-cat-${c}`}
            label={t(c)}
            active={c === "Todos" ? !catFilter : catFilter === c}
            onPress={() => applyCat(c)}
          />
        ))}
      </ScrollView>
    </View>
  );

  const renderItem = ({ item }: { item: any }) => {
    const img = fileUrl(item.image);
    const isSel = selected.has(item.id);
    return (
      <View style={styles.itemCard} testID={`catalog-item-${item.id}`}>
        <Pressable onPress={() => toggleSelect(item.id)} style={styles.checkbox} testID={`select-${item.id}`}>
          <Ionicons
            name={isSel ? "checkbox" : "square-outline"}
            size={24}
            color={isSel ? colors.brandPrimary : colors.borderStrong}
          />
        </Pressable>
        <Image source={{ uri: img || PRODUCT_PLACEHOLDER }} style={styles.itemImg} contentFit="cover" />
        <View style={{ flex: 1 }}>
          <View style={styles.storeBadge}>
            <Ionicons name="storefront" size={11} color={colors.brandPrimary} />
            <Text style={styles.storeBadgeText} numberOfLines={1}>
              {item.store_name}
            </Text>
          </View>
          <Text style={styles.itemName} numberOfLines={2}>
            {item.name}
          </Text>
          <View style={styles.itemBottom}>
            <Text style={styles.itemPrice}>{money(item.price)}</Text>
            <View style={styles.qtyRow}>
              <Pressable testID={`qty-minus-${item.id}`} onPress={() => changeQty(item, -1)} style={styles.qtyBtn}>
                <Ionicons name="remove" size={16} color={colors.brandPrimary} />
              </Pressable>
              <Text style={styles.qtyText}>{item.qty}</Text>
              <Pressable testID={`qty-plus-${item.id}`} onPress={() => changeQty(item, 1)} style={styles.qtyBtn}>
                <Ionicons name="add" size={16} color={colors.brandPrimary} />
              </Pressable>
              <Pressable testID={`remove-${item.id}`} onPress={() => removeItem(item)} style={styles.trashBtn} hitSlop={6}>
                <Ionicons name="trash-outline" size={18} color={colors.error} />
              </Pressable>
            </View>
          </View>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      {header}
      {state === "loading" ? (
        <Loading />
      ) : state === "error" ? (
        <ErrorState onRetry={() => load()} />
      ) : (
        <>
          <FlatList
            data={data.items}
            keyExtractor={(i) => i.id}
            renderItem={renderItem}
            ListHeaderComponent={data.items.length > 0 || storeFilter || catFilter ? filters : null}
            contentContainerStyle={{ paddingHorizontal: spacing.lg, paddingBottom: insets.bottom + 140 }}
            showsVerticalScrollIndicator={false}
            ListEmptyComponent={
              <EmptyState
                icon="albums-outline"
                title={t("Seu catálogo está vazio")}
                subtitle={t("Peça um convite a um lojista e adicione itens de várias lojas aqui.")}
              />
            }
          />
          {data.items.length > 0 && (
            <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.md }]}>
              <Pressable testID="catalog-pdf-button" onPress={openPdf} style={styles.pdfBtn}>
                <Ionicons name="document-text-outline" size={20} color={colors.brandPrimary} />
                <Text style={styles.pdfBtnText}>{t("Gerar PDF")}</Text>
              </Pressable>
              <Pressable testID="catalog-send-button" onPress={() => setSendOpen(true)} style={styles.sendBtn}>
                <Ionicons name="paper-plane" size={18} color="#fff" />
                <Text style={styles.sendBtnText}>
                  {t("Enviar")} ({selected.size}) · {money(selectedTotal)}
                </Text>
              </Pressable>
            </View>
          )}
        </>
      )}

      <Modal visible={sendOpen} transparent animationType="slide" onRequestClose={() => setSendOpen(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.modalOverlay}>
          <View style={[styles.modalCard, { paddingBottom: insets.bottom + spacing.lg }]}>
            <View style={styles.modalHandle} />
            <Text style={styles.modalTitle}>{t("Enviar aos lojistas")}</Text>
            <Text style={styles.modalSub}>
              {t("Os itens serão separados por loja e cada lojista recebe apenas os seus, em PDF e link.")}
            </Text>
            <Field
              testID="send-whatsapp"
              label={t("Seu WhatsApp (opcional)")}
              value={whats}
              onChangeText={setWhats}
              placeholder="55 45 99999-9999"
              keyboardType="phone-pad"
            />
            <Field
              testID="send-notes"
              label={t("Observações (opcional)")}
              value={notes}
              onChangeText={setNotes}
              placeholder={t("Ex.: entregar à tarde")}
            />
            <Button title={t("Enviar aos lojistas")} onPress={doSend} loading={sending} testID="confirm-send-button" />
          </View>
        </KeyboardAvoidingView>
      </Modal>
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
  brandRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  brandBadge: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    backgroundColor: "rgba(255,255,255,0.18)",
    alignItems: "center",
    justifyContent: "center",
  },
  hello: { fontSize: font.xl, fontWeight: "800", color: "#fff" },
  subtitle: { fontSize: font.sm, color: "rgba(255,255,255,0.9)", marginTop: 2 },
  filterLabel: { fontSize: font.sm, fontWeight: "700", color: colors.onSurfaceTertiary, paddingLeft: 2, marginTop: spacing.sm },
  chipRow: { gap: spacing.sm, paddingVertical: spacing.sm },
  itemCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.sm,
    marginBottom: spacing.sm,
    ...shadow.card,
  },
  checkbox: { padding: 2 },
  itemImg: { width: 60, height: 60, borderRadius: radius.md, backgroundColor: colors.surfaceTertiary },
  storeBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "rgba(74,124,89,0.10)",
    alignSelf: "flex-start",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radius.pill,
    marginBottom: 2,
  },
  storeBadgeText: { fontSize: 11, fontWeight: "700", color: colors.brandPrimary, maxWidth: 150 },
  itemName: { fontSize: font.base, fontWeight: "600", color: colors.onSurface },
  itemBottom: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 4 },
  itemPrice: { fontSize: font.base, fontWeight: "800", color: colors.brandPrimary },
  qtyRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  qtyBtn: {
    width: 28,
    height: 28,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  qtyText: { fontSize: font.base, fontWeight: "700", color: colors.onSurface, minWidth: 22, textAlign: "center" },
  trashBtn: { marginLeft: spacing.xs, padding: 4 },
  footer: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  pdfBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.lg,
    height: 52,
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: colors.brandPrimary,
    backgroundColor: colors.surface,
  },
  pdfBtnText: { color: colors.brandPrimary, fontWeight: "800", fontSize: font.base },
  sendBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    height: 52,
    borderRadius: radius.md,
    backgroundColor: colors.brandSecondary,
    ...shadow.float,
  },
  sendBtnText: { color: "#fff", fontWeight: "800", fontSize: font.base },
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
    marginBottom: spacing.md,
  },
  modalTitle: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface },
  modalSub: { fontSize: font.base, color: colors.onSurfaceTertiary, marginTop: 4, marginBottom: spacing.md },
});
