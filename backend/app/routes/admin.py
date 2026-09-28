import json
import os
import time
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import select, func, delete
from ..auth import get_db, roles, public_user, password_hash
from ..models import User, TrainingSession, Audit, AuthSession, now
from ..schemas import UserInput, ActiveInput
from ..common import audit
from ..db import Base

router=APIRouter(prefix='/admin',tags=['admin'],dependencies=[Depends(roles('admin'))])


@router.get('/status')
def status(request:Request,db=Depends(get_db),user=Depends(roles('admin'))):
    folder=request.app.state.settings.backup_dir
    backups=[]
    if folder.exists():
        for f in sorted(folder.glob('dds-backup-*'),reverse=True)[:30]:
            if f.is_file() and f.suffix in {'.sqlite3','.json'}: backups.append({'filename':f.name,'bytes':f.stat().st_size})
    return {'users_count':db.scalar(select(func.count()).select_from(User).where(User.username!='__seed__')),
      'sessions_count':db.scalar(select(func.count()).select_from(TrainingSession)),
      'audit_count':db.scalar(select(func.count()).select_from(Audit)),
      'database_backend':request.app.state.engine.dialect.name,'ai_mode':'rules','backup_files':backups,
      'uptime_seconds':round(time.monotonic()-request.app.state.started_monotonic,2)}


@router.get('/audit')
def audit_list(db=Depends(get_db),user=Depends(roles('admin'))):
    rows=db.execute(select(Audit,User.name).outerjoin(User,Audit.actor_id==User.id).order_by(Audit.at.desc()).limit(500))
    return [{'id':a.id,'actor_name':name or 'Система','action':a.action,'entity_type':a.entity_type,'entity_id':a.entity_id,'at':a.at,'details':a.details} for a,name in rows]


@router.post('/users')
def create_user(body:UserInput,request:Request,db=Depends(get_db),user=Depends(roles('admin'))):
    with request.app.state.mutation_lock:
        if body.username=='__seed__' or db.scalar(select(User).where(User.username==body.username)):
            raise HTTPException(409,'Логин уже занят')
        data=body.model_dump();password=data.pop('password');row=User(**data,password_hash=password_hash(password))
        db.add(row);db.flush();audit(db,user,'user_created','user',row.id,{'role':row.role});db.commit();return public_user(row)


@router.patch('/users/{user_id}')
def update_user(user_id:str,body:ActiveInput,request:Request,db=Depends(get_db),user=Depends(roles('admin'))):
    with request.app.state.mutation_lock:
        row=db.get(User,user_id)
        if not row or row.username=='__seed__':raise HTTPException(404,'Учётная запись не найдена')
        if row.id==user.id and not body.active:raise HTTPException(409,'Нельзя заблокировать собственную учётную запись')
        row.active=body.active
        if not body.active:db.execute(delete(AuthSession).where(AuthSession.user_id==row.id))
        audit(db,user,'user_active_changed','user',row.id,{'active':body.active});db.commit();return public_user(row)


@router.post('/backup')
def backup(request:Request,db=Depends(get_db),user=Depends(roles('admin'))):
    with request.app.state.mutation_lock:
        folder=request.app.state.settings.backup_dir
        folder.mkdir(parents=True,exist_ok=True)
        stamp=now();stem='dds-backup-'+stamp.replace(':','-')+'-'+uuid4().hex[:8]
        engine=request.app.state.engine
        suffix='.sqlite3' if engine.dialect.name=='sqlite' else '.json'
        path=folder/(stem+suffix);temp=folder/(stem+'.tmp')
        try:
            fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
            if engine.dialect.name=='sqlite':
                import sqlite3
                raw=engine.raw_connection()
                try:
                    with sqlite3.connect(temp) as destination:raw.driver_connection.backup(destination)
                finally:raw.close()
            else:
                # Portable logical backup in a consistent repeatable-read snapshot.
                with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
                    with connection.begin():
                        tables={table.name:[dict(r) for r in connection.execute(select(table)).mappings()] for table in Base.metadata.sorted_tables if table.name!='auth_sessions'}
                temp.write_text(json.dumps({'format':'dds-logical-backup-v1','created_at':stamp,'tables':tables},ensure_ascii=False))
            os.replace(temp,path)
        except Exception:
            temp.unlink(missing_ok=True)
            raise HTTPException(500,'Не удалось создать резервную копию. Проверьте доступ к локальному каталогу')
        audit(db,user,'backup_created','backup',path.name,{'bytes':path.stat().st_size});db.commit()
        return {'filename':path.name,'created_at':stamp,'bytes':path.stat().st_size}
