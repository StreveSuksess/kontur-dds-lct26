import json
import secrets
from uuid import uuid5, NAMESPACE_DNS
from sqlalchemy import select
from .auth import password_hash, password_matches
from .models import User, Scenario, now

SEED_OWNER=str(uuid5(NAMESPACE_DNS,'dds.local.seed.owner'))


def seed_database(db,settings):
    if not settings.demo_mode:
        for user in db.scalars(select(User).where(User.username.in_(['teacher','student','admin','student_water','student_bridge','student_lift']))):
            if password_matches('Demo112!', user.password_hash):
                raise ValueError('This database contains demo passwords. Use a fresh DATABASE_URL for production or rotate demo credentials before disabling DEMO_MODE.')
    if settings.demo_mode:
        users=[('teacher','Марина Сергеевна · преподаватель','teacher','Учебная ДДС'),('student','Алексей · учебный АРМ 01','student','Учебная ДДС'),('admin','Администратор учебного контура','admin','Учебная ДДС'),('student_water','Елена · учебный АРМ 02','student','Мосводоканал'),('student_bridge','Игорь · учебный АРМ 03','student','Гормост'),('student_lift','Ольга · учебный АРМ 04','student','Мослифт')]
        for username,name,role,service in users:
            if not db.scalar(select(User).where(User.username==username)):
                db.add(User(username=username,name=name,role=role,service=service,group_name='Группа 01',password_hash=password_hash('Demo112!')))
        db.flush()
    elif settings.bootstrap_admin_password and not db.scalar(select(User).where(User.role=='admin')):
        if len(settings.bootstrap_admin_password)<12:
            raise ValueError('BOOTSTRAP_ADMIN_PASSWORD must contain at least 12 characters')
        db.add(User(username='admin',name='Администратор',role='admin',service='',group_name='',password_hash=password_hash(settings.bootstrap_admin_password)))
        db.flush()
    # The seed owner cannot authenticate. Templates carry no production account credentials.
    if not db.get(User,SEED_OWNER):
        db.add(User(id=SEED_OWNER,username='__seed__',name='Библиотека учебных шаблонов',role='teacher',active=False,service='',group_name='',password_hash=password_hash(secrets.token_urlsafe(40))))
        db.flush()
    path=settings.data_dir/'scenarios.json'
    if path.exists():
        for item in json.loads(path.read_text()):
            sid=str(uuid5(NAMESPACE_DNS,'dds.local.seed.'+item['key']))
            if not db.get(Scenario,sid):
                data={k:v for k,v in item.items() if k!='key'}
                db.add(Scenario(id=sid,owner_id=SEED_OWNER,is_seed=True,status='approved',version=1,data=data,created_at=now(),updated_at=now()))
    db.commit()
