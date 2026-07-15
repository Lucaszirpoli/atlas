# Guia de publicação — Google Play Store

Este guia assume que o código já está pronto (RevenueCat integrado no app, webhook do backend funcionando). O que falta é 100% configuração em contas externas (RevenueCat, Google Play Console) que só você pode fazer, porque exige login nas suas contas e, em alguns passos, cartão/CNPJ.

Ordem recomendada: **RevenueCat → Google Play Console → build de produção → envio**.

---

## 0. O que o código já espera (não mude estes valores sem atualizar o código também)

| O que | Valor |
|---|---|
| Entitlement no RevenueCat | `pro` |
| Offering no RevenueCat | `default` |
| Produto mensal | `pro_monthly` |
| Produto anual | `pro_annual` |
| Pacote Android (`applicationId`) | `com.lucaszirpoli.atlas` |
| Nome do app | Atlas |

---

## 1. RevenueCat — configurar o projeto

Você já tem conta. Falta:

1. **Criar o app dentro do projeto RevenueCat**, plataforma Android, com o package name `com.lucaszirpoli.atlas`.
2. **Pegar a chave pública do SDK Android**: Project Settings → API Keys → copie a chave "Public app-specific API key" do app Android. Cole em `mobile/eas.json`, nos profiles `development`, `preview` e `production`, no lugar de `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY`.
3. **Criar o entitlement**: Entitlements → New → identifier `pro`.
4. **Criar a offering**: Offerings → New → identifier `default`, marque como "current".
5. Os **produtos** (`pro_monthly`, `pro_annual`) só dá pra vincular no RevenueCat depois de existirem no Google Play Console (passo 2.5 abaixo) — o RevenueCat lê os produtos que já existem lá, não cria produto novo.
6. **Webhook**: Project Settings → Integrations → Webhooks → adicione a URL do seu backend em produção: `https://SEU-BACKEND/billing/revenuecat/webhook`. Gere um secret e cole em `REVENUECAT_WEBHOOK_SECRET` no `.env` do backend de produção (ver seção 5).
7. Copie também a **Secret API Key** (para chamadas servidor→RevenueCat, se você optar pelo endpoint de sync opcional mencionado no plano) e cole em `REVENUECAT_API_KEY` no `.env` do backend — hoje não é estritamente necessária porque o webhook já resolve a sincronização, mas é bom já deixar preenchida.

---

## 2. Google Play Console

