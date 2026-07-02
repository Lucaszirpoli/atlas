from datetime import datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.challenge import Challenge, ChallengeMetric, ChallengeParticipant
from app.models.workout_session import WorkoutSession


def _sessions_in_period(db: Session, user_id: int, challenge: Challenge) -> list[WorkoutSession]:
    start = datetime.combine(challenge.start_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(challenge.end_date, time.max, tzinfo=timezone.utc)
    return list(
        db.execute(
            select(WorkoutSession).where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.completed_at.is_not(None),
                WorkoutSession.started_at >= start,
                WorkoutSession.started_at <= end,
            )
        ).scalars()
    )


def _longest_streak(sessions: list[WorkoutSession]) -> int:
    days = sorted({s.started_at.date() for s in sessions})
    if not days:
        return 0
    longest = current = 1
    for prev, curr in zip(days, days[1:]):
        if (curr - prev).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def compute_metric_value(db: Session, user_id: int, challenge: Challenge) -> float:
    sessions = _sessions_in_period(db, user_id, challenge)
    if challenge.metric == ChallengeMetric.WORKOUT_COUNT:
        return float(len(sessions))
    if challenge.metric == ChallengeMetric.TOTAL_VOLUME:
        return sum(s.weight_kg * s.reps for session in sessions for s in session.sets)
    if challenge.metric == ChallengeMetric.STREAK_DAYS:
        return float(_longest_streak(sessions))
    return 0.0


def build_leaderboard(db: Session, challenge: Challenge) -> list[dict]:
    participants = list(
        db.execute(
            select(ChallengeParticipant).where(ChallengeParticipant.challenge_id == challenge.id)
        ).scalars()
    )
    entries = [
        {"user_id": p.user_id, "value": compute_metric_value(db, p.user_id, challenge)}
        for p in participants
    ]
    entries.sort(key=lambda e: e["value"], reverse=True)
    return entries
