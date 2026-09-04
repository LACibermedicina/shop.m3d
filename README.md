# SHOP.M3D.pro (versão: catalogo)

Plataforma de **lojas virtuais organizadas por áreas de interesse e grupos de usuários**.
Este repositório contém a versão **catalogo** do projeto SHOP, parte do ecossistema **M3D.pro**.

## 🎯 Visão Geral

O **shop.m3d.pro** é um app mobile e web que funciona como uma **rede de indicações baseada em
grupos de interesse**, conectando clientes e lojistas de forma vinculativa. O objetivo é facilitar
conexões de confiança entre consumidores e vendedores por meio de comunidades temáticas,
protegendo ambos do distanciamento característico dos modelos tradicionais de consumo online.

### Por que shop.m3d.pro?
- 🤝 **Relacionamento direto**: conexão próxima entre clientes e vendedores, baseada em confiança
- 🎯 **Grupos de interesse**: organização customizada que facilita o encontro de produtos relevantes
- 🛡️ **Proteção da privacidade**: reduz o impacto da publicidade predatória de redes e buscadores
- 💚 **Saúde mental**: ambiente de consumo consciente, com menos ruído e mais relevância
- 🔗 **Indicações vinculativas**: recomendações orgânicas baseadas em comunidades

## 📋 Funcionalidades

### Para Clientes
- Acesso a catálogos de lojistas **por convite** (link/QR ou e-mail)
- **Catálogo pessoal de compras** multi-loja com filtros (por loja/categoria) e **relatório em PDF**
- **Carrinho** que separa por lojista: cada vendedor recebe **1 PDF só com seus itens** + link do pedido
- Múltiplos idiomas **PT / EN / ES** com tradução contextual por IA
- Comunicação direta via WhatsApp (link click-to-chat)

### Para Lojistas
- Vitrine/catálogo próprio e gestão de produtos
- **Pedidos por cliente** e edição real do pedido (quantidade, preço, disponibilidade, status)
- Convite de clientes por e-mail e por link/QR
- Notificação do cliente ao ajustar o pedido

### Hierarquia de acesso
- **master**: controle total (clientes, lojistas e administradores)
- **admin**: gerencia apenas os lojistas vinculados a ele
- **lojista**: apenas sua loja
- **cliente**: acesso somente por convite

## 🚀 Stack
- **Frontend**: Expo + React Native (Expo Router / file-based routing)
- **Backend**: FastAPI + MongoDB
- **IA**: tradução contextual (Emergent LLM / Gemini)

## 📞 Contato
📧 shop@m3d.pro

---
Versão: **catalogo** · Ecossistema **M3D.pro**
