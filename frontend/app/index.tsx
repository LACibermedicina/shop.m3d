import { useEffect } from "react";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import { Redirect } from "expo-router";
import { useAuth } from "@/src/auth";
import { colors } from "@/src/theme";

export default function Index() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.brandPrimary} />
      </View>
    );
  }

  if (!user) return <Redirect href="/login" />;
  if (user.role === "admin") return <Redirect href="/(admin)" />;
  if (user.role === "lojista") return <Redirect href="/(vendor)" />;
  return <Redirect href="/(customer)" />;
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface },
});
