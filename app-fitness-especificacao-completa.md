# [Nome provisório: "Vero Fit"] — Especificação Completa do Produto
### Documento de referência para desenvolvimento (Claude Code / Claude Cowork)
Versão 1.0 — Julho/2026

---

## PARTE 1 — ANÁLISE DE MERCADO (honesta, baseada em pesquisa)

### 1.1 Isso já existe? Resposta curta: **as partes sim, o combo completo não.**

Pesquisei o mercado em julho de 2026 e o cenário é o seguinte:

**Lado nutrição (log de comida + IA):**
- **Fitia** (10M+ usuários, nota 4.9) já faz quase tudo que você descreveu do lado alimentar: log por foto, voz ou texto, IA coach conversacional 24/7 que "explica seu dia e sugere ajustes", água, jejum intermitente, fotos de progresso, e até um recurso social chamado "Fitia Teams" onde você entra em grupos e compara resultados com amigos.
- **Cal AI** e clones (**CalZen, Cal Plus, Amy Food Journal**) fazem o reconhecimento por foto ser o carro-chefe, mas em geral têm banco de dados menor e erram bastante em pratos compostos (estudo publicado na *Nutrients* mediu **26,9% de erro médio** nas estimativas de IA por foto vs. valores reais — isso é importante, vou voltar nesse ponto).
- **MyFitnessPal** e **MacroFactor** dominam quem quer precisão via banco de dados, sem depender de IA generativa.

**Lado treino (montagem de treino + IA):**
- **Fitbod** é hoje "o padrão ouro" de treino gerado por IA: monta o treino considerando equipamento disponível, histórico e recuperação muscular, com 1.000+ exercícios em vídeo.
- **Befit** (brasileira!) é o case mais relevante pro seu contexto: nasceu em 2025, fechou o ano com R$ 5 milhões de faturamento e projeta R$ 25 milhões em 2026, com 2,4 milhões de usuários, justamente ocupando o vácuo de "não existe um Strava da musculação no Brasil". Eles estão lançando agora um "AI Coach" que acompanha a evolução ao longo do tempo — ou seja, estão indo na mesma direção que você quer.
- **Freeletics**, **JuggernautAI**, **Hevy**, **Strong**, **JEFIT** cobrem nichos específicos (peso corporal, powerlifting, log manual "raiz", etc.)

**Lado social:**
- **Strava** dominou corrida/ciclismo no Brasil (6 milhões de usuários), mas não tem essa força em musculação.
- **Hevy**, **Fito**, **BattleFit**, **Fitness Pact** fazem feed social de treino, mas nenhum combina isso com nutrição no mesmo nível.

**Lado sono + água + tudo junto:**
- **FitOn**, **Hoola**, **Centr** tentam ser "all-in-one", e há dados de mercado interessantes aqui: **apps que combinam treino + nutrição + recuperação têm 43% mais retenção** do que apps de função única (fonte: Heartwellness/pesquisa citada por Tech em 2026). Isso valida a tese de "app completo".
- Porém nenhum desses tem IA conversacional robusta nos dois lados (nutrição E treino) nem o nível de personalização de treino científico que você quer, nem uma pegada 100% brasileira.

### 1.2 Conclusão honesta

Você não vai inventar uma categoria nova — vai competir num mercado **saturado e sofisticado**, onde os líderes (Fitia, Fitbod, Befit) já resolveram muito bem *cada pedaço* do que você propôs, com times de dezenas de pessoas e milhões de dólares em dados de treinamento de modelo. O que **não existe** é um único app que:

1. Faça as duas coisas (nutrição IA + treino IA) **bem**, no mesmo produto, sem parecer que uma foi "encaixada" depois;
2. Tenha camada social nativa (amigos, feed, fotos de refeição E treino) integrada aos dois módulos, não só a um;
3. Seja pensado para o usuário brasileiro desde o dia 1 (voz/texto em português coloquial, alimentos e marcas brasileiras, preço em reais compatível com poder de compra local — Befit não é isso, é global desde o início);
4. Tenha honestidade científica declarada como diferencial de marca (nada de "treino bro split genérico"), o que hoje é promessa de marketing em quase todo app, mas raramente é entregue de verdade no algoritmo.

**Esse é o ângulo real de diferenciação: não é "o primeiro app disso", é "o app que finalmente une bem o que hoje precisa de 2-3 apps (Fitia + Fitbod/Befit + Strava/Hevy), com uma IA que realmente conversa em português e não erra o básico."**

### 1.3 Riscos que preciso te falar sem filtro

- **Risco técnico e de custo:** reconhecimento de comida por IA generativa erra ~20-27% em pratos compostos (dado real, não é FUD). Se você prometer isso como recurso central e ele errar feio nas primeiras semanas de uso, o usuário desinstala. Recomendo lançar o log por foto como "estimativa a confirmar" (o usuário sempre revisa antes de salvar), nunca como número final automático — é exatamente isso que os apps maduros fazem.
- **Risco de custo de IA:** cada mensagem de chat + cada foto analisada custa tokens de LLM real. Com usuários gratuitos ilimitados no chat, seu custo de infraestrutura cresce mais rápido que sua receita. Isso PRECISA ser limitado no plano free desde o dia 1 (ex: X mensagens de IA por dia, fotos ilimitadas só no Pro).
- **Risco de "feature completa, execução rasa":** app completo é ótimo em teoria (43% mais retenção, como vimos), mas construir 6 módulos (dieta, treino, social, sono, água, IA dupla) com qualidade de MVP real é MUITO trabalho. Recomendo fortemente uma ordem de construção (ver Parte 5 — Roadmap) em vez de tentar lançar tudo de uma vez.
- **Risco regulatório/LGPD:** você vai coletar peso, altura, condições de saúde, fotos corporais e de refeição — dados sensíveis pela LGPD. Precisa de política de privacidade real, consentimento explícito, e nunca usar IA para dar "conselho médico" (sempre disclaimer).
- **Risco de moderação social:** qualquer rede social com fotos e perfis vira alvo de assédio, fake profiles, conteúdo pró-transtorno alimentar ("fitspo" extremo) se não houver moderação. Isso precisa estar no roadmap, não é opcional.

