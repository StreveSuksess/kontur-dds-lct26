from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, Boolean, Integer, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def uid() -> str:
    return str(uuid4())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16))
    service: Mapped[str] = mapped_column(String(160), default='Учебная ДДС')
    group_name: Mapped[str] = mapped_column(String(160), default='Учебная группа')
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    expires_at: Mapped[str] = mapped_column(String(40))


class Scenario(Base):
    __tablename__ = 'scenarios'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default='draft')
    version: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class TrainingSession(Base):
    __tablename__ = 'training_sessions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    scenario_id: Mapped[str] = mapped_column(ForeignKey('scenarios.id'), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    mode: Mapped[str] = mapped_column(String(16), default='practice')
    status: Mapped[str] = mapped_column(String(16), default='assigned')
    snapshot: Mapped[dict] = mapped_column(JSON)
    assigned_at: Mapped[str] = mapped_column(String(40), default=now)
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    draft: Mapped[dict] = mapped_column(JSON, default=dict)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Event(Base):
    __tablename__ = 'events'
    __table_args__ = (UniqueConstraint('session_id', 'client_event_id', name='uq_event_idempotency'), Index('ix_event_session_at', 'session_id', 'at'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey('training_sessions.id'), index=True)
    client_event_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    at: Mapped[str] = mapped_column(String(40), default=now)
    elapsed_seconds: Mapped[float] = mapped_column(default=0.0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_cache: Mapped[dict | None] = mapped_column(JSON, nullable=True, deferred=True)


class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(100))
    at: Mapped[str] = mapped_column(String(40), default=now)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
