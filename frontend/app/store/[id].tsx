import { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  Dimensions,
  ScrollView,
} from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useLocalSearchParams, useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";
import { api, fileUrl } from "@/src/api";
import { useCart } from "@/src/cart";
import { Loading, EmptyState, ErrorState, Chip, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money } from "@/src/theme";

const { width } = Dimensions.get("window");
const GAP = spacing.lg;
const CARD_W = (width - GAP * 3) / 2;

const SORTS = [
  { key: "recent", label: "Recentes" },
  { key: "name", label: "Nome" },
  { key: "price_asc", label: "Menor preço" },
  { key: "price_desc", label: "Maior preço" },
];

const PLACEHOLDER =
  "https://images.unsplash.com/photo-1659822887922-c1386185cc6b?crop=entropy&cs=srgb&fm=jpg&w=500&q=80";

export default function StoreCatalog() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { add, count } = useCart();
  const [store, setStore] = useState<any>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [sort, setSort] = useState("recent");
  const [state, setState] = useState<"loading" | "error" | "done">("loading");

  const load = useCallback(
    async (s = sort) => {
      try {
        const [st, pr] = await Promise.all([api.store(id), api.products(id, s)]);
        setStore(st);
        setProducts(pr);
        setState("done");
      } catch {
        setState("error");
      }
    },
    [id, sort]
  );

  useFocusEffect(
    useCallback(() => {
      load();
    }, [id])
  );

  const changeSort = async (key: string) => {
    setSort(key);
    setState("loading");
    await load(key);
  };

  const handleAdd = (p: any) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    add({
      product_id: p.id,
      name: p.name,
      price: p.price,
      image: p.image,
      store_id: store.id,
      store_name: store.name,
      store_whatsapp: store.whatsapp,
    });
    toast(`${p.name} adicionado à sacola`, "success");
  };

  if (state === "loading") return <Loading />;
  if (state === "error") return <ErrorState onRetry={() => load()} />;

  const logo = fileUrl(store?.logo);

  const renderProduct = ({ item }: { item: any }) => {
    const img = fileUrl(item.image);
    return (
      <View style={styles.pCard} testID={`product-card-${item.id}`}>
        <Image source={{ uri: img || PLACEHOLDER }} style={styles.pImg} contentFit="cover" transition={200} />
        <View style={styles.pBody}>
          <Text style={styles.pName} numberOfLines={2}>
            {item.name}
          </Text>
          {!!item.description && (
            <Text style={styles.pDesc} numberOfLines={1}>
              {item.description}
            </Text>
          )}
          <View style={styles.pRow}>
            <Text style={styles.pPrice}>{money(item.price)}</Text>
            <Pressable
              testID={`add-product-${item.id}`}
              onPress={() => handleAdd(item)}
              style={({ pressed }) => [styles.addBtn, pressed && { opacity: 0.8 }]}
            >
              <Ionicons name="add" size={22} color="#fff" />
            </Pressable>
          </View>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <FlatList
        data={products}
        keyExtractor={(p) => p.id}
        renderItem={renderProduct}
        numColumns={2}
        columnWrapperStyle={{ gap: GAP, paddingHorizontal: GAP }}
        contentContainerStyle={{ paddingBottom: insets.bottom + 100 }}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          <View>
            <View style={styles.hero}>
              <Image source={{ uri: logo || PLACEHOLDER }} style={StyleSheet.absoluteFill} contentFit="cover" />
              <LinearGradient
                colors={["rgba(26,28,25,0.15)", "rgba(26,28,25,0.85)"]}
                style={StyleSheet.absoluteFill}
              />
              <Pressable
                testID="back-button"
                onPress={() => router.back()}
                style={[styles.backBtn, { top: insets.top + spacing.sm }]}
              >
                <Ionicons name="chevron-back" size={24} color="#fff" />
              </Pressable>
              <View style={styles.heroInfo}>
                <Text style={styles.heroName}>{store?.name}</Text>
                {!!store?.description && (
                  <Text style={styles.heroDesc} numberOfLines={2}>
                    {store.description}
                  </Text>
                )}
              </View>
            </View>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.sortRow}
            >
              {SORTS.map((s) => (
                <Chip
                  key={s.key}
                  testID={`sort-${s.key}`}
                  label={s.label}
                  active={sort === s.key}
                  onPress={() => changeSort(s.key)}
                />
              ))}
            </ScrollView>
          </View>
        }
        ListEmptyComponent={
          <EmptyState
            icon="pricetags-outline"
            title="Esta barraca ainda não tem produtos"
            subtitle="Aguarde novidades em breve."
          />
        }
      />

      {count > 0 && (
        <Pressable
          testID="go-to-cart-button"
          onPress={() => router.push("/(customer)/cart")}
          style={[styles.cartCta, { bottom: insets.bottom + spacing.lg }]}
        >
          <Ionicons name="bag-handle" size={20} color="#fff" />
          <Text style={styles.cartCtaText}>Ver sacola ({count})</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  hero: { height: 220, justifyContent: "flex-end" },
  backBtn: {
    position: "absolute",
    left: spacing.lg,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(0,0,0,0.3)",
    alignItems: "center",
    justifyContent: "center",
  },
  heroInfo: { padding: spacing.lg },
  heroName: { fontSize: font["2xl"], fontWeight: "800", color: "#fff" },
  heroDesc: { fontSize: font.base, color: "rgba(255,255,255,0.9)", marginTop: 4 },
  sortRow: { gap: spacing.sm, paddingHorizontal: spacing.lg, paddingVertical: spacing.lg },
  pCard: {
    width: CARD_W,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    marginBottom: GAP,
    ...shadow.card,
  },
  pImg: {
    width: "100%",
    height: CARD_W * 0.85,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    backgroundColor: colors.surfaceTertiary,
  },
  pBody: { padding: spacing.md },
  pName: { fontSize: font.base, fontWeight: "700", color: colors.onSurface, minHeight: 36 },
  pDesc: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  pRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.sm },
  pPrice: { fontSize: font.lg, fontWeight: "800", color: colors.brandPrimary },
  addBtn: {
    width: 36,
    height: 36,
    borderRadius: radius.md,
    backgroundColor: colors.brandPrimary,
    alignItems: "center",
    justifyContent: "center",
  },
  cartCta: {
    position: "absolute",
    left: spacing.lg,
    right: spacing.lg,
    height: 54,
    borderRadius: radius.md,
    backgroundColor: colors.brandSecondary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    ...shadow.float,
  },
  cartCtaText: { color: "#fff", fontSize: font.lg, fontWeight: "700" },
});
