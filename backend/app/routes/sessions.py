import copy
import csv
import hashlib
import io
import json
from uuid import uuid4
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from ..auth import get_db, roles
from ..models import User, TrainingSession, Event, now
from ..schemas import AssignInput, DraftInput, EventInput, ReviewInput, CriterionReviewInput, STATUSES
from ..common import scoped_session, visible_scenario, scenario_json, session_json, event_json, events_for, add_event, audit, require_active, compact_event_response, replay_event_response
from ..assessment import assess
from ..simulation import simulate_contact
from ..expert_review import effective_criteria, expert_summary

router=APIRouter(prefix='/sessions',tags=['sessions'],dependencies=[Depends(roles('student','teacher'))])
FINISHED={'submitted','reviewed','stopped'}


class ArriveInput(BaseModel):
    session_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator('session_ids')
    @classmethod
    def unique_ids(cls, values):
        if len(set(values)) != len(values):
            raise ValueError('Укажите каждое задание только один раз')
        return values


def session_query(user):
    return select(TrainingSession).where(TrainingSession.student_id==user.id if user.role=='student' else TrainingSession.teacher_id==user.id)


def can_assign(service,student_service):
    return service==student_service or service in {'Учебная ДДС','Все службы','универсальная'} or student_service=='Учебная ДДС'


@router.get('')
def listing(db=Depends(get_db),user=Depends(roles('student','teacher'))):
    return [session_json(db,row,user) for row in db.scalars(session_query(user).order_by(TrainingSession.assigned_at.desc()))]


@router.post('')
def assign(body:AssignInput,request:Request,db=Depends(get_db),user=Depends(roles('teacher'))):
    with request.app.state.mutation_lock:
        scenario=visible_scenario(db,body.scenario_id,user)
        if scenario.status!='approved': raise HTTPException(409,'Назначать можно только утверждённый сценарий')
        students=[]
        for sid in dict.fromkeys(body.student_ids):
            student=db.get(User,sid)
            if not student or student.role!='student' or not student.active:
                raise HTTPException(422,'Выбран недоступный обучающийся')
            if not can_assign(scenario.data['service'],student.service):
                raise HTTPException(422,f'Профиль службы не совпадает: {student.name}')
            students.append(student)
        rows=[]
        for student in students:
            row=TrainingSession(scenario_id=scenario.id,student_id=student.id,teacher_id=user.id,mode=body.mode,snapshot=copy.deepcopy(scenario_json(scenario)),draft={})
            db.add(row);db.flush();audit(db,user,'session_assigned','session',row.id,{'scenario_id':scenario.id,'version':scenario.version});rows.append(row)
        db.commit()
        return [session_json(db,row,user) for row in rows]


@router.post('/arrive')
def arrive(body:ArriveInput,request:Request,db=Depends(get_db),user=Depends(roles('teacher'))):
    """Deliver a selected set of preassigned cards at one server-authoritative time."""
    with request.app.state.mutation_lock:
        rows=list(db.scalars(select(TrainingSession).where(
            TrainingSession.id.in_(body.session_ids),TrainingSession.teacher_id==user.id)))
        if len(rows)!=len(body.session_ids) or any(row.status!='assigned' for row in rows):
            raise HTTPException(409,'Можно доставить только свои назначенные задания, ожидающие поступления')
        delivered_at=now()
        by_id={row.id:row for row in rows}
        for session_id in body.session_ids:
            row=by_id[session_id]
            row.status='active';row.started_at=delivered_at
            add_event(db,row,'session_started',{'mode':row.mode,'source':'teacher_arrival'})
            audit(db,user,'session_arrived','session',row.id,{'delivered_at':delivered_at})
        db.commit()
        return [session_json(db,by_id[session_id],user) for session_id in body.session_ids]


@router.get('/{session_id}')
def get_one(session_id:str,db=Depends(get_db),user=Depends(roles('student','teacher'))):
    return session_json(db,scoped_session(db,session_id,user),user)


@router.post('/{session_id}/start')
def start(session_id:str,request:Request,db=Depends(get_db),user=Depends(roles('student'))):
    with request.app.state.mutation_lock:
        row=scoped_session(db,session_id,user,True)
        if row.status=='assigned':
            row.status='active';row.started_at=now();add_event(db,row,'session_started',{'mode':row.mode});audit(db,user,'session_started','session',row.id);db.commit()
        elif row.status!='active': raise HTTPException(409,'Завершённую попытку нельзя запустить снова')
        return session_json(db,row,user)


