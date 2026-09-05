import { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Clipboard from "expo-clipboard";
import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Loading, ErrorState, Button, Field, Chip, useToast, EmptyState } from "@/src/ui";
import { colors, spacing, radius, font, shadow, gradients } from "@/src/theme";

export default function WhatsAppConfig() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const toast = useToast();
  const { user: me } = useAuth();
  const isMaster = me?.role === "master";

  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [config, setConfig] = useState<any>(null);
  const [phone, setPhone] = useState<any>(null);

  // editable fields
  const [sendMode, setSendMode] = useState<"auto" | "link">("auto");
  const [phoneId, setPhoneId] = useState("");
  const [apiVersion, setApiVersion] = useState("");
  const [verifyToken, setVerifyToken] = useState("");
  const [rootWa, setRootWa] = useState("");
  const [tmplLang, setTmplLang] = useState("");
  const [tmplOrder, setTmplOrder] = useState("");
  const [tmplStatus, setTmplStatus] = useState("");
  const [newToken, setNewToken] = useState("");
  const [newSecret, setNewSecret] = useState("");
  const [showCreds, setShowCreds] = useState(false);

  // test
  const [testTo, setTestTo] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [saving, setSaving] = useState(false);

  const hydrate = (data: any) => {
    const c = data?.config || {};
    setConfig(c);
    setPhone(data?.phone_info || null);
    setSendMode(c.send_mode === "link" ? "link" : "auto");
    setPhoneId(c.phone_number_id || "");
    setApiVersion(c.api_version || "");
    setVerifyToken(c.verify_token || "");
    setRootWa(c.root_whatsapp || "");
    setTmplLang(c.template_lang || "");
    setTmplOrder(c.template_order || "");
    setTmplStatus(c.template_status || "");
  };

  const load = useCallback(async () => {
    try {
      const data = await api.waConfig();
      hydrate(data);
      setState("done");
    } catch {
      setState("error");
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      if (isMaster) load();
    }, [isMaster, load])
  );

  const save = async () => {
    setSaving(true);
    try {
      const payload: any = {
        send_mode: sendMode,
        phone_number_id: phoneId,
        api_version: apiVersion,
        verify_token: verifyToken,
        root_whatsapp: rootWa,
        template_lang: tmplLang,
        template_order: tmplOrder,
        template_status: tmplStatus,
      };
      if (newToken.trim()) payload.access_token = newToken.trim();
      if (newSecret.trim()) payload.app_secret = newSecret.trim();
      const data = await api.waConfigUpdate(payload);
      hydrate(data);
      setNewToken("");
      setNewSecret("");
      toast("Configuração salva", "success");
    } catch (e: any) {
      toast(e?.message || "Falha ao salvar", "error");
    } finally {
      setSaving(false);
    }
  };

  const runTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const data = await api.waTest(testTo.trim());
      setPhone(data?.phone_info || null);
      setTestResult(data);
      toast(data?.direct_ok ? "Envio direto OK!" : "Diagnóstico concluído", data?.direct_ok ? "success" : "info");
    } catch (e: any) {
      toast(e?.message || "Falha no teste", "error");
    } finally {
      setTesting(false);
    }
  };

  const copyWebhook = async () => {
    if (config?.webhook_url) {
      await Clipboard.setStringAsync(config.webhook_url);
      toast("URL do webhook copiada", "success");
    }
  };
  const copyVerify = async () => {
    if (verifyToken) {
      await Clipboard.setStringAsync(verifyToken);
      toast("Verify token copiado", "success");
    }
  };

  const pdata = phone?.data || {};
  const platform = pdata.platform_type || "";
  const verified = pdata.code_verification_status === "VERIFIED";
  const cloudReady = platform === "CLOUD_API" && verified;
  const directBlocked = config?.configured && !cloudReady;

  if (!isMaster) {
    return (
      <View style={styles.container}>
        <Header insets={insets} onBack={() => router.back()} />
        <EmptyState icon="lock-closed-outline" title="Acesso restrito" subtitle="Somente o usuário master pode configurar o WhatsApp." />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <View style={styles.container}>
        <Header insets={insets} onBack={() => router.back()} />

        {state === "loading" ? (
          <Loading label="Carregando configuração…" />
        ) : state === "error" ? (
          <ErrorState onRetry={load} />
        ) : (
          <ScrollView
            contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing["3xl"] }}
            keyboardShouldPersistTaps="handled"
          >
            {/* STATUS CARD */}
            <View style={styles.card}>
              <View style={styles.rowBetween}>
                <Text style={styles.cardTitle}>Status atual</Text>
                <View style={[styles.pill, { backgroundColor: config?.configured ? colors.brandTertiary : colors.divider }]}>
                  <Ionicons
                    name={config?.configured ? "checkmark-circle" : "alert-circle"}
                    size={14}
                    color={config?.configured ? colors.onBrandTertiary : colors.muted}
                  />
                  <Text style={[styles.pillText, { color: config?.configured ? colors.onBrandTertiary : colors.muted }]}>
                    {config?.configured ? "Configurado" : "Não configurado"}
                  </Text>
                </View>
              </View>

              {phone?.ok ? (
                <View style={{ marginTop: spacing.md, gap: 6 }}>
                  <InfoRow label="Número" value={pdata.display_phone_number || "—"} />
                  <InfoRow label="Nome verificado" value={pdata.verified_name || "—"} />
                  <InfoRow label="Plataforma" value={platform || "—"} />
                  <InfoRow
                    label="Verificação"
                    value={pdata.code_verification_status || "—"}
                    valueColor={verified ? colors.success : colors.warning}
                  />
                  <InfoRow label="Modo da conta" value={pdata.account_mode || "—"} />
                </View>
              ) : (
                <Text style={[styles.dim, { marginTop: spacing.sm }]}>
                  {phone?.error === "not_configured"
                    ? "Informe o token e o Phone Number ID para consultar o status."
                    : "Não foi possível consultar o status na Meta."}
                </Text>
              )}

              {directBlocked && (
                <View style={styles.warnBox}>
                  <Ionicons name="warning" size={18} color={colors.warning} />
                  <Text style={styles.warnText}>
                    O número está como <Text style={{ fontWeight: "800" }}>{platform || "ON_PREMISE"}</Text>. Os envios diretos
                    pela Cloud API ficam bloqueados (erro #133010) até concluir a coexistência/onboarding no WhatsApp Manager
                    da Meta. Enquanto isso, a entrega híbrida por link wa.me continua funcionando.
                  </Text>
                </View>
              )}
              {cloudReady && (
                <View style={[styles.warnBox, { backgroundColor: colors.brandTertiary }]}>
                  <Ionicons name="checkmark-circle" size={18} color={colors.success} />
                  <Text style={[styles.warnText, { color: colors.onBrandTertiary }]}>
                    Número pronto na Cloud API. Envios diretos habilitados.
                  </Text>
                </View>
              )}
            </View>

            {/* SEND MODE */}
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Modo de envio</Text>
              <Text style={[styles.dim, { marginBottom: spacing.md }]}>
                “Automático” tenta a Cloud API e cai para link wa.me se falhar. “Somente link” sempre usa wa.me.
              </Text>
              <View style={{ flexDirection: "row", gap: spacing.sm }}>
                <Chip label="Automático (Cloud API)" active={sendMode === "auto"} onPress={() => setSendMode("auto")} testID="wa-mode-auto" />
                <Chip label="Somente link (wa.me)" active={sendMode === "link"} onPress={() => setSendMode("link")} testID="wa-mode-link" />
              </View>
            </View>

            {/* WEBHOOK */}
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Webhook (Meta)</Text>
              <Text style={styles.dim}>Configure esta URL e o Verify Token no painel da Meta.</Text>
              <Pressable onPress={copyWebhook} style={styles.copyRow}>
                <Text style={styles.copyText} numberOfLines={1}>{config?.webhook_url}</Text>
                <Ionicons name="copy-outline" size={18} color={colors.brandPrimary} />
              </Pressable>
              <Pressable onPress={copyVerify} style={styles.copyRow}>
                <Text style={styles.copyText} numberOfLines={1}>Verify Token: {verifyToken || "—"}</Text>
                <Ionicons name="copy-outline" size={18} color={colors.brandPrimary} />
              </Pressable>
            </View>

            {/* CREDENTIALS (collapsible) */}
            <View style={styles.card}>
              <Pressable onPress={() => setShowCreds((v) => !v)} style={styles.rowBetween}>
                <Text style={styles.cardTitle}>Credenciais e parâmetros</Text>
                <Ionicons name={showCreds ? "chevron-up" : "chevron-down"} size={20} color={colors.muted} />
              </Pressable>

              {showCreds && (
                <View style={{ marginTop: spacing.md }}>
                  <Field
                    label={`Access Token${config?.has_access_token ? ` (atual: ${config.access_token_masked})` : ""}`}
                    value={newToken}
                    onChangeText={setNewToken}
                    placeholder={config?.has_access_token ? "Deixe em branco para manter" : "Cole o token permanente"}
                    autoCapitalize="none"
                    secureTextEntry
                    testID="wa-access-token"
                  />
                  <Field label="Phone Number ID" value={phoneId} onChangeText={setPhoneId} placeholder="Ex.: 1329447850249783" keyboardType="number-pad" testID="wa-phone-id" />
                  <Field
                    label={`App Secret${config?.has_app_secret ? ` (atual: ${config.app_secret_masked})` : ""}`}
                    value={newSecret}
                    onChangeText={setNewSecret}
                    placeholder={config?.has_app_secret ? "Deixe em branco para manter" : "Chave secreta do app"}
                    autoCapitalize="none"
                    secureTextEntry
                    testID="wa-app-secret"
                  />
                  <Field label="Verify Token" value={verifyToken} onChangeText={setVerifyToken} placeholder="Token do webhook" autoCapitalize="none" testID="wa-verify-token" />
                  <Field label="API Version" value={apiVersion} onChangeText={setApiVersion} placeholder="v25.0" autoCapitalize="none" testID="wa-api-version" />
                  <Field label="WhatsApp do Root (admin)" value={rootWa} onChangeText={setRootWa} placeholder="Ex.: 5511999999999" keyboardType="phone-pad" testID="wa-root" />
                  <Field label="Template — Pedido" value={tmplOrder} onChangeText={setTmplOrder} placeholder="nome do template aprovado" autoCapitalize="none" testID="wa-tmpl-order" />
                  <Field label="Template — Status" value={tmplStatus} onChangeText={setTmplStatus} placeholder="nome do template aprovado" autoCapitalize="none" testID="wa-tmpl-status" />
                  <Field label="Template — Idioma" value={tmplLang} onChangeText={setTmplLang} placeholder="pt_BR" autoCapitalize="none" testID="wa-tmpl-lang" />
                </View>
              )}
            </View>

            <Button title="Salvar configuração" onPress={save} loading={saving} icon="save-outline" testID="wa-save" />

            {/* TEST */}
            <View style={[styles.card, { marginTop: spacing.xl }]}>
              <Text style={styles.cardTitle}>Validar envio direto</Text>
              <Text style={[styles.dim, { marginBottom: spacing.md }]}>
                Revalida o status na Meta e (opcional) tenta um envio real de teste para o número informado.
              </Text>
              <Field label="Número de teste (com DDI/DDD)" value={testTo} onChangeText={setTestTo} placeholder="Ex.: 5511960708817" keyboardType="phone-pad" testID="wa-test-to" />
              <Button title="Revalidar / Enviar teste" onPress={runTest} loading={testing} variant="outline" icon="paper-plane-outline" testID="wa-test-run" />

              {testResult && (
                <View
                  style={[
                    styles.resultBox,
                    { backgroundColor: testResult.direct_ok ? colors.brandTertiary : "rgba(224,149,74,0.14)" },
                  ]}
                >
                  <Ionicons
                    name={testResult.direct_ok ? "checkmark-circle" : "information-circle"}
                    size={18}
                    color={testResult.direct_ok ? colors.success : colors.warning}
                  />
                  <Text style={styles.resultText}>{testResult.hint || (testResult.direct_ok ? "OK" : "Concluído")}</Text>
                </View>
              )}
            </View>
          </ScrollView>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

function Header({ insets, onBack }: { insets: any; onBack: () => void }) {
  return (
    <LinearGradient
      colors={gradients.header}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={[styles.headerBar, { paddingTop: insets.top + spacing.md }]}
    >
      <View style={styles.headerRow}>
        <Pressable onPress={onBack} style={styles.headerBadge} testID="wa-back">
          <Ionicons name="chevron-back" size={22} color="#fff" />
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>WhatsApp</Text>
          <Text style={styles.headerSub}>Integração e envios diretos</Text>
        </View>
        <View style={styles.headerBadge}>
          <Ionicons name="logo-whatsapp" size={20} color="#fff" />
        </View>
      </View>
    </LinearGradient>
  );
}

function InfoRow({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={[styles.infoValue, valueColor && { color: valueColor }]} numberOfLines={1}>
        {value}
      </Text>
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
  },
  headerRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  title: { fontSize: font["2xl"], fontWeight: "800", color: "#fff" },
  headerSub: { fontSize: font.sm, color: "rgba(255,255,255,0.85)", marginTop: 2 },
  headerBadge: {
    width: 40,
    height: 40,
    borderRadius: radius.pill,
    backgroundColor: "rgba(255,255,255,0.18)",
    alignItems: "center",
    justifyContent: "center",
  },
  card: {
    backgroundColor: colors.solid,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    ...shadow.card,
  },
  cardTitle: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  dim: { fontSize: font.sm, color: colors.muted, lineHeight: 18 },
  pill: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: spacing.md, paddingVertical: 5, borderRadius: radius.pill },
  pillText: { fontSize: font.sm, fontWeight: "700" },
  infoRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: spacing.md },
  infoLabel: { fontSize: font.base, color: colors.muted },
  infoValue: { fontSize: font.base, color: colors.onSurface, fontWeight: "600", flexShrink: 1, textAlign: "right" },
  warnBox: {
    flexDirection: "row",
    gap: spacing.sm,
    backgroundColor: "rgba(224,149,74,0.14)",
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.md,
    alignItems: "flex-start",
  },
  warnText: { flex: 1, fontSize: font.sm, color: "#7a5320", lineHeight: 18 },
  copyRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
    backgroundColor: colors.surfaceTertiary,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.sm,
  },
  copyText: { flex: 1, fontSize: font.sm, color: colors.onSurface },
  resultBox: {
    flexDirection: "row",
    gap: spacing.sm,
    alignItems: "flex-start",
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.md,
  },
  resultText: { flex: 1, fontSize: font.sm, color: colors.onSurface, lineHeight: 18 },
});
