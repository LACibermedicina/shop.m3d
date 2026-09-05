import { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  Switch,
  Platform,
  KeyboardAvoidingView,
  RefreshControl,
  Linking,
  ActivityIndicator,
  Modal,
} from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Clipboard from "expo-clipboard";
import * as Sharing from "expo-sharing";
import * as FileSystem from "expo-file-system/legacy";
import { useRouter } from "expo-router";
import { api, fileUrl } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Button, Field, Loading, EmptyState, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, glass, gradients } from "@/src/theme";

type Catalog = { key: string; label: string; icon: string; ratio: string; w: number; h: number };
type NetState = Record<string, { enabled: boolean; handle: string; url: string }>;
type Asset = {
  network: string; label: string; icon: string; ratio: string; w: number; h: number;
  image_path: string; caption: string; hashtags: string[]; cta: string; profile_url?: string;
  stats?: { saves: number; copies: number; opens: number };
};
type Campaign = {
  id: string; product_name: string; concept: string; cover_path?: string;
  assets?: Asset[]; created_at: string;
};

const LANGS = [
  { key: "pt", label: "PT" },
  { key: "en", label: "EN" },
  { key: "es", label: "ES" },
];

type AssetEditorProps = {
  campaignId: string;
  asset: Asset;
  language: string;
  onUpdated: (a: Asset) => void;
  onCopy: (txt: string, label?: string) => void;
  onShare: (a: Asset) => void;
  onOpenProfile: (a: Asset) => void;
  onSchedule: (a: Asset) => void;
};

