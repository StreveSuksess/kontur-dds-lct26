"""Small, independent 112 intake exercise using synthetic caller statements."""
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from ..auth import get_db, roles
from ..db import Base
from ..models import Audit, User, now, uid

router = APIRouter(prefix='/intake112', tags=['intake112'])
SERVICES = ('Пожарная охрана', 'Полиция', 'Скорая помощь', 'Аварийная газовая служба')
FIELDS = ('incident_type', 'address', 'description', 'caller_name', 'caller_phone')
LABELS = {'incident_type': 'Тип происшествия', 'address': 'Адрес', 'description': 'Что произошло',
          'caller_name': 'Имя заявителя', 'caller_phone': 'Телефон заявителя'}
CASES = {
    'smoke-entrance': {
        'title': 'Дым в подъезде',
        'statement': 'Меня зовут Анна Петрова, мой номер 8 999 111-22-33. Москва, улица Лесная, дом 12, подъезд 2. На третьем этаже из квартиры идёт густой дым, за дверью слышен кашель человека. Нужны пожарные и скорая помощь.',
        'answer': {'incident_type': 'Пожар', 'address': 'Москва, улица Лесная, дом 12, подъезд 2',
                   'description': 'Дым из квартиры на третьем этаже, внутри человек кашляет',
                   'caller_name': 'Анна Петрова', 'caller_phone': '8 999 111-22-33'},
        'services': ['Пожарная охрана', 'Скорая помощь'],
    },
    'gas-kitchen': {
        'title': 'Запах газа',
        'statement': 'Я Иван Соколов, звоню с 8 999 444-55-66. Москва, улица Садовая, дом 8, квартира 14. На кухне сильный запах газа, плита выключена, никто не пострадал. Направьте аварийную газовую службу.',
        'answer': {'incident_type': 'Утечка газа', 'address': 'Москва, улица Садовая, дом 8, квартира 14',
                   'description': 'Сильный запах газа на кухне, плита выключена, пострадавших нет',
                   'caller_name': 'Иван Соколов', 'caller_phone': '8 999 444-55-66'},
        'services': ['Аварийная газовая служба'],
    },
}


class IntakeAttempt(Base):
    __tablename__ = 'intake112_attempts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(String(64))
    student_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    group_name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    submitted_at: Mapped[str] = mapped_column(String(40), default=now)
    card: Mapped[dict] = mapped_column(JSON)
    comparison: Mapped[dict] = mapped_column(JSON)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)


class IntakeCard(BaseModel):
    model_config = ConfigDict(extra='forbid')
    incident_type: str = Field(max_length=120)
    address: str = Field(max_length=240)
    description: str = Field(max_length=500)
    caller_name: str = Field(max_length=120)
    caller_phone: str = Field(max_length=60)
    services: list[str] = Field(max_length=4)


class Submission(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: str
    card: IntakeCard


class Review(BaseModel):
    model_config = ConfigDict(extra='forbid')
    comment: str = Field(min_length=1, max_length=2000)


def normalized(value: str) -> str:
    return ' '.join(re.findall(r'\w+', value.casefold(), flags=re.UNICODE))


def compare(case: dict, card: IntakeCard) -> dict:
    answer = case['answer']
    fields = []
    for key in FIELDS:
        actual = getattr(card, key).strip()
        expected = answer[key]
        matched = (''.join(filter(str.isdigit, actual)) == ''.join(filter(str.isdigit, expected))
                   if key == 'caller_phone' else normalized(actual) == normalized(expected))
        fields.append({'key': key, 'label': LABELS[key], 'entered': actual,
                       'expected': expected, 'matched': matched})
    selected = set(card.services)
    services = [{'name': name, 'selected': name in selected, 'expected': name in case['services'],
                 'matched': (name in selected) == (name in case['services'])} for name in SERVICES]
    return {'fields': fields, 'services': services,
            'matched': sum(x['matched'] for x in fields + services), 'total': len(fields) + len(services),
            'rule': 'Точное сравнение после нормализации регистра и пробелов; телефон — по цифрам. Смысл свободного текста проверяет преподаватель.'}


def public_attempt(row: IntakeAttempt, student_name: str | None = None) -> dict:
    case = CASES[row.case_id]
    return {'id': row.id, 'case_id': row.case_id, 'case_title': case['title'],
            'statement': case['statement'], 'student_id': row.student_id,
            'student_name': student_name, 'submitted_at': row.submitted_at,
            'card': row.card, 'comparison': row.comparison,
            'review_comment': row.review_comment, 'reviewed_at': row.reviewed_at}


@router.get('/cases')
def cases(user=Depends(roles('student', 'teacher'))):
    return {'services': SERVICES, 'cases': [{'id': key, 'title': value['title'],
            'statement': value['statement']} for key, value in CASES.items()]}


@router.get('/attempts')
def attempts(db=Depends(get_db), user=Depends(roles('student', 'teacher'))):
    query = select(IntakeAttempt).order_by(IntakeAttempt.submitted_at.desc())
    if user.role == 'student': query = query.where(IntakeAttempt.student_id == user.id)
    else: query = query.where(IntakeAttempt.group_name == user.group_name)
    rows = list(db.scalars(query.limit(100)))
    names = {u.id: u.name for u in db.scalars(select(User).where(User.id.in_([r.student_id for r in rows])))} if rows else {}
    return [public_attempt(row, names.get(row.student_id)) for row in rows]


@router.post('/attempts')
def submit(body: Submission, request: Request, db=Depends(get_db), user=Depends(roles('student'))):
    case = CASES.get(body.case_id)
    if not case: raise HTTPException(404, 'Учебная вводная не найдена')
    if len(body.card.services) != len(set(body.card.services)) or any(s not in SERVICES for s in body.card.services):
        raise HTTPException(422, 'Выберите службы из учебного списка без повторов')
    card = body.card.model_dump()
    row = IntakeAttempt(id=uid(), case_id=body.case_id, student_id=user.id, group_name=user.group_name,
                        card=card, comparison=compare(case, body.card))
    with request.app.state.mutation_lock:
        db.add(row)
        db.add(Audit(actor_id=user.id, action='intake112_submitted', entity_type='intake112_attempt',
                     entity_id=row.id, details={'case_id': body.case_id}))
        db.commit()
    return public_attempt(row, user.name)


@router.post('/attempts/{attempt_id}/review')
def review(attempt_id: str, body: Review, request: Request, db=Depends(get_db), user=Depends(roles('teacher'))):
    with request.app.state.mutation_lock:
        row = db.get(IntakeAttempt, attempt_id)
        if not row: raise HTTPException(404, 'Попытка не найдена')
        if row.group_name != user.group_name: raise HTTPException(403, 'Попытка другой группы')
        row.review_comment = body.comment.strip()
        if not row.review_comment: raise HTTPException(422, 'Напишите заключение')
        row.reviewed_at = now()
        row.reviewed_by = user.id
        db.add(Audit(actor_id=user.id, action='intake112_reviewed', entity_type='intake112_attempt',
                     entity_id=row.id, details={'comment': row.review_comment}))
        db.commit()
    student = db.get(User, row.student_id)
    return public_attempt(row, student.name if student else None)