Dito isso — a oportunidade é real, o mercado brasileiro de musculação está "aquecido e sem uma referência clara" (nas palavras do próprio fundador da Befit), e o combo completo bem executado tem espaço. Vamos para a especificação.

---

## PARTE 2 — PÚBLICO E DORES

### 2.1 Personas

**Persona 1 — "Rafa, o iniciante perdido"** (maior volume de usuários)
- 24 anos, começou a treinar há 2 meses, não sabe montar treino, não entende de macro.
- Dor: sente vergonha de perguntar na academia, não confia nos vídeos de YouTube que se contradizem.
- Quer: alguém (ou algo) que decida por ele com confiança, sem jargão.

**Persona 2 — "Carla, a intermediária que estagnou"**
- 31 anos, treina há 2 anos, resultado platinou, já usou 3 apps diferentes.
- Dor: cansada de treino genérico, quer entender O PORQUÊ das escolhas, quer flexibilidade quando viaja ou muda de rotina.
- Quer: ajuste fino, dados, e compartilhar evolução com o grupo de amigas da academia.

**Persona 3 — "Bruno e Fernanda, o casal fitness"**
- 28-35 anos, treinam juntos 3x/semana, querem treinos combináveis, competem de forma saudável.
- Dor: apps atuais tratam cada um isoladamente, não existe "conta compartilhada com dados individuais".
- Quer: ver o progresso um do outro, se desafiar, cozinhar as mesmas refeições ajustadas pra cada meta.

**Persona 4 — "Diego, o avançado cético"**
- 27 anos, 5+ anos de treino, sabe mais de hipertrofia que muito personal.
- Dor: odeia quando o app "acha que sabe mais que ele" e sugere treino ruim; quer controle manual total com ajuda pontual da IA.
- Quer: liberdade de sobrescrever qualquer sugestão, técnicas avançadas (drop-set, rest-pause, cluster sets), dados granulares (RIR, volume semanal por grupo muscular).

### 2.2 Dor central que o produto resolve

> "Eu preciso de disciplina e conhecimento técnico ao mesmo tempo, e não tenho tempo/dinheiro para ter um nutricionista E um personal trainer me acompanhando todo dia — mas apps que resolvem isso separadamente me fazem preencher tudo duas vezes e não conversam entre si."

---

## PARTE 3 — ESPECIFICAÇÃO FUNCIONAL COMPLETA

Organizei em módulos. Marquei com **[GAP]** tudo que você não mencionou mas que é necessário para o produto funcionar de verdade, e com **[V2]** o que pode esperar para depois do MVP.

### 3.1 Conta e Onboarding

- Cadastro por e-mail, Google, Apple Sign-In.
- Nome de usuário único (para adicionar amigos) — **[GAP]** precisa de validação em tempo real de disponibilidade, e um "@handle" separado do nome de exibição (nome de exibição pode repetir, handle não).
- Onboarding conversacional (pode ser feito pela própria IA, é uma boa oportunidade de já apresentar o assistente):
  - Sexo biológico, idade, altura, peso atual **[necessário para fórmulas metabólicas]**
  - Nível de atividade fora do treino (sedentário → muito ativo)
  - Objetivo: emagrecimento / hipertrofia / manutenção / performance / recomposição
  - Experiência de treino: iniciante / intermediário / avançado
  - Dias e horários disponíveis para treinar
  - Local de treino: academia completa / academia básica / casa com equipamento / casa sem equipamento
  - Restrições alimentares (vegetariano, vegano, low carb, alergias, intolerâncias) **[GAP]**
  - Lesões ou limitações físicas atuais **[GAP crítico — sem isso a IA pode sugerir exercício perigoso]**
  - Treina sozinho ou com parceiro(a) (se sim, vincular conta)
  - Preferência de estilo de treino (curto e intenso / longo e volumoso / deixa a IA decidir)
  - Técnica avançada preferida ou "deixe a IA escolher com base em ciência"
- **[GAP]** Termo de consentimento LGPD explícito para dados de saúde + disclaimer "isto não substitui acompanhamento médico/nutricional profissional".

### 3.2 Módulo Nutrição

**Registro de refeições:**
- Categorias: café da manhã, lanche da manhã, almoço, lanche da tarde, jantar, ceia (customizável — usuário pode renomear/adicionar categorias) **[GAP: refeições devem ser configuráveis, nem todo mundo faz 6 refeições]**
- Busca manual de alimento → mostra kcal, proteína, carboidrato, gordura, porção ajustável
- **[GAP]** Base de alimentos precisa ter cobertura de produtos e marcas brasileiras (ex: Nutren, Whey brasileiro, pão francês, tapioca, açaí, feijoada) — isso é uma vantagem competitiva real sobre apps globais como MyFitnessPal, que é fraco em comida latino-americana.
- Escaneamento de código de barras **[GAP, muito pedido pelos usuários em todos os apps concorrentes]**

**Como resolver a base de produtos com marca (Brasil + mundo) sem depender de um contrato caro:**

