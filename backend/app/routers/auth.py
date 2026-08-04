import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import AuthProvider, User
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SocialAuthRequest,
    TokenResponse,
)
from app.services import email_service, user_service
from app.services.social_auth import verify_apple_id_token, verify_google_id_token

# Código de 15 minutos: curto o bastante pra não valer a pena forçar (6
# dígitos = 1 milhão de combinações; o rate-limit implícito de "um código por
# pedido" já torna força bruta impraticável nesse intervalo), longo o
# bastante pra dar tempo de abrir o e-mail no outro app e voltar.
RESET_CODE_TTL_MINUTES = 15

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if user_service.get_by_email(db, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado"
        )
    if not user_service.handle_is_available(db, payload.handle):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Handle já está em uso"
        )

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        auth_provider=AuthProvider.EMAIL,
        handle=payload.handle,
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    # A tela diz "E-mail ou usuário": aceita as duas formas. Antes só olhava
    # e-mail, então quem digitava o @handle (o amigo que tentou "gabe") sempre
    # levava "senha inválida" mesmo com a senha certa.
    user = user_service.get_by_email_or_handle(db, payload.email)
    if (
        user is None
        or user.password_hash is None
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail/usuário ou senha incorretos.",
        )
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> ForgotPasswordResponse:
    """Gera um código de 6 dígitos e manda por e-mail. SEMPRE responde 200
    com a mesma mensagem genérica — e-mail existindo ou não, código enviado
    ou a Brevo tendo falhado — pra não dar pista de quais e-mails têm conta."""
    user = user_service.get_by_email(db, payload.email.strip().lower())
    if user is not None:
        codigo = f"{random.randint(0, 999999):06d}"
        user.reset_code_hash = hash_password(codigo)
        user.reset_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_CODE_TTL_MINUTES)
        db.add(user)
        db.commit()
        email_service.send_password_reset_code(user.email, user.display_name, codigo)
    return ForgotPasswordResponse()


@router.post("/reset-password", response_model=TokenResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Troca a senha se o código bater e ainda estiver dentro da validade.
    Devolve token de acesso — a pessoa já entra logada, sem precisar logar
    de novo com a senha que acabou de criar."""
    user = user_service.get_by_email(db, payload.email.strip().lower())
    erro_generico = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Código inválido ou expirado. Peça um novo.",
    )
    if user is None or user.reset_code_hash is None or user.reset_code_expires_at is None:
        raise erro_generico
    if datetime.now(timezone.utc) > user.reset_code_expires_at:
        raise erro_generico
    if not verify_password(payload.code, user.reset_code_hash):
        raise erro_generico

    user.password_hash = hash_password(payload.new_password)
    # Código é de USO ÚNICO: limpa depois de aplicado, senão o mesmo código
    # continuaria trocando a senha até expirar sozinho.
    user.reset_code_hash = None
    user.reset_code_expires_at = None
    db.add(user)
    db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id)))


def _login_or_register_social(
    db: Session,
    provider: AuthProvider,
    provider_user_id: str,
    email: str | None,
    display_name_hint: str | None,
    payload: SocialAuthRequest,
) -> TokenResponse:
    existing = db.execute(
        select(User).where(
            User.auth_provider == provider, User.provider_user_id == provider_user_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return TokenResponse(access_token=create_access_token(str(existing.id)))

    if not payload.handle or not payload.display_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Primeiro acesso com esse provedor requer handle e display_name",
        )
    if not user_service.handle_is_available(db, payload.handle):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Handle já está em uso"
        )
    if email and user_service.get_by_email(db, email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma conta com esse e-mail",
        )

    user = User(
        email=email or f"{provider.value}-{provider_user_id}@appfit.local",
        password_hash=None,
        auth_provider=provider,
        provider_user_id=provider_user_id,
        handle=payload.handle,
        display_name=payload.display_name or display_name_hint or payload.handle,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/google", response_model=TokenResponse)
def login_with_google(payload: SocialAuthRequest, db: Session = Depends(get_db)) -> TokenResponse:
    sub, email, name = verify_google_id_token(payload.id_token)
    return _login_or_register_social(db, AuthProvider.GOOGLE, sub, email, name, payload)


@router.post("/apple", response_model=TokenResponse)
def login_with_apple(payload: SocialAuthRequest, db: Session = Depends(get_db)) -> TokenResponse:
    sub, email, name = verify_apple_id_token(payload.id_token)
    return _login_or_register_social(db, AuthProvider.APPLE, sub, email, name, payload)
