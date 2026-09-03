import { useEffect, useState } from "react";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import { Redirect } from "expo-router";
import { useAuth } from "@/src/auth";
import { storage } from "@/src/utils/storage";
import { colors } from "@/src/theme";

export default function Index() {
  const { user, loading } = useAuth();
  const [pending, setPending] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    (async () => {
      const p = await storage.getItem<string>("pending_invite", "");
      setPending(p || null);
    })();
  }, []);

  if (loading || pending === undefined) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.brandPrimary} />
      </View>
    );
  }

  if (!user) return <Redirect href="/login" />;
  if (pending) {
    storage.removeItem("pending_invite");
    return <Redirect href={`/invite/${pending}`} />;
  }
  if (user.role === "master" || user.role === "admin") return <Redirect href="/(admin)" />;
  if (user.role === "lojista") return <Redirect href="/(vendor)" />;
  return <Redirect href="/(customer)" />;
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface },
});
