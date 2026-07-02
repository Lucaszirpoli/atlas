# appfit backend (Fase 0)

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

# 5. Subir a API
uvicorn app.main:app --reload
```

API disponível em `http://localhost:8000`, docs em `http://localhost:8000/docs`.

## Estrutura

- `app/models` — modelos SQLAlchemy (User, UserProfile, WeightLog append-only, ConsentRecord)
- `app/schemas` — schemas Pydantic de request/response
- `app/routers` — endpoints FastAPI (`/auth`, `/users`)
- `app/services` — regras de negócio e verificação de tokens sociais (Google/Apple)
- `alembic/` — migrations
