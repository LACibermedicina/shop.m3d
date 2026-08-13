import { View, Text, StyleSheet, ScrollView, Pressable } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useAuth } from "@/src/auth";
import { Avatar, Button } from "@/src/ui";
import { colors, spacing, radius, font, shadow } from "@/src/theme";

const ROLE_LABEL: Record<string, string> = {
  admin: "Administrador",
  lojista: "Lojista",
  cliente: "Cliente",
};

export function ProfileScreen() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const doLogout = async () => {
    await logout();
    router.replace("/login");
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
      </ScrollView>
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
});
