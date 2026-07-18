from pydantic import BaseModel, EmailStr, Field, field_validator

HANDLE_PATTERN = r"^[a-z0-9_]{3,30}$"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    handle: str = Field(min_length=3, max_length=30)
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("handle")
    @classmethod
    def handle_must_be_slug(cls, value: str) -> str:
        import re

        if not re.match(HANDLE_PATTERN, value):
            raise ValueError(
                "Handle deve ter 3-30 caracteres: letras minúsculas, números ou _"
            )
        return value


class LoginRequest(BaseModel):
    # Não é EmailStr de propósito: a tela de login aceita e-mail OU @handle
    # ("E-mail ou usuário"), e um handle não é um e-mail válido — validar como
    # EmailStr fazia o backend recusar a requisição inteira com 422 antes de
    # sequer checar a senha (e o app quebrava ao tentar mostrar esse erro).
    email: str = Field(min_length=1, max_length=255)
    password: str


class SocialAuthRequest(BaseModel):
    id_token: str
    handle: str | None = Field(default=None, min_length=3, max_length=30)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
