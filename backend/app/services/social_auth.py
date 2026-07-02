"""Verificação de identity tokens de provedores sociais (Google / Apple).

Cada função retorna (provider_user_id, email, name | None) a partir de um
id_token assinado pelo provedor, ou levanta HTTPException se inválido.
"""

import requests
from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import jwk, jwt
from jose.utils import base64url_decode

from app.core.config import settings

APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"


def verify_google_id_token(token: str) -> tuple[str, str, str | None]:
    try:
        payload = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.google_oauth_client_id or None
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token do Google inválido",
        ) from exc

    return payload["sub"], payload["email"], payload.get("name")


def verify_apple_id_token(token: str) -> tuple[str, str | None, str | None]:
    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token da Apple inválido",
        ) from exc

    keys_response = requests.get(APPLE_KEYS_URL, timeout=5)
    keys_response.raise_for_status()
    apple_keys = keys_response.json()["keys"]

    matching_key = next(
        (k for k in apple_keys if k["kid"] == unverified_header.get("kid")), None
    )
    if matching_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de verificação da Apple não encontrada",
        )

    public_key = jwk.construct(matching_key, algorithm="RS256")
    message, encoded_signature = token.rsplit(".", 1)
    decoded_signature = base64url_decode(encoded_signature.encode())
    if not public_key.verify(message.encode(), decoded_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Assinatura do token da Apple inválida",
        )

    claims = jwt.get_unverified_claims(token)
    if claims.get("iss") != APPLE_ISSUER:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Emissor inválido"
        )
    if settings.apple_oauth_client_id and claims.get("aud") != settings.apple_oauth_client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Audience inválida"
        )

    return claims["sub"], claims.get("email"), None