Pesquisei isso especificamente porque você pediu marca de produto e essa é normalmente a parte mais cara de construir do zero (é o motivo do MyFitnessPal ter levado uma década pra chegar a 14 milhões de itens). A solução recomendada:

1. **Open Food Facts** (`openfoodfacts.org`, e o subdomínio `br.openfoodfacts.org`) — banco de dados aberto, gratuito, sem necessidade de chave de API para leitura, com mais de 4 milhões de produtos de 150 países, incluindo uma base específica de produtos brasileiros mantida pela própria comunidade local. Cobre marca, código de barras, tabela nutricional completa, Nutri-Score. É o que recomendo como fonte primária de "produtos de marca" — zero custo de licenciamento, e você só precisa identificar sua aplicação com um User-Agent (não precisa de contrato comercial).
   - Limitação honesta: por ser mantido pela comunidade, alguns produtos brasileiros mais regionais podem estar ausentes ou desatualizados. Isso se resolve com o tempo do mesmo jeito que MyFitnessPal resolveu: **permitir que o próprio usuário cadastre um produto que falta**, e esse cadastro fica disponível pra ele (e opcionalmente, depois de validação, pra base geral).
2. **Alimentos genéricos/in natura brasileiros** (arroz, feijão, carnes, frutas): usar a **TACO (Tabela Brasileira de Composição de Alimentos, da UNICAMP)** como base local, carregada uma vez no banco de dados do app (não é uma API, é uma tabela de referência oficial que se importa direto pro Postgres) — garante que o "feijão com arroz" do dia a dia tenha dado nutricional correto e nacional, sem depender de rede.
3. Para o resto do mundo (usuário que viaja ou usa produto importado), o próprio Open Food Facts já cobre, porque é global por natureza.

Ou seja: **a única integração externa em tempo real necessária pra isso é o Open Food Facts, que é gratuita e não exige chave paga.** A tabela TACO entra como dado local (seed), sem chamada de API nenhuma.
- Registro por foto (com IA) — **sempre em modo "confirme antes de salvar"**, nunca automático 100%, por causa da margem de erro real de ~20-27%.
- Registro por chat com IA (texto ou voz): usuário descreve o que comeu em linguagem natural ("comi 2 ovos mexidos com uma fatia de pão integral e café com leite"), a IA:
  1. Interpreta quantidades e marcas quando mencionadas
  2. Pergunta o que faltar de forma clara ("foi 1 ou 2 fatias de pão?") em vez de assumir
  3. Classifica automaticamente na refeição certa pelo horário atual (editável)
  4. Mostra o resumo antes de confirmar
- Alimentos favoritos / refeições salvas para reuso rápido **[GAP, essencial para retenção — "memória de comida"]**
- Meta de calorias:
  - Modo manual: usuário define kcal e macros
  - Modo automático: calculado com base em fórmula validada (recomendo Mifflin-St Jeor para TMB + fator de atividade + ajuste por objetivo, é o padrão mais preciso hoje, mais confiável que Harris-Benedict)
  - **[GAP]** Ajuste automático periódico: a cada atualização de peso, o sistema recalcula e MOSTRA a comparação ("seu gasto real parece ser X, quer ajustar sua meta?") em vez de mudar sozinho sem avisar — isso é o que o MacroFactor faz bem e é considerado ouro no setor.
- Barra de progresso diário: calorias consumidas vs. meta, com indicação visual clara quando ultrapassa (não é "falha", é feedback neutro — cuidado com tom aqui, ver seção 3.7 sobre saúde mental)
- Água: meta personalizada (ex: 35ml/kg), registro rápido por botões (copo, garrafa, +250ml customizável), lembretes opcionais
- **[GAP]** Fibra, sódio, açúcar — pelo menos esses 3 micronutrientes além de macro, porque hoje é considerado padrão mínimo (Fitia, MyFitnessPal Premium já entregam isso) e ajuda muito quem tem objetivo de saúde geral, não só estética.
- **[GAP]** Fotos de progresso corporal + medidas (cintura, braço, etc.) com timeline comparativa — isso é mais importante para retenção do que o peso sozinho, porque o peso oscila e desanima, a mudança visual motiva.
- **[V2]** Lista de compras automática a partir do plano semanal
- **[V2]** Receitas sugeridas pela IA com os alimentos que o usuário já registrou ter em casa

### 3.3 Módulo Treino

**Biblioteca de exercícios:**
- Base inicial recomendada: 600-1000 exercícios (não tente competir com "todos os exercícios que existem" no dia 1 — isso é armadilha de escopo; a Befit, com sucesso comprovado, lançou com apenas 500, curados, "não uma lista infinita")
- Cada exercício: nome, grupo muscular primário/secundário, equipamento necessário, vídeo demonstrativo curto (10-15s, loop), texto de execução, nível de dificuldade
- Usuário pode criar exercício customizado (nome, grupo muscular, vídeo opcional, ou GIF gravado pelo próprio app)
- Filtros: grupo muscular, equipamento disponível, dificuldade

**Montagem de treino (manual):**
- Nome do treino (ex: "Treino A - Peito e Tríceps")
- Adicionar exercícios da lista
- Por exercício: séries, repetições (ou faixa de repetições, ex: 8-12), carga, tipo de série (aquecimento, série válida, drop-set, rest-pause, até a falha, cluster set, myo-reps, etc.) **[GAP: precisa listar TODAS as técnicas que a ciência reconhece, não só "até a falha" — ver lista completa abaixo]**
- Tempo de descanso entre séries (com timer automático)
- Notas por exercício ("cotovelo dói se pegada muito aberta")

