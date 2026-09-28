import copy
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import select, func
from .models import Scenario, TrainingSession, Event, Audit, User, now


def scenario_json(row: Scenario):
    return {**copy.deepcopy(row.data),'id':row.id,'owner_id':row.owner_id,'status':row.status,'version':row.version,'created_at':row.created_at,'updated_at':row.updated_at}


def visible_scenario(db, scenario_id, user, edit=False):
    row = db.get(Scenario, scenario_id)
    if not row: raise HTTPException(404, 'Сценарий не найден')
    if row.owner_id != user.id and (edit or not row.is_seed):
        raise HTTPException(403, 'Сценарий принадлежит другому преподавателю; шаблон можно скопировать')
    return row


def scoped_session(db, session_id, user, lock=False):
    query = select(TrainingSession).where(TrainingSession.id==session_id)
    if lock: query=query.with_for_update()
    row = db.scalar(query)
    if not row: raise HTTPException(404, 'Попытка не найдена')
    if not ((user.role=='student' and row.student_id==user.id) or (user.role=='teacher' and row.teacher_id==user.id)):
        raise HTTPException(403, 'Нет доступа к этой попытке')
    return row


def events_for(db, row, through_sequence=None):
    query=select(Event).where(Event.session_id==row.id)
    if through_sequence is not None:
        query=query.where(Event.sequence<=through_sequence)
    # response_cache is a deferred column: loading the journal never loads replay state.
    return list(db.scalars(query.order_by(Event.sequence, Event.at, Event.id)))


def event_json(event):
    return {key:getattr(event,key) for key in ['id','client_event_id','kind','at','elapsed_seconds','payload']}


def session_json(db, row, user):
    student=db.get(User,row.student_id)
    s=row.snapshot
    result={'id':row.id,'scenario_id':row.scenario_id,'scenario_title':s['title'],'scenario_version':s['version'],
      'student_id':row.student_id,'student_name':student.name if student else 'Учётная запись','teacher_id':row.teacher_id,
      'service':s['service'],'mode':row.mode,'status':row.status,'assigned_at':row.assigned_at,'started_at':row.started_at,'finished_at':row.finished_at,
      'card':copy.deepcopy(s['card']),'contacts':[{k:c[k] for k in ['id','name','role','phone']} for c in s['contacts']],
      'objective':s['objective'],'response_limit_seconds':s['response_limit_seconds'],'completion_limit_seconds':s['completion_limit_seconds'],
      'current_status':row.current_status,'draft':copy.deepcopy(row.draft),'events':[event_json(e) for e in events_for(db,row)],
      'report':copy.deepcopy(row.report) if row.status in {'submitted','reviewed','stopped'} else None}
    if user.role=='teacher': result['scenario_snapshot']=copy.deepcopy(s)
    return result


def add_event(db, row, kind, payload=None, client_event_id=None, request_hash=None):
    timestamp=now()
    elapsed=max(0,(datetime.fromisoformat(timestamp)-datetime.fromisoformat(row.started_at)).total_seconds()) if row.started_at else 0
    sequence=(db.scalar(select(func.max(Event.sequence)).where(Event.session_id==row.id)) or 0)+1
    ev=Event(sequence=sequence,session_id=row.id,kind=kind,payload=payload or {},client_event_id=client_event_id,at=timestamp,elapsed_seconds=elapsed,request_hash=request_hash)
    db.add(ev);db.flush()
    return ev


def audit(db,user,action,kind,entity_id,details=None):
    # Do not put passwords, learner content, or hidden references into the admin audit feed.
    db.add(Audit(actor_id=user.id,action=action,entity_type=kind,entity_id=entity_id,details=details or {}))


def require_active(row):
    if row.status!='active': raise HTTPException(409, 'Попытка должна быть активной')


def compact_event_response(db, row, response):
    """Keep immutable replay state without copying an ever-growing event journal.

    Events are append-only, so a sequence watermark reconstructs the exact historical
    prefix. The remaining session state is frozen: retries must not acquire a later
    draft, status, report or teacher review. This keeps storage linear in event count.
    """
    session_state=copy.deepcopy(response['session'])
    session_state.pop('events',None)
    watermark=db.scalar(select(func.max(Event.sequence)).where(Event.session_id==row.id)) or 0
    return {'_cache_version':2,'event':copy.deepcopy(response['event']),
      'reply':copy.deepcopy(response['reply']),'session_state':session_state,
      'event_prefix_sequence':watermark}


def replay_event_response(db, row, cache):
    # Existing databases can still replay records written before compact caching.
    if cache.get('_cache_version')!=2:
        return copy.deepcopy(cache)
    session=copy.deepcopy(cache['session_state'])
    session['events']=[event_json(e) for e in events_for(db,row,cache['event_prefix_sequence'])]
    return {'event':copy.deepcopy(cache['event']),'reply':copy.deepcopy(cache['reply']),'session':session}
