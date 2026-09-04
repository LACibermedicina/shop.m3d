// Imagens imersivas e engajadoras — comércio, tecnologia e saúde preventiva.
// Fotos hospedadas em CDN (Unsplash) usadas como planos de fundo decorativos
// sobre os quais aplicamos gradientes translúcidos para dar profundidade.

// Comércio / varejo moderno (hero principal)
const IMG_COMMERCE =
  "https://images.unsplash.com/photo-1481437156560-3205f6a55735?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzNDR8MHwxfHNlYXJjaHwyfHxzaG9wcGluZ3xlbnwwfHx8fDE3ODg1NDY4ODB8MA&ixlib=rb-4.1.0&q=85&w=1200";

// Tecnologia — rede digital / conexão
const IMG_TECH_NETWORK =
  "https://images.unsplash.com/photo-1644088379091-d574269d422f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NjV8MHwxfHNlYXJjaHwzfHx0ZWNobm9sb2d5fGVufDB8fHx8MTc4ODU0Njg4MHww&ixlib=rb-4.1.0&q=85&w=1200";

// Tecnologia — notebook / gadgets
const IMG_TECH_LAPTOP =
  "https://images.unsplash.com/photo-1531297484001-80022131f5a1?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NjV8MHwxfHNlYXJjaHw0fHx0ZWNobm9sb2d5fGVufDB8fHx8MTc4ODU0Njg4MHww&ixlib=rb-4.1.0&q=85&w=1200";

// Saúde preventiva — profissional de saúde
const IMG_HEALTH_PRO =
  "https://images.unsplash.com/photo-1576091160550-2173dba999ef?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1ODh8MHwxfHNlYXJjaHwxfHxoZWFsdGhjYXJlfGVufDB8fHx8MTc4ODU0Njg4MHww&ixlib=rb-4.1.0&q=85&w=1200";

// Saúde — estetoscópio (minimalista)
const IMG_HEALTH_STETH =
  "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1ODh8MHwxfHNlYXJjaHwzfHxoZWFsdGhjYXJlfGVufDB8fHx8MTc4ODU0Njg4MHww&ixlib=rb-4.1.0&q=85&w=1200";

// Rede global (mundo conectado à noite)
const IMG_GLOBAL_NETWORK =
  "https://images.unsplash.com/photo-1451187580459-43490279c0fa?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NjV8MHwxfHNlYXJjaHwyfHx0ZWNobm9sb2d5fGVufDB8fHx8MTc4ODU0Njg4MHww&ixlib=rb-4.1.0&q=85&w=1200";

// Hero principal (tela de login / vitrine)
export const HERO_IMAGE = IMG_COMMERCE;

// Heros temáticos por área de interesse
export const HERO_TECH = IMG_TECH_NETWORK;
export const HERO_HEALTH = IMG_HEALTH_PRO;
export const HERO_GLOBAL = IMG_GLOBAL_NETWORK;

// Coleção usada para planos de fundo/placeholder de lojas e produtos
export const ENGAGING_IMAGES = [
  IMG_COMMERCE,
  IMG_TECH_NETWORK,
  IMG_TECH_LAPTOP,
  IMG_HEALTH_PRO,
  IMG_HEALTH_STETH,
  IMG_GLOBAL_NETWORK,
];

// Compat: nome antigo usado em outras telas
export const REGIONAL_IMAGES = ENGAGING_IMAGES;

export const STORE_PLACEHOLDER = IMG_TECH_LAPTOP;
export const PRODUCT_PLACEHOLDER = IMG_TECH_NETWORK;

// Escolhe uma imagem de forma determinística a partir de um id,
// para que lojas/itens diferentes exibam contextos visuais diferentes.
export function regionalImageFor(id?: string): string {
  if (!id) return ENGAGING_IMAGES[0];
  let sum = 0;
  for (let i = 0; i < id.length; i++) sum += id.charCodeAt(i);
  return ENGAGING_IMAGES[sum % ENGAGING_IMAGES.length];
}
