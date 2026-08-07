# App Fitness — Contexto do Projeto

## O que é este projeto

App mobile completo de fitness/nutrição para o mercado brasileiro. **A marca é ATLAS** (a pasta/projeto ainda usa o codinome antigo `appfit`). Combina em um único produto: registro de dieta, montagem e execução de treino, sono, água e camada social — com um assistente de IA exclusivo do plano Pro para chat e coaching, e um motor determinístico (Python puro, sem IA) que monta treino e dieta.

*Correções do que a especificação original prometia e hoje não é mais verdade:* **o reconhecimento de refeição por FOTO foi REMOVIDO do produto** (2026-07-24, decisão do usuário — não existe mais `vision.py` nem tela de foto; o código-fonte foi apagado). O registro por linguagem natural continua existindo em `services/meal_parser.py` (a pessoa digita/dita "dois ovos e um pão" pelo teclado) — mas **não há biblioteca de voz**, o "por voz" é o ditado do próprio teclado do celular. **O leitor de código de barras ficou.**

**A especificação completa do produto está no arquivo `app-fitness-especificacao-completa.md`, nesta mesma pasta. Leia esse arquivo por inteiro antes de escrever qualquer código — ele contém a análise de mercado, todas as regras de negócio, o modelo de dados de treino (rotina vs. sessão), o modelo Free/Pro, e o design system completo (cores, tipografia, tom de voz). Esse documento é a fonte da verdade do produto.**

## Stack técnica

**Em uso de verdade hoje:**

- **Frontend mobile:** React Native (Expo) — publicado nas duas lojas
- **Backend:** FastAPI (Python), hospedado no Railway (deploy automático a cada push na `main`)
- **Banco de dados:** PostgreSQL em produção; **SQLite em dev local** (sem Docker, sem Alembic — o schema nasce de `Base.metadata.create_all` via `app.scripts.init_db`)
- **IA:** API da Anthropic (Claude), com function calling — **apenas nas funcionalidades exclusivas do plano Pro**. O motor que monta treino/dieta é Python determinístico; a IA só explica, conversa e enriquece.
- **Base de alimentos:** TACO (Tabela Brasileira de Composição de Alimentos) como seed local + Open Food Facts como API gratuita para produtos com marca/código de barras — sem chave paga
- **Assinatura Pro:** RevenueCat (Google Play + App Store)
- **LGPD:** dados de saúde são sensíveis — sempre exigir consentimento explícito e nunca tratar como opcional

**Estava na especificação original, mas NUNCA foi implementado** (não assumir que existe):

- ~~Redis~~ — só existe como variável de configuração, nenhum código usa
- ~~Armazenamento de mídia S3/Cloudflare R2~~ — as fotos ficam **no próprio celular** (`mobile/src/utils/photoStorage.ts`); trocar de aparelho perde as fotos
- ~~Notificações push (Firebase Cloud Messaging)~~ — não existe FCM no projeto, nem `google-services.json`

## Regras de negócio inegociáveis (não simplificar sem perguntar)

1. **IA é exclusiva do plano Pro, sem exceção e sem cota gratuita.** O plano Free precisa ser um produto manual **completo e robusto**, não capenga — todo o manual de treino, dieta, sono e social funciona sem IA.
2. **Rotinas de treino ativas: ILIMITADAS nos dois planos** (Free e Pro). *Esta regra foi ALTERADA por decisão explícita do usuário — o texto original era "3 no Free, 7 no Pro". A estratégia mudou: o produto manual é inteiro de graça e a monetização é SÓ pela IA/Pro (regra 1).* O código já reflete isso: `routine_service.ACTIVE_ROUTINE_LIMITS` = `{FREE: None, PRO: None}`. Se algum dia voltar a ter limite, rotinas arquivadas não contam.
3. **Rotina ≠ Sessão de treino.** Rotina é o molde salvo (reutilizável). Sessão é a execução real numa data, com os números que a pessoa realmente pegou naquele dia. Nunca modelar isso como uma coisa só.
4. **Toda tabela de histórico é append-only** (refeições, sessões de treino, peso, sono, água). Nunca fazer UPDATE destrutivo que apague o valor anterior — é a base de todos os gráficos de evolução.
5. **Tela de execução de treino:** peso e reps sempre visíveis e pré-preenchidos com o valor da última vez que o exercício foi feito. *Esta regra foi PARCIALMENTE ALTERADA por decisão explícita do usuário:* **RIR (chips 0-4) e o badge de tipo de série** (normal / A=aquecimento / P=preparatória / F=falha, alternado tocando no número da série) são **SEMPRE VISÍVEIS** — o texto original mandava esconder os dois. Continuam atrás do "mais opções": **RPE** e as demais técnicas avançadas (drop-set, superset, myo-reps, rest-pause etc.). Regra prática: RIR 0 **é** falha, não são dois dados diferentes.
6. **A IA de treino nunca usa bro-split (um músculo por dia) como padrão** — frequência mínima de 2x/semana por grupo muscular, a menos que o usuário peça explicitamente esse estilo (e mesmo assim a IA deve avisar de forma transparente, sem ser paternalista).
7. **Tom de voz:** nunca usar linguagem de culpa/vergonha ("falhou", "pecadinho") ao registrar dados de dieta. Ver seção 3.7 da especificação sobre saúde mental.
8. **Nenhuma tela de IA dá diagnóstico médico.** Sempre disclaimers apropriados quando relevante.

## Ordem de construção (Parte 5 da especificação)

Seguir as fases na ordem, mas o objetivo final é o app 100% completo — as fases são só sequência de implementação, não escopo de lançamento parcial:

