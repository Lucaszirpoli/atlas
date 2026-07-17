"""Libera Pro de cortesia pros e-mails de PRO_COMP_EMAILS.

POR QUE ASSIM: o banco de produção é o Postgres do Railway, e não dá pra
editá-lo da máquina de desenvolvimento. Uma variável de ambiente aplicada no
deploy é o caminho auditável (o valor fica versionado na config do Railway, não
escondido num UPDATE manual que ninguém lembra ter rodado).

Só CONCEDE, nunca rebaixa: tirar um e-mail da lista não remove o Pro de
ninguém — quem assinou de verdade continua Pro, e o rebaixamento legítimo é
responsabilidade do webhook do RevenueCat.

Idempotente. Roda no init_db, a cada deploy.

Uso local: PRO_COMP_EMAILS=a@b.com python -m app.scripts.grant_comp_pro
"""

from sqlalchemy import func, select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.user import Plan, User


def run() -> None:
    emails = settings.pro_comp_email_list
    if not emails:
        return

    db = SessionLocal()
    try:
        liberados, ja_pro, nao_achados = [], [], []
        for email in emails:
            # Comparação case-insensitive: a pessoa pode ter se cadastrado com
            # maiúscula em alguma letra e o e-mail não bateria.
            user = db.execute(
                select(User).where(func.lower(User.email) == email)
            ).scalar_one_or_none()
            if user is None:
                nao_achados.append(email)
                continue
            if user.plan == Plan.PRO:
                ja_pro.append(email)
                continue
            user.plan = Plan.PRO
            db.add(user)
            liberados.append(email)
        db.commit()

        if liberados:
            print(f"Pro de cortesia liberado: {', '.join(liberados)}")
        if ja_pro:
            print(f"Já eram Pro: {', '.join(ja_pro)}")
        if nao_achados:
            # Não é erro: a pessoa pode ainda não ter criado a conta. Na próxima
            # subida do deploy ela é pega.
            print(f"Ainda sem conta (serão pegos num deploy futuro): {', '.join(nao_achados)}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
