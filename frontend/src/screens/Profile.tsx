import { useState } from "react";
import { View, Text, StyleSheet, ScrollView, Pressable, Modal } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useAuth } from "@/src/auth";
import { Avatar, Button, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow } from "@/src/theme";

const ROLE_LABEL: Record<string, string> = {
  admin: "Administrador",
  lojista: "Lojista",
  cliente: "Cliente",
};

export function ProfileScreen() {
  const { user, logout, deleteAccount } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const doLogout = async () => {
    await logout();
    router.replace("/login");
  };

  const doDelete = async () => {
    setDeleting(true);
    try {
      await deleteAccount();
      toast("Conta excluída", "success");
      router.replace("/login");
    } catch {
      toast("Falha ao excluir conta", "error");
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.title}>Perfil</Text>
      </View>
      <ScrollView contentContainerStyle={{ padding: spacing.lg }}>
        <View style={styles.card}>
          <Avatar name={user?.name} size={72} />
          <Text style={styles.name}>{user?.name}</Text>
          <Text style={styles.email}>{user?.email}</Text>
          <View style={styles.roleBadge}>
            <Ionicons name="ribbon-outline" size={14} color={colors.onBrandTertiary} />
            <Text style={styles.roleText}>{ROLE_LABEL[user?.role || "cliente"]}</Text>
          </View>
        </View>

        <View style={styles.infoRow} testID="profile-user-id">
          <Ionicons name="finger-print-outline" size={18} color={colors.onSurfaceTertiary} />
          <Text style={styles.infoLabel}>ID</Text>
          <Text style={styles.infoValue} numberOfLines={1}>
            {user?.user_id}
          </Text>
        </View>

        <View style={{ height: spacing.xl }} />
        <Button title="Sair" icon="log-out-outline" variant="danger" onPress={doLogout} testID="logout-button" />
        <Pressable testID="delete-account-button" onPress={() => setConfirmDelete(true)} style={styles.deleteLink}>
          <Ionicons name="trash-outline" size={16} color={colors.error} />
          <Text style={styles.deleteText}>Excluir minha conta</Text>
        </Pressable>
      </ScrollView>

      <Modal visible={confirmDelete} transparent animationType="fade" onRequestClose={() => setConfirmDelete(false)}>
        <View style={styles.overlay}>
          <View style={styles.confirmCard}>
            <Ionicons name="warning-outline" size={40} color={colors.error} />
            <Text style={styles.confirmTitle}>Excluir conta?</Text>
            <Text style={styles.confirmMsg}>
              Esta ação é permanente. Seus favoritos e avaliações serão removidos. Não é possível desfazer.
            </Text>
            <Button title="Excluir permanentemente" variant="danger" onPress={doDelete} loading={deleting} testID="confirm-delete-button" />
            <Pressable testID="cancel-delete-button" onPress={() => setConfirmDelete(false)} style={{ paddingVertical: spacing.md }}>
              <Text style={styles.cancelText}>Cancelar</Text>
            </Pressable>
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
  card: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.xl,
    alignItems: "center",
    gap: spacing.xs,
    marginBottom: spacing.lg,
    ...shadow.card,
  },
  name: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface, marginTop: spacing.sm },
  email: { fontSize: font.base, color: colors.onSurfaceTertiary },
  roleBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.brandTertiary,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    marginTop: spacing.sm,
  },
  roleText: { fontSize: font.sm, fontWeight: "700", color: colors.onBrandTertiary },
  infoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
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