Fase 0 (fundação: auth, perfil, onboarding) → Fase 1 (nutrição manual) → Fase 2 (treino manual) → Fase 3 (IA nutrição) → Fase 4 (IA treino) → Fase 5 (social) → Fase 6 (sono + cruzamento de dados) → Fase 7 (refinamento: deload automático, detecção de platô, wearables).

## Status da publicação nas lojas

**O app é publicado nas DUAS lojas: Google Play (Android) e App Store (iOS).** Desde 2026-08-07 o iOS deixou de ser "futuro" e virou plataforma-alvo de verdade (conta Apple Developer Individual aprovada nessa data).

A consequência que vale pra sempre: **é um código só (`mobile/`, Expo/React Native), mas builds e submissões são separados por plataforma** (`eas build --platform android` / `--platform ios`). Não existe mais "só Android" — toda mudança em `mobile/` precisa chegar nas duas lojas pra valer pra todo mundo. Ver a regra dura sobre isso no fim deste arquivo.

*O estado do dia a dia (qual build está em qual loja, o que falta pra submeter, credenciais de teste) NÃO mora aqui — mora na memória do projeto, arquivo `project_ios_launch.md`. Este arquivo guarda regra, não status volátil.*

## Como trabalhar neste projeto

- Rodar `git init` já está feito antes de qualquer alteração de código — sempre commitar em pontos estáveis.
- Antes de implementar cada fase, resumir o plano e confirmar comigo antes de começar a escrever código.
- Design system (cores em hex, fontes, tom de voz) está na Parte 7 da especificação — seguir à risca, não inventar paleta nova.
- Qualquer dúvida de regra de negócio que não estiver clara na especificação: perguntar antes de assumir.

## Manter este arquivo e a memória sempre em dia (obrigatório)

**Toda vez que algo mudar de verdade, atualizar o registro na mesma sessão — não deixar pra depois, não esperar ser pedido.** Regra prática do que vai onde:

- **`CLAUDE.md` (este arquivo) = regra durável.** Regra de negócio, decisão de arquitetura, como trabalhar. Se uma regra daqui for alterada por decisão minha (do usuário), **editar o texto da regra na hora**, marcando que foi alterada e por quê — nunca deixar a regra antiga escrita "por educação". Uma regra errada aqui é pior que nenhuma: a próxima sessão vai obedecer ela e "consertar" o código pro lado errado. Isso já aconteceu (regras 2 e 5 ficaram semanas contradizendo o código).
- **Memória do projeto (`MEMORY.md` + arquivos) = estado volátil e contexto.** Onde cada coisa está, o que falta, credencial de teste, armadilha descoberta, motivo de uma decisão. Status de loja/build **nunca** entra no CLAUDE.md — entra na memória.
- **Antes de afirmar que algo "é assim"**, conferir no código quando for barato conferir. Nota antiga é observação datada, não verdade atual.
- **Ao terminar um bloco de trabalho**, checar se alguma dessas coisas mudou e ficou sem registro: regra de negócio alterada, build novo gerado/enviado, credencial/serviço externo configurado, armadilha nova descoberta, decisão de produto tomada.

## Aviso obrigatório de status da alteração

Toda vez que eu pedir uma alteração (correção de bug, feature, etc.), termine a resposta com um aviso em MAIÚSCULO dizendo exatamente o estado da entrega. Isso existe porque backend (Railway) e app mobile são publicados separadamente do código-fonte, e "arrumei" no código não quer dizer "já está valendo pra mim no celular" — foi exatamente essa confusão que gerou o bug do sono continuar aparecendo depois de "corrigido" (2026-08-07).

O aviso precisa deixar claro qual desses estados se aplica:

- **SÓ NO CÓDIGO, NADA COMMITADO** — a alteração existe só nos arquivos locais, ninguém rodando o app vê ela ainda.
- **COMMITADO MAS NÃO ENVIADO** — está no git local, mas não foi feito push pro GitHub.
- **NO AR NO BACKEND (RAILWAY)** — o push foi feito e o Railway já deve ter reimplantado (backend em Python/FastAPI; a maioria das correções de bug de dado/regra de negócio é só isso, e já resolve pra quem já tem o app instalado).
- **PRECISA DE NOVO BUILD DO APP (.aab/.ipa)** — a alteração mexeu em código do app mobile (`mobile/`) que só chega no celular com uma nova versão gerada e publicada nas lojas (Google Play/App Store) — enviar o backend sozinho NÃO resolve esse tipo de mudança pra quem já tem o app instalado.

Quando for uma mudança de mobile, avisar também se é algo que dá pra esperar ir num lote de atualização futuro ou se é urgente o suficiente pra justificar gerar o build agora.

**Regra adicional, sem exceção — as duas lojas são um pacote só:** desde que o iOS entrou em cena (2026-08-07), **nunca gerar/enviar build de UMA plataforma sem, na mesma resposta, dizer explicitamente o status da OUTRA.** Se rodei `eas build --platform ios`, a resposta tem que dizer na hora se o Android também precisa de build novo (e por quê) — nunca esperar ser perguntado, nunca deixar implícito. Isso já falhou uma vez: gerei e enviei build de iOS (2026-08-07, correção do botão "Criar conta" incluída) sem avisar que a mesma mudança de código também não tinha chegado no Android, e só corrigi quando o usuário perguntou "cadê a versão pro Android". Antes de fechar QUALQUER resposta que envolveu gerar/enviar um build, checar mentalmente: "isso mexeu em código de `mobile/`? se sim, as DUAS plataformas estão com um build refletindo isso, ou só uma?" — e dizer o resultado dessa checagem em voz alta, sempre.
