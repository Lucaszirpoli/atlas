# App Fitness — Contexto do Projeto

## O que é este projeto

App mobile completo de fitness/nutrição para o mercado brasileiro (nome de marca ainda não definido — pasta/projeto usa o codinome `appfit`). Combina em um único produto: registro de dieta, montagem e execução de treino, sono, água e camada social — com um assistente de IA exclusivo do plano Pro para chat, reconhecimento de refeição por foto/voz e montagem automática de treino baseada em ciência.

**A especificação completa do produto está no arquivo `app-fitness-especificacao-completa.md`, nesta mesma pasta. Leia esse arquivo por inteiro antes de escrever qualquer código — ele contém a análise de mercado, todas as regras de negócio, o modelo de dados de treino (rotina vs. sessão), o modelo Free/Pro, e o design system completo (cores, tipografia, tom de voz). Esse documento é a fonte da verdade do produto.**

## Stack técnica

- **Frontend mobile:** React Native (Expo)
- **Backend:** FastAPI (Python)
- **Banco de dados:** PostgreSQL (dados relacionais) + Redis (cache/sessão)
- **IA:** API da Anthropic (Claude), com function calling — usada **apenas nas funcionalidades exclusivas do plano Pro**
- **Base de alimentos:** TACO (Tabela Brasileira de Composição de Alimentos) como seed local + Open Food Facts (`openfoodfacts.org` / `br.openfoodfacts.org`) como API gratuita para busca de produtos com marca/código de barras — sem chave paga necessária
- **Armazenamento de mídia:** S3-compatible (Cloudflare R2 recomendado)
- **Notificações push:** Firebase Cloud Messaging
- **LGPD:** dados de saúde são sensíveis — sempre exigir consentimento explícito e nunca tratar como opcional

## Regras de negócio inegociáveis (não simplificar sem perguntar)

1. **IA é exclusiva do plano Pro, sem exceção e sem cota gratuita.** O plano Free precisa ser um produto manual **completo e robusto**, não capenga — todo o manual de treino, dieta, sono e social funciona sem IA.
2. **Limite de rotinas de treino ativas: 3 no Free, 7 no Pro** (rotinas arquivadas não contam pro limite).
3. **Rotina ≠ Sessão de treino.** Rotina é o molde salvo (reutilizável). Sessão é a execução real numa data, com os números que a pessoa realmente pegou naquele dia. Nunca modelar isso como uma coisa só.
4. **Toda tabela de histórico é append-only** (refeições, sessões de treino, peso, sono, água). Nunca fazer UPDATE destrutivo que apague o valor anterior — é a base de todos os gráficos de evolução.
5. **Tela de execução de treino:** peso e reps sempre visíveis e pré-preenchidos com o valor da última vez que o exercício foi feito. Tipo de série (drop-set, rest-pause etc.) e RPE/RIR ficam escondidos atrás de um "mais opções" por série — não expor por padrão.
6. **A IA de treino nunca usa bro-split (um músculo por dia) como padrão** — frequência mínima de 2x/semana por grupo muscular, a menos que o usuário peça explicitamente esse estilo (e mesmo assim a IA deve avisar de forma transparente, sem ser paternalista).
7. **Tom de voz:** nunca usar linguagem de culpa/vergonha ("falhou", "pecadinho") ao registrar dados de dieta. Ver seção 3.7 da especificação sobre saúde mental.
8. **Nenhuma tela de IA dá diagnóstico médico.** Sempre disclaimers apropriados quando relevante.

## Ordem de construção (Parte 5 da especificação)

Seguir as fases na ordem, mas o objetivo final é o app 100% completo — as fases são só sequência de implementação, não escopo de lançamento parcial:

Fase 0 (fundação: auth, perfil, onboarding) → Fase 1 (nutrição manual) → Fase 2 (treino manual) → Fase 3 (IA nutrição) → Fase 4 (IA treino) → Fase 5 (social) → Fase 6 (sono + cruzamento de dados) → Fase 7 (refinamento: deload automático, detecção de platô, wearables).

## Como trabalhar neste projeto

- Rodar `git init` já está feito antes de qualquer alteração de código — sempre commitar em pontos estáveis.
- Antes de implementar cada fase, resumir o plano e confirmar comigo antes de começar a escrever código.
- Design system (cores em hex, fontes, tom de voz) está na Parte 7 da especificação — seguir à risca, não inventar paleta nova.
- Qualquer dúvida de regra de negócio que não estiver clara na especificação: perguntar antes de assumir.
