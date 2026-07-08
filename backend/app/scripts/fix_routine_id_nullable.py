"""Corrige o banco de dev (SQLite) existente: workout_sessions.routine_id
vira nullable com ON DELETE SET NULL (era NOT NULL sem regra, então excluir
uma rotina já usada em algum treino quebrava com FOREIGN KEY constraint
failed). SQLite não suporta ALTER COLUMN nem adicionar ON DELETE a uma FK
existente — a correção é recriar a tabela e copiar os dados, como a própria
documentação do SQLite recomenda para esse tipo de mudança.

    cd backend && .venv/Scripts/python -m app.scripts.fix_routine_id_nullable

Idempotente: sai sem fazer nada se a tabela já estiver no formato novo.
Em produção (Postgres) isso é feito pela migração Alembic 0010, não por
este script.
"""

from sqlalchemy import text

from app.core.db import engine


def main() -> None:
    with engine.begin() as conn:
        ddl = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='workout_sessions'")
        ).scalar_one()
        if "routine_id INTEGER NOT NULL" not in ddl:
            print("workout_sessions já está no formato novo (routine_id nullable). Nada a fazer.")
            return

        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(
            text(
                """
                CREATE TABLE workout_sessions_new (
                    id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    routine_id INTEGER,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY(routine_id) REFERENCES routines (id) ON DELETE SET NULL
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO workout_sessions_new "
                "SELECT id, user_id, routine_id, started_at, completed_at, created_at FROM workout_sessions"
            )
        )
        conn.execute(text("DROP TABLE workout_sessions"))
        conn.execute(text("ALTER TABLE workout_sessions_new RENAME TO workout_sessions"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
        n = conn.execute(text("SELECT COUNT(*) FROM workout_sessions")).scalar_one()
        print(f"workout_sessions recriada com routine_id nullable + ON DELETE SET NULL ({n} linhas preservadas).")


if __name__ == "__main__":
    main()
