"""Dietas semi-prontas (curadas, SEM IA). Lista os moldes já escalados pra meta
da pessoa, mostra o preview de um dia inteiro e registra no diário de hoje."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services import diet_template_service

router = APIRouter(prefix="/diet-templates", tags=["diet-templates"])


@router.get("")
def list_diet_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return diet_template_service.list_templates(db, current_user.id)


@router.get("/{template_id}/preview")
def preview_diet_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = diet_template_service.preview(db, current_user.id, template_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dieta não encontrada")
    return result


@router.post("/{template_id}/apply")
def apply_diet_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = diet_template_service.apply(db, current_user.id, template_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dieta não encontrada")
    return result
