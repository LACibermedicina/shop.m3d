import React from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useI18n, LANGS, Lang } from "@/src/i18n";
import { radius, font } from "@/src/theme";

export function LangSelector({ variant = "light" }: { variant?: "light" | "dark" }) {
  const { lang, setLang } = useI18n();
  const onDark = variant === "light"; // used on gradient (dark) headers => light text
  const baseBg = onDark ? "rgba(255,255,255,0.15)" : "rgba(74,124,89,0.10)";
  const activeBg = onDark ? "#fff" : "#4A7C59";
  const activeText = onDark ? "#2E513A" : "#fff";
  const idleText = onDark ? "rgba(255,255,255,0.9)" : "#4A7C59";
  return (
    <View style={[styles.wrap, { backgroundColor: baseBg }]} testID="lang-selector">
      <Ionicons name="globe-outline" size={14} color={idleText} style={{ marginLeft: 6, marginRight: 2 }} />
      {LANGS.map((l) => {
        const active = lang === l.key;
        return (
          <Pressable
            key={l.key}
            testID={`lang-${l.key}`}
            accessibilityRole="button"
            accessibilityLabel={`Idioma ${l.label}`}
            accessibilityState={{ selected: active }}
            onPress={() => setLang(l.key as Lang)}
            style={[styles.pill, active && { backgroundColor: activeBg }]}
            hitSlop={6}
          >
            <Text style={styles.flag}>{l.flag}</Text>
            <Text style={[styles.txt, { color: active ? activeText : idleText }]}>{l.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: radius.pill,
    padding: 3,
    alignSelf: "flex-start",
  },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderRadius: radius.pill,
    minHeight: 30,
  },
  flag: { fontSize: 15, lineHeight: 18 },
  txt: { fontSize: font.sm, fontWeight: "800", letterSpacing: 0.3 },
});