function AssetEditor({ campaignId, asset, language, onUpdated, onCopy, onShare, onOpenProfile, onSchedule }: AssetEditorProps) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [caption, setCaption] = useState(asset.caption || "");
  const [hashtags, setHashtags] = useState((asset.hashtags || []).join(" "));
  const [cta, setCta] = useState(asset.cta || "");
  const [saving, setSaving] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [regen, setRegen] = useState<"" | "same" | "distinct">("");

  const parseTags = (s: string) =>
    s.split(/[\s,]+/).map((t) => t.trim()).filter(Boolean).map((t) => (t.startsWith("#") ? t : `#${t}`));

  const startEdit = () => {
    setCaption(asset.caption || "");
    setHashtags((asset.hashtags || []).join(" "));
    setCta(asset.cta || "");
    setEditing(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.updateCampaignAsset(campaignId, asset.network, caption.trim(), parseTags(hashtags), cta.trim());
      onUpdated(updated);
      setEditing(false);
      toast("Textos salvos", "success");
    } catch (e: any) {
      toast(e.message || "Falha ao salvar", "error");
    } finally {
      setSaving(false);
    }
  };

  const suggest = async () => {
    setSuggesting(true);
    try {
      const s = await api.suggestCampaignCopy(campaignId, asset.network, language);
      setCaption(s.caption || "");
      setHashtags((s.hashtags || []).join(" "));
      setCta(s.cta || "");
      setEditing(true);
      toast("Sugestão da IA aplicada — revise e salve", "success");
    } catch (e: any) {
      toast(e.message || "Falha ao sugerir", "error");
    } finally {
      setSuggesting(false);
    }
  };

  const regenerate = async (distinct: boolean) => {
    setRegen(distinct ? "distinct" : "same");
    try {
      const updated = await api.regenerateCampaignAsset(campaignId, asset.network, distinct);
      onUpdated(updated);
      toast(distinct ? "Variação distinta gerada!" : "Imagem regerada!", "success");
    } catch (e: any) {
      toast(e.message || "Falha ao gerar imagem", "error");
    } finally {
      setRegen("");
    }
  };

  const busyImg = regen !== "";

  const track = (action: "save" | "copy" | "open") => {
    api.trackCampaignAsset(campaignId, asset.network, action).then(onUpdated).catch(() => {});
  };
  const handleShare = () => { track("save"); onShare(asset); };
  const handleCopyAll = () => { track("copy"); onCopy(`${asset.caption}\n\n${(asset.hashtags || []).join(" ")}`, "Texto copiado"); };
  const handleOpen = () => { track("open"); onOpenProfile(asset); };
  const st = asset.stats || { saves: 0, copies: 0, opens: 0 };

  return (
    <View style={styles.assetCard}>
      <View style={styles.assetHead}>
        <Ionicons name={asset.icon as any} size={18} color={colors.brandPrimary} />
        <Text style={styles.assetLabel}>{asset.label}</Text>
        <View style={styles.ratioBadge}>
          <Text style={styles.ratioText}>{asset.ratio}</Text>
        </View>
      </View>

      <View style={styles.imgWrap}>
        <Image
          source={{ uri: fileUrl(asset.image_path) || "" }}
          style={[styles.assetImg, { aspectRatio: asset.w / asset.h }]}
          contentFit="cover"
          transition={200}
        />
        {busyImg && (
          <View style={styles.imgOverlay}>
            <ActivityIndicator size="large" color="#fff" />
            <Text style={styles.overlayText}>
              {regen === "distinct" ? "Criando variação distinta..." : "Regerando imagem..."}
            </Text>
          </View>
        )}
      </View>

      {/* Regerar imagem / variação distinta */}
      <View style={styles.toolbar}>
        <Pressable testID={`regen-same-${asset.network}`} disabled={busyImg} style={styles.toolBtn} onPress={() => regenerate(false)}>
          <Ionicons name="refresh" size={15} color={colors.brandPrimary} />
          <Text style={styles.toolText}>Regerar</Text>
        </Pressable>
        <Pressable testID={`regen-distinct-${asset.network}`} disabled={busyImg} style={styles.toolBtn} onPress={() => regenerate(true)}>
          <Ionicons name="color-wand" size={15} color={colors.brandPrimary} />
          <Text style={styles.toolText}>Variação distinta</Text>
        </Pressable>
      </View>

      {editing ? (
        <View style={styles.editBox}>
          <Field testID={`edit-caption-${asset.network}`} label="Legenda" value={caption} onChangeText={setCaption} placeholder="Escreva a legenda..." multiline />
          <Field testID={`edit-hashtags-${asset.network}`} label="Hashtags" value={hashtags} onChangeText={setHashtags} placeholder="#exemplo #promo" autoCapitalize="none" />
          <Field testID={`edit-cta-${asset.network}`} label="Chamada para ação (CTA)" value={cta} onChangeText={setCta} placeholder="Compre agora" />
          <View style={styles.editActions}>
            <Pressable testID={`cancel-edit-${asset.network}`} style={styles.actBtn} onPress={() => setEditing(false)}>
              <Ionicons name="close" size={16} color={colors.onSurface} />
              <Text style={styles.actText}>Cancelar</Text>
            </Pressable>
            <Pressable testID={`suggest-${asset.network}`} style={styles.actBtn} disabled={suggesting} onPress={suggest}>
              {suggesting ? <ActivityIndicator size="small" color={colors.brandPrimary} /> : <Ionicons name="sparkles" size={16} color={colors.brandPrimary} />}
              <Text style={styles.actText}>Sugerir IA</Text>
            </Pressable>
            <Pressable testID={`save-asset-${asset.network}`} style={[styles.actBtn, styles.actPrimary]} disabled={saving} onPress={save}>
              {saving ? <ActivityIndicator size="small" color="#fff" /> : <Ionicons name="save" size={16} color="#fff" />}
              <Text style={[styles.actText, { color: "#fff" }]}>Salvar</Text>
            </Pressable>
          </View>
        </View>
      ) : (
        <>
          {!!asset.caption && (
            <Pressable onPress={() => onCopy(asset.caption, "Legenda copiada")}>
              <Text style={styles.caption}>{asset.caption}</Text>
            </Pressable>
          )}
          {!!(asset.hashtags && asset.hashtags.length) && (
            <Pressable onPress={() => onCopy(asset.hashtags.join(" "), "Hashtags copiadas")}>
              <Text style={styles.hashtags}>{asset.hashtags.join("  ")}</Text>
            </Pressable>
          )}
          {!!asset.cta && (
            <View style={styles.ctaBox}>
              <Ionicons name="megaphone-outline" size={14} color={colors.brandSecondary} />
              <Text style={styles.ctaText}>{asset.cta}</Text>
            </View>
          )}
          <View style={styles.statsRow}>
            <View style={styles.statBadge}>
              <Ionicons name="download-outline" size={13} color={colors.brandPrimary} />
              <Text style={styles.statText}>{st.saves} salvas</Text>
            </View>
            <View style={styles.statBadge}>
              <Ionicons name="copy-outline" size={13} color={colors.brandPrimary} />
              <Text style={styles.statText}>{st.copies} cópias</Text>
            </View>
            <View style={styles.statBadge}>
              <Ionicons name="open-outline" size={13} color={colors.brandPrimary} />
              <Text style={styles.statText}>{st.opens} aberturas</Text>
            </View>
          </View>
          <View style={styles.assetActions}>
            <Pressable testID={`edit-asset-${asset.network}`} style={styles.actBtn} onPress={startEdit}>
              <Ionicons name="create-outline" size={16} color={colors.onSurface} />
              <Text style={styles.actText}>Editar</Text>
            </Pressable>
            <Pressable testID={`copy-asset-${asset.network}`} style={styles.actBtn} onPress={handleCopyAll}>
              <Ionicons name="copy-outline" size={16} color={colors.onSurface} />
              <Text style={styles.actText}>Copiar</Text>
            </Pressable>
            <Pressable testID={`share-asset-${asset.network}`} style={[styles.actBtn, styles.actPrimary]} onPress={handleShare}>
              <Ionicons name="download-outline" size={16} color="#fff" />
              <Text style={[styles.actText, { color: "#fff" }]}>Salvar</Text>
            </Pressable>
          </View>
          <View style={styles.assetActions}>
            <Pressable testID={`schedule-asset-${asset.network}`} style={styles.actBtn} onPress={() => onSchedule(asset)}>
              <Ionicons name="calendar-outline" size={16} color={colors.onSurface} />
              <Text style={styles.actText}>Agendar</Text>
            </Pressable>
            <Pressable style={styles.actBtn} onPress={handleOpen}>
              <Ionicons name="open-outline" size={16} color={colors.onSurface} />
              <Text style={styles.actText}>Abrir rede</Text>
            </Pressable>
          </View>
        </>
      )}
    </View>
  );
}