@router.put('/{session_id}/draft')
def draft(session_id:str,body:DraftInput,request:Request,db=Depends(get_db),user=Depends(roles('student'))):
    if set(body.draft)-{'comment','selected_status','phone','message'}:
        raise HTTPException(422,'Черновик может содержать только comment, selected_status, phone, message')
    if any(not isinstance(v,str) or len(v)>1999 for v in body.draft.values()):
        raise HTTPException(422,'Поля черновика должны быть строками до 1999 символов')
    if body.draft.get('selected_status') and body.draft['selected_status'] not in STATUSES:
        raise HTTPException(422,'Неизвестный статус')
    with request.app.state.mutation_lock:
        row=scoped_session(db,session_id,user,True);require_active(row)
        row.draft={**row.draft,**body.draft}
        ev=add_event(db,row,'draft_saved',{'fields':list(body.draft)})
        db.commit();return {'saved_at':ev.at}


def validate_payload(kind,payload):
    allowed={'card_opened':set(),'status_changed':{'status','comment'},'call_started':{'phone'},'call_ended':{'call_id'},'trainee_message':{'text','call_id'},'hint_used':{'hint'},'connection_restored':{'offline_seconds'}}
    if set(payload)-allowed[kind]: raise HTTPException(422,'Неизвестное поле события')
    for key in ('comment','text','hint'):
        if key in payload and (not isinstance(payload[key],str) or len(payload[key])>1999):
            raise HTTPException(422,f'{key}: требуется строка до 1999 символов')
    if kind=='status_changed' and payload.get('status') not in STATUSES:
        raise HTTPException(422,'Неизвестный учебный статус')
    if kind=='status_changed' and (not isinstance(payload.get('comment'),str) or not payload['comment'].strip()):
        raise HTTPException(422,'Для изменения статуса нужен непустой комментарий')
    if kind=='call_started' and (not isinstance(payload.get('phone'),str) or not 1<=len(payload['phone'])<=40):
        raise HTTPException(422,'Укажите учебный номер')
    if kind=='trainee_message' and (not isinstance(payload.get('text'),str) or not payload['text'].strip() or not isinstance(payload.get('call_id'),str)):
        raise HTTPException(422,'Для доклада нужны непустой текст и call_id')
    if kind=='call_ended' and 'call_id' in payload and not isinstance(payload['call_id'],str):
        raise HTTPException(422,'Некорректный call_id')
    if kind=='connection_restored':
        n=payload.get('offline_seconds')
        if not isinstance(n,(int,float)) or isinstance(n,bool) or not 0<=n<=86400:
            raise HTTPException(422,'offline_seconds: ожидается число от 0 до 86400')


def active_call(db,row,call_id=None):
    events=events_for(db,row)
    ended={e.payload.get('call_id') for e in events if e.kind=='call_ended'}
    for e in reversed(events):
        if e.kind=='call_started' and e.payload.get('connected') and e.payload.get('call_id') not in ended:
            if call_id is None or e.payload.get('call_id')==call_id: return e
    return None


