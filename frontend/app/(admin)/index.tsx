import { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  Modal,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Switch,
} from "react-native";
import { Image } from "expo-image";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api, fileUrl, uploadImage } from "@/src/api";
import { useAuth } from "@/src/auth";
import { pickImage, openAppSettings } from "@/src/imagePicker";
import { Loading, EmptyState, ErrorState, Button, Field, Chip, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money, gradients, CATEGORIES } from "@/src/theme";

export default function AdminStores() {
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const router = useRouter();
  const { user: me } = useAuth();
  const isMaster = me?.role === "master";
  const [stores, setStores] = useState<any[]>([]);
  const [admins, setAdmins] = useState<any[]>([]);
  const [state, setState] = useState<"loading" | "error" | "done">("loading");

  // product/category manager
  const [prodStore, setProdStore] = useState<any>(null);
  const [prods, setProds] = useState<any[]>([]);

  const openProducts = async (s: any) => {
    setProdStore(s);
    setProds([]);
    try {
      setProds(await api.products(s.id));
    } catch {}
  };

  const setCat = async (p: any, cat: string) => {
    try {
      const u = await api.updateProduct(p.id, { category: cat });
      setProds((prev) => prev.map((x) => (x.id === p.id ? u : x)));
      toast("Categoria atualizada", "success");
    } catch {
      toast("Falha ao atualizar", "error");
    }
  };

  const delProd = async (p: any) => {
    try {
      await api.deleteProduct(p.id);
      setProds((prev) => prev.filter((x) => x.id !== p.id));
      toast("Produto removido", "success");
    } catch {
      toast("Falha ao remover", "error");
    }
  };

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [whats, setWhats] = useState("");
  const [adminWhats, setAdminWhats] = useState("");
  const [logoPath, setLogoPath] = useState("");
  const [logoUri, setLogoUri] = useState("");
  const [featured, setFeatured] = useState(false);
  const [adminId, setAdminId] = useState<string | null>(null);
  const [groups, setGroups] = useState<any[]>([]);
  const [selGroups, setSelGroups] = useState<string[]>([]);
  const [newGroup, setNewGroup] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [data, grps] = await Promise.all([api.stores(), api.groups().catch(() => [])]);
      const scoped = isMaster ? data : data.filter((s: any) => s.admin_id === me?.user_id);
      setStores(scoped);
      setGroups(grps || []);
      if (isMaster) {
        try {
          const us = await api.users();
          setAdmins(us.filter((u: any) => u.role === "admin"));
        } catch {}
      }
      setState("done");
    } catch {
      setState("error");
    }
  }, [isMaster, me?.user_id]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const openNew = () => {
    setEditing(null);
    setName("");
    setDesc("");
    setWhats("");
    setAdminWhats("");
    setLogoPath("");
    setLogoUri("");
    setFeatured(false);
    setAdminId(isMaster ? null : me?.user_id ?? null);
    setSelGroups([]);
    setFormOpen(true);
  };

  const openEdit = (s: any) => {
    setEditing(s);
    setName(s.name);
    setDesc(s.description || "");
    setWhats(s.whatsapp || "");
    setAdminWhats(s.admin_whatsapp || "");
    setLogoPath(s.logo || "");
    setLogoUri("");
    setFeatured(!!s.featured);
    setAdminId(s.admin_id ?? null);
    setSelGroups(s.group_ids || []);
    setFormOpen(true);
  };

  const handlePick = async () => {
    const res = await pickImage();
    if ("error" in res) {
      if (res.error === "blocked") {
        toast("Permissão bloqueada. Abra os ajustes.", "error");
        openAppSettings();
      } else if (res.error === "denied") {
        toast("Permissão da galeria negada", "error");
      }
      return;
    }
    try {
      setSaving(true);
      const path = await uploadImage(res.uri);
      setLogoPath(path);
      setLogoUri(res.uri);
    } catch {
      toast("Falha ao enviar imagem", "error");
    } finally {
      setSaving(false);
    }
  };

  const save = async () => {
    if (!name.trim() || !whats.trim()) {
      toast("Nome e WhatsApp são obrigatórios", "info");
      return;
    }
    setSaving(true);
    try {
      const body: any = { name, description: desc, whatsapp: whats, admin_whatsapp: adminWhats, logo: logoPath, featured, group_ids: selGroups };
      if (isMaster) body.admin_id = adminId || undefined;
      if (editing) {
        await api.updateStore(editing.id, body);
        // master pode (re)atribuir a loja a um admin mesmo em edição
        if (isMaster) await api.masterAssignStore(editing.id, adminId);
      } else {
        await api.createStore(body);
      }
      setFormOpen(false);
      toast("Loja salva", "success");
      await load();
    } catch (e: any) {
      toast(e.message || "Falha ao salvar", "error");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (s: any) => {
    try {
      await api.deleteStore(s.id);
      setStores((prev) => prev.filter((x) => x.id !== s.id));
      toast("Loja excluída", "success");
    } catch {
      toast("Falha ao excluir", "error");
    }
  };

  return (
    <View style={styles.container}>
      <LinearGradient
        colors={gradients.header}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.headerBar, { paddingTop: insets.top + spacing.md }]}
      >
        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>{isMaster ? "Todas as lojas" : "Minhas lojas"}</Text>
            <Text style={styles.headerSub}>
              {isMaster ? "Painel master · gestão completa" : "Lojas vinculadas a você"}
            </Text>
          </View>
          <View style={styles.headerBadge}>
            <Ionicons name={isMaster ? "shield-checkmark" : "business"} size={20} color="#fff" />
          </View>
          <Pressable testID="admin-invite-button" onPress={() => router.push("/invites")} style={styles.headerBadge}>
            <Ionicons name="person-add" size={20} color="#fff" />
          </Pressable>
        </View>
      </LinearGradient>

      {state === "loading" ? (
        <Loading />
      ) : state === "error" ? (
        <ErrorState onRetry={load} />
      ) : (
        <FlatList
          data={stores}
          keyExtractor={(s) => s.id}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 90 }}
          ListEmptyComponent={
            <EmptyState icon="business-outline" title="Nenhuma loja cadastrada" subtitle="Toque em + para criar a primeira loja." />
          }
          renderItem={({ item }) => (
            <View style={styles.card} testID={`admin-store-${item.id}`}>
              <Image source={{ uri: fileUrl(item.logo) || undefined }} style={styles.logo} contentFit="cover" />
              <View style={{ flex: 1 }}>
                <Text style={styles.name} numberOfLines={1}>
                  {item.name}
                </Text>
                <Text style={styles.meta} numberOfLines={1}>
                  <Ionicons name="logo-whatsapp" size={12} color={colors.onSurfaceTertiary} /> {item.whatsapp}
                </Text>
                <Text style={styles.meta}>{item.product_count || 0} produtos</Text>
              </View>
              <Pressable testID={`manage-products-${item.id}`} onPress={() => openProducts(item)} style={styles.iconBtn}>
                <Ionicons name="pricetags-outline" size={20} color={colors.onSurfaceTertiary} />
              </Pressable>
              <Pressable testID={`edit-store-${item.id}`} onPress={() => openEdit(item)} style={styles.iconBtn}>
                <Ionicons name="create-outline" size={20} color={colors.brandPrimary} />
              </Pressable>
              <Pressable testID={`delete-store-${item.id}`} onPress={() => remove(item)} style={styles.iconBtn}>
                <Ionicons name="trash-outline" size={20} color={colors.error} />
              </Pressable>
            </View>
          )}
        />
      )}

      <Pressable testID="add-store-fab" onPress={openNew} style={[styles.fab, { bottom: insets.bottom + spacing.lg }]}>
        <Ionicons name="add" size={28} color="#fff" />
      </Pressable>

      <Modal visible={!!prodStore} transparent animationType="slide" onRequestClose={() => setProdStore(null)}>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, { paddingBottom: insets.bottom + spacing.lg }]}>
            <View style={styles.modalHandle} />
            <View style={styles.modalTitleRow}>
              <Text style={styles.modalTitle} numberOfLines={1}>Produtos — {prodStore?.name}</Text>
              <Pressable testID="close-products" onPress={() => setProdStore(null)}>
                <Ionicons name="close" size={24} color={colors.onSurfaceTertiary} />
              </Pressable>
            </View>
            <ScrollView keyboardShouldPersistTaps="handled">
              {prods.length === 0 ? (
                <Text style={styles.emptyProd}>Nenhum produto nesta loja.</Text>
              ) : (
                prods.map((p) => (
                  <View key={p.id} style={styles.adminProd} testID={`admin-prod-${p.id}`}>
                    <View style={styles.adminProdTop}>
                      <Image source={{ uri: fileUrl(p.image) || undefined }} style={styles.adminProdImg} contentFit="cover" />
                      <View style={{ flex: 1 }}>
                        <Text style={styles.adminProdName} numberOfLines={1}>{p.name}</Text>
                        <Text style={styles.adminProdPrice}>{money(p.price)}</Text>
                      </View>
                      <Pressable testID={`admin-del-prod-${p.id}`} onPress={() => delProd(p)} style={styles.iconBtn}>
                        <Ionicons name="trash-outline" size={18} color={colors.error} />
                      </Pressable>
                    </View>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.catScroll}>
                      {CATEGORIES.map((c) => (
                        <Chip
                          key={c}
                          testID={`admin-cat-${p.id}-${c}`}
                          label={c}
                          active={(p.category || "Outros") === c}
                          onPress={() => setCat(p, c)}
                        />
                      ))}
                    </ScrollView>
                  </View>
                ))
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>

      <Modal visible={formOpen} transparent animationType="slide" onRequestClose={() => setFormOpen(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.modalOverlay}>
          <View style={[styles.modalCard, { paddingBottom: insets.bottom + spacing.lg }]}>
            <View style={styles.modalHandle} />
            <View style={styles.modalTitleRow}>
              <Text style={styles.modalTitle}>{editing ? "Editar loja" : "Nova loja"}</Text>
              <Pressable testID="close-store-form" onPress={() => setFormOpen(false)}>
                <Ionicons name="close" size={24} color={colors.onSurfaceTertiary} />
              </Pressable>
            </View>
            <ScrollView keyboardShouldPersistTaps="handled">
              <Pressable testID="store-pick-logo" onPress={handlePick} style={styles.logoPick}>
                {logoUri || logoPath ? (
                  <Image source={{ uri: logoUri || fileUrl(logoPath) || undefined }} style={styles.logoPickInner} contentFit="cover" />
                ) : (
                  <>
                    <Ionicons name="image-outline" size={28} color={colors.brandPrimary} />
                    <Text style={styles.logoPickText}>Logo da loja</Text>
                  </>
                )}
              </Pressable>
              <Field testID="store-name" label="Nome" value={name} onChangeText={setName} placeholder="Nome da loja" />
              <Field testID="store-desc" label="Descrição" value={desc} onChangeText={setDesc} placeholder="Descrição" multiline />
              <Field
                testID="store-whatsapp"
                label="WhatsApp do responsável"
                value={whats}
                onChangeText={setWhats}
                placeholder="Ex: 5511999999999"
                keyboardType="phone-pad"
              />
              <Field
                testID="store-admin-whatsapp"
                label="WhatsApp do administrador (recebe cópias)"
                value={adminWhats}
                onChangeText={setAdminWhats}
                placeholder="Ex: 5511920946954"
                keyboardType="phone-pad"
              />
              <View style={styles.switchRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.switchLabel}>Destaque na home</Text>
                  <Text style={styles.switchHint}>Aparece na vitrine de destaques dos clientes</Text>
                </View>
                <Switch
                  testID="store-featured-switch"
                  value={featured}
                  onValueChange={setFeatured}
                  trackColor={{ true: colors.brandPrimary, false: colors.borderStrong }}
                  thumbColor="#fff"
                />
              </View>
              {isMaster && (
                <View style={{ marginBottom: spacing.lg }}>
                  <Text style={styles.switchLabel}>Administrador responsável</Text>
                  <Text style={styles.switchHint}>Vincule esta loja a um admin (opcional)</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.catScroll}>
                    <Chip
                      testID="assign-admin-none"
                      label="Sem admin"
                      active={!adminId}
                      onPress={() => setAdminId(null)}
                    />
                    {admins.map((a) => (
                      <Chip
                        key={a.user_id}
                        testID={`assign-admin-${a.user_id}`}
                        label={a.name || a.email}
                        active={adminId === a.user_id}
                        onPress={() => setAdminId(a.user_id)}
                      />
                    ))}
                  </ScrollView>
                </View>
              )}
              <View style={{ marginBottom: spacing.lg }}>
                <Text style={styles.switchLabel}>Áreas de interesse</Text>
                <Text style={styles.switchHint}>Classifique a loja por grupos (o cliente filtra por área)</Text>
                <View style={styles.groupWrap}>
                  {groups.map((g) => {
                    const on = selGroups.includes(g.id);
                    return (
                      <Pressable
                        key={g.id}
                        testID={`store-group-${g.id}`}
                        onPress={() =>
                          setSelGroups((prev) => (on ? prev.filter((x) => x !== g.id) : [...prev, g.id]))
                        }
                        style={[styles.grpChip, on && { backgroundColor: g.color || colors.brandPrimary, borderColor: g.color || colors.brandPrimary }]}
                      >
                        <Ionicons name={g.icon || "pricetags"} size={14} color={on ? "#fff" : g.color || colors.brandPrimary} />
                        <Text style={[styles.grpChipText, { color: on ? "#fff" : g.color || colors.brandPrimary }]}>{g.name}</Text>
                      </Pressable>
                    );
                  })}
                </View>
                <View style={styles.newGroupRow}>
                  <View style={{ flex: 1 }}>
                    <Field testID="new-group-input" value={newGroup} onChangeText={setNewGroup} placeholder="Nova área (ex: Pet Shop)" />
                  </View>
                  <Pressable
                    testID="add-group-button"
                    onPress={async () => {
                      if (!newGroup.trim()) return;
                      try {
                        const g = await api.createGroup(newGroup.trim());
                        setGroups((prev) => [...prev, g]);
                        setSelGroups((prev) => [...prev, g.id]);
                        setNewGroup("");
                        toast("Área criada", "success");
                      } catch (e: any) {
                        toast(e.message || "Falha", "error");
                      }
                    }}
                    style={styles.addGroupBtn}
                  >
                    <Ionicons name="add" size={22} color="#fff" />
                  </Pressable>
                </View>
              </View>
              <Button title="Salvar loja" onPress={save} loading={saving} testID="save-store-button" />
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  headerBar: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    borderBottomLeftRadius: radius.xl,
    borderBottomRightRadius: radius.xl,
    ...shadow.card,
  },
  headerRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  headerSub: { fontSize: font.sm, color: "rgba(255,255,255,0.85)", marginTop: 2 },
  headerBadge: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    backgroundColor: "rgba(255,255,255,0.18)",
    alignItems: "center",
    justifyContent: "center",
  },
  title: { fontSize: font["2xl"], fontWeight: "800", color: "#fff" },
  groupWrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.sm },
  grpChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: spacing.md,
    paddingVertical: 7,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  grpChipText: { fontSize: font.sm, fontWeight: "700" },
  newGroupRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm, marginTop: spacing.sm },
  addGroupBtn: {
    width: 48,
    height: 48,
    borderRadius: radius.md,
    backgroundColor: colors.brandPrimary,
    alignItems: "center",
    justifyContent: "center",
  },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    ...shadow.card,
  },
  logo: { width: 56, height: 56, borderRadius: radius.md, backgroundColor: colors.surfaceTertiary },
  name: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  meta: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  iconBtn: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  fab: {
    position: "absolute",
    right: spacing.lg,
    width: 58,
    height: 58,
    borderRadius: 29,
    backgroundColor: colors.brandPrimary,
    alignItems: "center",
    justifyContent: "center",
    ...shadow.float,
  },
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  modalCard: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    padding: spacing.lg,
    maxHeight: "88%",
  },
  modalHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.borderStrong,
    alignSelf: "center",
    marginBottom: spacing.md,
  },
  modalTitleRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.lg },
  modalTitle: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface },
  logoPick: {
    height: 120,
    borderRadius: radius.md,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
    overflow: "hidden",
  },
  logoPickInner: { width: "100%", height: "100%" },
  emptyProd: { fontSize: font.base, color: colors.onSurfaceTertiary, paddingVertical: spacing.lg, textAlign: "center" },
  adminProd: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    ...shadow.card,
  },
  adminProdTop: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  adminProdImg: { width: 44, height: 44, borderRadius: radius.sm, backgroundColor: colors.surfaceTertiary },
  adminProdName: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  adminProdPrice: { fontSize: font.sm, color: colors.brandPrimary, fontWeight: "700", marginTop: 2 },
  catScroll: { gap: spacing.sm, paddingTop: spacing.md },
  logoPickText: { fontSize: font.base, color: colors.brandPrimary, fontWeight: "600", marginTop: 4 },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  switchLabel: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  switchHint: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
});
