export const colors = {
  surface: "#EAF1EE",
  onSurface: "#0E1B16",
  surfaceSecondary: "rgba(255,255,255,0.78)",
  onSurfaceSecondary: "#0E1B16",
  surfaceTertiary: "rgba(14,124,90,0.09)",
  onSurfaceTertiary: "#3C4A44",
  surfaceInverse: "#0E241C",
  onSurfaceInverse: "#FFFFFF",
  brand: "#0E7C5A",
  brandPrimary: "#0E7C5A",
  onBrandPrimary: "#FFFFFF",
  brandSecondary: "#E0824F",
  onBrandSecondary: "#FFFFFF",
  brandTertiary: "#D8EBE2",
  onBrandTertiary: "#0B4A36",
  success: "#1E7A4F",
  warning: "#E0954A",
  error: "#C4514E",
  onError: "#FFFFFF",
  border: "rgba(14,27,22,0.10)",
  borderStrong: "rgba(14,27,22,0.18)",
  divider: "rgba(14,27,22,0.07)",
  muted: "#7A857F",
  // opaque surfaces (use for tab bars / places that must not bleed content)
  solid: "#FFFFFF",
  tabBar: "#F7FAF8",
};

// Translucent glass tokens for depth (use over tinted backgrounds or images)
export const glass = {
  card: "rgba(255,255,255,0.72)",
  cardStrong: "rgba(255,255,255,0.86)",
  tint: "rgba(255,255,255,0.55)",
  dark: "rgba(14,36,28,0.5)",
  border: "rgba(255,255,255,0.55)",
  borderDark: "rgba(255,255,255,0.14)",
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, "2xl": 32, "3xl": 48 };
export const radius = { sm: 6, md: 12, lg: 20, xl: 28, pill: 999 };
export const font = { sm: 12, base: 14, lg: 16, xl: 20, "2xl": 24, "3xl": 30, "4xl": 36 };

// Immersive gradient palette (use with expo-linear-gradient)
export const gradients = {
  brand: ["#0E7C5A", "#0B3D2E"] as const,
  header: ["#0B3D2E", "#0E7C5A", "#37A98A"] as const,
  warm: ["#0E7C5A", "#E0824F"] as const,
  sunset: ["#E0824F", "#E0954A"] as const,
  night: ["#0E241C", "#0A130F"] as const,
  ocean: ["#0B3D2E", "#0E5E6E", "#127C71"] as const,
  scrimBottom: ["transparent", "rgba(10,19,15,0.0)", "rgba(10,19,15,0.9)"] as const,
  scrimCard: ["rgba(10,19,15,0.0)", "rgba(10,19,15,0.35)", "rgba(10,19,15,0.82)"] as const,
};

export const shadow = {
  card: {
    shadowColor: "#0A130F",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.10,
    shadowRadius: 14,
    elevation: 3,
  },
  float: {
    shadowColor: "#0A130F",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.22,
    shadowRadius: 22,
    elevation: 8,
  },
};

export const money = (n: number) =>
  `R$ ${Number(n || 0).toFixed(2).replace(".", ",")}`;

export const CATEGORIES = [
  "Eletrônicos",
  "Informática",
  "Celulares",
  "Perfumaria",
  "Moda",
  "Calçados",
  "Casa & Decoração",
  "Brinquedos",
  "Bebidas",
  "Alimentos",
  "Acessórios",
  "Outros",
];
