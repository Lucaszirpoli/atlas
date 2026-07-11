"""Assinatura Pro (crítica #1 da simulação: não existia NENHUMA forma de virar
Pro). Provedor: RevenueCat, que embrulha a compra in-app da Apple/Google —
obrigatória pra assinatura digital em app mobile.

Três caminhos:
- GET  /billing/offering        -> dados do plano pro paywall (preço, benefícios).
- POST /billing/revenuecat/webhook -> produção: RevenueCat avisa compra/renovação/
  cancelamento; a gente liga/desliga o Pro do usuário. Autenticado por segredo.
- POST /billing/dev-activate    -> TESTE (billing_dev_mode): vira Pro sem cobrança,
  pra validar o desbloqueio ponta a ponta. Fica desligado em produção.

Quando o RevenueCat estiver plugado (chave no .env + build nativo com o SDK), a
compra real acontece no app e chega aqui pelo webhook — o resto do app não muda.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import Plan, User

router = APIRouter(prefix="/billing", tags=["billing"])

PRO_BENEFITS = [
    "Assistente de IA ilimitado (chat, dieta e treino personalizados)",
    "Registrar refeição por foto",
    "Análises e cruzamentos avançados de evolução",
    "Prioridade em novos recursos",
]


class Offering(BaseModel):
    price_brl: float
    period: str
    benefits: list[str]
    provider_ready: bool  # RevenueCat configurado? (senão, modo teste)
    dev_mode: bool


class PlanStatus(BaseModel):
    plan: str
    is_pro: bool


@router.get("/offering", response_model=Offering)
def get_offering(current_user: User = Depends(get_current_user)) -> Offering:
    return Offering(
        price_brl=settings.pro_price_brl,
        period="mês",
        benefits=PRO_BENEFITS,
        provider_ready=bool(settings.revenuecat_api_key),
        dev_mode=settings.billing_dev_mode,
    )


def _set_plan(db: Session, user: User, plan: Plan) -> None:
    user.plan = plan
    db.add(user)
    db.commit()


@router.post("/dev-activate", response_model=PlanStatus)
def dev_activate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanStatus:
    """Ativa o Pro SEM cobrança — só em modo de teste. Serve pra validar todo o
    desbloqueio antes do RevenueCat estar ligado."""
    if not settings.billing_dev_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ativação de teste desligada. Assine pela loja (Apple/Google).",
        )
    _set_plan(db, current_user, Plan.PRO)
    return PlanStatus(plan=current_user.plan.value, is_pro=True)


@router.post("/dev-deactivate", response_model=PlanStatus)
def dev_deactivate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanStatus:
    if not settings.billing_dev_mode:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Indisponível.")
    _set_plan(db, current_user, Plan.FREE)
    return PlanStatus(plan=current_user.plan.value, is_pro=False)


# --- Webhook do RevenueCat (produção) -------------------------------------
# Eventos que LIGAM o Pro vs os que DESLIGAM. RevenueCat manda o app_user_id
# que a gente usou no SDK (setamos = id do usuário) pra saber de quem é.
_GRANT_EVENTS = {"INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION", "PRODUCT_CHANGE", "NON_RENEWING_PURCHASE"}
_REVOKE_EVENTS = {"CANCELLATION", "EXPIRATION", "BILLING_ISSUE", "SUBSCRIPTION_PAUSED"}


@router.post("/revenuecat/webhook")
def revenuecat_webhook(
    payload: dict,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """RevenueCat chama isto a cada mudança de assinatura. Protegido pelo
    segredo compartilhado (Authorization: Bearer <REVENUECAT_WEBHOOK_SECRET>)."""
    secret = settings.revenuecat_webhook_secret
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook de pagamento não configurado.")
    if authorization != f"Bearer {secret}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura inválida.")

    event = payload.get("event", {})
    event_type = event.get("type", "")
    app_user_id = event.get("app_user_id") or event.get("original_app_user_id")
    if not app_user_id:
        return {"ok": True, "ignored": "sem app_user_id"}

    # app_user_id foi setado como o id do usuário no SDK do app.
    try:
        user_id = int(app_user_id)
    except (TypeError, ValueError):
        return {"ok": True, "ignored": "app_user_id não numérico"}

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        return {"ok": True, "ignored": "usuário não encontrado"}

    if event_type in _GRANT_EVENTS:
        _set_plan(db, user, Plan.PRO)
    elif event_type in _REVOKE_EVENTS:
        _set_plan(db, user, Plan.FREE)
    return {"ok": True, "event": event_type, "user_id": user_id}
