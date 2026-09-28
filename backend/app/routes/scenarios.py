import copy
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import select, or_
from ..auth import get_db, roles
from ..models import Scenario, now
from ..schemas import ScenarioInput, GenerateInput
from ..common import scenario_json, visible_scenario, audit
from ..ai import generate_patch, ModelUnavailable

router=APIRouter(prefix='/scenarios',tags=['scenarios'],dependencies=[Depends(roles('teacher'))])


def validate_approval(data):
    if not data['contacts'] or not data['expected_statuses'] or not data['required_facts'] or not data['reference_response'].strip():
        raise HTTPException(422,'Для утверждения нужны контакты, действия, смысловые критерии и эталонный ответ')
    if len({c['phone'] for c in data['contacts']})!=len(data['contacts']) or len({c['id'] for c in data['contacts']})!=len(data['contacts']):
        raise HTTPException(422,'Номера и идентификаторы контактов должны быть уникальны')
    if len({f['id'] for f in data['required_facts']})!=len(data['required_facts']):
        raise HTTPException(422,'Идентификаторы критериев должны быть уникальны')
    contact_ids={contact['id'] for contact in data['contacts']}
    for fact in data['required_facts']:
        if set(fact.get('confirmed_by_contact_ids',[]))-contact_ids:
            raise HTTPException(422,'Критерий ссылается на отсутствующий подтверждающий контакт')
    if data['completion_limit_seconds'] < data['response_limit_seconds']:
        raise HTTPException(422,'Время обработки не может быть меньше времени реакции')
    if any(not str(value).strip() for value in [data['title'],data['objective'],data['card']['address'],data['card']['description']]):
        raise HTTPException(422,'Карточка, цель и название не могут состоять из пробелов')


@router.get('')
def list_scenarios(db=Depends(get_db),user=Depends(roles('teacher'))):
    rows=db.scalars(select(Scenario).where(or_(Scenario.owner_id==user.id,Scenario.is_seed.is_(True))).order_by(Scenario.created_at.desc()))
    return [scenario_json(row) for row in rows]


@router.post('')
def create_scenario(body:ScenarioInput,request:Request,db=Depends(get_db),user=Depends(roles('teacher'))):
    with request.app.state.mutation_lock:
        row=Scenario(owner_id=user.id,data=body.model_dump(),status='draft')
        db.add(row);db.flush();audit(db,user,'scenario_created','scenario',row.id);db.commit()
        return scenario_json(row)


# Static path must precede /{scenario_id}.
@router.post('/generate')
def generate_scenario(body:GenerateInput,request:Request,db=Depends(get_db),user=Depends(roles('teacher'))):
    catalog=request.app.state.classifier
    item=next((x for x in catalog.get('items',[]) if x['code']==body.incident_code),None)
    if not item: raise HTTPException(404,'Код отсутствует в загруженном классификаторе')
    # This adapter is deliberately labelled templates. No network/model call is implied.
    data={'title':f"Учебная карточка: {item['label']}",'description':body.instructions or 'Черновик из локального шаблона. Проверьте факты перед утверждением.',
      'service':body.service,'difficulty':body.difficulty,'objective':'Открыть карточку, принять её и передать сведения ответственному должностному лицу. Зафиксировать полученное подтверждение.',
      'card':{'number':'УЧ-НОВАЯ','address':'Учебная улица, дом 10','description':f"Учебное происшествие: {item['label']}. Преподавателю необходимо уточнить обстоятельства.",'incident_type':item['label'],'incident_code':item['code'],'caller_name':'Учебный заявитель','caller_phone':'0000','casualties':'unknown','services':[body.service]},
      'contacts':[{'id':'contact-main','name':'Дежурный учебной службы','role':'Ответственное должностное лицо','phone':'2001','greeting':'Учебный дежурный. Передайте сведения.','reply':'Информация принята. В рамках упражнения бригада направлена к месту.'}],
      'expected_statuses':['accepted','responding'],'required_facts':[{'id':'dispatch','label':'Направление бригады подтверждено','patterns':['Бригада направлена','Аварийная группа выехала'],'critical':True}],
      'reference_response':'Карточка принята. Информация передана должностному лицу. Бригада направлена к месту.',
      'response_limit_seconds':30,'completion_limit_seconds':180,
      'source_note':f"Генератор: templates (локальный шаблон, без нейросети). Тип {item['code']}, строка {item['source_row']}, {catalog.get('version','')}. Учебные факты и маршрутизация заданы автором; требуется проверка преподавателя."}
    settings = request.app.state.settings
    if settings.ai_mode == 'local' and settings.ai_endpoint:
        try:
            patch, latency = generate_patch(settings, body, item)
            candidate = copy.deepcopy(data)
            candidate['title'] = patch.title
            candidate['card']['description'] = patch.card_description
            candidate['contacts'][0]['reply'] = patch.contact_reply + ' По условиям упражнения бригада направлена к месту.'
            candidate['source_note'] = (f"Генератор: local_llm, {settings.ai_model}, {latency} с. Тип {item['code']}, "
                                      f"строка {item['source_row']}, {catalog.get('version','')}. Синтетический черновик; факты, эталон и рубрику проверяет преподаватель.")
            ScenarioInput.model_validate(candidate)
            data = candidate
        except (ModelUnavailable, ValueError):
            data['source_note'] += ' Локальная модель не вернула допустимый черновик; применён резервный шаблон.'
    validated=ScenarioInput.model_validate(data)
    return create_scenario(validated,request,db,user)


@router.get('/{scenario_id}')
def get_scenario(scenario_id:str,db=Depends(get_db),user=Depends(roles('teacher'))):
    return scenario_json(visible_scenario(db,scenario_id,user))


@router.put('/{scenario_id}')
def update_scenario(scenario_id:str,body:ScenarioInput,request:Request,db=Depends(get_db),user=Depends(roles('teacher'))):
    with request.app.state.mutation_lock:
        row=visible_scenario(db,scenario_id,user,edit=True)
        row.data=body.model_dump();row.version+=1;row.status='draft';row.updated_at=now()
        audit(db,user,'scenario_updated','scenario',row.id,{'version':row.version});db.commit()
        return scenario_json(row)


@router.post('/{scenario_id}/approve')
def approve(scenario_id:str,request:Request,db=Depends(get_db),user=Depends(roles('teacher'))):
    with request.app.state.mutation_lock:
        row=visible_scenario(db,scenario_id,user,edit=True)
        validate_approval(row.data)
        row.status='approved';row.updated_at=now();audit(db,user,'scenario_approved','scenario',row.id,{'version':row.version});db.commit()
        return scenario_json(row)


@router.post('/{scenario_id}/duplicate')
def duplicate(scenario_id:str,request:Request,db=Depends(get_db),user=Depends(roles('teacher'))):
    with request.app.state.mutation_lock:
        original=visible_scenario(db,scenario_id,user)
        data=copy.deepcopy(original.data);data['title']=data['title'][:190]+' · копия'
        row=Scenario(owner_id=user.id,data=data,status='draft')
        db.add(row);db.flush();audit(db,user,'scenario_duplicated','scenario',row.id,{'source_id':original.id});db.commit()
        return scenario_json(row)


@router.post('/{scenario_id}/archive')
def archive(scenario_id:str,request:Request,db=Depends(get_db),user=Depends(roles('teacher'))):
    with request.app.state.mutation_lock:
        row=visible_scenario(db,scenario_id,user,edit=True)
        row.status='archived';row.updated_at=now();audit(db,user,'scenario_archived','scenario',row.id);db.commit()
        return scenario_json(row)