**Técnicas de treino avançadas a suportar (baseado em ciência de hipertrofia, não modinha):**
- Séries diretas (straight sets), Drop-set, Rest-pause, Myo-reps, Cluster sets, Até a falha muscular concêntrica, Falha técnica (parar antes da falha total), Tempo controlado (ex: 3-1-1), Séries excêntricas enfatizadas, Pré-exaustão, Superset, Bi-set, Tri-set, Circuito.

**Execução do treino (modo "durante o treino") — como funciona o preenchimento, na prática:**

Primeiro, o modelo de dados precisa deixar claro (isso é importante pro Code entender a estrutura do banco):

- **Rotina** = o "molde"/template salvo (ex: "Treino A - Peito e Tríceps"), com a lista de exercícios e a meta de cada um (ex: Supino reto, 4 séries, 8-12 reps). A rotina em si não muda toda vez que a pessoa treina — ela é reutilizável.
- **Sessão de treino** = uma execução real, em uma data específica, de uma rotina. É aqui que entram os números reais que a pessoa pegou naquele dia.

Fluxo de uso:
1. Na Home ou na aba Treino, a pessoa toca em "Treinar agora" e escolhe qual rotina salva vai fazer hoje (ex: entre as 3-7 rotinas que ela tem salvas, escolhe "Treino B").
2. Abre a tela de execução, que já mostra, exercício por exercício, uma **tabela de preenchimento rápido**, pensada pra ser preenchida com o polegar, no meio da série, sem fricção:

   | Série | Anterior (última vez) | Carga (kg) | Reps | ✓ |
   |---|---|---|---|---|
   | 1 (aquecimento) | 20kg x 12 | [campo numérico, pré-preenchido com o valor anterior] | [campo numérico] | ☐ |
   | 2 | 40kg x 10 | [pré-preenchido] | [pré-preenchido] | ☐ |
   | 3 | 40kg x 9 | [pré-preenchido] | [pré-preenchido] | ☐ |
   | 4 | 40kg x 8 | [pré-preenchido] | [pré-preenchido] | ☐ |

   - O app **sempre pré-preenche com o que a pessoa fez na última vez** que executou aquele exercício (isso já existe em apps como Strong/Hevy e é considerado essencial — ninguém quer digitar peso do zero toda vez, só ajustar pra cima ou pra baixo). O usuário só toca em ✓ se repetiu igual, ou ajusta o número antes de marcar.
   - **Campos de peso e reps ficam sempre visíveis e são o padrão de preenchimento — a tela não pode ficar poluída.** Tipo de série (aquecimento, válida, drop-set, rest-pause, até a falha etc.) e RPE/RIR ficam **escondidos atrás de um botão "mais opções" (ícone de reticências ⋯) discreto ao lado de cada série**, não expostos por padrão. Quem quer registrar RPE ou marcar uma técnica avançada toca em "mais opções" e o campo aparece ali mesmo, sem sair da tela; sem tocar, o app assume "série válida" e deixa o RPE em branco — nenhum dos dois é obrigatório pra concluir o treino.
   - Botão "+ série" pra adicionar série extra não planejada.
   - Cronômetro de descanso dispara automaticamente ao marcar ✓, com notificação/vibração quando acabar.
3. Ao concluir o exercício, avança pro próximo automaticamente (mantendo o fluxo, sem sair da tela de execução).
4. Ao final do treino: tela de resumo (volume total levantado, tempo de duração, comparação com a sessão anterior da mesma rotina — "você levantou 8% mais volume que da última vez").

**Rotinas salvas:**
- Cada usuário tem sua biblioteca de treinos, vinculada ao login, limitada a 3 (Free) ou 7 (Pro) rotinas ativas simultâneas (arquivadas não contam pro limite — ver Parte 4)
- Pode duplicar, editar, excluir, arquivar (arquivar preserva o histórico de sessões já feitas com aquela rotina, mesmo que ela saia da lista ativa)
- Histórico completo de cada sessão (data, exercícios, cargas, reps, volume total, duração) — nada é sobrescrito, cada sessão fica registrada individualmente pra sempre, é a base de todo o gráfico de evolução (ver seção 3.8)
- **[GAP]** Calendário/planejador semanal: qual treino cai em qual dia
- **[GAP]** Detecção de platô: se um exercício não progride em X semanas, o app avisa e sugere ajuste (troca de exercício, deload, mudança de faixa de repetição)
- **[GAP]** Semana de deload automática sugerida a cada 4-8 semanas de treino intenso — isso é ciência básica de periodização que a maioria dos apps ignora e é justamente o tipo de coisa que separa "app sério" de "app genérico"

**IA de montagem de treino (o coração científico do produto):**

A IA deve seguir uma hierarquia de decisão clara (isso deve virar um prompt de sistema bem estruturado no backend, não "converse livremente e monte qualquer coisa"):

1. Coletar via conversa: dias disponíveis, tempo por sessão, objetivo, nível, equipamento, pontos fracos/fortes, lesões, se treina em dupla, preferência de duração/intensidade, se tem técnica preferida ou "IA decide".
2. Escolher a **divisão de treino (split)** com base em evidência, não em modismo:
   - Frequência mínima recomendada por grupamento muscular: **2x por semana** (a literatura atual — ex: meta-análises de Schoenfeld e colegas — mostra volume semanal total como principal driver de hipertrofia, com frequência 2x sendo consistentemente igual ou superior a 1x/semana para o mesmo volume). Isso significa: **evitar bro-split de "um músculo por dia" como padrão**, exatamente como você pediu, a menos que o usuário peça explicitamente.
   - Splits recomendados como default: Upper/Lower (2-4x/semana), Push/Pull/Legs (3-6x/semana), Full Body (2-3x/semana) — a escolha entre eles depende de dias disponíveis, não de moda.
