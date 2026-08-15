import { useState, useCallback } from "react";
import { View, Text, StyleSheet, FlatList, Pressable, Modal } from "react-native";
import { useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api } from "@/src/api";
import { Loading, EmptyState, ErrorState, Avatar, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow } from "@/src/theme";

const ROLES = [
  { key: "cliente", label: "Cliente" },
  { key: "lojista", label: "Lojista" },
  { key: "admin", label: "Admin" },
];

export default function AdminUsers() {
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const [users, setUsers] = useState<any[]>([]);
  const [stores, setStores] = useState<any[]>([]);
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [storePickUser, setStorePickUser] = useState<any>(null);

  const load = useCallback(async () => {
    try {
      const [u, s] = await Promise.all([api.users(), api.stores()]);
      setUsers(u);
      setStores(s);
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

  const applyRole = async (user: any, role: string, storeId?: string | null) => {
    try {
      const updated = await api.setUserRole(user.user_id, role, storeId ?? null);
      setUsers((prev) => prev.map((x) => (x.user_id === user.user_id ? updated : x)));
      toast("Papel atualizado", "success");
    } catch (e: any) {
      toast(e.message || "Falha", "error");
    }
  };

  const onRolePress = (user: any, role: string) => {
    if (role === "lojista") {
      setStorePickUser(user);
    } else {
      applyRole(user, role);
    }
  };

  const storeName = (id?: string | null) => stores.find((s) => s.id === id)?.name;

  return (
    <View style={styles.container}>
      <View style={[styles.headerBar, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.title}>Usuários</Text>
      </View>

      {state === "loading" ? (
        <Loading />
      ) : state === "error" ? (
        <ErrorState onRetry={load} />
      ) : (
        <FlatList
          data={users}
          keyExtractor={(u) => u.user_id}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 40 }}
          ListEmptyComponent={<EmptyState icon="people-outline" title="Nenhum usuário" />}
          renderItem={({ item }) => (
            <View style={styles.card} testID={`user-${item.user_id}`}>
              <View style={styles.userRow}>
                <Avatar name={item.name} size={40} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.name} numberOfLines={1}>
                    {item.name}
                  </Text>
                  <Text style={styles.email} numberOfLines={1}>
                    {item.email}
                  </Text>
                  {item.role === "lojista" && item.store_id && (
                    <Text style={styles.storeTag}>🏪 {storeName(item.store_id) || "Loja"}</Text>
                  )}
                </View>
              </View>
              <View style={styles.roleRow}>
                {ROLES.map((r) => (
                  <Pressable
                    key={r.key}
                    testID={`set-role-${r.key}-${item.user_id}`}
                    onPress={() => onRolePress(item, r.key)}
                    style={[styles.roleChip, item.role === r.key && styles.roleChipActive]}
                  >
                    <Text style={[styles.roleChipText, item.role === r.key && { color: "#fff", fontWeight: "700" }]}>
                      {r.label}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>
          )}
        />
      )}

      <Modal visible={!!storePickUser} transparent animationType="slide" onRequestClose={() => setStorePickUser(null)}>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, { paddingBottom: insets.bottom + spacing.lg }]}>
            <View style={styles.modalHandle} />
            <Text style={styles.modalTitle}>Vincular a uma barraca</Text>
            <Text style={styles.modalSub}>Escolha a barraca deste lojista</Text>
            <FlatList
              data={stores}
              keyExtractor={(s) => s.id}
              style={{ maxHeight: 340 }}
              ListEmptyComponent={<Text style={styles.email}>Cadastre uma barraca primeiro.</Text>}
              renderItem={({ item }) => (
                <Pressable
                  testID={`pick-store-${item.id}`}
                  style={styles.storePickRow}
                  onPress={() => {
                    applyRole(storePickUser, "lojista", item.id);
                    setStorePickUser(null);
                  }}
                >
                  <Ionicons name="storefront-outline" size={20} color={colors.brandPrimary} />
                  <Text style={styles.storePickName}>{item.name}</Text>
                  <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                </Pressable>
              )}
            />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  headerBar: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  title: { fontSize: font["2xl"], fontWeight: "800", color: colors.onSurface },
  card: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    ...shadow.card,
  },
  userRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  name: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  email: { fontSize: font.sm, color: colors.onSurfaceTertiary },
  storeTag: { fontSize: font.sm, color: colors.brandPrimary, marginTop: 2, fontWeight: "600" },
  roleRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md },
  roleChip: {
    flex: 1,
    height: 36,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  roleChipActive: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  roleChipText: { fontSize: font.base, color: colors.onSurfaceTertiary },
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
  modalTitle: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface },
  modalSub: { fontSize: font.base, color: colors.onSurfaceTertiary, marginBottom: spacing.md },
  storePickRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  storePickName: { flex: 1, fontSize: font.lg, fontWeight: "600", color: colors.onSurface },
});