@router.post('/{session_id}/events')
def record_event(session_id:str,body:EventInput,request:Request,db=Depends(get_db),user=Depends(roles('student'))):
    validate_payload(body.kind,body.payload)
    digest=hashlib.sha256(json.dumps({'kind':body.kind,'payload':body.payload},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    with request.app.state.mutation_lock:
        row=scoped_session(db,session_id,user,True)
        previous=db.scalar(select(Event).where(Event.session_id==row.id,Event.client_event_id==body.client_event_id))
        if previous:
            if previous.request_hash!=digest: raise HTTPException(409,'Этот client_event_id уже использован для другого события')
            return replay_event_response(db,row,previous.response_cache)
        require_active(row)
        payload=copy.deepcopy(body.payload);reply=None
        if body.kind=='hint_used' and row.mode=='exam': raise HTTPException(403,'Подсказки недоступны в режиме контроля')
        if body.kind=='status_changed': row.current_status=payload['status']
        if body.kind=='call_started':
            if active_call(db,row): raise HTTPException(409,'Сначала завершите текущий учебный звонок')
            sim=simulate_contact(row.snapshot,payload['phone'])
            payload.update({'connected':sim['connected'],'call_id':str(uuid4()),'contact_id':sim['contact_id'],'engine':'templates'})
            reply={'text':sim['text'],'call_id':payload['call_id']}
        if body.kind=='trainee_message':
            call=active_call(db,row,payload['call_id'])
            if not call: raise HTTPException(409,'Для доклада нужен активный соединённый учебный звонок')
            sim=simulate_contact(row.snapshot,call.payload['phone'],payload['text'])
            reply={'text':sim['text'],'call_id':payload['call_id']}
        if body.kind=='call_ended':
            call=active_call(db,row,payload.get('call_id'))
            if not call: raise HTTPException(409,'Активный звонок не найден')
            payload['call_id']=call.payload['call_id']
        ev=add_event(db,row,body.kind,payload,body.client_event_id,digest)
        if reply:
            add_event(db,row,'contact_message',{'text':reply['text'],'call_id':reply['call_id'],'engine':'templates'})
        response={'event':event_json(ev),'session':session_json(db,row,user),'reply':reply}
        ev.response_cache=compact_event_response(db,row,response)
        db.commit();return response


@router.post('/{session_id}/submit')
def submit(session_id:str,request:Request,db=Depends(get_db),user=Depends(roles('student'))):
    with request.app.state.mutation_lock:
        row=scoped_session(db,session_id,user,True)
        if row.status in {'submitted','reviewed'}: return session_json(db,row,user)
        require_active(row)
        row.status='submitted';row.finished_at=now();add_event(db,row,'session_submitted')
        row.report=assess(row.snapshot,[event_json(e) for e in events_for(db,row)],row.started_at,row.finished_at)
        audit(db,user,'session_submitted','session',row.id);db.commit();return session_json(db,row,user)


@router.post('/{session_id}/stop')
def stop(session_id:str,request:Request,db=Depends(get_db),user=Depends(roles('teacher'))):
    with request.app.state.mutation_lock:
        row=scoped_session(db,session_id,user,True)
        if row.status=='stopped': return session_json(db,row,user)
        if row.status in FINISHED: raise HTTPException(409,'Попытка уже завершена')
        row.status='stopped';row.finished_at=now();add_event(db,row,'teacher_stopped')
        row.report=assess(row.snapshot,[event_json(e) for e in events_for(db,row)],row.started_at,row.finished_at,stopped=True)
        audit(db,user,'session_stopped','session',row.id);db.commit();return session_json(db,row,user)


def require_criterion_revision(report, expected):
    current=report.get('criterion_review_revision',0)
    if (expected is not None and expected!=current) or (current>0 and expected is None):
        raise HTTPException(409,'Разбор критериев изменился. Обновите отчёт и подтвердите актуальную ревизию')


@router.post('/{session_id}/criterion-reviews')
def criterion_review(session_id:str,body:CriterionReviewInput,request:Request,db=Depends(get_db),user=Depends(roles('teacher'))):
    with request.app.state.mutation_lock:
        row=scoped_session(db,session_id,user,True)
        if row.status not in FINISHED or not row.report:
            raise HTTPException(409,'Разбирать критерии можно только в завершённой попытке')
        report=copy.deepcopy(row.report)
        require_criterion_revision(report,body.expected_criterion_revision)
        criterion=next((c for c in report['criteria'] if c['id']==body.criterion_id),None)
        if criterion is None: raise HTTPException(422,'Критерий отсутствует в исходном отчёте')
        evidence_ids=list(criterion.get('evidence_ids',[])) if body.evidence_ids is None else body.evidence_ids
        # The same bound applies when evidence is copied from the rule report.
        if len(evidence_ids)>50 or len(set(evidence_ids))!=len(evidence_ids):
            raise HTTPException(422,'Нужно выбрать не более 50 уникальных событий этой попытки')
        event_ids=set(db.scalars(select(Event.id).where(Event.session_id==row.id)))
        if any(eid not in event_ids for eid in evidence_ids):
            raise HTTPException(422,'Доказательства должны быть событиями этой попытки')
        previous=report.get('criterion_reviews',{}).get(body.criterion_id)
        if previous and all((previous.get('status')==body.status,
                             previous.get('comment')==body.comment,
                             previous.get('evidence_ids')==evidence_ids)):
            # Re-submitting the same decision is a read: it must not invalidate
            # an already confirmed overall review or pollute the audit history.
            return session_json(db,row,user)
        revision=report.get('criterion_review_revision',0)+1
        decisions=report.setdefault('criterion_reviews',{})
        decision={'status':body.status,'comment':body.comment,'evidence_ids':evidence_ids,
                  'reviewed_at':now(),'reviewer_name':user.name,'revision':revision}
        add_event(db,row,'criterion_review_saved',{'criterion_id':body.criterion_id,
                  'previous':copy.deepcopy(decisions.get(body.criterion_id)),'current':copy.deepcopy(decision)})
        decisions[body.criterion_id]=decision
        report['criterion_review_revision']=revision
        report['expert_assessment']=expert_summary(report)
        report['teacher_review_stale']=bool(report.get('teacher_review'))
        if row.status=='reviewed': row.status='submitted'
        # Assignment snapshot and every original rule-report field stay unchanged.
        row.report=report
        audit(db,user,'criterion_review_saved','session',row.id,
              {'criterion_id':body.criterion_id,'revision':revision,'status':body.status,'evidence_count':len(evidence_ids)})
        db.commit()
        return session_json(db,row,user)


@router.post('/{session_id}/review')
def review(session_id:str,body:ReviewInput,request:Request,db=Depends(get_db),user=Depends(roles('teacher'))):
    with request.app.state.mutation_lock:
        row=scoped_session(db,session_id,user,True)
        if row.status not in FINISHED or not row.report: raise HTTPException(409,'Оценивать можно только завершённую попытку')
        report=copy.deepcopy(row.report)
        require_criterion_revision(report,body.expected_criterion_revision)
        teacher_review={'score':body.score,'comment':body.comment,'reviewed_at':now(),'reviewer_name':user.name,'criterion_revision':report.get('criterion_review_revision',0)}
        add_event(db,row,'review_saved',{'previous_review':report.get('teacher_review'),'review':teacher_review})
        report['teacher_review']=teacher_review
        report['teacher_review_stale']=False
        # Original score, criteria, requires_review and generated_at remain untouched.
        row.report=report;row.status='reviewed';audit(db,user,'review_saved','session',row.id,{'has_reason':True,'criterion_revision':teacher_review['criterion_revision']});db.commit()
        return session_json(db,row,user)


@router.post('/{session_id}/repeat')
def repeat(session_id:str,request:Request,db=Depends(get_db),user=Depends(roles('student','teacher'))):
    with request.app.state.mutation_lock:
        original=scoped_session(db,session_id,user,True)
        if original.status not in FINISHED: raise HTTPException(409,'Повтор доступен после завершения попытки')
        if user.role=='student' and original.mode!='practice': raise HTTPException(403,'Повтор контрольного задания назначает преподаватель')
        row=TrainingSession(scenario_id=original.scenario_id,student_id=original.student_id,teacher_id=original.teacher_id,mode=original.mode,snapshot=copy.deepcopy(original.snapshot),draft={})
        db.add(row);db.flush();audit(db,user,'session_repeated','session',row.id,{'source_session_id':original.id});db.commit()
        return session_json(db,row,user)


def csv_safe(value):
    text=str(value if value is not None else '')
    if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')): return "'"+text
    return text


@router.get('/{session_id}/export.csv')
def export_csv(session_id:str,db=Depends(get_db),user=Depends(roles('student','teacher'))):
    row=scoped_session(db,session_id,user)
    if row.status not in FINISHED or not row.report: raise HTTPException(409,'Отчёт доступен после завершения попытки')
    buffer=io.StringIO(newline='');writer=csv.writer(buffer,delimiter=';')
    def write(values): writer.writerow([csv_safe(x) for x in values])
    write(['Попытка','Сценарий','Версия','Учащийся','Режим','Автоматический балл','Экспертный балл','Баллы после разбора критериев','Общий итог устарел','Ревизия критериев'])
    write([row.id,row.snapshot['title'],row.snapshot['version'],db.get(User,row.student_id).name,row.mode,row.report['score'],(row.report.get('teacher_review') or {}).get('score'),(row.report.get('expert_assessment') or {}).get('score'),row.report.get('teacher_review_stale',False),row.report.get('criterion_review_revision',0)])
    write(['Критерий','Исход','Баллы','Максимум','Факт','Ожидание','Объяснение','События','Решение преподавателя','Эффективный исход','Эффективные баллы','Основание решения','Доказательства решения','Автор решения','Время решения'])
    effective={c['id']:c for c in effective_criteria(row.report)}
    decisions=row.report.get('criterion_reviews') or {}
    for c in row.report['criteria']:
        decision=decisions.get(c['id'],{});current=effective[c['id']]
        write([c['title'],c['status'],c['points'],c['max_points'],c['actual'],c['expected'],c['explanation'],','.join(c['evidence_ids']),decision.get('status'),current['status'],current['points'],decision.get('comment'),','.join(decision.get('evidence_ids',[])),decision.get('reviewer_name'),decision.get('reviewed_at')])
    if row.report.get('teacher_review'): write(['Комментарий преподавателя',row.report['teacher_review']['comment']])
    return Response(content=('\ufeff'+buffer.getvalue()).encode('utf-8'),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="session-{row.id}.csv"'})
