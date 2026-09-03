import { useState, useEffect, useCallback } from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api, fileUrl } from "@/src/api";
import { useAuth } from "@/src/auth";
import { useI18n } from "@/src/i18n";
import { storage } from "@/src/utils/storage";
import { Loading, ErrorState, Button, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, gradients } from "@/src/theme";
import { regionalImageFor } from "@/src/images";

export default function AcceptInvite() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { user, loading: authLoading, loginGoogle } = useAuth();
  const { t } = useI18n();
  const [invite, setInvite] = useState<any>(null);
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [accepting, setAccepting] = useState(false);

  const load = useCallback(async () => {
    try {
      const inv = await api.getInvite(token as string);
      setInvite(inv);
      setState("done");
    } catch {
      setState("error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const accept = async () => {
    if (!user) {
      await storage.setItem("pending_invite", token as string);
      await loginGoogle();
      return;
    }
    setAccepting(true);
    try {
      const res = await api.acceptInvite(token as string);
      await storage.removeItem("pending_invite");
      toast(`${t("Convite aceito")} · ${res.store_name}`, "success");
      router.replace(`/store/${res.store_id}`);
    } catch (e: any) {
      toast(e.message || "Falha ao aceitar", "error");
    } finally {
      setAccepting(false);
    }
  };

  if (state === "loading" || authLoading) return <Loading />;
  if (state === "error") return <ErrorState onRetry={load} />;

  const logo = fileUrl(invite?.store_logo);
  const revoked = invite?.status === "revoked";

  return (
    <View style={styles.container}>
      <LinearGradient colors={gradients.header} style={StyleSheet.absoluteFill} />
      <View style={[styles.content, { paddingTop: insets.top + 40 }]}>
        <Pressable onPress={() => router.replace("/")} style={[styles.close, { top: insets.top + spacing.sm }]}>
          <Ionicons name="close" size={24} color="#fff" />
        </Pressable>
        <View style={styles.card}>
          <Image
            source={{ uri: logo || regionalImageFor(invite?.store_id || "default") }}
            style={styles.logo}
            contentFit="cover"
          />
          <View style={styles.badge}>
            <Ionicons name="mail-open" size={16} color={colors.brandPrimary} />
            <Text style={styles.badgeText}>{t("Convite de loja")}</Text>
          </View>
          <Text style={styles.storeName}>{invite?.store_name}</Text>
          <Text style={styles.desc}>
            {t("Você foi convidado(a) a acessar o catálogo desta loja e adicionar itens ao seu catálogo pessoal.")}
          </Text>
          {revoked ? (
            <View style={styles.revoked}>
              <Ionicons name="alert-circle" size={18} color={colors.error} />
              <Text style={styles.revokedText}>{t("Este convite foi revogado.")}</Text>
            </View>
          ) : (
            <Button
              title={user ? t("Aceitar convite") : t("Entrar para aceitar")}
              onPress={accept}
              loading={accepting}
              testID="accept-invite-button"
            />
          )}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.brandPrimary },
  content: { flex: 1, padding: spacing.lg, justifyContent: "center" },
  close: {
    position: "absolute",
    right: spacing.lg,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.2)",
    alignItems: "center",
    justifyContent: "center",
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    padding: spacing.xl,
    alignItems: "center",
    ...shadow.float,
  },
  logo: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: colors.surfaceTertiary,
    marginBottom: spacing.lg,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(74,124,89,0.10)",
    paddingHorizontal: spacing.md,
    paddingVertical: 4,
    borderRadius: radius.pill,
  },
  badgeText: { color: colors.brandPrimary, fontWeight: "800", fontSize: font.sm },
  storeName: { fontSize: font["2xl"], fontWeight: "800", color: colors.onSurface, marginTop: spacing.sm, textAlign: "center" },
  desc: { fontSize: font.base, color: colors.onSurfaceTertiary, textAlign: "center", marginTop: spacing.sm, marginBottom: spacing.xl },
  revoked: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  revokedText: { color: colors.error, fontWeight: "700", fontSize: font.base },
});
