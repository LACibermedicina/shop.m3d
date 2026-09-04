import { useState, useCallback, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  RefreshControl,
  Dimensions,
  ScrollView,
  TextInput,
  ActivityIndicator,
} from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api, fileUrl } from "@/src/api";
import { Loading, EmptyState, ErrorState, Stars, useToast } from "@/src/ui";
import { useI18n } from "@/src/i18n";
import { LangSelector } from "@/src/LangSelector";
import { colors, spacing, radius, font, shadow, money, gradients } from "@/src/theme";
import { LinearGradient } from "expo-linear-gradient";
import { regionalImageFor, PRODUCT_PLACEHOLDER } from "@/src/images";

const { width } = Dimensions.get("window");
const GAP = spacing.lg;
const CARD_W = (width - GAP * 3) / 2;

type Store = {
  id: string;
  name: string;
  description?: string;
  logo?: string;
  product_count?: number;
  featured?: boolean;
  avg_rating?: number;
  review_count?: number;
};

const COVER = regionalImageFor("default");
const PROD_PLACEHOLDER = PRODUCT_PLACEHOLDER;

export default function Marketplace() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { t } = useI18n();
  const [stores, setStores] = useState<Store[]>([]);
  const [featured, setFeatured] = useState<Store[]>([]);
  const [newProducts, setNewProducts] = useState<any[]>([]);
  const [favIds, setFavIds] = useState<string[]>([]);
  const [groups, setGroups] = useState<any[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<string>("");
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ stores: Store[]; products: any[] } | null>(null);
  const [searching, setSearching] = useState(false);

  const load = useCallback(async () => {
    try {
      const [list, home, favs, grps] = await Promise.all([
        api.stores(),
        api.home(),
        api.favoriteIds().catch(() => []),
        api.groups().catch(() => []),
      ]);
      setStores(list);
      setFeatured(home.featured_stores || []);
      setNewProducts(home.new_products || []);
      setFavIds(favs || []);
      setGroups(grps || []);
      setState("done");
    } catch {
      setState("error");
    }
  }, []);

  const toggleFav = async (id: string) => {
    const isFav = favIds.includes(id);
    setFavIds((prev) => (isFav ? prev.filter((x) => x !== id) : [...prev, id]));
    try {
      if (isFav) await api.removeFavorite(id);
      else {
        await api.addFavorite(id);
        toast("Loja adicionada aos favoritos", "success");
      }
    } catch {
      // revert on error
      setFavIds((prev) => (isFav ? [...prev, id] : prev.filter((x) => x !== id)));
    }
  };

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setResults(null);
      return;
    }
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const r = await api.search(q);
        setResults(r);
      } catch {
        setResults({ stores: [], products: [] });
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const openStore = (id: string) => router.push(`/store/${id}`);

  const renderCard = ({ item }: { item: Store }) => {
    const logo = fileUrl(item.logo);
    const isFav = favIds.includes(item.id);
    return (
      <Pressable
        testID={`store-card-${item.id}`}
        style={({ pressed }) => [styles.card, pressed && { opacity: 0.9 }]}
        onPress={() => openStore(item.id)}
      >
        <Image
          source={{ uri: logo || regionalImageFor(item.id) }}
          style={styles.cover}
          contentFit="cover"
          transition={200}
        />
        <View
          testID={`store-status-${item.id}`}
          style={[styles.statusPill, { backgroundColor: item.online ? "rgba(58,107,76,0.92)" : "rgba(60,62,58,0.8)" }]}
        >
          <View style={[styles.statusDot, { backgroundColor: item.online ? "#8FE3B0" : "#C9C9C4" }]} />
          <Text style={styles.statusText}>{item.online ? "Aberta" : "Fechada"}</Text>
        </View>
        <Pressable
          testID={`fav-toggle-${item.id}`}
          onPress={() => toggleFav(item.id)}
          hitSlop={8}
          style={styles.heartBtn}
        >
          <Ionicons name={isFav ? "heart" : "heart-outline"} size={18} color={isFav ? colors.brandSecondary : "#fff"} />
        </Pressable>
        <View style={styles.logoBadge}>
          {logo ? (
            <Image source={{ uri: logo }} style={styles.logoImg} contentFit="cover" />
          ) : (
            <Ionicons name="storefront" size={18} color={colors.brandPrimary} />
          )}
        </View>
        <View style={styles.cardBody}>
          <Text style={styles.cardName} numberOfLines={1}>
            {item.name}
          </Text>
          <Stars value={item.avg_rating || 0} count={item.review_count || 0} size={12} />
          <Text style={styles.cardMeta}>
            {item.product_count || 0} {item.product_count === 1 ? "produto" : "produtos"}
          </Text>
        </View>
      </Pressable>
    );
  };

  const searchBar = (
    <View style={styles.searchBar}>
      <Ionicons name="search" size={18} color={colors.muted} />
      <TextInput
        testID="search-input"
        value={query}
        onChangeText={setQuery}
        placeholder={t("Buscar lojas ou produtos")}
        placeholderTextColor={colors.muted}
        style={styles.searchInput}
        autoCapitalize="none"
        returnKeyType="search"
      />
      {query.length > 0 && (
        <Pressable testID="search-clear" onPress={() => setQuery("")} hitSlop={8}>
          <Ionicons name="close-circle" size={18} color={colors.muted} />
        </Pressable>
      )}
    </View>
  );

  const favStores = stores.filter((s) => favIds.includes(s.id));

  const carousels = (
    <View>
      {favStores.length > 0 && (
        <View style={{ marginBottom: spacing.lg }}>
          <Text style={styles.sectionTitle}>❤️ Suas lojas favoritas</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.hRow}>
            {favStores.map((s) => (
              <Pressable
                key={s.id}
                testID={`fav-store-${s.id}`}
                style={styles.featuredCard}
                onPress={() => openStore(s.id)}
              >
                <Image source={{ uri: fileUrl(s.logo) || regionalImageFor(s.id) }} style={styles.featuredImg} contentFit="cover" />
                <View style={styles.featuredOverlay}>
                  <Text style={styles.featuredName} numberOfLines={1}>{s.name}</Text>
                  <Text style={styles.featuredMeta}>{s.product_count || 0} produtos</Text>
                </View>
              </Pressable>
            ))}
          </ScrollView>
        </View>
      )}
      {featured.length > 0 && (
        <View style={{ marginBottom: spacing.lg }}>
          <Text style={styles.sectionTitle}>⭐ {t("Destaques da fronteira")}</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.hRow}>
            {featured.map((s) => (
              <Pressable
                key={s.id}
                testID={`featured-store-${s.id}`}
                style={styles.featuredCard}
                onPress={() => openStore(s.id)}
              >
                <Image source={{ uri: fileUrl(s.logo) || regionalImageFor(s.id) }} style={styles.featuredImg} contentFit="cover" />
                <View style={styles.featuredOverlay}>
                  <Text style={styles.featuredName} numberOfLines={1}>
                    {s.name}
                  </Text>
                  <Text style={styles.featuredMeta}>{s.product_count || 0} produtos</Text>
                </View>
              </Pressable>
            ))}
          </ScrollView>
        </View>
      )}
      {newProducts.length > 0 && (
        <View style={{ marginBottom: spacing.lg }}>
          <Text style={styles.sectionTitle}>🆕 Novidades</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.hRow}>
            {newProducts.map((p) => (
              <Pressable
                key={p.id}
                testID={`new-product-${p.id}`}
                style={styles.newProdCard}
                onPress={() => openStore(p.store_id)}
              >
                <Image
                  source={{ uri: fileUrl(p.image) || PROD_PLACEHOLDER }}
                  style={styles.newProdImg}
                  contentFit="cover"
                />
                <Text style={styles.newProdName} numberOfLines={1}>
                  {p.name}
                </Text>
                <Text style={styles.newProdPrice}>{money(p.price)}</Text>
                <Text style={styles.newProdStore} numberOfLines={1}>
                  {p.store_name}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
        </View>
      )}
      {groups.length > 0 && (
        <View style={{ marginBottom: spacing.lg }}>
          <Text style={styles.sectionTitle}>🧭 {t("Áreas de interesse")}</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.hRow}>
            <Pressable
              testID="group-all"
              onPress={() => setSelectedGroup("")}
              style={[styles.groupChip, !selectedGroup && styles.groupChipActive]}
            >
              <Ionicons name="apps" size={18} color={!selectedGroup ? "#fff" : colors.brandPrimary} />
              <Text style={[styles.groupChipText, !selectedGroup && { color: "#fff" }]}>{t("Todas")}</Text>
            </Pressable>
            {groups.map((g) => {
              const active = selectedGroup === g.id;
              return (
                <Pressable
                  key={g.id}
                  testID={`group-${g.id}`}
                  onPress={() => setSelectedGroup(active ? "" : g.id)}
                  style={[styles.groupChip, active && { backgroundColor: g.color || colors.brandPrimary, borderColor: g.color || colors.brandPrimary }]}
                >
                  <Ionicons name={g.icon || "pricetags"} size={18} color={active ? "#fff" : g.color || colors.brandPrimary} />
                  <Text style={[styles.groupChipText, active && { color: "#fff" }, !active && { color: g.color || colors.brandPrimary }]}>
                    {t(g.name)}
                  </Text>
                </Pressable>
              );
            })}
          </ScrollView>
        </View>
      )}
      <Text style={styles.sectionTitle}>{selectedGroup ? t(groups.find((g) => g.id === selectedGroup)?.name || "Lojas") : t("Todas as lojas")}</Text>
    </View>
  );

  const renderSearch = () => {
    if (searching && !results) return <Loading />;
    const r = results || { stores: [], products: [] };
    const empty = r.stores.length === 0 && r.products.length === 0;
    return (
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: GAP, paddingBottom: insets.bottom + 40 }}
        showsVerticalScrollIndicator={false}
      >
        {empty ? (
          <EmptyState icon="search-outline" title="Nada encontrado" subtitle={`Sem resultados para "${query}"`} />
        ) : (
          <>
            {r.stores.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>Lojas</Text>
                {r.stores.map((s) => (
                  <Pressable
                    key={s.id}
                    testID={`result-store-${s.id}`}
                    style={styles.resultRow}
                    onPress={() => openStore(s.id)}
                  >
                    <Image source={{ uri: fileUrl(s.logo) || regionalImageFor(s.id) }} style={styles.resultImg} contentFit="cover" />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.resultName}>{s.name}</Text>
                      <Text style={styles.resultMeta}>{s.product_count || 0} produtos</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                  </Pressable>
                ))}
              </>
            )}
            {r.products.length > 0 && (
              <>
                <Text style={[styles.sectionTitle, { marginTop: spacing.lg }]}>Produtos</Text>
                {r.products.map((p) => (
                  <Pressable
                    key={p.id}
                    testID={`result-product-${p.id}`}
                    style={styles.resultRow}
                    onPress={() => openStore(p.store_id)}
                  >
                    <Image
                      source={{ uri: fileUrl(p.image) || PROD_PLACEHOLDER }}
                      style={styles.resultImg}
                      contentFit="cover"
                    />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.resultName}>{p.name}</Text>
                      <Text style={styles.resultMeta}>
                        {money(p.price)} • {p.store_name}
                      </Text>
                    </View>
                    <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                  </Pressable>
                ))}
              </>
            )}
          </>
        )}
      </ScrollView>
    );
  };

  return (
    <View style={styles.container}>
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
            <Ionicons name="basket" size={20} color="#fff" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.hello}>shop.m3d.pro</Text>
            <Text style={styles.subtitle}>{t("Compre de quem entende, na sua rede de confiança")}</Text>
          </View>
        </View>
        {searchBar}
      </LinearGradient>

      {state === "loading" ? (
        <Loading />
      ) : state === "error" ? (
        <ErrorState onRetry={load} />
      ) : query.trim() ? (
        renderSearch()
      ) : (
        <FlatList
          data={selectedGroup ? stores.filter((s: any) => (s.group_ids || []).includes(selectedGroup)) : stores}
          keyExtractor={(s) => s.id}
          renderItem={renderCard}
          numColumns={2}
          ListHeaderComponent={carousels}
          columnWrapperStyle={{ gap: GAP, paddingHorizontal: GAP }}
          contentContainerStyle={{ gap: GAP, paddingVertical: GAP, paddingBottom: insets.bottom + 40 }}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.brandPrimary} />}
          ListEmptyComponent={
            <EmptyState
              icon="basket-outline"
              title="Nenhuma loja disponível"
              subtitle="Volte em breve — novas lojas estão chegando."
            />
          }
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
  brandRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  groupChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: spacing.md,
    height: 40,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
  },
  groupChipActive: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  groupChipText: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  topBar: { flexDirection: "row", justifyContent: "flex-end", marginBottom: spacing.sm },
  brandBadge: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    backgroundColor: "rgba(255,255,255,0.18)",
    alignItems: "center",
    justifyContent: "center",
  },
  hello: { fontSize: font.xl, fontWeight: "800", color: "#fff" },
  subtitle: { fontSize: font.sm, color: "rgba(255,255,255,0.85)", marginTop: 2 },
  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: "#fff",
    borderWidth: 0,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    height: 48,
    marginTop: spacing.lg,
    ...shadow.card,
  },
  searchInput: { flex: 1, fontSize: font.base, color: colors.onSurface, paddingVertical: 0 },
  sectionTitle: {
    fontSize: font.lg,
    fontWeight: "800",
    color: colors.onSurface,
    paddingHorizontal: GAP,
    marginBottom: spacing.md,
  },
  hRow: { gap: spacing.md, paddingHorizontal: GAP },
  featuredCard: {
    width: 220,
    height: 120,
    borderRadius: radius.lg,
    overflow: "hidden",
    backgroundColor: colors.surfaceTertiary,
    ...shadow.card,
  },
  featuredImg: { width: "100%", height: "100%" },
  featuredOverlay: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    padding: spacing.md,
    backgroundColor: "rgba(26,28,25,0.55)",
  },
  featuredName: { color: "#fff", fontSize: font.lg, fontWeight: "800" },
  featuredMeta: { color: "rgba(255,255,255,0.85)", fontSize: font.sm },
  newProdCard: { width: 120 },
  newProdImg: {
    width: 120,
    height: 120,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceTertiary,
    marginBottom: spacing.xs,
  },
  newProdName: { fontSize: font.base, fontWeight: "600", color: colors.onSurface },
  newProdPrice: { fontSize: font.base, fontWeight: "800", color: colors.brandPrimary },
  newProdStore: { fontSize: font.sm, color: colors.onSurfaceTertiary },
  resultRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    ...shadow.card,
  },
  resultImg: { width: 52, height: 52, borderRadius: radius.sm, backgroundColor: colors.surfaceTertiary },
  resultName: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  resultMeta: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  card: {
    width: CARD_W,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    ...shadow.card,
  },
  cover: {
    width: "100%",
    height: CARD_W * 0.7,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    backgroundColor: colors.surfaceTertiary,
  },
  logoBadge: {
    position: "absolute",
    top: CARD_W * 0.7 - 20,
    left: spacing.md,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 2,
    borderColor: colors.surfaceSecondary,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    ...shadow.card,
  },
  logoImg: { width: "100%", height: "100%" },
  heartBtn: {
    position: "absolute",
    top: spacing.sm,
    right: spacing.sm,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "rgba(26,28,25,0.35)",
    alignItems: "center",
    justifyContent: "center",
  },
  statusPill: {
    position: "absolute",
    top: spacing.sm,
    left: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radius.pill,
  },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  statusText: { color: "#fff", fontSize: 11, fontWeight: "700" },
  cardBody: { padding: spacing.md, paddingTop: spacing.xl },
  cardName: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  cardMeta: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
});