3. Definir volume semanal por grupo muscular dentro de faixas baseadas em evidência (aprox. 10-20 séries semanais por grupo muscular para hipertrofia, ajustando por nível: iniciante mais perto do piso, avançado pode precisar mais para continuar progredindo).
4. Definir faixa de repetições conforme objetivo (força: mais pesado/menos reps; hipertrofia: faixa ampla 6-20 reps já é sustentada pela ciência atual, desde que perto da falha; resistência: reps altas).
5. Se o usuário pedir explicitamente um estilo não-ótimo (ex: bro split), a IA pode entregar, mas **deve avisar de forma transparente e não paternalista**: "Beleza, vou montar assim. Só um adendo rápido: a ciência atual sugere treinar cada grupo pelo menos 2x/semana pra otimizar ganho de massa — se quiser, posso ajustar. Mas a decisão é sua."
6. Para casais: gerar treinos combináveis (mesmos dias, exercícios adaptáveis a diferentes níveis de força/experiência, competição saudável de volume ou consistência, não de carga absoluta).
7. Ao final, a IA cria automaticamente as rotinas na conta do usuário (não é só um "texto no chat" — vira dado estruturado utilizável no módulo de treino).
8. **[GAP]** A IA deve reavaliar periodicamente (ex: a cada 4 semanas ou quando detecta estagnação) e propor ajustes, não só montar uma vez e esquecer.

### 3.4 Módulo Sono

- Registro manual: horário de dormir, horário de acordar (calcula duração automaticamente), qualidade percebida (escala simples de 1-5 ou emojis), como acordou (descansado / cansado / muito cansado)
- **[GAP]** Notas rápidas: acordou de madrugada, teve dificuldade pra dormir, etc.
- Registro via chat com IA: "dormi umas 6h, acordei de madrugada duas vezes" → IA estrutura os dados
- Gráfico semanal/mensal de duração e qualidade
- **[GAP]** Cruzamento com os outros módulos: a IA pode comentar padrões ("seus últimos 3 treinos de pernas caíram em dias que você dormiu menos de 6h — isso pode estar afetando seu desempenho") — isso é diferencial real, porque a maioria dos apps trata sono, treino e dieta como silos separados.
- **[V2]** Integração com wearables (Apple Health, Google Health Connect, Fitbit, Garmin, Whoop) para importar sono automático — recomendo fortemente para V2, é extremamente valorizado e citado em quase todos os apps concorrentes pesquisados.

### 3.5 Módulo Social

- Adicionar amigos por @handle único ou e-mail
- Solicitação de amizade com aceite (não seguir automático — para dar controle de privacidade)
- Feed de atividades: treino concluído (com resumo: duração, volume, PRs batidos), refeições (opcional, foto + resumo), fotos de progresso (opt-in explícito, é dado sensível)
- Reações rápidas (curtir, emoji, comentário curto)
- **[GAP]** Configuração de privacidade granular: por padrão, perfil privado (só amigos veem), com opção de tornar público; usuário escolhe especificamente o que compartilha (ex: pode compartilhar treino mas não peso)
- **[GAP]** Bloquear/denunciar usuário, e moderação de conteúdo (mínimo: filtro automático de imagens problemáticas + canal de denúncia com resposta humana) — não é feature "legal de ter", é responsabilidade básica ao lidar com fotos corporais e de menores de idade eventualmente presentes na base.
- Desafios entre amigos ou grupos (streak de dias treinados, volume total do mês, etc.)
- **[V2]** Grupos/comunidades temáticas (ex: "hipertrofia natural", "corrida de rua SP")

### 3.6 Assistente de IA (arquitetura transversal)

Recomendação de arquitetura: **um único assistente com "modos de contexto"**, não 3 chatbots separados. Um FAB (botão flutuante) de chat acessível em qualquer tela, que já entra sabendo em qual módulo o usuário está (nutrição, treino ou sono) mas pode conversar sobre qualquer coisa e rotear a ação certa. Isso é melhor do que 3 chats isolados porque:
- Evita o usuário ter que "lembrar" onde perguntar o quê
- Permite perguntas cruzadas naturais ("o que eu como hoje pra recuperar melhor do treino de ontem?")
- É tecnicamente mais simples de manter (um único orquestrador de IA com ferramentas/funções para cada módulo, ao invés de 3 sistemas)

**Ferramentas (function calling) que a IA deve ter acesso:**
- `registrar_refeicao(alimentos, refeição, horário)`
- `buscar_alimento(nome)`
- `atualizar_peso(valor, data)`
- `criar_rotina_treino(...)`
- `registrar_execucao_treino(...)`
- `registrar_sono(...)`
- `consultar_historico(módulo, período)`
- `ajustar_meta_calorica(...)` — sempre com confirmação do usuário antes de aplicar mudanças que afetam metas

**[GAP crítico de segurança de produto:** a IA nunca deve: diagnosticar condições médicas, recomendar déficit calórico extremo, incentivar comportamento compulsivo de checagem de peso/calorias, ou ignorar sinais de possível transtorno alimentar (ex: usuário relatando restrição extrema, purgação, medo intenso de comer). Nesses casos, a IA deve responder com cuidado e sugerir buscar um profissional, sem fazer diagnóstico. Isso precisa estar no prompt de sistema desde o dia 1, não é feature "para depois".]

### 3.7 Saúde mental e responsabilidade de produto **[GAP não mencionado, mas essencial]**

