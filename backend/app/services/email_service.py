"""E-mail transacional via Brevo (REST, sem SDK — é uma chamada só).

Hoje o único uso é o código de "esqueci minha senha". Falha de envio nunca
propaga como 500 pra quem chamou: o chamador decide o que fazer (ver
routers/auth.py, que sempre responde 200 em forgot-password pra não revelar
se o e-mail existe — sucesso ou falha de envio parecem a mesma coisa por fora).
"""

import logging

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_password_reset_code(to_email: str, to_name: str, code: str) -> bool:
    """Manda o código de 6 dígitos por e-mail. Devolve False (sem levantar
    exceção) se a chave não estiver configurada ou o envio falhar — só loga."""
    if not settings.brevo_api_key:
        logger.warning("BREVO_API_KEY não configurada — código de reset não enviado (%s)", to_email)
        return False

    corpo_html = f"""
    <div style="font-family:sans-serif;max-width:420px;margin:0 auto;padding:24px">
      <h2 style="color:#3563FF;margin-bottom:4px">ATLAS</h2>
      <p>Use este código pra criar uma nova senha. Ele vale por 15 minutos.</p>
      <p style="font-size:32px;font-weight:700;letter-spacing:6px;
                background:#F4F7FB;padding:16px 24px;border-radius:12px;
                text-align:center;color:#0F172A">{code}</p>
      <p style="color:#64748B;font-size:13px">
        Se você não pediu isso, pode ignorar este e-mail — sua senha continua a mesma.
      </p>
    </div>
    """
    try:
        resp = requests.post(
            BREVO_API_URL,
            headers={
                "api-key": settings.brevo_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "sender": {"email": settings.brevo_sender_email, "name": settings.brevo_sender_name},
                "to": [{"email": to_email, "name": to_name or to_email}],
                "subject": "Seu código para redefinir a senha — ATLAS",
                "htmlContent": corpo_html,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.error("Falha ao enviar e-mail de reset via Brevo (%s): %s", to_email, exc)
        return False
