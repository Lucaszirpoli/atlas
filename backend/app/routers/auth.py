from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import AuthProvider, User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    SocialAuthRequest,
    TokenResponse,
)
from app.services import user_service
from app.services.social_auth import verify_apple_id_token, verify_google_id_token

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
    user = user_service.get_by_email(db, payload.email)
    if (
        user is None
        or user.password_hash is None
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos"
        )
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
