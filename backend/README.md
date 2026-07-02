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
cp .env.example .env

# 4. Rodar as migrations
alembic upgrade head

# 5. Popular a base de alimentos (TACO)
python -m app.scripts.seed_taco

# 6. Subir a API
uvicorn app.main:app --reload
```

API disponível em `http://localhost:8000`, docs em `http://localhost:8000/docs`.

## Estrutura

- `app/models` — modelos SQLAlchemy
  - Fase 0: `User`, `UserProfile`, `WeightLog` (append-only), `ConsentRecord`
  - Fase 1: `Food` (TACO/Open Food Facts/custom), `MealCategory`, `MealLog`/`MealLogItem` (append-only, snapshot nutricional), `SavedMeal`, `FavoriteFood`, `CalorieGoal` (append-only), `WaterLog` (append-only), `BodyMeasurement`/`ProgressPhoto` (append-only)
- `app/schemas` — schemas Pydantic de request/response
- `app/routers` — endpoints FastAPI (`/auth`, `/users`, `/foods`, `/meals`, `/goals/calorie`, `/water`, `/measurements`, `/progress-photos`)
- `app/services` — regras de negócio, verificação de tokens sociais (Google/Apple), cliente do Open Food Facts, cálculo de meta calórica (Mifflin-St Jeor)
- `app/data/taco_seed.csv` — subconjunto curado (~40 itens) da TACO para desenvolvimento; trocar pelo CSV oficial completo da UNICAMP quando disponível, mantendo as mesmas colunas
- `alembic/` — migrations

## Observação sobre fotos de progresso

`ProgressPhoto.photo_url` hoje aceita qualquer URL que o cliente mande. O
upload real para Cloudflare R2 (S3-compatible) ainda não foi implementado —
o mobile está salvando a URI local do dispositivo como placeholder. Quando o
bucket R2 for configurado, trocar por um fluxo de upload (presigned URL) e
persistir a URL remota.
