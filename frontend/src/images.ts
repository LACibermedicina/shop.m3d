// Imagens da Tríplice Fronteira (Foz do Iguaçu / Ciudad del Este / Puerto Iguazú)
// URLs estáveis via Wikimedia Commons Special:FilePath (redireciona para o arquivo,
// com redimensionamento por ?width=).
const WM = "https://commons.wikimedia.org/wiki/Special:FilePath";

// Ponte da Amizade — símbolo que conecta Brasil e Paraguai
export const HERO_IMAGE = `${WM}/Ponte_da_Amizade_in_Foz_do_Iguacu.jpg?width=1000`;

// Coleção regional que ilustra a diversidade da Tríplice Fronteira
export const REGIONAL_IMAGES = [
  `${WM}/Marco_das_3_fronteiras.jpg?width=800`, // Marco das Três Fronteiras
  `${WM}/Triple_Frontier%2C_Ciudad_del_Este.jpg?width=900`, // vista de Ciudad del Este
  `${WM}/Cataratas_de_Igua%C3%A7u_-_ca%C3%ADdas_de_agua.jpg?width=900`, // Cataratas
  `${WM}/Omar_Ibn_Al-Khatab_Mosque%2C_Foz_do_Igua%C3%A7u_72.jpg?width=800`, // Mesquita (diversidade étnica)
  `${WM}/Ponte_da_Amizade_in_Foz_do_Iguacu.jpg?width=900`, // Ponte da Amizade
];

export const STORE_PLACEHOLDER = REGIONAL_IMAGES[0];
export const PRODUCT_PLACEHOLDER = `${WM}/Triple_Frontier%2C_Ciudad_del_Este.jpg?width=600`;

// Escolhe uma imagem regional de forma determinística a partir de um id,
// para que lojas diferentes exibam contextos diferentes da região.
export function regionalImageFor(id?: string): string {
  if (!id) return REGIONAL_IMAGES[0];
  let sum = 0;
  for (let i = 0; i < id.length; i++) sum += id.charCodeAt(i);
  return REGIONAL_IMAGES[sum % REGIONAL_IMAGES.length];
}