Apps de contagem de calorias e peso corporal são conhecidos por poderem alimentar padrões pouco saudáveis em usuários vulneráveis. Recomendações concretas:
- Nunca usar linguagem de "trapaça", "falhou", "pecado" ao ultrapassar meta calórica — usar linguagem neutra e informativa.
- Permitir "pausar" o rastreamento de peso/calorias sem perder dados (para quem precisa de uma pausa da relação com números).
- Opção de esconder números de calorias e mostrar só indicadores qualitativos, para quem prefere.
- Ter um texto de ajuda visível levando a canais de apoio (ex: no Brasil, CVV 188) sem parecer alarmista.

### 3.8 Evolução e histórico (transversal a todos os módulos) **[GAP explicitado pelo Lucas — precisa existir em treino, dieta, sono e água]**

Isso não é um módulo à parte na navegação, é um **requisito de dado que atravessa tudo**: toda informação registrada (sessão de treino, refeição, peso, sono, água) precisa ficar guardada individualmente, com data, pra sempre — nunca sobrescrever o valor anterior. Em cima disso, cada módulo tem sua própria visão de evolução:

- **Treino:** gráfico de carga ao longo do tempo por exercício (ex: evolução do supino nos últimos 6 meses), gráfico de volume total por sessão/semana, contagem de treinos concluídos por semana/mês, recordes pessoais (PRs) destacados automaticamente quando batidos, comparação "essa sessão vs. a anterior da mesma rotina".
- **Dieta:** gráfico de peso ao longo do tempo (com média móvel de 7 dias, porque peso oscila dia a dia e a média suaviza isso e evita ansiedade), adesão à meta calórica (dias dentro da meta vs. fora, sem tom de julgamento — ver seção 3.7), evolução de macros, fotos de progresso lado a lado por data.
- **Sono:** gráfico de duração e qualidade por semana/mês, identificação de padrão (ex: dias da semana que dorme pior).
- **Água:** streak de dias que bateu a meta, média diária por semana.
- **[GAP]** Uma tela de "Resumo/Evolução" na Home ou no Perfil que junta os destaques dos 4 módulos em um só lugar (ex: "essa semana: 4 treinos concluídos, +2kg de carga no supino, meta de água batida 6/7 dias, sono médio de 7h"), pra dar a sensação de progresso real sem o usuário precisar entrar em cada módulo separadamente.

Tecnicamente, isso significa: cada tabela do banco (sessões de treino, refeições registradas, registros de peso, registros de sono, registros de água) é sempre um **histórico append-only** (nunca UPDATE destrutivo do valor antigo), e os gráficos são só consultas agregadas em cima desse histórico. É importante que o Code monte o schema do banco já pensando nisso desde a Fase 0, porque é a base de tudo que vem depois — se os dados não forem guardados como histórico desde o início, a tela de evolução simplesmente não tem o que mostrar.

### 3.10 Perfil e Configurações

- Dados pessoais, foto de perfil, @handle
- Atualização de peso (histórico com gráfico) → ao atualizar, pergunta se mantém o objetivo atual ou quer revisar
- Metas (editável a qualquer momento)
- Unidades (kg/lb, cm/in) — **[GAP, importante mesmo focando Brasil por causa de usuários que migram de outros apps]**
- Notificações (quais tipos, horários)
- Privacidade (visibilidade do perfil, do que é compartilhado)
- Gerenciar assinatura (Free/Pro)
- **[GAP]** Exportar meus dados (LGPD exige isso) e excluir conta permanentemente

---

## PARTE 4 — MODELO DE NEGÓCIO (Free vs. Pro)

**Decisão confirmada: a IA continua exclusiva do Pro (zero cota grátis), e agora o Pro também ganha limites maiores em funcionalidades manuais, como quantidade de rotinas de treino salvas.** Isso dá ao Pro valor mesmo pra quem eventualmente não usa muito a IA, sem quebrar a promessa de "o app manual é completo no Free".

**Plano Free (produto manual robusto, sem custo de IA):**
- Registro manual ilimitado de refeições (busca de alimento, código de barras, alimentos salvos)
- Metas de calorias/macros: cálculo automático via fórmula (Mifflin-St Jeor), sem IA envolvida
- Água, peso, fotos de progresso, medidas — tudo manual, ilimitado, com histórico e gráficos de evolução (ver seção 3.8)
- **Até 3 rotinas de treino salvas simultaneamente**, com execução completa (log de carga/reps/séries), histórico e gráfico de evolução por exercício
- Módulo de sono manual completo, com histórico
- Social completo: amigos, feed, fotos, desafios
- **Chat com IA: bloqueado.**

**Plano Pro (assinatura mensal/anual):**
- **Até 7 rotinas de treino salvas simultaneamente** (útil pra quem varia treino por fase — ex: bulking/cutting, temporada de prova, ou quem treina em dupla e quer rotinas separadas por pessoa)
- Chat com IA ilimitado (orquestrador único descrito na seção 3.6)
- Registro de refeição por foto (visão computacional) e por voz/texto em linguagem natural
- Montagem automática de treino pela IA (questionário conversacional → rotina gerada)
- Reavaliação periódica automática, detecção de platô e sugestão de deload feitas pela IA
- Ajuste automático de metas calóricas sugerido pela IA com base em progresso real
- **[V2, ideia de expansão futura de limites Pro]:** dashboards de evolução mais avançados (comparação de períodos, projeções), exportação de relatório em PDF pra levar ao médico/nutricionista

