# WhatsApp — entrega híbrida de mensagens (aprovado: opção C)

## Decisão tomada
Abordagem **híbrida (C)** para garantir que lojista e cliente sempre recebam o aviso do pedido:
1. **Dentro da janela de 24h** → envia mensagem de texto automática (como hoje).
2. **Fora da janela de 24h** → envia automaticamente um **template de utilidade aprovado**.
3. **Se o template falhar / não existir** → o app gera um **link wa.me** pronto para envio manual,
   para nada ficar sem comunicação.
4. **Registro de status** de cada envio (enviado por API / via template / por link / simulado),
   visível para o lojista.

## Insumos já fornecidos (prontos para uso)
- Credenciais da Cloud API (token, phone number id, app secret) — já configuradas.
- **PIN de verificação em duas etapas: fornecido** → o número será registrado na Cloud API
  (resolve o erro 133010 que hoje impede qualquer envio automático).

## Como os templates serão criados
- Serão criados **via API** dois modelos de categoria **Utilidade**, idioma **pt_BR**:
  - `pedido_confirmado` — confirmação de pedido (nome do cliente, itens/total).
  - `pedido_status` — atualização de status do pedido.
- O identificador da conta (WABA ID) necessário para criar os templates será obtido
  automaticamente a partir do token; se não for possível, será solicitado a você.
- **A aprovação dos modelos é feita pela Meta** (normalmente minutos a algumas horas). Enquanto
  não aprovados, o sistema usa o fallback por link wa.me fora da janela de 24h.

## Consentimento
- Os avisos são **apenas transacionais** (relacionados a pedidos). Sem disparos de marketing.

## Fora do escopo
- Campanhas/marketing em massa por WhatsApp.
- Qualquer método não-oficial (automação do WhatsApp Web) — descartado (viola termos, risco de ban).

## Resultado esperado
Notificações de pedido chegam de forma confiável: automáticas quando as regras da Meta permitem
(janela aberta ou template aprovado) e, como rede de segurança, sempre com um link de WhatsApp
pronto para envio manual. O lojista consegue ver o status de cada notificação.
