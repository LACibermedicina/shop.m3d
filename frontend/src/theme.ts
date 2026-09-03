export const colors = {
  surface: "#FDFBF7",
  onSurface: "#1A1C19",
  surfaceSecondary: "#FFFFFF",
  onSurfaceSecondary: "#1A1C19",
  surfaceTertiary: "#F4F0EA",
  onSurfaceTertiary: "#4A4C48",
  surfaceInverse: "#2E312D",
  onSurfaceInverse: "#FFFFFF",
  brand: "#4A7C59",
  brandPrimary: "#4A7C59",
  onBrandPrimary: "#FFFFFF",
  brandSecondary: "#C16E53",
  onBrandSecondary: "#FFFFFF",
  brandTertiary: "#E9F0EC",
  onBrandTertiary: "#2E513A",
  success: "#3A6B4C",
  warning: "#D48C46",
  error: "#B34D4D",
  onError: "#FFFFFF",
  border: "#E8E3DB",
  borderStrong: "#D1C9BE",
  divider: "#F0ECE5",
  muted: "#8A8D86",
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, "2xl": 32, "3xl": 48 };
export const radius = { sm: 6, md: 12, lg: 20, xl: 28, pill: 999 };
export const font = { sm: 12, base: 14, lg: 16, xl: 20, "2xl": 24, "3xl": 30, "4xl": 36 };

// Immersive gradient palette (use with expo-linear-gradient)
export const gradients = {
  brand: ["#4A7C59", "#2E513A"] as const,
  header: ["#2E513A", "#4A7C59", "#5E9A6F"] as const,
  warm: ["#4A7C59", "#C16E53"] as const,
  sunset: ["#C16E53", "#D48C46"] as const,
  night: ["#2E312D", "#1A1C19"] as const,
  scrimBottom: ["transparent", "rgba(26,28,25,0.0)", "rgba(26,28,25,0.85)"] as const,
};

export const shadow = {
  card: {
    shadowColor: "#1A1C19",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  float: {
    shadowColor: "#1A1C19",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 6,
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
