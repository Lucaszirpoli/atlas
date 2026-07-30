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

    # E-mails com Pro liberado de cortesia (testador, amigo, imprensa),
    # separados por vírgula. Aplicado a cada deploy pelo init_db — é o jeito de
    # liberar Pro sem tocar no banco de produção na mão. Só CONCEDE, nunca tira:
    # remover daqui não rebaixa ninguém (quem paga de verdade continua Pro).
    pro_comp_emails: str = ""

    @property
    def pro_comp_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.pro_comp_emails.split(",") if e.strip()]

    # FatSecret Platform (busca de alimentos de marca, com prioridade pro
    # catálogo do Brasil — region=BR). OAuth2 client-credentials: sem estas
    # duas, a busca FatSecret fica desligada e o app continua funcionando só
    # com TACO + Open Food Facts (nunca hardcoded no código — sempre via .env
    # local ou variável de ambiente no Railway).
    fatsecret_client_id: str = ""
    fatsecret_client_secret: str = ""

    # A API do ExerciseDB (RapidAPI) foi APOSENTADA em 2026-07-30: todas as
    # imagens da biblioteca são arquivos locais versionados em
    # static/exercise_images/curated/, então não existe mais chamada de rede
    # nem cota pra administrar. Os 3 scripts que consumiam a API (fetch,
    # backfill e audit de imagens) foram removidos junto com a chave.

    # URL pública onde o backend é acessível (usada pra montar o video_url
    # completo dos exercícios cujo GIF fica hospedado localmente em /static).
    # Mesma convenção do EXPO_PUBLIC_API_URL do mobile.
    public_base_url: str = "http://100.117.241.0:8090"

    # Em dev, "*" libera qualquer origem (Expo Web em qualquer porta). Em
    # produção, restringir para os domínios reais do app.
    cors_allow_origins: list[str] = ["*"]


settings = Settings()