Por que 3 e 7 (e não outro número)? 3 rotinas cobre o padrão mais comum de quem treina sozinho (ex: A/B/C, ou Push/Pull/Legs) — é suficiente pra ser um produto free genuinamente útil, não capenga. 7 no Pro cobre o caso do casal (2-3 rotinas por pessoa) ou de quem alterna fases de treino ao longo do ano sem precisar apagar a rotina antiga pra criar uma nova. Ajustável depois de validar com uso real — é fácil mudar esse número no banco, não é uma decisão que trava arquitetura.

Preço sugerido (benchmark: Fitia US$19,99/mês; Fitbod ~R$60-80/mês; Cal AI ~R$150-250/ano): **R$ 24,90-34,90/mês ou R$ 199-249/ano** para o Pro — ajustar depois de validar com usuários reais.

Preço sugerido inicial pro mercado brasileiro: **R$ 24,90-34,90/mês ou R$ 199-249/ano**, competitivo com Befit e abaixo de apps globais convertidos em reais — ajustar depois de validar disposição a pagar com usuários reais.

---

## PARTE 5 — ROADMAP DE CONSTRUÇÃO (recomendado)

**Importante: isto é uma ORDEM DE CONSTRUÇÃO, não um escopo de lançamento parcial.** O objetivo final é o app 100% completo, com todos os módulos desta especificação implementados — o roadmap existe só para o Claude Code seguir uma sequência lógica (cada fase depende de estrutura de dados criada na fase anterior) em vez de tentar gerar tudo simultaneamente e misturar as coisas. Ao final da Fase 7, o app deve estar completo e funcional de ponta a ponta, não "pronto pra beta".

Ordem sugerida:

**Fase 0 — Fundação (semanas 1-3):** Auth, perfil, onboarding, estrutura de dados de usuário.

**Fase 1 — MVP Nutrição manual:** log manual de refeições + banco de alimentos brasileiro + metas automáticas (fórmula) + água. Sem IA ainda. Isso já é usável e testável sozinho.

**Fase 2 — MVP Treino manual:** biblioteca de exercícios + montagem manual de rotina + execução com timer + histórico.

**Fase 3 — IA de nutrição:** chat + foto (com confirmação manual) integrados ao módulo já existente.

**Fase 4 — IA de treino:** questionário conversacional + geração automática de rotina + RPE/RIR.

**Fase 5 — Social:** amigos, feed, compartilhamento.

**Fase 6 — Sono + cruzamento de dados entre módulos.**

**Fase 7 — Refinamento:** deload automático, detecção de platô, wearables, gamificação.

Essa ordem prioriza ter algo testável com usuários reais o quanto antes (Fase 1-2 já formam um produto usável), em vez de só lançar quando "tudo" estiver pronto.

---

## PARTE 6 — ARQUITETURA TÉCNICA SUGERIDA

- **Frontend mobile:** React Native (Expo) — permite prototipar rápido no Claude Code e publicar iOS/Android a partir da mesma base.
- **Backend:** FastAPI (Python) — escolha natural já que você tem familiaridade com o framework.
- **Banco de dados:** PostgreSQL (dados relacionais: usuários, refeições, treinos) + Redis (cache, sessões).
- **Armazenamento de mídia:** S3-compatible (Cloudflare R2 é mais barato para volume de fotos/vídeos de exercício).
- **Vídeos de exercício:** para os 600-1000 exercícios, considere licenciar um banco existente (ExerciseDB, Ninjas API) ou produção própria em lote, e importar tudo como dado local (seed) no banco — não precisa ficar consultando uma API externa em tempo real depois de importado uma vez.
- **Notificações push:** Firebase Cloud Messaging.
- **LGPD:** política de privacidade, consentimento explícito para dados de saúde, endpoint de exportação/exclusão de dados.

### 6.1 Quais integrações externas o app realmente precisa (resumo direto)

Você pediu para minimizar dependência de API externa, exceto onde for realmente necessário. Levantamento honesto do que é obrigatório vs. o que é só dado importado uma vez:

| Precisa de chamada de API em tempo real (obrigatório, contínuo) | Só precisa importar o dado uma vez (não é "API vinculada" no sentido de dependência contínua) |
|---|---|
| **Anthropic API** (Claude) — chat de IA, geração de treino, visão para foto de comida. Único ponto realmente crítico e pago, e só é usado pelo plano Pro. | **TACO** (tabela brasileira de alimentos) — importada uma vez pro Postgres |
| **Open Food Facts** — busca de produto por código de barras/nome. É gratuita, sem chave paga, mas tecnicamente é uma chamada de rede em tempo real (para pegar produtos novos que ainda não estão no seu banco). Pode (e deve) ser cacheada: uma vez que um produto é consultado, ele fica salvo no seu próprio banco e não precisa ser buscado de novo. | **Banco de exercícios com vídeo** — importado/licenciado uma vez, armazenado no seu próprio storage (R2/S3) |
| **Firebase Cloud Messaging** — só dispara notificação push, não é uma dependência de "funcionalidade" do produto | — |

Ou seja, na prática: **a única API que o app fica de fato "vinculado" e dependente para funcionar em tempo real é a da Anthropic (IA), como você pediu.** O Open Food Facts é mais uma questão de "primeira busca de um produto novo" — depois disso, o produto já está salvo no seu banco e o app funciona 100% offline-capable para tudo que já foi consultado antes.

---

## PARTE 7 — DESIGN SYSTEM (para Claude Code / Cowork usar diretamente)

### 7.1 Direção de marca

Tom: **sério mas acessível**. Nem o exagero "gym bro" agressivo (preto/vermelho/tipografia pesada tipo app de suplemento), nem o clínico frio de app médico. A referência de sensação: confiança de dado científico + calor humano de "alguém que te acompanha", parecido com o equilíbrio que MacroFactor e Fitbod atingem visualmente, mas com identidade brasileira (cores mais vivas, tom de voz mais próximo, menos "corporate americano").

