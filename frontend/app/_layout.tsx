import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";
import { LogBox } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { useIconFonts } from "@/src/hooks/use-icon-fonts";
import { AuthProvider } from "@/src/auth";
import { CartProvider } from "@/src/cart";
import { I18nProvider } from "@/src/i18n";
import { ToastProvider } from "@/src/ui";

// Disable logbox errors etc so that users can see the app
// and agent works as expected.
LogBox.ignoreAllLogs(true);

// Keep the native splash visible from cold start until icon fonts register.
// Required because @expo/vector-icons' componentDidMount fallback fires
// Font.loadAsync against a broken vendor path if any <Icon> mounts before
// the family is registered — which throws on Android Expo Go.
SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [loaded, error] = useIconFonts();

  useEffect(() => {
    if (loaded || error) {
      SplashScreen.hideAsync();
    }
  }, [loaded, error]);

  // If the CDN is unreachable we fall through on error rather than wedging
  // the app — icons will tofu, but the app still boots.
  if (!loaded && !error) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <AuthProvider>
          <CartProvider>
            <I18nProvider>
              <ToastProvider>
                <Stack screenOptions={{ headerShown: false }}>
                  <Stack.Screen name="index" />
                  <Stack.Screen name="login" />
                  <Stack.Screen name="(customer)" />
                  <Stack.Screen name="(vendor)" />
                  <Stack.Screen name="(admin)" />
                  <Stack.Screen name="store/[id]" options={{ presentation: "card" }} />
                  <Stack.Screen name="order/[id]" options={{ presentation: "card" }} />
                  <Stack.Screen name="invite/[token]" options={{ presentation: "card" }} />
                  <Stack.Screen name="invites" options={{ presentation: "card" }} />
                  <Stack.Screen name="groups-admin" options={{ presentation: "card" }} />
                  <Stack.Screen name="whatsapp-config" options={{ presentation: "card" }} />
                </Stack>
              </ToastProvider>
            </I18nProvider>
          </CartProvider>
        </AuthProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
