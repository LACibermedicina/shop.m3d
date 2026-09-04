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
} from "react-native";
import { Image } from "expo-image";
import { useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api, fileUrl, uploadImage } from "@/src/api";
import { useAuth } from "@/src/auth";
import { pickImage, openAppSettings } from "@/src/imagePicker";
import { Loading, EmptyState, ErrorState, Button, Field, Chip, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, money, CATEGORIES } from "@/src/theme";

export default function VendorCatalog() {
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const toast = useToast();
  const storeId = user?.store_id;

  const [products, setProducts] = useState<any[]>([]);
  const [state, setState] = useState<"loading" | "error" | "done">("loading");

  // AI import
  const [aiMsg, setAiMsg] = useState("");
  const [aiImagePath, setAiImagePath] = useState<string>("");
  const [aiImageUri, setAiImageUri] = useState<string>("");
  const [aiBusy, setAiBusy] = useState(false);

  // form modal
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [fName, setFName] = useState("");
  const [fPrice, setFPrice] = useState("");
  const [fDesc, setFDesc] = useState("");
  const [fImagePath, setFImagePath] = useState("");
  const [fImageUri, setFImageUri] = useState("");
  const [fCategory, setFCategory] = useState("Outros");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!storeId) {
      setState("done");
      return;
    }
    try {
      const data = await api.products(storeId);
      setProducts(data);
      setState("done");
    } catch {
      setState("error");
    }
  }, [storeId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const handlePick = async (forAi: boolean) => {
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
      if (forAi) setAiBusy(true);
      else setSaving(true);
      const path = await uploadImage(res.uri);
      if (forAi) {
        setAiImagePath(path);
        setAiImageUri(res.uri);
      } else {
        setFImagePath(path);
        setFImageUri(res.uri);
      }
    } catch {
      toast("Falha ao enviar imagem", "error");
    } finally {
      setAiBusy(false);
      setSaving(false);
    }
  };

  const processAi = async () => {
    if (!aiMsg.trim() && !aiImagePath) {
      toast("Cole a mensagem do WhatsApp ou envie uma imagem", "info");
      return;
    }
    setAiBusy(true);
    try {
      const parsed = await api.aiImport({ message: aiMsg, image: aiImagePath, store_id: storeId });
      // open form prefilled
      setEditing(null);
      setFName(parsed.name || "");
      setFPrice(parsed.price ? String(parsed.price) : "");
      setFDesc(parsed.description || "");
      setFCategory(parsed.category || "Outros");
      setFImagePath(aiImagePath || "");
      setFImageUri(aiImageUri || "");
      setFormOpen(true);
      toast("Dados extraídos! Revise e salve.", "success");
    } catch (e: any) {
      toast(e.message || "Falha na IA", "error");
    } finally {
      setAiBusy(false);
    }
  };

  const openNew = () => {
    setEditing(null);
    setFName("");
    setFPrice("");
    setFDesc("");
    setFCategory("Outros");
    setFImagePath("");
    setFImageUri("");
    setFormOpen(true);
  };

  const openEdit = (p: any) => {
    setEditing(p);
    setFName(p.name);
    setFPrice(String(p.price));
    setFDesc(p.description || "");
    setFCategory(p.category || "Outros");
    setFImagePath(p.image || "");
    setFImageUri("");
    setFormOpen(true);
  };

  const saveProduct = async () => {
    if (!fName.trim()) {
      toast("Informe o nome do produto", "info");
      return;
    }
    const price = parseFloat(fPrice.replace(",", ".")) || 0;
    setSaving(true);
    try {
      if (editing) {
        await api.updateProduct(editing.id, {
          name: fName,
          price,
          description: fDesc,
          image: fImagePath,
          category: fCategory,
        });
      } else {
        await api.createProduct({
          store_id: storeId,
          name: fName,
          price,
          description: fDesc,
          image: fImagePath,
          category: fCategory,
        });
      }
      setFormOpen(false);
      setAiMsg("");
      setAiImagePath("");
      setAiImageUri("");
      toast("Produto salvo", "success");
      await load();
    } catch (e: any) {
      toast(e.message || "Falha ao salvar", "error");
    } finally {
      setSaving(false);
    }
  };

  const deleteProduct = async (p: any) => {
    try {
      await api.deleteProduct(p.id);
      setProducts((prev) => prev.filter((x) => x.id !== p.id));
      toast("Produto removido", "success");
    } catch {
      toast("Falha ao remover", "error");
    }
  };

  if (!storeId) {
    return (
      <View style={styles.container}>
        <View style={[styles.headerBar, { paddingTop: insets.top + spacing.sm }]}>
          <Text style={styles.title}>Catálogo</Text>
        </View>
        <EmptyState
          icon="storefront-outline"
          title="Nenhuma loja vinculada"
          subtitle="Peça ao administrador para vincular sua conta a uma loja."
        />
      </View>
    );
  }

  const aiCard = (
    <View style={styles.aiCard}>
      <View style={styles.aiHeader}>
        <Ionicons name="sparkles" size={18} color={colors.brandPrimary} />
        <Text style={styles.aiTitle}>Adicionar por WhatsApp (IA)</Text>
      </View>
      <Text style={styles.aiHint}>Cole a mensagem do produto e/ou envie a foto. A IA preenche tudo.</Text>
      <Field
        testID="ai-message-input"
        value={aiMsg}
        onChangeText={setAiMsg}
        placeholder="Ex: Fone de ouvido Bluetooth, R$ 120,00, com microfone"
        multiline
      />
      <View style={styles.aiActions}>
        <Pressable testID="ai-pick-image" onPress={() => handlePick(true)} style={styles.aiImageBtn}>
          {aiImageUri ? (
            <Image source={{ uri: aiImageUri }} style={styles.aiThumb} contentFit="cover" />
          ) : (
            <>
              <Ionicons name="image-outline" size={20} color={colors.brandPrimary} />
              <Text style={styles.aiImageText}>Foto</Text>
            </>
          )}
        </Pressable>
        <View style={{ flex: 1 }}>
          <Button title="Processar com IA" icon="sparkles" onPress={processAi} loading={aiBusy} testID="ai-process-button" />
        </View>
      </View>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={[styles.headerBar, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.title}>Catálogo</Text>
        <Pressable testID="add-product-fab" onPress={openNew} style={styles.headerAdd}>
          <Ionicons name="add" size={22} color="#fff" />
        </Pressable>
      </View>

      {state === "loading" ? (
        <Loading />
      ) : state === "error" ? (
        <ErrorState onRetry={load} />
      ) : (
        <FlatList
          data={products}
          keyExtractor={(p) => p.id}
          ListHeaderComponent={aiCard}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 40 }}
          ListEmptyComponent={
            <EmptyState icon="pricetag-outline" title="Comece a adicionar seus produtos" subtitle="Use a IA acima ou o botão +." />
          }
          renderItem={({ item }) => (
            <View style={styles.pRow} testID={`vendor-product-${item.id}`}>
              <Image source={{ uri: fileUrl(item.image) || undefined }} style={styles.pImg} contentFit="cover" />
              <View style={{ flex: 1 }}>
                <Text style={styles.pName} numberOfLines={1}>
                  {item.name}
                </Text>
                <Text style={styles.pPrice}>{money(item.price)}</Text>
              </View>
              <Pressable testID={`edit-product-${item.id}`} onPress={() => openEdit(item)} style={styles.iconBtn}>
                <Ionicons name="create-outline" size={20} color={colors.brandPrimary} />
              </Pressable>
              <Pressable testID={`delete-product-${item.id}`} onPress={() => deleteProduct(item)} style={styles.iconBtn}>
                <Ionicons name="trash-outline" size={20} color={colors.error} />
              </Pressable>
            </View>
          )}
        />
      )}

      <Modal visible={formOpen} transparent animationType="slide" onRequestClose={() => setFormOpen(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.modalOverlay}>
          <View style={[styles.modalCard, { paddingBottom: insets.bottom + spacing.lg }]}>
            <View style={styles.modalHandle} />
            <View style={styles.modalTitleRow}>
              <Text style={styles.modalTitle}>{editing ? "Editar produto" : "Novo produto"}</Text>
              <Pressable testID="close-form" onPress={() => setFormOpen(false)}>
                <Ionicons name="close" size={24} color={colors.onSurfaceTertiary} />
              </Pressable>
            </View>
            <ScrollView keyboardShouldPersistTaps="handled">
              <Pressable testID="form-pick-image" onPress={() => handlePick(false)} style={styles.formImage}>
                {fImageUri || fImagePath ? (
                  <Image source={{ uri: fImageUri || fileUrl(fImagePath) || undefined }} style={styles.formImageInner} contentFit="cover" />
                ) : (
                  <>
                    <Ionicons name="camera-outline" size={28} color={colors.brandPrimary} />
                    <Text style={styles.formImageText}>Adicionar foto</Text>
                  </>
                )}
              </Pressable>
              <Field testID="form-name" label="Nome" value={fName} onChangeText={setFName} placeholder="Nome do produto" />
              <Field
                testID="form-price"
                label="Preço (R$)"
                value={fPrice}
                onChangeText={setFPrice}
                placeholder="0,00"
                keyboardType="decimal-pad"
              />
              <Field
                testID="form-desc"
                label="Descrição"
                value={fDesc}
                onChangeText={setFDesc}
                placeholder="Detalhes do produto"
                multiline
              />
              <Text style={styles.catLabel}>Categoria</Text>
              <View style={styles.catWrap}>
                {CATEGORIES.map((c) => (
                  <Chip
                    key={c}
                    testID={`form-cat-${c}`}
                    label={c}
                    active={fCategory === c}
                    onPress={() => setFCategory(c)}
                  />
                ))}
              </View>
              <Button title="Salvar produto" onPress={saveProduct} loading={saving} testID="save-product-button" />
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
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  title: { fontSize: font["2xl"], fontWeight: "800", color: colors.onSurface },
  headerAdd: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.brandPrimary,
    alignItems: "center",
    justifyContent: "center",
  },
  aiCard: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.brandTertiary,
    ...shadow.card,
  },
  aiHeader: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  aiTitle: { fontSize: font.lg, fontWeight: "800", color: colors.onSurface },
  aiHint: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 4, marginBottom: spacing.md },
  aiActions: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  aiImageBtn: {
    width: 64,
    height: 52,
    borderRadius: radius.md,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  aiThumb: { width: "100%", height: "100%" },
  aiImageText: { fontSize: font.sm, color: colors.brandPrimary, fontWeight: "600" },
  pRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    ...shadow.card,
  },
  pImg: { width: 52, height: 52, borderRadius: radius.sm, backgroundColor: colors.surfaceTertiary },
  pName: { fontSize: font.base, fontWeight: "700", color: colors.onSurface },
  pPrice: { fontSize: font.base, color: colors.brandPrimary, fontWeight: "700", marginTop: 2 },
  iconBtn: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceTertiary,
    alignItems: "center",
    justifyContent: "center",
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
  formImage: {
    height: 140,
    borderRadius: radius.md,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
    overflow: "hidden",
  },
  formImageInner: { width: "100%", height: "100%" },
  formImageText: { fontSize: font.base, color: colors.brandPrimary, fontWeight: "600", marginTop: 4 },
  catLabel: { fontSize: font.base, fontWeight: "600", color: colors.onSurface, marginBottom: spacing.sm },
  catWrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.lg },
});
