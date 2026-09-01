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
- Admin: CRUD barracas (soft delete) + toggle "Destaque na home", métricas globais, gestão de usuários + atribuição lojista→barraca.
- Lojista: import por IA (mensagem + foto), CRUD produtos, lista de pedidos com métricas, edição de itens e status.
- Cliente: marketplace grid, catálogo por barraca com ordenação, sacola agrupada, checkout multi-barraca, envio via wa.me com link do PDF.
- Pedidos: criação, visualização pública por token, edição de itens (recalcula total), status, PDF profissional (reportlab).
- Upload de imagens via Object Storage; exibição pública com expo-image (lazy).

### Iteração 2 (2026-08-13) — features adicionais
- **Vitrine em Destaque**: home com carrossel "Destaques da feira" (barracas featured) + "Novidades" (produtos recentes). Endpoint GET /api/home.
- **Busca na Feira**: barra de busca na home filtrando barracas e produtos (debounce). Endpoint GET /api/search?q=.
- **Alertas de Pedido**: contexto de polling (15s) no grupo lojista, banner "novo pedido chegou!" + badge na aba Pedidos, marca como visto ao abrir.
- **WhatsApp Oficial (Cloud API)**: backend completo (webhook verify/receive → cria produto via IA + download de mídia p/ Object Storage; POST /api/orders/send-whatsapp envia texto + PDF). **DORMENTE** — usuário optou por manter wa.me por enquanto. Ativar setando WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID, META_APP_SECRET, WA_VERIFY_TOKEN, PUBLIC_BASE_URL no backend/.env.

### Iteração 3 (2026-08-15) — features + rebrand
- **Rebrand "feira" → "Lojas da Fronteira"**: textos, marca e terminologia (barraca→loja) atualizados em todo o app, backend e PDF.
- **Imagens regionais da Tríplice Fronteira**: Ponte da Amizade, Marco das 3 Fronteiras, Cataratas, Mesquita Omar (diversidade étnica) via Wikimedia Commons (Special:FilePath). `src/images.ts` com `regionalImageFor(id)` para variar contextos por loja.
- **Categorias de Produtos**: campo `category` (Frutas/Verduras/Legumes/Laticínios/Padaria/Bebidas/Carnes/Outros), chips no cadastro (lojista) + IA extrai categoria; filtro por categoria no catálogo (GET products?category=).
- **Favoritar Lojas**: coleção favorites; POST/DELETE /api/favorites/{id}, GET /my/favorites e /my/favorite-ids. Coração nos cards e no hero da loja + faixa "Suas lojas favoritas" na home.
- **Avaliações de Loja**: coleção reviews (1 por usuário/loja, upsert); POST/GET /api/stores/{id}/reviews; média (avg_rating/review_count) exibida em cards, home, busca e hero; modal de avaliação com estrelas + comentário.
- **Relatório de Vendas (lojista)**: nova aba "Vendas" com cards (total, pedidos, ticket médio) e gráficos de barras (faturamento por dia — 7 dias; por semana — 4 semanas). GET /api/vendor/report.

### Iteração 4 (2026-08-15) — presença + cupons
- **Loja aberta/fechada (presença em tempo real)**: campos is_open/last_seen na loja; PUT /api/vendor/store/open (toggle) + POST /api/vendor/heartbeat (a cada 25s enquanto app ativo, via VendorOrdersProvider). `online` = is_open && heartbeat < 60s. Selo verde "Aberta"/cinza "Fechada" nos cards da home, favoritos, destaques e no hero da loja. Toggle no topo da tela Pedidos do lojista.
- **Cupons de desconto**: coleção coupons (código único por loja, percent/fixed). POST /api/coupons, GET /api/vendor/coupons, DELETE /api/coupons/{id}, POST /api/coupons/apply. Lojista cria/gerencia via modal na tela Pedidos. Cliente aplica cupom por loja no carrinho (desconto + total recalculados). create_order aplica cupom (subtotal/discount/coupon_code/total); PDF e tela de pedido mostram desconto.

### Iteração 5 (2026-08-15) — taxonomia de varejo + categoria editável pelo admin
- **Categorias de lojas/varejo** (Tríplice Fronteira/Ciudad del Este) substituem as de feira de frutas: Eletrônicos, Informática, Celulares, Perfumaria, Moda, Calçados, Casa & Decoração, Brinquedos, Bebidas, Alimentos, Acessórios, Outros.
- **IA** classifica automaticamente cada produto nessas categorias (prompt atualizado).
- **Edição da categoria**: lojista altera no cadastro do produto (chips) e **admin** altera pelo novo gerenciador de produtos (ícone de etiqueta no card da loja → modal lista produtos com chips de categoria + excluir). Backend permite update de produto por lojista dono e por admin.

### Iteração 6 (deploy + notificações)
- **Correções de deploy**: httpx no requirements; dev-login server-gated (ALLOW_DEV_LOGIN) e segredo removido do bundle; exclusão de conta (DELETE /api/auth/me).
- **Login em 2 modos**: Cliente vs Lojista/Administrador (segmentado); acesso definido pelo role.
- **Notificações de pedido (modo teste)**: criar pedido e cada mudança de status notifica Lojista + Administrador (WhatsApp SIMULADO) e Cliente (WhatsApp se informado, senão e-mail real via Resend). Novos campos: store.admin_whatsapp, order.customer_whatsapp; ROOT_WHATSAPP=11920946954 fallback. Painel "Avisos enviados" no pedido; confirmação no app após a compra.

