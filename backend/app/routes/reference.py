from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy import select
from ..auth import get_db, roles, current_user, public_user
from ..models import User, TrainingSession, Event
from ..common import session_json
from ..expert_review import trusted_score, trusted_criteria
from .sessions import session_query, FINISHED

router=APIRouter(tags=['reference'])


@router.get('/users')
def users(db=Depends(get_db),user=Depends(roles('teacher','admin'))):
    query=select(User).where(User.username!='__seed__')
    if user.role=='teacher':query=query.where(User.role=='student',User.active.is_(True))
    return [public_user(u) for u in db.scalars(query.order_by(User.name))]


@router.get('/classifier')
def classifier(request:Request,q:str='',limit:int=Query(30,ge=1,le=100),user=Depends(current_user)):
    catalog=request.app.state.classifier
    if len(q)>300: raise HTTPException(422,'Слишком длинный поисковый запрос')
    norm=q.casefold().strip()
    matches=[i for i in catalog.get('items',[]) if not norm or norm in (' '.join(str(i.get(k,'')) for k in ['code','label','group','primary_service'])).casefold()]
    keys=['code','label','group','features','primary_service','source_row']
    return {'total':len(matches),'version':catalog.get('version','не загружен'),'items':[{k:i.get(k) for k in keys} for i in matches[:limit]],'warnings':catalog.get('warnings',[])}


@router.get('/classifier/{code}')
def classifier_item(code:str,request:Request,user=Depends(current_user)):
    catalog=request.app.state.classifier
    item=next((i for i in catalog.get('items',[]) if i['code']==code),None)
    if not item: raise HTTPException(404,'Код не найден')
    return {**item,'source_file':item.get('source_file') or catalog.get('metadata',{}).get('source_file','')}


@router.get('/knowledge')
def knowledge(request:Request,user=Depends(current_user)):
    data=request.app.state.knowledge
    return data if isinstance(data,list) else data.get('items',[])


@router.get('/analytics')
def analytics(db=Depends(get_db),user=Depends(roles('teacher','student'))):
    rows=list(db.scalars(session_query(user).order_by(TrainingSession.assigned_at.desc())))
    stopped=set(db.scalars(select(Event.session_id).where(Event.session_id.in_([r.id for r in rows]),Event.kind=='teacher_stopped')))
    complete=[r for r in rows if r.status in {'submitted','reviewed'} and r.report and r.id not in stopped]
    scores=[score for r in complete if (score:=trusted_score(r.report)) is not None]
    reactions=[r.report['reaction_seconds'] for r in complete if r.report.get('reaction_seconds') is not None]
    aggregate={}
    for row in complete:
        for c in trusted_criteria(row.report):
            # An authored criterion ID can be reused with a different label in a
            # later scenario version. Keep unlike findings separate in analytics.
            key=(c['id'],c['title'])
            stat=aggregate.setdefault(key,{'id':c['id'],'title':c['title'],'failed':0,'total':0})
            stat['total']+=1;stat['failed']+=int(c['status']=='fail')
    criteria=sorted(aggregate.values(),key=lambda c:(-c['failed'],-c['failed']/c['total'],c['title'],c['id']))
    return {'total_sessions':len(rows),'completed_sessions':len(complete),'active_sessions':sum(r.status=='active' for r in rows),
      'scored_sessions':len(scores),'stopped_sessions':sum(r.status=='stopped' or r.id in stopped for r in rows),
      'pending_review_sessions':len(complete)-len(scores),
      'average_score':round(sum(scores)/len(scores),2) if scores else None,
      'average_reaction_seconds':round(sum(reactions)/len(reactions),2) if reactions else None,
      'criteria':criteria,'recent_sessions':[session_json(db,r,user) for r in rows[:8]]}