### 7.2 Paleta de cores

**Cor primária (ação, marca):**
- `--color-primary: #1F7A5C` — verde-esmeralda profundo (transmite "saúde/progresso" sem ser o verde genérico de app de finanças; suficientemente sério para dado científico)
- `--color-primary-light: #2FA37A`
- `--color-primary-dark: #145C43`

**Cor secundária (energia, treino, CTA de destaque):**
- `--color-secondary: #FF6B35` — laranja vibrante (usado com moderação: botão principal de "iniciar treino", conquistas, streaks — dá a energia que falta se tudo fosse só verde)

**Neutros:**
- `--color-bg: #FAFAF8` (fundo claro, levemente quente, não branco puro clínico)
- `--color-bg-dark: #121714` (modo escuro)
- `--color-surface: #FFFFFF` / `--color-surface-dark: #1B211D`
- `--color-text-primary: #1A1F1C`
- `--color-text-secondary: #5C6660`
- `--color-border: #E4E7E2`

**Cores semânticas (usar com cuidado, evitar linguagem de "certo/errado" para calorias — ver seção 3.7):**
- `--color-success: #2FA37A`
- `--color-warning: #E8A33D`
- `--color-danger: #D64545` (reservar para erros reais de sistema, não para "você passou da meta")
- `--color-info: #3B82C4`

**Cores por módulo (uso sutil em ícones/tags, não em telas inteiras):**
- Nutrição: verde-esmeralda (`--color-primary`)
- Treino: laranja (`--color-secondary`)
- Sono: azul-noturno `#4A5B8C`
- Social: coral suave `#E8637A`

### 7.3 Tipografia

- **Fonte de destaque/números (kcal, cargas, PRs):** **Space Grotesk** ou **Inter Tight** — geométrica, moderna, ótima para números grandes em dashboards.
- **Fonte de corpo/texto de chat:** **Inter** — altíssima legibilidade em português (acentuação limpa), padrão de mercado para produtos digitais em 2026, gratuita (Google Fonts).
- Hierarquia sugerida:
  - Display (número grande de calorias/PR): 40-48px, peso 600-700
  - H1 (título de tela): 24px, peso 700
  - H2 (seção): 18px, peso 600
  - Corpo: 15-16px, peso 400
  - Legenda/metadado: 13px, peso 400, `--color-text-secondary`

### 7.4 Tom de voz (para textos de UI e prompts da IA)

- Português brasileiro coloquial, mas sem gíria forçada. Trata o usuário por "você".
- Frases curtas, diretas, sem jargão técnico não explicado (quando usar termo técnico como "RPE", explicar em 4-5 palavras na primeira vez).
- Nunca usar culpa ou vergonha ("você falhou", "pecadinho") — usar tom informativo e encorajador mesmo quando o dado é "ruim" (ex: ultrapassou meta calórica, faltou ao treino).
- A IA se apresenta como parceira de treino/nutrição, não como autoridade infalível — ela pode dizer "não tenho certeza, isso é uma estimativa" quando aplicável (importante pela questão de accuracy de foto).

### 7.5 Componentes-chave e padrões de UI

- **Bottom navigation** com 5 itens: Início (resumo do dia) / Nutrição / Treino / Social / Perfil. Botão de IA como FAB flutuante sobreposto, não como 6º item de nav (fica sempre acessível, em qualquer tela).
- **Cards de resumo diário** na Home: anel de progresso de calorias (estilo "activity ring"), barra de água, próximo treino do dia, resumo de sono da última noite — tudo em cards compactos e tocáveis (leva ao módulo completo).
- **Chat de IA:** bolhas de mensagem com cantos arredondados (16px radius), mensagens da IA com fundo `--color-surface` e leve borda, mensagens do usuário com fundo `--color-primary-light` translúcido. Ações estruturadas (ex: "confirmar refeição") aparecem como cards inline no chat, não só texto.
- **Timer de descanso (treino):** tela de destaque com número grande central, cores do módulo treino (laranja), vibração/som configurável ao terminar.
- **Gráficos:** usar biblioteca de charts simples (linhas suaves, sem 3D, sem excesso de grid) — peso, volume de treino, calorias ao longo do tempo.
- Cantos arredondados consistentes: 12px em cards, 8px em botões pequenos, 16-20px em modais/bottom sheets.
- Modo escuro é obrigatório desde o MVP (público de academia usa o app de manhã cedo e à noite, tela clara ofusca).

---

## PARTE 8 — RESUMO DO QUE MUDEI/ADICIONEI EM RELAÇÃO AO SEU BRIEFING ORIGINAL

**Mantive tudo que você descreveu.** Adicionei principalmente:
1. Confirmação manual obrigatória no log por foto (proteção contra a imprecisão real da IA)
2. RPE/RIR e técnicas avançadas nomeadas explicitamente no treino
3. Deload automático e detecção de platô (o que realmente separa "app sério" de "app genérico")
4. Camada de segurança/saúde mental (tom de voz, limites da IA, opção de pausar métricas)
5. Privacidade granular e moderação no módulo social
6. Fibra/sódio/açúcar além dos macros básicos
7. Fotos de progresso corporal e medidas (mais retenção que peso sozinho)
8. Modelo de negócio Free/Pro detalhado com limites técnicos claros
9. Roadmap faseado (para você não travar tentando construir tudo simultaneamente)
10. Design system completo pronto para implementar

**Não tirei nada do que você pediu** — o app completo que você descreveu é validado pelo mercado (apps completos retêm 43% melhor), só precisa ser construído em fases.
