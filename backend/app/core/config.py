from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://appfit:appfit@localhost:5432/appfit"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        # Provedores de nuvem (Railway, Render, Heroku) injetam a DATABASE_URL no
        # formato "postgres://" ou "postgresql://" — mas o SQLAlchemy com psycopg3
        # (nosso driver) precisa do sufixo "+psycopg". Normaliza aqui pra o mesmo
        # código funcionar em dev (SQLite) e produção (Postgres gerenciado).
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://") :]
        return v
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 10080  # 7 dias

    google_oauth_client_id: str = ""
    apple_oauth_client_id: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    # Pagamento / Pro (RevenueCat). A chave e o segredo do webhook entram aqui
    # via .env quando o RevenueCat estiver configurado. Enquanto não, o modo de
    # teste (billing_dev_mode) deixa ativar o Pro sem cobrança pra validar o
    # fluxo ponta a ponta. Preço mensal do Pro em reais.
    revenuecat_api_key: str = ""
    revenuecat_webhook_secret: str = ""
    pro_price_brl: float = 20.0
    billing_dev_mode: bool = True

    # ExerciseDB (RapidAPI) — fonte de GIF/imagem demonstrativa por exercício.
    # Cache permanente em Exercise.video_url após a primeira busca (ver
    # scripts/backfill_exercise_images.py) pra não estourar a cota do plano.
    rapidapi_exercisedb_key: str = ""

    # URL pública onde o backend é acessível (usada pra montar o video_url
    # completo dos exercícios cujo GIF fica hospedado localmente em /static).
    # Mesma convenção do EXPO_PUBLIC_API_URL do mobile.
    public_base_url: str = "http://100.117.241.0:8090"

    # Em dev, "*" libera qualquer origem (Expo Web em qualquer porta). Em
    # produção, restringir para os domínios reais do app.
    cors_allow_origins: list[str] = ["*"]


settings = Settings()
