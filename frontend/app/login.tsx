import { useState, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useAuth } from "@/src/auth";
import { Button, Field, useToast } from "@/src/ui";
import { colors, spacing, radius, font, shadow, glass } from "@/src/theme";
import { HERO_IMAGE } from "@/src/images";

const HERO = HERO_IMAGE;

export default function Login() {
  const { user, login } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const [busy, setBusy] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);

  useEffect(() => {
    if (user) router.replace("/");
  }, [user]);

  const handleLogin = async () => {
    if (!username.trim() || !password) {
      toast("Informe usuário e senha", "info");
      return;
    }
    setBusy(true);
    try {
      await login(username.trim(), password);
    } catch (e: any) {
      toast(e.message || "Falha no login", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.container}>
      <Image source={{ uri: HERO }} style={styles.hero} contentFit="cover" />
      {/* Scrim imersivo: escurece a base para dar profundidade ao card */}
      <LinearGradient
        colors={["rgba(10,19,15,0.15)", "rgba(10,19,15,0.55)", "rgba(10,19,15,0.92)"]}
        locations={[0, 0.5, 1]}
        style={StyleSheet.absoluteFill}
      />

      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.flex}
      >
        <ScrollView
          contentContainerStyle={[
            styles.scroll,
            { paddingTop: insets.top + spacing.xl, paddingBottom: insets.bottom + spacing.xl },
          ]}
          keyboardShouldPersistTaps="handled"
        >
          {/* Marca no topo, sobre a imagem */}
          <View style={styles.topBrand}>
            <Image
              source={require("../assets/images/m3d-logo.png")}
              style={styles.brandLogo}
              contentFit="contain"
            />
            <Text style={styles.brandTop}>shop.m3d.pro</Text>
            <Text style={styles.tagline}>
              Lojas por áreas de interesse. Compre de quem entende, numa rede de confiança.
            </Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Entrar</Text>
            <Text style={styles.cardSub}>Acesse com seu usuário e senha</Text>

            <View style={styles.inputWrap}>
              <Ionicons name="person-outline" size={18} color={colors.brandPrimary} style={styles.inputIcon} />
              <View style={{ flex: 1 }}>
                <Field
                  testID="login-username"
                  label="Usuário"
                  value={username}
                  onChangeText={setUsername}
                  placeholder="root, admin, lojista ou cliente"
                  autoCapitalize="none"
                />
              </View>
            </View>

            <View style={styles.inputWrap}>
              <Ionicons name="lock-closed-outline" size={18} color={colors.brandPrimary} style={styles.inputIcon} />
              <View style={{ flex: 1 }}>
                <Field
                  testID="login-password"
                  label="Senha"
                  value={password}
                  onChangeText={setPassword}
                  placeholder="Sua senha"
                  autoCapitalize="none"
                  secureTextEntry={!showPass}
                  returnKeyType="go"
                  onSubmitEditing={handleLogin}
                />
              </View>
              <Pressable
                testID="toggle-password"
                onPress={() => setShowPass((v) => !v)}
                style={styles.eyeBtn}
                hitSlop={10}
              >
                <Ionicons
                  name={showPass ? "eye-off-outline" : "eye-outline"}
                  size={20}
                  color={colors.onSurfaceTertiary}
                />
              </Pressable>
            </View>

            <Button
              title="Entrar"
              onPress={handleLogin}
              loading={busy}
              testID="login-button"
              icon="log-in-outline"
            />

            <View style={styles.footerRow}>
              <Ionicons name="shield-checkmark-outline" size={14} color={colors.muted} />
              <Text style={styles.footerText}>Acesso seguro · rede de confiança m3d.pro</Text>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: { flex: 1, backgroundColor: "#0A130F" },
  hero: { ...StyleSheet.absoluteFillObject, height: "60%" },
  scroll: { flexGrow: 1, justifyContent: "flex-end", padding: spacing.lg },
  topBrand: { alignItems: "center", marginBottom: spacing.xl },
  brandLogo: { width: 64, height: 64, borderRadius: radius.md, marginBottom: spacing.sm },
  brandTop: { fontSize: font["3xl"], fontWeight: "800", color: "#fff", letterSpacing: 0.3 },
  tagline: {
    fontSize: font.base,
    color: "rgba(255,255,255,0.88)",
    textAlign: "center",
    marginTop: spacing.sm,
    lineHeight: 20,
    paddingHorizontal: spacing.lg,
  },
  card: {
    backgroundColor: glass.cardStrong,
    borderRadius: radius.xl,
    padding: spacing.xl,
    borderWidth: 1,
    borderColor: glass.border,
    ...shadow.float,
  },
  cardTitle: { fontSize: font["2xl"], fontWeight: "800", color: colors.onSurface },
  cardSub: { fontSize: font.base, color: colors.onSurfaceTertiary, marginTop: 2, marginBottom: spacing.lg },
  inputWrap: { flexDirection: "row", alignItems: "flex-start" },
  inputIcon: { marginTop: 38, marginRight: spacing.sm },
  eyeBtn: {
    width: 40,
    height: 48,
    marginTop: 26,
    alignItems: "center",
    justifyContent: "center",
  },
  footerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    marginTop: spacing.lg,
  },
  footerText: { fontSize: font.sm, color: colors.muted },
});