### Iteração 7 (2026-08-31) — CRUD por WhatsApp (número root) via IA
- **Webhook interpreta comandos**: `_process_inbound` agora identifica o remetente (lojista pelo whatsapp da loja) e usa IA (`interpret_command`, gemini-3-flash-preview) para classificar a intenção: **criar / atualizar / desativar / catálogo / ajuda / desconhecido**.
  - criar: extrai nome/preço/descrição/categoria (texto ou imagem via `extract_product`) → insere produto (source=whatsapp) → responde confirmação.
  - atualizar: acha produto por nome (match exato/substring) → aplica preço/nome/descrição/categoria → responde.
  - desativar: soft-delete do produto → responde.
  - catálogo: envia PDF (documento) via `GET /api/stores/{id}/catalog.pdf` + mensagem.
  - ajuda/desconhecido: envia HELP_TEXT com exemplos de comandos.
- **Respostas ao remetente**: helpers `wa_reply` (texto) e `wa_send_document` (PDF). Falham em silêncio se WA não configurado/token inválido (fluxo local continua funcionando).
- **PDF de catálogo sob demanda**: `build_catalog_pdf(store, products)` + endpoint público `GET /api/stores/{id}/catalog.pdf`.
- **Auditoria**: coleção `wa_inbound` registra remetente/loja/texto/intenção/resultado. Endpoint `GET /api/admin/wa-inbound`. Nova seção "Comandos por WhatsApp" na tela Admin → Métricas.
- **Credenciais Meta**: preenchidas no backend/.env (WA_ACCESS_TOKEN/WA_PHONE_NUMBER_ID/META_APP_SECRET/WA_VERIFY_TOKEN/PUBLIC_BASE_URL). Token fornecido estava EXPIRADO e Phone Number ID incorreto (usuário enviou o telefone, não o ID). Webhook verify OK; envio real pendente de credenciais válidas (token de Usuário do Sistema + Phone Number ID correto do MESMO app do App Secret).
- Testado via `tests/test_wa_crud.py` (assina HMAC e simula webhook): criar/atualizar/desativar/catálogo/ajuda + PDF gerando 200.

### Iteração 8 (2026-08-31) — comandos naturais do lojista + carrinho de cliente por WhatsApp
- **Roteamento por remetente** em `_process_inbound`: loja (por whatsapp) → `_handle_vendor`; número ROOT_WHATSAPP → superadmin (aviso); senão → `_handle_customer` (cliente).
- **Lojista (linguagem natural, `interpret_command` expandido)**: além de criar/atualizar/desativar/catálogo, agora **abrir_loja**, **fechar_loja** (is_open), **ver_pedidos** (últimos 10 da loja), **criar_cupom** (extrai código/valor/tipo, upsert em coupons).
- **Cliente (`interpret_customer` + coleção `wa_carts`)**:
  - **buscar**: texto OU foto (foto → `extract_product` vira query) → `search_products_global` (tokens em nome/categoria/descrição, top 8) → lista numerada + guarda candidates.
  - **adicionar N [qtd]** / **remover N** / **ver_carrinho** (PDF via `build_cart_pdf` agrupado por loja) / **cancelar**.
  - **finalizar** → estado `confirm_create` → cliente responde SIM → cria **1 pedido por loja** (source=whatsapp, general_order_id=cart, sent_to_vendor=False) → estado `confirm_send` → SIM → `notify_order(created)` por pedido, sent_to_vendor=True.
  - Cada lojista recebe/vê SÓ os itens da própria loja; `GET /vendor/orders` (lojista) esconde pedidos WhatsApp com sent_to_vendor=False. O PDF geral do cliente mostra tudo (multi-loja).
- **Endpoints novos**: `GET /api/wa/cart/{id}/pdf?token=`, `GET /api/stores/{id}/catalog.pdf`, `GET /api/admin/wa-inbound`.
- **Admin → Métricas**: seção "Comandos por WhatsApp" com ícones por tipo (inclui novos intents).
- Testado via `tests/test_wa_full.py`: comandos de lojista + carrinho multi-loja (2 lojas) criando e enviando pedidos separados corretamente.

## Backlog
- FASE GRANDE: CRUD por WhatsApp via número root — CONCLUÍDA no backend (ver Iteração 7). Falta apenas credenciais Meta válidas p/ envio/recebimento real.
- P1: Ativar WhatsApp Cloud API (envios reais substituem o modo simulado automaticamente).
- P2: Filtro de categoria também na home; ordenação por avaliação; validade/limite de uso nos cupons.
- P2: Desabilitar dev-login em produção (EXPO_PUBLIC_ENABLE_DEV_LOGIN=false).
- P2: Filtro de categoria também na home; ordenação por avaliação; favoritos offline.
- P2: Desabilitar dev-login em produção (EXPO_PUBLIC_ENABLE_DEV_LOGIN=false).

## Next tasks
- Conectar WhatsApp Cloud API quando o usuário fornecer credenciais.
- Adicionar busca global no marketplace.
