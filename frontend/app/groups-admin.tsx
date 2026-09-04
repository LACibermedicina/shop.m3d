import { useState, useCallback } from "react";
import { View, Text, StyleSheet, FlatList, Pressable, ScrollView, Modal, KeyboardAvoidingView, Platform } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api } from "@/src/api";
import { Loading, ErrorState, Button, Field, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, gradients } from "@/src/theme";

const ICONS = ["pricetags", "hardware-chip", "shirt", "sparkles", "home", "fast-food", "construct", "cart", "gift", "fitness", "paw", "book", "car", "cafe", "rose", "game-controller"];
const COLORS = ["#4A7C59", "#3A6EA5", "#C16E53", "#B0568A", "#D48C46", "#6B7A8F", "#8A6D3B", "#2E7D6B"];

export default function GroupsAdmin() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const toast = useToast();
  const [groups, setGroups] = useState<any[]>([]);
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [name, setName] = useState("");
  const [icon, setIcon] = useState("pricetags");
  const [color, setColor] = useState("#4A7C59");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setGroups(await api.groups());
      setState("done");
    } catch {
      setState("error");
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, []));

  const openNew = () => {
    setEditing(null); setName(""); setIcon("pricetags"); setColor("#4A7C59"); setOpen(true);
  };
  const openEdit = (g: any) => {
    setEditing(g); setName(g.name); setIcon(g.icon || "pricetags"); setColor(g.color || "#4A7C59"); setOpen(true);
  };

  const save = async () => {
    if (!name.trim()) { toast("Informe o nome", "info"); return; }
    setSaving(true);
    try {
      if (editing) await api.updateGroup(editing.id, name.trim(), icon, color);
      else await api.createGroup(name.trim(), icon, color);
      setOpen(false); toast("Área salva", "success"); await load();
    } catch (e: any) { toast(e.message || "Falha", "error"); } finally { setSaving(false); }
  };

  const remove = async (g: any) => {
    try { await api.deleteGroup(g.id); setGroups((p) => p.filter((x) => x.id !== g.id)); toast("Área excluída", "info"); }
    catch (e: any) { toast(e.message || "Falha", "error"); }
  };

  return (
    <View style={styles.container}>
      <LinearGradient colors={gradients.header} style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.headerRow}>
          <Pressable onPress={() => router.back()} style={styles.back}>
            <Ionicons name="chevron-back" size={24} color="#fff" />
          </Pressable>
          <Text style={styles.title}>Áreas de interesse</Text>
          <Pressable testID="new-area-button" onPress={openNew} style={styles.back}>
            <Ionicons name="add" size={24} color="#fff" />
          </Pressable>
        </View>
      </LinearGradient>

      {state === "loading" ? <Loading /> : state === "error" ? <ErrorState onRetry={load} /> : (
        <FlatList
          data={groups}
          keyExtractor={(g) => g.id}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 40 }}
          renderItem={({ item }) => (
            <View style={styles.row} testID={`area-${item.id}`}>
              <View style={[styles.iconBadge, { backgroundColor: item.color || colors.brandPrimary }]}>
                <Ionicons name={item.icon || "pricetags"} size={20} color="#fff" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{item.name}</Text>
                <Text style={styles.count}>{item.store_count || 0} loja(s)</Text>
              </View>
              <Pressable onPress={() => openEdit(item)} style={styles.iconBtn} testID={`edit-area-${item.id}`}>
                <Ionicons name="create-outline" size={20} color={colors.brandPrimary} />
              </Pressable>
              <Pressable onPress={() => remove(item)} style={styles.iconBtn} testID={`del-area-${item.id}`}>
                <Ionicons name="trash-outline" size={20} color={colors.error} />
              </Pressable>
            </View>
          )}
        />
      )}

      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.overlay}>
          <View style={[styles.card, { paddingBottom: insets.bottom + spacing.lg }]}>
            <View style={styles.handle} />
            <Text style={styles.modalTitle}>{editing ? "Editar área" : "Nova área"}</Text>
            <Field testID="area-name" label="Nome" value={name} onChangeText={setName} placeholder="Ex: Pet Shop" />
            <Text style={styles.lbl}>Ícone</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.picker}>
              {ICONS.map((ic) => (
                <Pressable key={ic} onPress={() => setIcon(ic)} style={[styles.pick, icon === ic && { backgroundColor: color, borderColor: color }]}>
                  <Ionicons name={ic as any} size={20} color={icon === ic ? "#fff" : colors.onSurface} />
                </Pressable>
              ))}
            </ScrollView>
            <Text style={styles.lbl}>Cor</Text>
            <View style={styles.colorRow}>
              {COLORS.map((c) => (
                <Pressable key={c} onPress={() => setColor(c)} style={[styles.color, { backgroundColor: c }, color === c && styles.colorActive]} />
              ))}
            </View>
            <Button title="Salvar área" onPress={save} loading={saving} testID="save-area-button" />
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  header: { paddingHorizontal: spacing.lg, paddingBottom: spacing.lg, borderBottomLeftRadius: radius.xl, borderBottomRightRadius: radius.xl, ...shadow.card },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  back: { width: 40, height: 40, borderRadius: 20, backgroundColor: "rgba(255,255,255,0.18)", alignItems: "center", justifyContent: "center" },
  title: { fontSize: font.xl, fontWeight: "800", color: "#fff" },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, padding: spacing.md, marginBottom: spacing.sm, ...shadow.card },
  iconBadge: { width: 44, height: 44, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  name: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  count: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  iconBtn: { width: 36, height: 36, borderRadius: radius.sm, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  overlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  card: { backgroundColor: colors.surface, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: spacing.lg },
  handle: { width: 40, height: 4, borderRadius: 2, backgroundColor: colors.borderStrong, alignSelf: "center", marginBottom: spacing.md },
  modalTitle: { fontSize: font.xl, fontWeight: "800", color: colors.onSurface, marginBottom: spacing.md },
  lbl: { fontSize: font.sm, fontWeight: "700", color: colors.onSurfaceTertiary, marginTop: spacing.sm, marginBottom: spacing.xs },
  picker: { gap: spacing.sm, paddingVertical: spacing.xs },
  pick: { width: 44, height: 44, borderRadius: radius.md, borderWidth: 1.5, borderColor: colors.border, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  colorRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.lg },
  color: { width: 40, height: 40, borderRadius: 20 },
  colorActive: { borderWidth: 3, borderColor: colors.onSurface },
});
