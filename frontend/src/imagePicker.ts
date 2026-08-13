import * as ImagePicker from "expo-image-picker";
import { Linking } from "react-native";

export type PickResult = { uri: string } | { error: "denied" | "blocked" | "cancelled" };

export async function pickImage(): Promise<PickResult> {
  let perm = await ImagePicker.getMediaLibraryPermissionsAsync();
  if (!perm.granted) {
    if (perm.canAskAgain) {
      perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    }
    if (!perm.granted) {
      return { error: perm.canAskAgain ? "denied" : "blocked" };
    }
  }
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ["images"],
    quality: 0.7,
    allowsEditing: true,
    aspect: [1, 1],
  });
  if (result.canceled || !result.assets?.length) return { error: "cancelled" };
  return { uri: result.assets[0].uri };
}

export function openAppSettings() {
  Linking.openSettings();
}
