# PRD — Feira Online (Marketplace multi-lojista)

## Problem statement (original)
App de feira online multi-lojista. Login Google (3 roles: admin, lojista, cliente). Admin: CRUD de barracas + métricas. Lojista: recebe produtos via WhatsApp processados por IA + CRUD de produtos + gerencia pedidos. Cliente: navega barracas, sacola, finaliza pedido gerando PDF e enviando via WhatsApp. Integração WhatsApp, catálogo com ordenação, PDF profissional, CRUD completo com soft delete.

Solicitado originalmente como web (Next.js/Express/Prisma/Postgres); **adaptado para app mobile Expo + FastAPI + MongoDB** por escolha do usuário.

## User choices
- Plataforma: App mobile Expo (iOS/Android)
- Auth: Google gerenciado pela Emergent
- WhatsApp: fluxo via wa.me (sem Cloud API por enquanto)
- IA: Gemini (gemini-3-flash-preview) para extrair nome/preço/descrição
- Design: definido pelo agente (tema feira/mercado, verde/terracota)

## Architecture
- Frontend: Expo Router (React Native), 3 grupos de rota por role: (customer), (vendor), (admin) + telas compartilhadas store/[id] e order/[id]. Contexts: Auth, Cart, Toast.
- Backend: FastAPI (/api), MongoDB (motor). Sessões via Bearer token (user_sessions, TTL 7 dias).
- Integrações: Emergent Google Auth, Emergent Object Storage (imagens), Emergent LLM key (Gemini vision), reportlab (PDF).

## Personas
- Admin: gerencia barracas, usuários/roles, vê métricas globais.
- Lojista: gerencia catálogo (IA + manual), gerencia pedidos e status.
- Cliente: navega, monta sacola, finaliza e acompanha pedidos.

## Implemented (2026-08-13)
- Auth Google (Emergent) + dev-login para testes (gated por DEV_LOGIN_SECRET); roles + admin por ADMIN_EMAILS.
- Admin: CRUD barracas (soft delete), métricas globais, gestão de usuários + atribuição lojista→barraca.
- Lojista: import por IA (mensagem + foto), CRUD produtos, lista de pedidos com métricas, edição de itens e status.
- Cliente: marketplace grid, catálogo por barraca com ordenação (recentes/nome/preço), sacola agrupada por barraca, checkout multi-barraca, envio via wa.me com link do PDF.
- Pedidos: criação, visualização pública por token, edição de itens (recalcula total), status, PDF profissional (reportlab).
- Upload de imagens via Object Storage; exibição pública com expo-image (lazy).
- Testes: backend 31/31 pass; fluxos frontend admin e cliente verificados.

## Backlog
- P1: Integração WhatsApp Cloud API/Green API (webhook receber produtos + envio automático de pedidos com PDF anexado).
- P1: Busca/filtro de produtos e barracas; categorias.
- P2: Avaliações de barracas; favoritos; histórico de faturamento por período (gráficos).
- P2: Notificações de novos pedidos para lojista.
- P2: Desabilitar dev-login em produção (EXPO_PUBLIC_ENABLE_DEV_LOGIN=false).

## Next tasks
- Conectar WhatsApp Cloud API quando o usuário fornecer credenciais.
- Adicionar busca global no marketplace.
