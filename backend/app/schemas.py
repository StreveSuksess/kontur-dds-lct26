from typing import Literal, Any
from pydantic import BaseModel, Field, field_validator

STATUSES = {'accepted','rejected','responding','arrived','working','refused','completed'}
STATUS_LABELS = {'accepted':'Принята','rejected':'Не принято','responding':'Начало реагирования','arrived':'Прибытие','working':'Проведение работ','refused':'Отказ от выполнения работ','completed':'Работы завершены'}


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class CardInput(BaseModel):
    number: str = Field(min_length=1, max_length=80)
    address: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=1999)
    incident_type: str = Field(min_length=1, max_length=300)
    incident_code: str = Field(min_length=1, max_length=80)
    caller_name: str = Field(default='Учебный заявитель', max_length=160)
    caller_phone: str = Field(default='0000', max_length=40)
    casualties: Literal['unknown','no','yes'] = 'unknown'
    services: list[str] = Field(min_length=1, max_length=30)


class ContactInput(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    role: str = Field(min_length=1, max_length=160)
    phone: str = Field(pattern=r'^\d{3,4}$')
    greeting: str = Field(min_length=1, max_length=1999)
    reply: str = Field(min_length=1, max_length=1999)


class FactInput(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=300)
    patterns: list[str] = Field(min_length=1, max_length=30)
    critical: bool = False
    confirmed_by_contact_ids: list[str] = Field(default_factory=list, max_length=10)

    @field_validator('confirmed_by_contact_ids')
    @classmethod
    def confirmation_ids_safe(cls, values):
        if any(not value.strip() or len(value)>80 for value in values):
            raise ValueError('Идентификатор подтверждающего контакта должен содержать 1–80 символов')
        if len(set(values)) != len(values):
            raise ValueError('Подтверждающие контакты не должны повторяться')
        return values

    @field_validator('patterns')
    @classmethod
    def patterns_safe(cls, values):
        if any(not x.strip() or len(x)>200 for x in values):
            raise ValueError('Каждая смысловая формулировка должна содержать 1–200 символов')
        return values


class ScenarioInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=1999)
    service: str = Field(min_length=1, max_length=160)
    difficulty: Literal['basic','intermediate','advanced'] = 'basic'
    objective: str = Field(min_length=1, max_length=1999)
    card: CardInput
    contacts: list[ContactInput] = Field(default_factory=list, max_length=10)
    expected_statuses: list[str] = Field(default_factory=list, max_length=12)
    required_facts: list[FactInput] = Field(default_factory=list, max_length=20)
    reference_response: str = Field(default='', max_length=1999)
    response_limit_seconds: int = Field(default=30, ge=1, le=3600)
    completion_limit_seconds: int = Field(default=180, ge=1, le=86400)
    source_note: str = Field(default='Авторский учебный сценарий; требуется утверждение преподавателем.', max_length=3000)

    @field_validator('expected_statuses')
    @classmethod
    def valid_statuses(cls, values):
        if any(v not in STATUSES for v in values):
            raise ValueError('Неизвестный учебный статус')
        return values


class GenerateInput(BaseModel):
    incident_code: str = Field(min_length=1, max_length=80)
    service: str = Field(min_length=1, max_length=160)
    difficulty: Literal['basic','intermediate','advanced'] = 'basic'
    instructions: str = Field(default='', max_length=1999)


class AssignInput(BaseModel):
    scenario_id: str
    student_ids: list[str] = Field(min_length=1, max_length=100)
    mode: Literal['practice','exam'] = 'practice'


class DraftInput(BaseModel):
    draft: dict[str, Any]


class EventInput(BaseModel):
    client_event_id: str = Field(min_length=1, max_length=100)
    kind: Literal['card_opened','status_changed','call_started','call_ended','trainee_message','hint_used','connection_restored']
    payload: dict[str, Any] = Field(default_factory=dict)


class ReviewInput(BaseModel):
    expected_criterion_revision: int | None = Field(default=None, ge=0, strict=True)
    score: float = Field(ge=0, le=100, allow_inf_nan=False)
    comment: str = Field(min_length=1, max_length=1999)

    @field_validator('comment')
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError('Нужна причина экспертной оценки')
        return value.strip()


class CriterionReviewInput(BaseModel):
    expected_criterion_revision: int | None = Field(default=None, ge=0, strict=True)
    model_config = {'extra': 'forbid'}
    criterion_id: str = Field(min_length=1, max_length=160)
    status: Literal['pass', 'fail', 'review']
    comment: str = Field(min_length=3, max_length=1999)
    evidence_ids: list[str] | None = Field(default=None, max_length=50)

    @field_validator('comment', mode='before')
    @classmethod
    def strip_reason(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('evidence_ids')
    @classmethod
    def unique_evidence(cls, values):
        if values is not None and (len(set(values)) != len(values) or any(not x or len(x)>100 for x in values)):
            raise ValueError('Нужны уникальные идентификаторы событий этой попытки')
        return values


class UserInput(BaseModel):
    username: str = Field(pattern=r'^[a-zA-Z0-9_.-]{3,80}$')
    name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=8, max_length=256)
    role: Literal['student','teacher','admin']
    service: str = Field(default='Учебная ДДС', max_length=160)
    group_name: str = Field(default='Учебная группа', max_length=160)


class ActiveInput(BaseModel):
    active: bool
