import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { View, Text, StyleSheet, Platform } from "react-native";
import { colors, spacing, font } from "@/src/theme";
import { VendorOrdersProvider, useVendorOrders } from "@/src/vendorOrders";

function OrdersIcon({ color, size }: { color: string; size: number }) {
  const { newCount } = useVendorOrders();
  return (
    <View>
      <Ionicons name="receipt-outline" size={size} color={color} />
      {newCount > 0 && (
        <View style={styles.badge} testID="vendor-orders-badge">
          <Text style={styles.badgeText}>{newCount > 99 ? "99+" : newCount}</Text>
        </View>
      )}
    </View>
  );
}

function VendorTabs() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.brandPrimary,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: {
          backgroundColor: colors.surfaceSecondary,
          borderTopColor: colors.border,
          height: Platform.OS === "ios" ? 88 : 64,
          paddingTop: spacing.sm,
          paddingBottom: Platform.OS === "ios" ? spacing.xl : spacing.sm,
        },
        tabBarLabelStyle: { fontSize: font.sm, fontWeight: "600" },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Pedidos",
          tabBarIcon: ({ color, size }) => <OrdersIcon color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="catalog"
        options={{
          title: "Catálogo",
          tabBarIcon: ({ color, size }) => <Ionicons name="pricetags-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Perfil",
          tabBarIcon: ({ color, size }) => <Ionicons name="person-outline" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}

export default function VendorLayout() {
  return (
    <VendorOrdersProvider>
      <VendorTabs />
    </VendorOrdersProvider>
  );
}

const styles = StyleSheet.create({
  badge: {
    position: "absolute",
    top: -6,
    right: -10,
    backgroundColor: colors.brandSecondary,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 4,
  },
  badgeText: { color: "#fff", fontSize: 10, fontWeight: "800" },
});
