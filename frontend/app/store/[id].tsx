import { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  Dimensions,
  ScrollView,
  Modal,
  TextInput,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useLocalSearchParams, useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";
import { api, fileUrl } from "@/src/api";
import { useCart } from "@/src/cart";
import { Loading, EmptyState, ErrorState, Chip, Stars, Button, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money, CATEGORIES } from "@/src/theme";
import { regionalImageFor, PRODUCT_PLACEHOLDER } from "@/src/images";

const { width } = Dimensions.get("window");
const GAP = spacing.lg;
const CARD_W = (width - GAP * 3) / 2;

const SORTS = [
  { key: "recent", label: "Recentes" },
  { key: "name", label: "Nome" },
  { key: "price_asc", label: "Menor preço" },
  { key: "price_desc", label: "Maior preço" },
];

const CATS = ["Todos", ...CATEGORIES];
const PLACEHOLDER = PRODUCT_PLACEHOLDER;

export default function StoreCatalog() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { add, count } = useCart();
  const [store, setStore] = useState<any>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [reviews, setReviews] = useState<any[]>([]);
  const [isFav, setIsFav] = useState(false);
  const [sort, setSort] = useState("recent");
  const [category, setCategory] = useState("Todos");
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [reviewOpen, setReviewOpen] = useState(false);
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(
    async (s = sort, c = category) => {
      try {
        const [st, pr, rv, favs] = await Promise.all([
          api.store(id),
          api.products(id, s, c),
          api.reviews(id).catch(() => ({ reviews: [] })),
          api.favoriteIds().catch(() => []),
        ]);
        setStore(st);
        setProducts(pr);
        setReviews(rv.reviews || []);
        setIsFav((favs || []).includes(id));
        setState("done");
      } catch {
        setState("error");
      }
    },
    [id, sort, category]
  );

  useFocusEffect(
    useCallback(() => {
      load();
    }, [id])
  );

  const changeSort = async (key: string) => {
    setSort(key);
    setState("loading");
    await load(key, category);
  };

  const changeCategory = async (key: string) => {
    setCategory(key);
    setState("loading");
    await load(sort, key);
  };

  const toggleFav = async () => {
    const next = !isFav;
    setIsFav(next);
    try {
      if (next) {
        await api.addFavorite(id);
        toast("Loja adicionada aos favoritos", "success");
      } else {
        await api.removeFavorite(id);
      }
    } catch {
      setIsFav(!next);
    }
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

  const submitReview = async () => {
    setSubmitting(true);
    try {
      await api.addReview(id, rating, comment);
      setReviewOpen(false);
      setComment("");
      toast("Avaliação enviada. Obrigado!", "success");
      await load();
    } catch (e: any) {
      toast(e.message || "Falha ao avaliar", "error");
    } finally {
      setSubmitting(false);
    }
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

  const footer = (
    <View style={styles.reviewsSection}>
      <View style={styles.reviewsHeader}>
        <Text style={styles.sectionH}>Avaliações</Text>
        <Pressable testID="write-review-button" onPress={() => setReviewOpen(true)} style={styles.reviewBtn}>
          <Ionicons name="star" size={14} color="#fff" />
          <Text style={styles.reviewBtnText}>Avaliar</Text>
        </Pressable>
      </View>
      <Stars value={store?.avg_rating || 0} count={store?.review_count || 0} size={16} />
      {reviews.length === 0 ? (
        <Text style={styles.dim}>Seja o primeiro a avaliar esta loja.</Text>
      ) : (
        reviews.map((r) => (
          <View key={r.id} style={styles.reviewCard} testID={`review-${r.id}`}>
            <View style={styles.reviewTop}>
              <Text style={styles.reviewName}>{r.user_name || "Cliente"}</Text>
              <Stars value={r.rating} size={12} />
            </View>
            {!!r.comment && <Text style={styles.reviewComment}>{r.comment}</Text>}
          </View>
        ))
      )}
    </View>
  );

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
              <Image
                source={{ uri: logo || regionalImageFor(id) }}
                style={StyleSheet.absoluteFill}
                contentFit="cover"
              />
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
              <Pressable
                testID="store-fav-toggle"
                onPress={toggleFav}
                style={[styles.favBtn, { top: insets.top + spacing.sm }]}
              >
                <Ionicons name={isFav ? "heart" : "heart-outline"} size={22} color={isFav ? colors.brandSecondary : "#fff"} />
              </Pressable>
              <View style={styles.heroInfo}>
                <View style={styles.heroTitleRow}>
                  <Text style={styles.heroName}>{store?.name}</Text>
                  <View
                    testID="store-hero-status"
                    style={[styles.heroStatus, { backgroundColor: store?.online ? "rgba(58,107,76,0.95)" : "rgba(60,62,58,0.85)" }]}
                  >
                    <View style={[styles.statusDot, { backgroundColor: store?.online ? "#8FE3B0" : "#C9C9C4" }]} />
                    <Text style={styles.statusText}>{store?.online ? "Aberta" : "Fechada"}</Text>
                  </View>
                </View>
                <View style={{ marginTop: 4 }}>
                  <Stars value={store?.avg_rating || 0} count={store?.review_count || 0} size={13} />
                </View>
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
              contentContainerStyle={styles.chipRow}
            >
              {CATS.map((c) => (
                <Chip
                  key={c}
                  testID={`cat-${c}`}
                  label={c}
                  active={category === c}
                  onPress={() => changeCategory(c)}
                />
              ))}
            </ScrollView>
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
        ListFooterComponent={footer}
        ListEmptyComponent={
          <EmptyState
            icon="pricetags-outline"
            title="Nenhum produto nesta categoria"
            subtitle="Tente outra categoria ou volte em breve."
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

      <Modal visible={reviewOpen} transparent animationType="slide" onRequestClose={() => setReviewOpen(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.modalOverlay}>
          <View style={[styles.modalCard, { paddingBottom: insets.bottom + spacing.lg }]}>
            <View style={styles.modalHandle} />
            <Text style={styles.modalTitle}>Avaliar {store?.name}</Text>
            <View style={styles.starPicker}>
              {[1, 2, 3, 4, 5].map((i) => (
                <Pressable key={i} testID={`rate-star-${i}`} onPress={() => setRating(i)} hitSlop={6}>
                  <Ionicons
                    name={i <= rating ? "star" : "star-outline"}
                    size={36}
                    color={i <= rating ? "#E8A33D" : colors.borderStrong}
                  />
                </Pressable>
              ))}
            </View>
            <TextInput
              testID="review-comment-input"
              value={comment}
              onChangeText={setComment}
              placeholder="Conte como foi sua experiência (opcional)"
              placeholderTextColor={colors.muted}
              multiline
              style={styles.reviewInput}
            />
            <Button title="Enviar avaliação" onPress={submitReview} loading={submitting} testID="submit-review-button" />
          </View>
        </KeyboardAvoidingView>
      </Modal>
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
  favBtn: {
    position: "absolute",
    right: spacing.lg,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(0,0,0,0.3)",
    alignItems: "center",
    justifyContent: "center",
  },
  heroInfo: { padding: spacing.lg },
  heroTitleRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, flexWrap: "wrap" },
  heroStatus: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radius.pill,
  },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  statusText: { color: "#fff", fontSize: 11, fontWeight: "700" },
  heroName: { fontSize: font["2xl"], fontWeight: "800", color: "#fff" },
  heroDesc: { fontSize: font.base, color: "rgba(255,255,255,0.9)", marginTop: 4 },
  chipRow: { gap: spacing.sm, paddingHorizontal: spacing.lg, paddingTop: spacing.lg },
  sortRow: { gap: spacing.sm, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
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
  reviewsSection: { paddingHorizontal: GAP, paddingTop: spacing.sm, gap: spacing.sm },
  reviewsHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sectionH: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface },
  reviewBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.brandPrimary,
    paddingHorizontal: spacing.md,
    height: 36,
    borderRadius: radius.pill,
  },
  reviewBtnText: { color: "#fff", fontWeight: "700", fontSize: font.base },
  dim: { color: colors.onSurfaceTertiary, fontSize: font.base, marginTop: spacing.xs },
  reviewCard: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.xs,
    ...shadow.card,
  },
  reviewTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  reviewName: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  reviewComment: { fontSize: font.base, color: colors.onSurfaceTertiary, marginTop: spacing.xs },
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
  modalTitle: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface, marginBottom: spacing.lg },
  starPicker: { flexDirection: "row", justifyContent: "center", gap: spacing.sm, marginBottom: spacing.lg },
  reviewInput: {
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    fontSize: font.lg,
    color: colors.onSurface,
    height: 90,
    textAlignVertical: "top",
    marginBottom: spacing.lg,
  },
});
