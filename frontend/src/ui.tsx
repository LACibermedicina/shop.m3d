import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
  TextInput,
  Animated,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, radius, font, shadow } from "@/src/theme";

/* ------------------------------------------------------------------ Toast */
type ToastType = "success" | "error" | "info";
const ToastCtx = createContext<(msg: string, type?: ToastType) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [msg, setMsg] = useState<string | null>(null);
  const [type, setType] = useState<ToastType>("info");
  const opacity = useRef(new Animated.Value(0)).current;
  const timer = useRef<any>(null);

  const show = useCallback(
    (m: string, t: ToastType = "info") => {
      setMsg(m);
      setType(t);
      Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }).start();
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        Animated.timing(opacity, { toValue: 0, duration: 250, useNativeDriver: true }).start(() =>
          setMsg(null)
        );
      }, 2600);
    },
    [opacity]
  );

  useEffect(() => () => timer.current && clearTimeout(timer.current), []);

  const bg = type === "error" ? colors.error : type === "success" ? colors.success : colors.surfaceInverse;
  const icon = type === "error" ? "alert-circle" : type === "success" ? "checkmark-circle" : "information-circle";

  return (
    <ToastCtx.Provider value={show}>
      {children}
      {msg && (
        <Animated.View style={[styles.toast, { opacity, backgroundColor: bg }]} pointerEvents="none" testID="toast">
          <Ionicons name={icon as any} size={18} color="#fff" />
          <Text style={styles.toastText}>{msg}</Text>
        </Animated.View>
      )}
    </ToastCtx.Provider>
  );
}

/* ------------------------------------------------------------------ Button */
export function Button({
  title,
  onPress,
  variant = "primary",
  loading,
  disabled,
  icon,
  testID,
  style,
}: {
  title: string;
  onPress: () => void;
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  loading?: boolean;
  disabled?: boolean;
  icon?: any;
  testID?: string;
  style?: any;
}) {
  const bg =
    variant === "primary" ? colors.brandPrimary
    : variant === "secondary" ? colors.brandSecondary
    : variant === "danger" ? colors.error
    : "transparent";
  const border = variant === "outline" ? colors.borderStrong : "transparent";
  const fg =
    variant === "outline" || variant === "ghost" ? colors.onSurface : "#fff";
  const isDisabled = disabled || loading;
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.btn,
        { backgroundColor: bg, borderColor: border, borderWidth: variant === "outline" ? 1.5 : 0 },
        isDisabled && { opacity: 0.5 },
        pressed && { opacity: 0.85 },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <View style={styles.btnRow}>
          {icon && <Ionicons name={icon} size={18} color={fg} />}
          <Text style={[styles.btnText, { color: fg }]}>{title}</Text>
        </View>
      )}
    </Pressable>
  );
}

/* ------------------------------------------------------------------ Field */
export function Field({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType,
  multiline,
  testID,
  autoCapitalize,
}: any) {
  return (
    <View style={{ marginBottom: spacing.lg }}>
      {label && <Text style={styles.label}>{label}</Text>}
      <TextInput
        testID={testID}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.muted}
        keyboardType={keyboardType}
        multiline={multiline}
        autoCapitalize={autoCapitalize}
        style={[styles.input, multiline && { height: 96, textAlignVertical: "top" }]}
      />
    </View>
  );
}

/* ------------------------------------------------------------------ Loading / Empty / Error */
export function Loading({ label }: { label?: string }) {
  return (
    <View style={styles.center} testID="loading">
      <ActivityIndicator color={colors.brandPrimary} size="large" />
      {label && <Text style={styles.dim}>{label}</Text>}
    </View>
  );
}

export function EmptyState({
  icon = "cube-outline",
  title,
  subtitle,
  action,
}: {
  icon?: any;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <View style={styles.center} testID="empty-state">
      <View style={styles.emptyIcon}>
        <Ionicons name={icon} size={40} color={colors.brandPrimary} />
      </View>
      <Text style={styles.emptyTitle}>{title}</Text>
      {subtitle && <Text style={styles.dim}>{subtitle}</Text>}
      {action && <View style={{ marginTop: spacing.lg }}>{action}</View>}
    </View>
  );
}

export function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <View style={styles.center} testID="error-state">
      <Ionicons name="cloud-offline-outline" size={40} color={colors.error} />
      <Text style={styles.emptyTitle}>Algo deu errado</Text>
      <Button title="Tentar novamente" onPress={onRetry} variant="outline" testID="retry-button" />
    </View>
  );
}

/* ------------------------------------------------------------------ Chip */
export function Chip({ label, active, onPress, testID }: any) {
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      style={[styles.chip, active && { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary }]}
    >
      <Text style={[styles.chipText, active && { color: "#fff", fontWeight: "700" }]}>{label}</Text>
    </Pressable>
  );
}

/* ------------------------------------------------------------------ Avatar */
export function Avatar({ name, size = 44 }: { name?: string; size?: number }) {
  const initials = (name || "?")
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <View style={[styles.avatar, { width: size, height: size, borderRadius: size / 2 }]}>
      <Text style={{ color: colors.onBrandTertiary, fontWeight: "700", fontSize: size / 2.6 }}>
        {initials}
      </Text>
    </View>
  );
}

/* ------------------------------------------------------------------ StatusBadge */
export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; fg: string; label: string }> = {
    novo: { bg: colors.brandTertiary, fg: colors.onBrandTertiary, label: "Novo" },
    editando: { bg: "#FCEFD9", fg: colors.warning, label: "Editando" },
    pronto: { bg: colors.brandTertiary, fg: colors.success, label: "Pronto" },
    entregue: { bg: colors.surfaceTertiary, fg: colors.onSurfaceTertiary, label: "Entregue" },
    cancelado: { bg: "#F6E1E1", fg: colors.error, label: "Cancelado" },
  };
  const s = map[status] || map.novo;
  return (
    <View style={[styles.badge, { backgroundColor: s.bg }]}>
      <Text style={{ color: s.fg, fontSize: font.sm, fontWeight: "700" }}>{s.label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  toast: {
    position: "absolute",
    bottom: 90,
    left: spacing.lg,
    right: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.md,
    ...shadow.float,
  },
  toastText: { color: "#fff", fontSize: font.base, flex: 1, fontWeight: "500" },
  btn: {
    height: 52,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
  },
  btnRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  btnText: { fontSize: font.lg, fontWeight: "700" },
  label: { fontSize: font.base, fontWeight: "600", color: colors.onSurface, marginBottom: spacing.sm },
  input: {
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: font.lg,
    color: colors.onSurface,
  },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl, gap: spacing.sm },
  dim: { color: colors.onSurfaceTertiary, fontSize: font.base, textAlign: "center" },
  emptyIcon: {
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm,
  },
  emptyTitle: { fontSize: font.xl, fontWeight: "700", color: colors.onSurface, textAlign: "center" },
  chip: {
    height: 36,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  chipText: { fontSize: font.base, color: colors.onSurfaceTertiary, fontWeight: "500" },
  avatar: { backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  badge: { paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.sm, alignSelf: "flex-start" },
});