export default function MarketingStudio({ showBack = false }: { showBack?: boolean }) {
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const router = useRouter();
  const { user } = useAuth();

  const [view, setView] = useState<"novo" | "campanhas" | "redes" | "agenda">("novo");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [catalog, setCatalog] = useState<Catalog[]>([]);
  const [netState, setNetState] = useState<NetState>({});
  const [savingNets, setSavingNets] = useState(false);

  const [source, setSource] = useState<"manual" | "produto">("manual");
  const [products, setProducts] = useState<any[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [details, setDetails] = useState("");
  const [price, setPrice] = useState("");
  const [category, setCategory] = useState("");
  const [selectedNetworks, setSelectedNetworks] = useState<string[]>([]);
  const [tone, setTone] = useState("");
  const [language, setLanguage] = useState("pt");
  const [generating, setGenerating] = useState(false);

  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [detail, setDetail] = useState<Campaign | null>(null);

  const [styles2, setStyles2] = useState<{ key: string; label: string; icon: string }[]>([]);
  const [style, setStyle] = useState("auto");
  const [schedule, setSchedule] = useState<any[]>([]);
  const [waConfigured, setWaConfigured] = useState(true);
  const [downloadingKit, setDownloadingKit] = useState(false);

  // agendamento
  const [schedAsset, setSchedAsset] = useState<Asset | null>(null);
  const [schedDate, setSchedDate] = useState("");
  const [schedTime, setSchedTime] = useState("");
  const [schedWhats, setSchedWhats] = useState("");
  const [schedBusy, setSchedBusy] = useState(false);

  const loadAll = useCallback(async () => {
    try {
      const [soc, camps, sch] = await Promise.all([
        api.marketingSocials(),
        api.campaigns(),
        api.scheduleList().catch(() => ({ items: [], whatsapp_configured: true })),
      ]);
      const cat: Catalog[] = soc.catalog || [];
      setCatalog(cat);
      setStyles2(soc.styles || []);
      const ns: NetState = {};
      cat.forEach((c) => {
        const found = (soc.networks || []).find((n: any) => n.network === c.key);
        ns[c.key] = {
          enabled: found ? !!found.enabled : false,
          handle: found?.handle || "",
          url: found?.url || "",
        };
      });
      setNetState(ns);
      const enabled = cat.filter((c) => ns[c.key]?.enabled).map((c) => c.key);
      setSelectedNetworks(enabled.length ? enabled : cat.map((c) => c.key));
      setCampaigns(camps || []);
      setSchedule(sch.items || []);
      setWaConfigured(!!sch.whatsapp_configured);
    } catch (e: any) {
      toast(e.message || "Erro ao carregar", "error");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    (async () => {
      if (source === "produto" && user?.store_id && products.length === 0) {
        try {
          const p = await api.products(user.store_id);
          setProducts(p || []);
        } catch {}
      }
    })();
  }, [source, user?.store_id]);

  const toggleNetwork = (key: string) => {
    setSelectedNetworks((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  const saveNetworks = async () => {
    setSavingNets(true);
    try {
      const networks = catalog.map((c) => ({
        network: c.key,
        enabled: netState[c.key]?.enabled || false,
        handle: netState[c.key]?.handle || "",
        url: netState[c.key]?.url || "",
      }));
      await api.saveMarketingSocials(networks);
      toast("Redes salvas", "success");
    } catch (e: any) {
      toast(e.message || "Falha ao salvar", "error");
    } finally {
      setSavingNets(false);
    }
  };

  const generate = async () => {
    if (selectedNetworks.length === 0) {
      toast("Selecione ao menos uma rede", "info");
      return;
    }
    const body: any = { networks: selectedNetworks, language, tone: tone.trim(), style };
    if (source === "produto") {
      if (!selectedProduct) {
        toast("Selecione um produto", "info");
        return;
      }
      body.product_id = selectedProduct;
    } else {
      if (!name.trim()) {
        toast("Informe o nome do produto/serviço", "info");
        return;
      }
      body.product_name = name.trim();
      body.product_details = details.trim();
      body.price = price.trim();
      body.category = category.trim();
    }
    setGenerating(true);
    try {
      const res = await api.createCampaign(body);
      toast("Campanha gerada!", "success");
      setDetail(res);
      loadAll();
    } catch (e: any) {
      toast(e.message || "Falha ao gerar campanha", "error");
    } finally {
      setGenerating(false);
    }
  };

  const openCampaign = async (id: string) => {
    try {
      const c = await api.campaign(id);
      setDetail(c);
    } catch (e: any) {
      toast(e.message || "Erro", "error");
    }
  };

  const removeCampaign = async (id: string) => {
    try {
      await api.deleteCampaign(id);
      setCampaigns((prev) => prev.filter((c) => c.id !== id));
      toast("Campanha excluída", "success");
    } catch (e: any) {
      toast(e.message || "Erro", "error");
    }
  };

  const updateDetailAsset = useCallback((updated: Asset) => {
    setDetail((prev) => {
      if (!prev) return prev;
      const assets = (prev.assets || []).map((x) => (x.network === updated.network ? updated : x));
      const cover = prev.assets && prev.assets[0]?.network === updated.network ? updated.image_path : prev.cover_path;
      return { ...prev, assets, cover_path: cover };
    });
  }, []);

  const downloadKit = async () => {
    if (!detail) return;
    setDownloadingKit(true);
    try {
      const url = await api.campaignKitUrl(detail.id);
      if (Platform.OS === "web") {
        await Linking.openURL(url);
      } else {
        const dest = `${FileSystem.cacheDirectory}kit_${detail.id}.zip`;
        const dl = await FileSystem.downloadAsync(url, dest);
        const available = await Sharing.isAvailableAsync();
        if (available) await Sharing.shareAsync(dl.uri, { mimeType: "application/zip", dialogTitle: "Kit de publicação" });
        else toast("Compartilhamento indisponível", "error");
      }
      toast("Kit gerado!", "success");
    } catch {
      toast("Falha ao gerar o kit", "error");
    } finally {
      setDownloadingKit(false);
    }
  };

  const openSchedule = (a: Asset) => {
    const d = new Date(Date.now() + 60 * 60 * 1000);
    const pad = (n: number) => String(n).padStart(2, "0");
    setSchedDate(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`);
    setSchedTime(`${pad(d.getHours())}:${pad(d.getMinutes())}`);
    setSchedWhats(user?.whatsapp || "");
    setSchedAsset(a);
  };

  const applyPreset = (preset: "1h" | "tonight" | "tomorrow9" | "tomorrow18") => {
    const pad = (n: number) => String(n).padStart(2, "0");
    let d = new Date();
    if (preset === "1h") d = new Date(Date.now() + 60 * 60 * 1000);
    else if (preset === "tonight") { d.setHours(18, 0, 0, 0); if (d.getTime() < Date.now()) d = new Date(Date.now() + 60 * 60 * 1000); }
    else if (preset === "tomorrow9") { d.setDate(d.getDate() + 1); d.setHours(9, 0, 0, 0); }
    else if (preset === "tomorrow18") { d.setDate(d.getDate() + 1); d.setHours(18, 0, 0, 0); }
    setSchedDate(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`);
    setSchedTime(`${pad(d.getHours())}:${pad(d.getMinutes())}`);
  };

  const confirmSchedule = async () => {
    if (!detail || !schedAsset) return;
    if (!schedWhats.trim()) { toast("Informe o WhatsApp para o lembrete", "info"); return; }
    const iso = new Date(`${schedDate}T${schedTime}:00`);
    if (isNaN(iso.getTime())) { toast("Data/hora inválida", "error"); return; }
    if (iso.getTime() <= Date.now()) { toast("Escolha uma data/hora futura", "info"); return; }
    setSchedBusy(true);
    try {
      await api.scheduleCampaignPost(detail.id, schedAsset.network, iso.toISOString(), schedWhats.trim());
      toast("Publicação agendada!", "success");
      setSchedAsset(null);
      const sch = await api.scheduleList().catch(() => ({ items: [], whatsapp_configured: true }));
      setSchedule(sch.items || []);
      setWaConfigured(!!sch.whatsapp_configured);
    } catch (e: any) {
      toast(e.message || "Falha ao agendar", "error");
    } finally {
      setSchedBusy(false);
    }
  };

  const cancelSchedule = async (sid: string) => {
    try {
      await api.cancelSchedule(sid);
      setSchedule((prev) => prev.map((s) => (s.id === sid ? { ...s, status: "cancelled" } : s)));
      toast("Agendamento cancelado", "success");
    } catch (e: any) {
      toast(e.message || "Erro", "error");
    }
  };

  const copyText = async (txt: string, label = "Copiado") => {
    try {
      await Clipboard.setStringAsync(txt);
      toast(label, "success");
    } catch {
      toast("Não foi possível copiar", "error");
    }
  };

  const shareAsset = async (asset: Asset) => {
    const url = fileUrl(asset.image_path);
    if (!url) return;
    const caption = `${asset.caption}\n\n${(asset.hashtags || []).join(" ")}${asset.cta ? `\n\n${asset.cta}` : ""}`;
    try {
      await Clipboard.setStringAsync(caption);
    } catch {}
    try {
      if (Platform.OS === "web") {
        await Linking.openURL(url);
        toast("Legenda copiada. Imagem aberta em nova aba.", "info");
        return;
      }
      const available = await Sharing.isAvailableAsync();
      const dest = `${FileSystem.cacheDirectory}campaign_${asset.network}_${Date.now()}.jpg`;
      const dl = await FileSystem.downloadAsync(url, dest);
      if (available) {
        await Sharing.shareAsync(dl.uri, { mimeType: "image/jpeg", dialogTitle: `Publicar em ${asset.label}` });
        toast("Legenda copiada — cole ao publicar", "success");
      } else {
        toast("Compartilhamento indisponível neste dispositivo", "error");
      }
    } catch {
      toast("Falha ao compartilhar", "error");
    }
  };

  const openProfile = (asset: Asset) => {
    let u = (asset.profile_url || "").trim();
    if (!u) {
      toast("Configure sua rede em 'Minhas redes'", "info");
      return;
    }
    if (!u.startsWith("http")) u = `https://${u.replace(/^@/, "")}`;
    Linking.openURL(u).catch(() => toast("Não foi possível abrir", "error"));
  };

  // ---------------------------------------------------------------- Render
  const Header = (
    <LinearGradient colors={gradients.header} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
      style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
      <View style={styles.headerRow}>
        {showBack && (
          <Pressable onPress={() => router.back()} hitSlop={10} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={24} color="#fff" />
          </Pressable>
        )}
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Estúdio de Campanhas IA</Text>
          <Text style={styles.headerSub}>Anúncios com imagens geradas por IA para suas redes</Text>
        </View>
        <View style={styles.headerIcon}>
          <Ionicons name="sparkles" size={20} color="#fff" />
        </View>
      </View>
      <View style={styles.segment}>
        {([
          ["novo", "Nova", "add-circle-outline"],
          ["campanhas", "Campanhas", "images-outline"],
          ["agenda", "Agenda", "calendar-outline"],
          ["redes", "Redes", "share-social-outline"],
        ] as const).map(([k, lbl, ic]) => (
          <Pressable key={k} onPress={() => setView(k)}
            style={[styles.segItem, view === k && styles.segItemActive]}>
            <Ionicons name={ic as any} size={16} color={view === k ? colors.brandPrimary : "#fff"} />
            <Text style={[styles.segText, view === k && { color: colors.brandPrimary }]}>{lbl}</Text>
          </Pressable>
        ))}
      </View>
    </LinearGradient>
  );

  if (detail) {
    return (
      <View style={styles.container}>
        <LinearGradient colors={gradients.header} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
          style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
          <View style={styles.headerRow}>
            <Pressable onPress={() => setDetail(null)} hitSlop={10} style={styles.backBtn}>
              <Ionicons name="chevron-back" size={24} color="#fff" />
            </Pressable>
            <View style={{ flex: 1 }}>
              <Text style={styles.headerTitle} numberOfLines={1}>{detail.product_name}</Text>
              <Text style={styles.headerSub}>{(detail.assets || []).length} formato(s) gerado(s)</Text>
            </View>
            <Pressable testID="download-kit-btn" onPress={downloadKit} hitSlop={10} style={styles.headerIcon}>
              {downloadingKit ? <ActivityIndicator size="small" color="#fff" /> : <Ionicons name="cloud-download-outline" size={20} color="#fff" />}
            </Pressable>
          </View>
        </LinearGradient>
        <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 100 }}>
          {!!detail.concept && (
            <View style={styles.conceptBox}>
              <Ionicons name="bulb-outline" size={16} color={colors.brandPrimary} />
              <Text style={styles.conceptText}>{detail.concept}</Text>
            </View>
          )}
          <Pressable testID="kit-button" style={styles.kitBtn} onPress={downloadKit} disabled={downloadingKit}>
            {downloadingKit ? <ActivityIndicator size="small" color="#fff" /> : <Ionicons name="cloud-download-outline" size={18} color="#fff" />}
            <Text style={styles.kitBtnText}>Baixar kit de publicação (todos os formatos)</Text>
          </Pressable>
          {(detail.assets || []).map((a) => (
            <AssetEditor
              key={a.network}
              campaignId={detail.id}
              asset={a}
              language={language}
              onUpdated={updateDetailAsset}
              onCopy={copyText}
              onShare={shareAsset}
              onOpenProfile={openProfile}
              onSchedule={openSchedule}
            />
          ))}
        </ScrollView>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      {Header}
      {loading ? (
        <Loading label="Carregando estúdio..." />
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 120 }}
          keyboardShouldPersistTaps="handled"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadAll(); }} />}
        >
          {view === "novo" && (
            <>
              <Text style={styles.sectionLabel}>Origem do item</Text>
              <View style={styles.sourceRow}>
                <Pressable style={[styles.sourceBtn, source === "manual" && styles.sourceActive]} onPress={() => setSource("manual")}>
                  <Ionicons name="create-outline" size={18} color={source === "manual" ? "#fff" : colors.onSurface} />
                  <Text style={[styles.sourceText, source === "manual" && { color: "#fff" }]}>Informações manuais</Text>
                </Pressable>
                <Pressable style={[styles.sourceBtn, source === "produto" && styles.sourceActive]} onPress={() => setSource("produto")}>
                  <Ionicons name="pricetag-outline" size={18} color={source === "produto" ? "#fff" : colors.onSurface} />
                  <Text style={[styles.sourceText, source === "produto" && { color: "#fff" }]}>Produto cadastrado</Text>
                </Pressable>
              </View>

              {source === "manual" ? (
                <View style={styles.card}>
                  <Field label="Produto / Serviço" value={name} onChangeText={setName} placeholder="Ex.: Smartwatch Fitness Pro" />
                  <Field label="Detalhes / diferenciais" value={details} onChangeText={setDetails} placeholder="Descreva características, benefícios, público..." multiline />
                  <View style={{ flexDirection: "row", gap: spacing.md }}>
                    <View style={{ flex: 1 }}><Field label="Preço" value={price} onChangeText={setPrice} placeholder="R$ 399,90" /></View>
                    <View style={{ flex: 1 }}><Field label="Categoria" value={category} onChangeText={setCategory} placeholder="Eletrônicos" /></View>
                  </View>
                </View>
              ) : (
                <View style={styles.card}>
                  {!user?.store_id ? (
                    <Text style={styles.hint}>Nenhuma loja vinculada à sua conta. Use as informações manuais.</Text>
                  ) : products.length === 0 ? (
                    <Text style={styles.hint}>Nenhum produto cadastrado na sua loja ainda.</Text>
                  ) : (
                    products.map((p) => (
                      <Pressable key={p.id} onPress={() => setSelectedProduct(p.id)}
                        style={[styles.prodRow, selectedProduct === p.id && styles.prodRowActive]}>
                        <Image source={{ uri: fileUrl(p.image) || "" }} style={styles.prodThumb} contentFit="cover" />
                        <View style={{ flex: 1 }}>
                          <Text style={styles.prodName} numberOfLines={1}>{p.name}</Text>
                          <Text style={styles.prodPrice}>R$ {Number(p.price || 0).toFixed(2)}</Text>
                        </View>
                        {selectedProduct === p.id && <Ionicons name="checkmark-circle" size={22} color={colors.brandPrimary} />}
                      </Pressable>
                    ))
                  )}
                </View>
              )}

              <Text style={styles.sectionLabel}>Redes e formatos</Text>
              <View style={styles.netGrid}>
                {catalog.map((c) => {
                  const active = selectedNetworks.includes(c.key);
                  return (
                    <Pressable key={c.key} onPress={() => toggleNetwork(c.key)}
                      style={[styles.netChip, active && styles.netChipActive]}>
                      <Ionicons name={c.icon as any} size={18} color={active ? "#fff" : colors.brandPrimary} />
                      <Text style={[styles.netChipText, active && { color: "#fff" }]}>{c.label}</Text>
                      <Text style={[styles.netChipRatio, active && { color: "rgba(255,255,255,0.85)" }]}>{c.ratio}</Text>
                    </Pressable>
                  );
                })}
              </View>

              <Text style={styles.sectionLabel}>Tom e idioma</Text>
              <View style={styles.card}>
                <Field label="Tom / objetivo (opcional)" value={tone} onChangeText={setTone} placeholder="Ex.: luxuoso, divertido, promoção relâmpago" />
                <Text style={styles.miniLabel}>Idioma dos textos</Text>
                <View style={{ flexDirection: "row", gap: spacing.sm }}>
                  {LANGS.map((l) => (
                    <Pressable key={l.key} onPress={() => setLanguage(l.key)}
                      style={[styles.langChip, language === l.key && styles.langChipActive]}>
                      <Text style={[styles.langText, language === l.key && { color: "#fff" }]}>{l.label}</Text>
                    </Pressable>
                  ))}
                </View>
              </View>

              <Button
                title={generating ? "Gerando (pode levar ~30s)..." : "Gerar campanha com IA"}
                icon="sparkles"
                onPress={generate}
                loading={generating}
                style={{ marginTop: spacing.md }}
              />
              {generating && (
                <Text style={styles.genHint}>Criando imagens e textos para {selectedNetworks.length} rede(s)...</Text>
              )}
            </>
          )}

          {view === "campanhas" && (
            campaigns.length === 0 ? (
              <EmptyState icon="images-outline" title="Nenhuma campanha ainda"
                subtitle="Crie sua primeira campanha na aba 'Nova'." />
            ) : (
              campaigns.map((c) => (
                <Pressable key={c.id} style={styles.campRow} onPress={() => openCampaign(c.id)}>
                  <Image source={{ uri: fileUrl(c.cover_path) || "" }} style={styles.campCover} contentFit="cover" />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.campName} numberOfLines={1}>{c.product_name}</Text>
                    <Text style={styles.campConcept} numberOfLines={2}>{c.concept}</Text>
                    <Text style={styles.campDate}>{new Date(c.created_at).toLocaleDateString("pt-BR")}</Text>
                  </View>
                  <Pressable hitSlop={10} onPress={() => removeCampaign(c.id)} style={styles.trashBtn}>
                    <Ionicons name="trash-outline" size={18} color={colors.error} />
                  </Pressable>
                </Pressable>
              ))
            )
          )}

          {view === "redes" && (
            <>
              <Text style={styles.hint}>Configure as redes sociais da sua loja. Elas serão usadas nas campanhas e no botão publicar.</Text>
              {catalog.map((c) => {
                const st = netState[c.key] || { enabled: false, handle: "", url: "" };
                return (
                  <View key={c.key} style={styles.card}>
                    <View style={styles.netHead}>
                      <Ionicons name={c.icon as any} size={20} color={colors.brandPrimary} />
                      <Text style={styles.netTitle}>{c.label}</Text>
                      <Switch
                        value={st.enabled}
                        onValueChange={(v) => setNetState((p) => ({ ...p, [c.key]: { ...st, enabled: v } }))}
                        trackColor={{ true: colors.brandPrimary, false: colors.borderStrong }}
                        thumbColor="#fff"
                      />
                    </View>
                    <Field label="Perfil / usuário" value={st.handle}
                      onChangeText={(v: string) => setNetState((p) => ({ ...p, [c.key]: { ...st, handle: v } }))}
                      placeholder="@sualoja" autoCapitalize="none" />
                    <Field label="Link do perfil (opcional)" value={st.url}
                      onChangeText={(v: string) => setNetState((p) => ({ ...p, [c.key]: { ...st, url: v } }))}
                      placeholder="https://..." autoCapitalize="none" />
                  </View>
                );
              })}
              <Button title="Salvar redes" icon="save-outline" onPress={saveNetworks} loading={savingNets} />
            </>
          )}
        </ScrollView>
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  header: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomLeftRadius: radius.lg,
    borderBottomRightRadius: radius.lg,
  },
  headerRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  backBtn: { padding: 2 },
  headerTitle: { fontSize: font.xl, fontWeight: "800", color: "#fff" },
  headerSub: { fontSize: font.sm, color: "rgba(255,255,255,0.82)", marginTop: 2 },
  headerIcon: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.18)", alignItems: "center", justifyContent: "center",
  },
  segment: {
    flexDirection: "row", gap: spacing.xs, marginTop: spacing.lg,
    backgroundColor: "rgba(255,255,255,0.14)", borderRadius: radius.pill, padding: 4,
  },
  segItem: {
    flex: 1, flexDirection: "row", gap: 4, alignItems: "center", justifyContent: "center",
    paddingVertical: 8, borderRadius: radius.pill,
  },
  segItemActive: { backgroundColor: "#fff" },
  segText: { color: "#fff", fontWeight: "700", fontSize: font.sm },

  sectionLabel: { fontSize: font.base, fontWeight: "800", color: colors.onSurface, marginBottom: spacing.sm, marginTop: spacing.md },
  card: {
    backgroundColor: glass.cardStrong, borderRadius: radius.lg, padding: spacing.lg,
    borderWidth: 1, borderColor: colors.border, marginBottom: spacing.md, ...shadow.card,
  },
  hint: { fontSize: font.base, color: colors.onSurfaceTertiary, lineHeight: 20, marginBottom: spacing.md },
  miniLabel: { fontSize: font.base, fontWeight: "600", color: colors.onSurface, marginBottom: spacing.sm },

  sourceRow: { flexDirection: "row", gap: spacing.sm },
  sourceBtn: {
    flex: 1, flexDirection: "row", gap: 6, alignItems: "center", justifyContent: "center",
    paddingVertical: spacing.md, borderRadius: radius.md, borderWidth: 1.5, borderColor: colors.border,
    backgroundColor: glass.card,
  },
  sourceActive: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  sourceText: { fontSize: font.sm, fontWeight: "700", color: colors.onSurface },

  prodRow: {
    flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: spacing.sm,
    borderBottomWidth: 1, borderBottomColor: colors.divider,
  },
  prodRowActive: {},
  prodThumb: { width: 46, height: 46, borderRadius: radius.sm, backgroundColor: colors.surfaceTertiary },
  prodName: { fontSize: font.base, fontWeight: "600", color: colors.onSurface },
  prodPrice: { fontSize: font.sm, color: colors.brandPrimary, fontWeight: "700" },

  netGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  netChip: {
    flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: spacing.md,
    paddingVertical: 10, borderRadius: radius.pill, borderWidth: 1.5, borderColor: colors.border,
    backgroundColor: glass.card,
  },
  netChipActive: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  netChipText: { fontSize: font.sm, fontWeight: "700", color: colors.onSurface },
  netChipRatio: { fontSize: 10, color: colors.muted, fontWeight: "700" },

  langChip: {
    paddingHorizontal: spacing.lg, paddingVertical: 8, borderRadius: radius.pill,
    borderWidth: 1.5, borderColor: colors.border, backgroundColor: glass.card,
  },
  langChipActive: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  langText: { fontSize: font.sm, fontWeight: "700", color: colors.onSurface },
  genHint: { textAlign: "center", color: colors.onSurfaceTertiary, fontSize: font.sm, marginTop: spacing.sm },

  // campaigns list
  campRow: {
    flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: glass.cardStrong,
    borderRadius: radius.lg, padding: spacing.md, marginBottom: spacing.md, borderWidth: 1,
    borderColor: colors.border, ...shadow.card,
  },
  campCover: { width: 60, height: 75, borderRadius: radius.sm, backgroundColor: colors.surfaceTertiary },
  campName: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  campConcept: { fontSize: font.sm, color: colors.onSurfaceTertiary, marginTop: 2 },
  campDate: { fontSize: font.sm, color: colors.muted, marginTop: 4 },
  trashBtn: { padding: spacing.sm },

  // detail
  conceptBox: {
    flexDirection: "row", gap: spacing.sm, backgroundColor: colors.brandTertiary,
    padding: spacing.md, borderRadius: radius.md, marginBottom: spacing.lg,
  },
  conceptText: { flex: 1, fontSize: font.base, color: colors.onBrandTertiary, lineHeight: 20 },
  assetCard: {
    backgroundColor: glass.cardStrong, borderRadius: radius.lg, padding: spacing.md,
    marginBottom: spacing.lg, borderWidth: 1, borderColor: colors.border, ...shadow.card,
  },
  assetHead: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm },
  assetLabel: { flex: 1, fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  ratioBadge: { backgroundColor: colors.surfaceTertiary, paddingHorizontal: spacing.sm, paddingVertical: 3, borderRadius: radius.sm },
  ratioText: { fontSize: font.sm, fontWeight: "700", color: colors.onSurfaceTertiary },
  assetImg: { width: "100%", borderRadius: radius.md, backgroundColor: colors.surfaceTertiary },
  imgWrap: { position: "relative" },
  imgOverlay: {
    ...StyleSheet.absoluteFillObject,
    borderRadius: radius.md,
    backgroundColor: "rgba(10,19,15,0.55)",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
  },
  overlayText: { color: "#fff", fontSize: font.sm, fontWeight: "700" },
  toolbar: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm },
  toolBtn: {
    flex: 1, flexDirection: "row", gap: 5, alignItems: "center", justifyContent: "center",
    paddingVertical: 9, borderRadius: radius.md, borderWidth: 1.5, borderColor: colors.brandPrimary,
    backgroundColor: colors.brandTertiary,
  },
  toolText: { fontSize: font.sm, fontWeight: "700", color: colors.brandPrimary },
  editBox: { marginTop: spacing.md },
  editActions: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm },
  caption: { fontSize: font.base, color: colors.onSurface, lineHeight: 21, marginTop: spacing.md },
  hashtags: { fontSize: font.sm, color: colors.brandPrimary, fontWeight: "600", marginTop: spacing.sm, lineHeight: 20 },
  ctaBox: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: spacing.sm },
  ctaText: { flex: 1, fontSize: font.sm, color: colors.brandSecondary, fontWeight: "700" },
  assetActions: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md },
  actBtn: {
    flex: 1, flexDirection: "row", gap: 5, alignItems: "center", justifyContent: "center",
    paddingVertical: 10, borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderStrong,
    backgroundColor: glass.card,
  },
  actPrimary: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  actText: { fontSize: font.sm, fontWeight: "700", color: colors.onSurface },
  netHead: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.md },
  netTitle: { flex: 1, fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
});
