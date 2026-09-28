"""Read-only, owner-scoped suggestions; does not assign exercises or change scores."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, or_
from ..auth import get_db, roles
from ..models import User, TrainingSession, Event, Scenario
from ..recommendations import recommend, POLICY_VERSION, MIN_SAMPLE_SIZE, WINDOW_SIZE

router = APIRouter(prefix='/recommendations', tags=['recommendations'])


@router.get('')
def listing(db=Depends(get_db), user=Depends(roles('student', 'teacher'))):
    scope = TrainingSession.student_id == user.id if user.role == 'student' else TrainingSession.teacher_id == user.id
    attempts = list(db.scalars(select(TrainingSession).where(scope)))
    if user.role == 'student':
        students = [user]
        # Learners see only seed summaries and scenarios their teachers already assigned.
        visible_scenarios = or_(Scenario.is_seed.is_(True), Scenario.id.in_({r.scenario_id for r in attempts}))
    else:
        students = list(db.scalars(select(User).where(User.id.in_({r.student_id for r in attempts}), User.role == 'student').order_by(User.name, User.id)))
        visible_scenarios = or_(Scenario.is_seed.is_(True), Scenario.owner_id == user.id)
    scenarios = list(db.scalars(select(Scenario).where(Scenario.status == 'approved', visible_scenarios)))
    # A stopped attempt can subsequently acquire status=reviewed. Preserve its exclusion.
    stopped = set(db.scalars(select(Event.session_id).join(TrainingSession, Event.session_id == TrainingSession.id).where(scope, Event.kind == 'teacher_stopped')))
    grouped = {}
    for attempt in attempts:
        grouped.setdefault(attempt.student_id, []).append(attempt)
    return {'policy_version': POLICY_VERSION, 'min_sample_size': MIN_SAMPLE_SIZE, 'window_size': WINDOW_SIZE,
            'teacher_decides': True,
            'items': [recommend(student, grouped.get(student.id, []), stopped, scenarios) for student in students]}
