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
import { Button, Field, useToast, Chip } from "@/src/ui";
import { colors, spacing, radius, font, shadow } from "@/src/theme";

const HERO =
  "https://images.unsplash.com/photo-1485637701894-09ad422f6de6?crop=entropy&cs=srgb&fm=jpg&w=1000&q=80";

const DEV_ENABLED = process.env.EXPO_PUBLIC_ENABLE_DEV_LOGIN === "true";

export default function Login() {
  const { user, loginGoogle, devLogin } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const [busy, setBusy] = useState(false);
  const [devOpen, setDevOpen] = useState(false);
  const [role, setRole] = useState("cliente");
  const [email, setEmail] = useState("cliente@feira.test");

  useEffect(() => {
    if (user) router.replace("/");
  }, [user]);

  const handleGoogle = async () => {
    setBusy(true);
    try {
      await loginGoogle();
    } catch (e: any) {
      toast(e.message || "Falha no login", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleDev = async () => {
    setBusy(true);
    try {
      await devLogin(email.trim(), role);
    } catch (e: any) {
      toast(e.message || "Falha no login de teste", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.container}>
      <Image source={{ uri: HERO }} style={styles.hero} contentFit="cover" />
      <LinearGradient
        colors={["transparent", "rgba(253,251,247,0.6)", colors.surface]}
        locations={[0, 0.55, 1]}
        style={styles.scrim}
      />
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.flex}
      >
        <ScrollView
          contentContainerStyle={[styles.scroll, { paddingBottom: insets.bottom + spacing.xl }]}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.card}>
            <View style={styles.logoRow}>
              <View style={styles.logoBadge}>
                <Ionicons name="basket" size={26} color="#fff" />
              </View>
              <Text style={styles.brand}>Feira Online</Text>
            </View>
            <Text style={styles.subtitle}>
              Compre direto das barracas da sua feira, sem sair de casa.
            </Text>

            <Pressable
              testID="google-signin-button"
              onPress={handleGoogle}
              disabled={busy}
              style={({ pressed }) => [styles.googleBtn, pressed && { opacity: 0.85 }]}
            >
              <Ionicons name="logo-google" size={20} color={colors.onSurface} />
              <Text style={styles.googleText}>Entrar com Google</Text>
            </Pressable>

            {DEV_ENABLED && (
              <View style={styles.devBox}>
                <Pressable
                  testID="dev-login-toggle"
                  onPress={() => setDevOpen((v) => !v)}
                  style={styles.devToggle}
                >
                  <Ionicons name="construct-outline" size={16} color={colors.onSurfaceTertiary} />
                  <Text style={styles.devToggleText}>Entrar como teste (dev)</Text>
                  <Ionicons
                    name={devOpen ? "chevron-up" : "chevron-down"}
                    size={16}
                    color={colors.onSurfaceTertiary}
                  />
                </Pressable>
                {devOpen && (
                  <View style={{ marginTop: spacing.md }}>
                    <View style={styles.roleRow}>
                      {["cliente", "lojista", "admin"].map((r) => (
                        <Chip
                          key={r}
                          testID={`dev-role-${r}`}
                          label={r}
                          active={role === r}
                          onPress={() => {
                            setRole(r);
                            setEmail(`${r}@feira.test`);
                          }}
                        />
                      ))}
                    </View>
                    <View style={{ height: spacing.md }} />
                    <Field
                      testID="dev-email-input"
                      label="E-mail de teste"
                      value={email}
                      onChangeText={setEmail}
                      autoCapitalize="none"
                    />
                    <Button
                      title="Entrar (teste)"
                      onPress={handleDev}
                      loading={busy}
                      testID="dev-login-button"
                      variant="outline"
                    />
                  </View>
                )}
              </View>
            )}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: { flex: 1, backgroundColor: colors.surface },
  hero: { position: "absolute", top: 0, left: 0, right: 0, height: "55%" },
  scrim: { position: "absolute", top: 0, left: 0, right: 0, height: "60%" },
  scroll: { flexGrow: 1, justifyContent: "flex-end", padding: spacing.lg },
  card: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.xl,
    ...shadow.float,
  },
  logoRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginBottom: spacing.sm },
  logoBadge: {
    width: 48,
    height: 48,
    borderRadius: radius.md,
    backgroundColor: colors.brandPrimary,
    alignItems: "center",
    justifyContent: "center",
  },
  brand: { fontSize: font["2xl"], fontWeight: "800", color: colors.onSurface },
  subtitle: { fontSize: font.lg, color: colors.onSurfaceTertiary, marginBottom: spacing.xl, lineHeight: 22 },
  googleBtn: {
    height: 54,
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: colors.borderStrong,
    backgroundColor: colors.surfaceSecondary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
  },
  googleText: { fontSize: font.lg, fontWeight: "700", color: colors.onSurface },
  devBox: { marginTop: spacing.lg, borderTopWidth: 1, borderTopColor: colors.divider, paddingTop: spacing.md },
  devToggle: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm },
  devToggleText: { fontSize: font.base, color: colors.onSurfaceTertiary, fontWeight: "600" },
  roleRow: { flexDirection: "row", gap: spacing.sm },
});