### 2.1 Conta de desenvolvedor
Se ainda não tem: [play.google.com/console/signup](https://play.google.com/console/signup) — taxa única de US$25, precisa de conta Google + verificação de identidade (pode pedir documento). Leva de minutos a alguns dias se cair em revisão manual.

### 2.2 Criar o app
Play Console → "Criar app" → nome "Atlas" (ou o nome de marca definitivo, se decidir trocar antes de publicar — trocar depois de publicado é mais chato) → idioma padrão português (Brasil) → tipo "App" → gratuito (a monetização é via assinatura in-app, o app em si não é pago).

### 2.3 Ficha da loja (Store listing)
Obrigatório antes de publicar:
- Descrição curta (80 caracteres) e completa (4000 caracteres).
- Ícone 512x512, banner de destaque, pelo menos 2 screenshots de celular (screenshots reais do app — pode gerar rodando `/run` e printando as telas principais: Dashboard, Treino, Chat IA, Social).
- Categoria: Saúde e fitness.
- E-mail de contato e política de privacidade (URL pública — precisa hospedar um texto simples em algum lugar, ex: uma página estática; obrigatório porque o app coleta dados de saúde).

### 2.4 Content rating, Data safety, Público-alvo
Três questionários obrigatórios no menu "Política" do Console:
- **Classificação de conteúdo**: preencha o formulário (IARC) — app de fitness sem conteúdo sensível costuma sair "Livre"/"10+".
- **Segurança de dados (Data safety)**: declare que o app coleta dados de saúde (peso, sono, dieta), dados de conta (e-mail) — é obrigatório ser preciso aqui, a Google audita isso. Diga que os dados não são vendidos e são usados só para o funcionamento do app.
- **Público-alvo**: marque que não é voltado para crianças (evita regras extras da COPPA/design for families).

### 2.5 Criar os produtos de assinatura
Monetize → Produtos → Assinaturas → "Criar assinatura":
- Product ID: `pro_monthly` — preço mensal (sugestão da especificação: R$24,90–34,90).
- Product ID: `pro_annual` — preço anual (sugestão: R$199–249).

Depois de criados aqui, volte ao RevenueCat (passo 1.5) e nas Offerings vincule esses dois product IDs como packages dentro da offering `default` (um como "Monthly", outro como "Annual" — os helpers `offering.monthly`/`offering.annual` que o app usa dependem desse mapeamento de tipo).

### 2.6 Vincular Play Console ↔ RevenueCat (Service Account)
RevenueCat precisa de permissão para consultar/validar compras: Play Console → Configurações → Acesso à API → criar uma conta de serviço (Service Account) no Google Cloud vinculada, dar a ela permissão de "Financeiro" no Play Console, gerar a chave JSON, e subir esse JSON no RevenueCat em Project Settings → Integrations → Google Play Store. Sem isso o RevenueCat não consegue validar as compras reais (só funciona em modo sandbox local).

---

## 3. Build de produção

Antes de gerar o build, confirme em `mobile/eas.json` que o profile `production` tem:
- `EXPO_PUBLIC_API_URL` apontando para o backend **público** (não o IP local do Tailscale usado em dev/preview — esse IP só funciona na sua rede). Você precisa decidir onde o backend vai rodar publicamente (ex: VPS, Railway, Fly.io) antes deste passo — isso ainda não está definido no projeto.
- As duas chaves do RevenueCat preenchidas (passo 1.2).

Depois:
```
cd mobile
eas build --platform android --profile production
```
Isso gera um `.aab` (Android App Bundle), formato que a Play Store exige (não é o `.apk` usado no profile `preview`).

---

## 4. Enviar para a Play Store

Duas formas:
- **Manual**: baixe o `.aab` do link que o `eas build` mostrar no final, suba em Play Console → Produção (ou comece por "Teste interno"/"Teste fechado" para validar com poucos usuários antes de liberar geral — recomendado na primeira versão).
- **Automática**: `eas submit --platform android --profile production` (usa a config `"submit"` do `eas.json`, que hoje está vazia — na primeira vez o EAS pede pra gerar/associar uma service account key do Google, é um fluxo guiado).

Recomendo começar por **Teste interno** (até 100 testadores, sem revisão da Google, disponível em minutos) pra validar o fluxo de compra real (sandbox de teste do Google) antes de mandar pra revisão de produção, que pode levar de horas a poucos dias.

---

## 5. Backend em produção

O `.env` do backend em produção precisa ter, além do que já existe hoje:
```
REVENUECAT_API_KEY=<secret key do RevenueCat>
REVENUECAT_WEBHOOK_SECRET=<o mesmo secret configurado no passo 1.6>
BILLING_DEV_MODE=false
```
Com `BILLING_DEV_MODE=false`, a rota `/billing/dev-activate` deixa de funcionar (é só pra dev) — o Pro só ativa via compra real + webhook.

---

## Depois: App Store (iOS)

Você mencionou que quer publicar na App Store em seguida. O processo é parecido mas com diferenças importantes (Apple Developer Program é US$99/ano, revisão mais rigorosa, exige política de privacidade mais detalhada, App Store Connect em vez de Play Console, produtos de assinatura configurados lá e vinculados ao mesmo entitlement `pro` no RevenueCat). Quando chegar nessa etapa, é melhor eu escrever um guia dedicado — os passos de review da Apple mudam com frequência e vale conferir o estado mais atual nessa hora.
