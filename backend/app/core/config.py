from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://appfit:appfit@localhost:5432/appfit"
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

    # Em dev, "*" libera qualquer origem (Expo Web em qualquer porta). Em
    # produção, restringir para os domínios reais do app.
    cors_allow_origins: list[str] = ["*"]


settings = Settings()
