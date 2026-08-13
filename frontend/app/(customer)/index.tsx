import { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  RefreshControl,
  Dimensions,
} from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api, fileUrl } from "@/src/api";
import { Loading, EmptyState, ErrorState } from "@/src/ui";
import { colors, spacing, radius, font, shadow } from "@/src/theme";

const { width } = Dimensions.get("window");
const GAP = spacing.lg;
const CARD_W = (width - GAP * 3) / 2;

type Store = {
  id: string;
  name: string;
  description?: string;
  logo?: string;
  cover?: string;
  product_count?: number;
};

const COVER =
  "https://images.unsplash.com/photo-1542838132-92c53300491e?crop=entropy&cs=srgb&fm=jpg&w=600&q=80";

export default function Marketplace() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [stores, setStores] = useState<Store[]>([]);
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.stores();
      setStores(data);
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

  const renderCard = ({ item }: { item: Store }) => {
    const logo = fileUrl(item.logo);
    return (
      <Pressable
        testID={`store-card-${item.id}`}
        style={({ pressed }) => [styles.card, pressed && { opacity: 0.9 }]}
        onPress={() => router.push(`/store/${item.id}`)}
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

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.hello}>Feira Online</Text>
        <Text style={styles.subtitle}>Escolha uma barraca para começar</Text>
      </View>

      {state === "loading" ? (
        <Loading />
      ) : state === "error" ? (
        <ErrorState onRetry={load} />
      ) : (
        <FlatList
          data={stores}
          keyExtractor={(s) => s.id}
          renderItem={renderCard}
          numColumns={2}
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
