import { useState } from "react";
import { View, Text, StyleSheet, ScrollView, Pressable, Modal } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useAuth } from "@/src/auth";
import { api } from "@/src/api";
import { useI18n } from "@/src/i18n";
import { LangSelector } from "@/src/LangSelector";
import { Avatar, Button, Field, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, gradients } from "@/src/theme";

const ROLE_LABEL: Record<string, string> = {
  master: "Master",
  admin: "Administrador",
  lojista: "Lojista",
  cliente: "Cliente",
};
const ROLE_ICON: Record<string, any> = {
  master: "shield-checkmark",
  admin: "briefcase",
  lojista: "storefront",
  cliente: "person",
};
const ROLE_GRAD: Record<string, readonly string[]> = {
  master: ["#8A6D3B", "#C79A3B", "#4A7C59"] as const,
  admin: ["#B4682E", "#D48C46"] as const,
  lojista: gradients.header,
  cliente: gradients.header,
};

export function ProfileScreen() {
  const { user, logout, deleteAccount, refresh } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { t } = useI18n();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [wa, setWa] = useState(user?.whatsapp || "");
  const [savingWa, setSavingWa] = useState(false);

  const role = user?.role || "cliente";

  const saveWa = async () => {
    setSavingWa(true);
    try {
      await api.setMyWhatsapp(wa.trim());
      await refresh();
      toast(t("WhatsApp salvo"), "success");
    } catch {
      toast(t("Falha ao salvar"), "error");
    } finally {
      setSavingWa(false);
    }
  };

  const doLogout = async () => {
    await logout();
    router.replace("/login");
  };

  const doDelete = async () => {
    setDeleting(true);
    try {
      await deleteAccount();
      toast(t("Conta excluída"), "success");
      router.replace("/login");
    } catch {
      toast(t("Falha ao excluir conta"), "error");
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  return (
    <View style={styles.container}>
      <LinearGradient
        colors={(ROLE_GRAD[role] as any) || gradients.header}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.hero, { paddingTop: insets.top + spacing.sm }]}
      >
        <View style={styles.topBar}>
          <Text style={styles.heroTitle}>{t("Perfil")}</Text>
          <LangSelector variant="light" />
        </View>
      </LinearGradient>

      <ScrollView
        contentContainerStyle={{ paddingHorizontal: spacing.lg, paddingBottom: insets.bottom + 40 }}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.avatarCard}>
          <View style={styles.avatarWrap}>
            <Avatar name={user?.name} size={84} />
            <View style={[styles.roleDot, { backgroundColor: role === "master" ? "#C79A3B" : colors.brandPrimary }]}>
              <Ionicons name={ROLE_ICON[role]} size={16} color="#fff" />
            </View>
          </View>
          <Text style={styles.name}>{user?.name}</Text>
          <Text style={styles.email}>{user?.email}</Text>
          <View
            style={[
              styles.roleBadge,
              { backgroundColor: role === "master" ? "rgba(199,154,59,0.15)" : colors.brandTertiary },
            ]}
          >
            <Ionicons
              name={ROLE_ICON[role]}
              size={14}
              color={role === "master" ? "#9A7B2E" : colors.onBrandTertiary}
            />
            <Text style={[styles.roleText, { color: role === "master" ? "#9A7B2E" : colors.onBrandTertiary }]}>
              {ROLE_LABEL[role]}
            </Text>
          </View>
        </View>

        <View style={styles.infoRow} testID="profile-user-id">
          <Ionicons name="finger-print-outline" size={18} color={colors.onSurfaceTertiary} />
          <Text style={styles.infoLabel}>ID</Text>
          <Text style={styles.infoValue} numberOfLines={1}>
            {user?.user_id}
          </Text>
        </View>

        <View style={{ height: spacing.lg }} />
        <View style={styles.waCard}>
          <View style={styles.waHead}>
            <Ionicons name="logo-whatsapp" size={20} color="#25D366" />
            <Text style={styles.waTitle}>{t("Meu WhatsApp (para confirmações)")}</Text>
          </View>
          <Field
            testID="profile-whatsapp-input"
            value={wa}
            onChangeText={setWa}
            placeholder="Ex: 5545999990000"
            keyboardType="phone-pad"
          />
          <Button title={t("Salvar WhatsApp")} onPress={saveWa} loading={savingWa} testID="save-whatsapp-button" variant="outline" />
        </View>

        <View style={{ height: spacing.xl }} />
        <Button title={t("Sair")} icon="log-out-outline" variant="danger" onPress={doLogout} testID="logout-button" />
        <Pressable testID="delete-account-button" onPress={() => setConfirmDelete(true)} style={styles.deleteLink}>
          <Ionicons name="trash-outline" size={16} color={colors.error} />
          <Text style={styles.deleteText}>{t("Excluir minha conta")}</Text>
        </Pressable>
      </ScrollView>

      <Modal visible={confirmDelete} transparent animationType="fade" onRequestClose={() => setConfirmDelete(false)}>
        <View style={styles.overlay}>
          <View style={styles.confirmCard}>
            <Ionicons name="warning-outline" size={40} color={colors.error} />
            <Text style={styles.confirmTitle}>{t("Excluir conta?")}</Text>
            <Text style={styles.confirmMsg}>
              {t("Esta ação é permanente. Seus favoritos e avaliações serão removidos. Não é possível desfazer.")}
            </Text>
            <Button title={t("Excluir permanentemente")} variant="danger" onPress={doDelete} loading={deleting} testID="confirm-delete-button" />
            <Pressable testID="cancel-delete-button" onPress={() => setConfirmDelete(false)} style={{ paddingVertical: spacing.md }}>
              <Text style={styles.cancelText}>{t("Cancelar")}</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  hero: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing["3xl"],
    borderBottomLeftRadius: radius.xl,
    borderBottomRightRadius: radius.xl,
    ...shadow.card,
  },
  topBar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  heroTitle: { fontSize: font["2xl"], fontWeight: "800", color: "#fff" },
  avatarCard: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.xl,
    alignItems: "center",
    gap: spacing.xs,
    marginTop: -spacing.xl,
    ...shadow.float,
  },
  avatarWrap: { position: "relative" },
  roleDot: {
    position: "absolute",
    bottom: -2,
    right: -2,
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 3,
    borderColor: colors.surfaceSecondary,
  },
  name: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface, marginTop: spacing.sm },
  email: { fontSize: font.base, color: colors.onSurfaceTertiary },
  roleBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    marginTop: spacing.sm,
  },
  roleText: { fontSize: font.sm, fontWeight: "700" },
  infoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.lg,
  },
  infoLabel: { fontSize: font.base, color: colors.onSurfaceTertiary },
  infoValue: { fontSize: font.base, color: colors.onSurface, flex: 1, textAlign: "right", fontWeight: "600" },
  deleteLink: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    marginTop: spacing.lg,
    paddingVertical: spacing.md,
  },
  deleteText: { color: colors.error, fontSize: font.base, fontWeight: "600" },
  waCard: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, padding: spacing.lg, ...shadow.card },
  waHead: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm },
  waTitle: { fontSize: font.base, fontWeight: "700", color: colors.onSurface, flex: 1 },
  overlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.45)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  confirmCard: {
    width: "100%",
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.xl,
    alignItems: "center",
    gap: spacing.sm,
  },
  confirmTitle: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface },
  confirmMsg: { fontSize: font.base, color: colors.onSurfaceTertiary, textAlign: "center", marginBottom: spacing.md },
  cancelText: { fontSize: font.base, color: colors.onSurfaceTertiary, fontWeight: "600", textAlign: "center" },
});
