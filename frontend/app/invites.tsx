import { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  ScrollView,
  Share,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { useI18n } from "@/src/i18n";
import { Loading, ErrorState, Button, Field, Chip, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, gradients } from "@/src/theme";

const qrUrl = (data: string) =>
  `https://api.qrserver.com/v1/create-qr-code/?size=200x200&margin=8&data=${encodeURIComponent(data)}`;

export default function InvitesScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const toast = useToast();
  const { user } = useAuth();
  const { t } = useI18n();

  const [stores, setStores] = useState<any[]>([]);
  const [invites, setInvites] = useState<any[]>([]);
  const [storeId, setStoreId] = useState<string>("");
  const [email, setEmail] = useState("");
  const [creating, setCreating] = useState(false);
  const [lastLink, setLastLink] = useState<string>("");
  const [state, setState] = useState<"loading" | "error" | "done">("loading");

  const load = useCallback(async () => {
    try {
      const [allStores, inv] = await Promise.all([api.stores().catch(() => []), api.invites().catch(() => [])]);
      let mine = allStores;
      if (user?.role === "lojista") mine = allStores.filter((s: any) => s.id === user.store_id);
      else if (user?.role === "admin") mine = allStores.filter((s: any) => s.admin_id === user.user_id);
      setStores(mine);
      setInvites(inv);
      if (!storeId && mine.length > 0) setStoreId(mine[0].id);
      setState("done");
    } catch {
      setState("error");
    }
  }, [user, storeId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [])
  );

  const create = async () => {
    if (!storeId) {
      toast(t("Selecione uma loja"), "info");
      return;
    }
    setCreating(true);
    try {
      const inv = await api.createInvite(storeId, email.trim());
      setLastLink(inv.link);
      setEmail("");
      toast(t("Convite criado"), "success");
      await load();
    } catch (e: any) {
      toast(e.message || "Falha ao criar convite", "error");
    } finally {
      setCreating(false);
    }
  };

  const shareLink = async (link: string) => {
    try {
      await Share.share({ message: `${t("Acesse o catálogo da nossa loja")}: ${link}` });
    } catch {}
  };

  const revoke = async (id: string) => {
    try {
      await api.revokeInvite(id);
      setInvites((prev) => prev.map((i) => (i.id === id ? { ...i, status: "revoked" } : i)));
      toast(t("Convite revogado"), "info");
    } catch (e: any) {
      toast(e.message || "Falha", "error");
    }
  };

  if (state === "loading") return <Loading />;
  if (state === "error") return <ErrorState onRetry={load} />;

  const statusColor = (s: string) =>
    s === "accepted" ? colors.brandPrimary : s === "revoked" ? colors.error : colors.warning;

  return (
    <View style={styles.container}>
      <LinearGradient colors={gradients.header} style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.headerRow}>
          <Pressable onPress={() => router.back()} style={styles.back}>
            <Ionicons name="chevron-back" size={24} color="#fff" />
          </Pressable>
          <Text style={styles.title}>{t("Convidar clientes")}</Text>
        </View>
      </LinearGradient>

      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <FlatList
          data={invites}
          keyExtractor={(i) => i.id}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 40 }}
          ListHeaderComponent={
            <View style={styles.formCard}>
              {stores.length > 1 && (
                <>
                  <Text style={styles.label}>{t("Loja")}</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
                    {stores.map((s) => (
                      <Chip key={s.id} label={s.name} active={storeId === s.id} onPress={() => setStoreId(s.id)} testID={`inv-store-${s.id}`} />
                    ))}
                  </ScrollView>
                </>
              )}
              <Field
                testID="invite-email"
                label={t("E-mail do cliente (opcional)")}
                value={email}
                onChangeText={setEmail}
                placeholder="cliente@exemplo.com"
                autoCapitalize="none"
                keyboardType="email-address"
              />
              <Button title={t("Gerar convite")} onPress={create} loading={creating} testID="create-invite-button" />

              {!!lastLink && (
                <View style={styles.qrBox}>
                  <Image source={{ uri: qrUrl(lastLink) }} style={styles.qr} contentFit="contain" />
                  <Text style={styles.linkText} numberOfLines={2}>
                    {lastLink}
                  </Text>
                  <Pressable onPress={() => shareLink(lastLink)} style={styles.shareBtn} testID="share-invite-button">
                    <Ionicons name="share-social" size={18} color="#fff" />
                    <Text style={styles.shareText}>{t("Compartilhar link")}</Text>
                  </Pressable>
                </View>
              )}
              <Text style={[styles.label, { marginTop: spacing.lg }]}>{t("Convites enviados")}</Text>
            </View>
          }
          renderItem={({ item }) => (
            <View style={styles.inviteRow} testID={`invite-${item.id}`}>
              <View style={{ flex: 1 }}>
                <Text style={styles.inviteStore}>{item.store_name}</Text>
                <Text style={styles.inviteEmail}>{item.client_email || t("Convite por link")}</Text>
              </View>
              <View style={[styles.statusPill, { backgroundColor: statusColor(item.status) }]}>
                <Text style={styles.statusText}>{item.status}</Text>
              </View>
              <Pressable onPress={() => shareLink(item.link || `${item.token}`)} hitSlop={6} style={styles.iconBtn}>
                <Ionicons name="share-outline" size={18} color={colors.brandPrimary} />
              </Pressable>
              {item.status !== "revoked" && (
                <Pressable onPress={() => revoke(item.id)} hitSlop={6} style={styles.iconBtn} testID={`revoke-${item.id}`}>
                  <Ionicons name="trash-outline" size={18} color={colors.error} />
                </Pressable>
              )}
            </View>
          )}
          ListEmptyComponent={<Text style={styles.dim}>{t("Nenhum convite ainda.")}</Text>}
        />
      </KeyboardAvoidingView>
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
  headerRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  back: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "rgba(255,255,255,0.18)",
    alignItems: "center",
    justifyContent: "center",
  },
  title: { fontSize: font.xl, fontWeight: "800", color: "#fff" },
  formCard: {},
  label: { fontSize: font.sm, fontWeight: "700", color: colors.onSurfaceTertiary, marginBottom: spacing.xs },
  chipRow: { gap: spacing.sm, paddingBottom: spacing.md },
  qrBox: {
    alignItems: "center",
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginTop: spacing.lg,
    ...shadow.card,
  },
  qr: { width: 180, height: 180, backgroundColor: "#fff", borderRadius: radius.md },
  linkText: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: spacing.sm, textAlign: "center" },
  shareBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.brandPrimary,
    paddingHorizontal: spacing.lg,
    height: 44,
    borderRadius: radius.pill,
    marginTop: spacing.md,
  },
  shareText: { color: "#fff", fontWeight: "800", fontSize: font.base },
  inviteRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    ...shadow.card,
  },
  inviteStore: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  inviteEmail: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  statusPill: { paddingHorizontal: spacing.sm, paddingVertical: 3, borderRadius: radius.pill },
  statusText: { color: "#fff", fontSize: 10, fontWeight: "800", textTransform: "uppercase" },
  iconBtn: {
    width: 34,
    height: 34,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  dim: { color: colors.onSurfaceTertiary, fontSize: font.base, textAlign: "center", marginTop: spacing.lg },
});
