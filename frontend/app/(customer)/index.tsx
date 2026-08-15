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
import { Loading, EmptyState, ErrorState } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money } from "@/src/theme";

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
};

const COVER =
  "https://images.unsplash.com/photo-1542838132-92c53300491e?crop=entropy&cs=srgb&fm=jpg&w=600&q=80";
const PROD_PLACEHOLDER =
  "https://images.unsplash.com/photo-1659822887922-c1386185cc6b?crop=entropy&cs=srgb&fm=jpg&w=400&q=80";

export default function Marketplace() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [stores, setStores] = useState<Store[]>([]);
  const [featured, setFeatured] = useState<Store[]>([]);
  const [newProducts, setNewProducts] = useState<any[]>([]);
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ stores: Store[]; products: any[] } | null>(null);
  const [searching, setSearching] = useState(false);

  const load = useCallback(async () => {
    try {
      const [list, home] = await Promise.all([api.stores(), api.home()]);
      setStores(list);
      setFeatured(home.featured_stores || []);
      setNewProducts(home.new_products || []);
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
    return (
      <Pressable
        testID={`store-card-${item.id}`}
        style={({ pressed }) => [styles.card, pressed && { opacity: 0.9 }]}
        onPress={() => openStore(item.id)}
      >
        <Image source={{ uri: logo || COVER }} style={styles.cover} contentFit="cover" transition={200} />
        <View style={styles.logoBadge}>
          {logo ? (
            <Image source={{ uri: logo }} style={styles.logoImg} contentFit="cover" />
          ) : (
            <Ionicons name="leaf" size={18} color={colors.brandPrimary} />
          )}
        </View>
        <View style={styles.cardBody}>
          <Text style={styles.cardName} numberOfLines={1}>
            {item.name}
          </Text>
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
        placeholder="Buscar barracas ou produtos"
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

  const carousels = (
    <View>
      {featured.length > 0 && (
        <View style={{ marginBottom: spacing.lg }}>
          <Text style={styles.sectionTitle}>⭐ Destaques da feira</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.hRow}>
            {featured.map((s) => (
              <Pressable
                key={s.id}
                testID={`featured-store-${s.id}`}
                style={styles.featuredCard}
                onPress={() => openStore(s.id)}
              >
                <Image source={{ uri: fileUrl(s.logo) || COVER }} style={styles.featuredImg} contentFit="cover" />
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
      <Text style={styles.sectionTitle}>Todas as barracas</Text>
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
                <Text style={styles.sectionTitle}>Barracas</Text>
                {r.stores.map((s) => (
                  <Pressable
                    key={s.id}
                    testID={`result-store-${s.id}`}
                    style={styles.resultRow}
                    onPress={() => openStore(s.id)}
                  >
                    <Image source={{ uri: fileUrl(s.logo) || COVER }} style={styles.resultImg} contentFit="cover" />
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
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.hello}>Feira Online</Text>
        <Text style={styles.subtitle}>Compre direto das barracas da sua feira</Text>
        {searchBar}
      </View>

      {state === "loading" ? (
        <Loading />
      ) : state === "error" ? (
        <ErrorState onRetry={load} />
      ) : query.trim() ? (
        renderSearch()
      ) : (
        <FlatList
          data={stores}
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
              title="Nenhuma barraca disponível"
              subtitle="Volte em breve — novas barracas estão chegando."
            />
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  header: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  hello: { fontSize: font["2xl"], fontWeight: "800", color: colors.onSurface },
  subtitle: { fontSize: font.base, color: colors.onSurfaceTertiary, marginTop: 2 },
  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    height: 46,
    marginTop: spacing.md,
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
  cardBody: { padding: spacing.md, paddingTop: spacing.xl },
  cardName: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  cardMeta: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
});
