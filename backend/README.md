# appfit backend

## Rodar localmente

```bash
# 1. Subir Postgres + Redis
docker compose up -d          # a partir da raiz do repo

# 2. Criar venv e instalar dependências
cd backend
python -m venv .venv
.venv/Scripts/activate         # Windows
pip install -e ".[dev]"

# 3. Configurar variáveis de ambiente
cp .env.example .env           # preencher ANTHROPIC_API_KEY para as rotas /ai/*

# 4. Rodar as migrations
alembic upgrade head

# 5. Popular a base de alimentos (TACO) e a biblioteca de exercícios
python -m app.scripts.seed_taco
python -m app.scripts.seed_exercises

# 6. Subir a API
uvicorn app.main:app --reload
```

API disponível em `http://localhost:8000`, docs em `http://localhost:8000/docs`.

## Estrutura

- `app/models` — modelos SQLAlchemy, um por fase do roadmap:
  - Fase 0: `User`, `UserProfile`, `WeightLog` (append-only), `ConsentRecord`
  - Fase 1: `Food` (TACO/Open Food Facts/custom), `MealCategory`, `MealLog`/`MealLogItem` (append-only, snapshot nutricional), `SavedMeal`, `FavoriteFood`, `CalorieGoal` (append-only), `WaterLog` (append-only), `BodyMeasurement`/`ProgressPhoto` (append-only)
  - Fase 2: `Exercise`, `Routine`/`RoutineExercise` (molde), `WorkoutSession`/`WorkoutSetLog` (append-only, execução real)
  - Fase 3/4: `ChatMessage` (histórico do assistente único, append-only)
  - Fase 5: `FriendRequest`, `BlockedUser`, `ContentReport`, `UserPrivacySettings`, `FeedPost`/`FeedReaction`/`FeedComment`, `Challenge`/`ChallengeParticipant`
  - Fase 6: `SleepLog` (append-only)
- `app/ai` — orquestrador do assistente único (tool-calling), system prompt, ferramentas de leitura/escrita, reconhecimento de refeição por foto
- `app/schemas` — schemas Pydantic de request/response
- `app/routers` — endpoints FastAPI (ver `app/main.py` para a lista completa)
- `app/services` — regras de negócio: verificação de tokens sociais (Google/Apple), Open Food Facts, cálculo de meta calórica (Mifflin-St Jeor), limite de rotinas ativas, feed/amizades, PRs, detecção de platô/deload
- `app/data/` — seeds locais (TACO, biblioteca de exercícios)
- `alembic/` — migrations

## O que ficou de fora (V2, conforme a especificação)

- **Wearables** (Apple Health, Google Health Connect, Fitbit, Garmin, Whoop) — a espec. já recomenda isso como V2 explicitamente (Parte 3.4). Nenhum código de integração foi iniciado.
- **Moderação automática de imagem** no feed social — o canal de denúncia com fila para revisão humana está implementado (`ContentReport`), mas o filtro automático de conteúdo problemático dependeria de um serviço de moderação dedicado (AWS Rekognition, Google Vision SafeSearch, Hive etc.). Não dá pra usar a IA do app pra isso porque violaria a regra de "IA exclusiva do Pro" numa feature de segurança que precisa valer pra todo mundo — é uma decisão de fornecedor que fica para o produto escolher.
- **Upload real de mídia (Cloudflare R2)** — `ProgressPhoto.photo_url` aceita qualquer URL que o cliente mande; hoje o mobile salva a URI local do dispositivo como placeholder. Precisa de credenciais R2 e um fluxo de presigned URL.

## Detecção de platô e sugestão de deload

A análise (`app/services/workout_insights_service.py`) é 100% determinística — não
chama a Anthropic API. O endpoint `/workout-insights` e a tool de chat
`verificar_platos_e_deload` ficam atrás de `require_pro_plan` porque a
especificação (Parte 4) lista essa reavaliação como um recurso do plano Pro,
não porque a análise em si dependa de IA generativa.
