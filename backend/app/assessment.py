"""Transparent local rubric. Heuristics are limited; uncertain semantics stay reviewable.

The assessor does not execute instructions in learner text or read live services.
Rules are authored training criteria, not official emergency-service regulations.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from .models import now
from .schemas import STATUS_LABELS

SOURCE = 'Авторская учебная рубрика утверждённой версии сценария; не официальный регламент'


@dataclass
class Detection:
    status: str
    explanation: str
    evidence: str = ''


def normalize(text: str) -> str:
    text=unicodedata.normalize('NFKC',text).lower().replace('ё','е')
    # Normalize obvious look-alike characters only inside mixed Cyrillic/Latin words.
    trans=str.maketrans('aceopxyABCEHKMOPTXY','асеорхуАВСЕНКМОРТХУ')
    text=re.sub(r'[\w]+',lambda m:m[0].translate(trans) if re.search('[а-я]',m[0]) and re.search('[a-zA-Z]',m[0]) else m[0],text)
    text=re.sub(r'\bул(?:\.|\b)\s*','улица ',text)
    return re.sub(r'\s+',' ',text).strip()


def detect_dispatch(text: str) -> Detection:
    norm=normalize(text)
    # A very small transparent dictionary, not a general spelling model.
    norm=re.sub(r'\bнапровлена\b','направлена',norm)
    norm=re.sub(r'\bавар\.', 'аварийная', norm)
    norm=re.sub(r'\bнапр\.', 'направлена', norm)
    if not norm: return Detection('fail','Комментарий не содержит подтверждения направления бригады.')
    clauses=re.split(r'(?<=[.!?;])\s+|\n',norm)
    outcomes=[]
    subject=r'(?:бригад\w*|аварийн\w* групп\w*|экипаж\w*)'
    verb=r'(?:направлен(?:а|о|ы)?\b|отправлен(?:а|о|ы)?\b|направил\w*|отправил\w*|выехал\w*|выдвинул\w*)'
    previous_brigade=False
    for clause in clauses:
        if re.search(r'\b(?:направление|выезд) (?:бригады )?отмен[её]н[оа]?\b',clause):
            outcomes.append(('fail',clause));continue
        if not re.search(verb,clause): continue
        if not re.search(subject,clause) and not re.search(r'\b(?:она|они)\b',clause): continue
        if re.search(r'(игнорируй|поставь .*балл|считай .*направлен|role.{0,6}system|<system)',clause):
            continue
        has_subject=bool(re.search(subject,clause))
        if not has_subject and not (previous_brigade and re.search(r'актуальн|\d{1,2}:\d{2}',clause)):
            outcomes.append(('review',clause));continue
        previous_brigade=has_subject or previous_brigade
        if '?' in clause:
            outcomes.append(('fail',clause));continue
        if re.search(r'вероятно|возможно|кажется|предполож|подтверждения нет|не уверен',clause):
            outcomes.append(('review',clause));continue
        if re.search(r'(будет|будут|планиру\w*|собира\w*|поручено|поручил\w*|долж\w*|необходимо|намерен\w*)[^.!?]{0,65}'+verb,clause):
            outcomes.append(('fail',clause));continue
        # A dispatch of a document is not a dispatch of a brigade mentioned elsewhere.
        if re.search(r'карточк\w* (?:была )?(?:отправлен|направлен)',clause) and not re.search(subject+r'.{0,20}'+verb,clause):
            continue
        neg=re.search(r'\bне\b(?:\s+\w+){0,3}\s+'+verb,clause)
        if neg and not re.search(r'(неверно|неправда),? что',clause):
            outcomes.append(('fail',clause));continue
        outcomes.append(('pass',clause))
    if not outcomes:
        if re.search(r'карточк\w* (?:была )?(?:отправлен|направлен)',norm):
            return Detection('fail','Передача карточки не подтверждает направление бригады.',text)
        if re.search(r'игнорируй|поставь .*балл|считай .*направлен|<system',norm):
            return Detection('fail','Инструкция оценщику не сообщает о выполненном направлении.',text)
        if re.search(r'направить|отправить|направление.{0,20}отменено',norm):
            return Detection('fail','Поручение, намерение или отмена не подтверждают выполненное направление.',text)
        return Detection('review' if norm else 'fail','Не удалось уверенно определить выполненное направление. Нужна проверка смысла преподавателем.',text)
    statuses={v[0] for v in outcomes}
    if 'pass' in statuses and 'fail' in statuses:
        if outcomes[-1][0]=='pass' and re.search(r'после|затем|актуальн|\d{1,2}:\d{2}',outcomes[-1][1]):
            return Detection('pass','Учтено явно обозначенное обновление состояния.',outcomes[-1][1])
        return Detection('review','В тексте есть конфликтующие утверждения о направлении; нужно уточнение.',text)
    state=outcomes[-1][0]
    return Detection(state,{'pass':'Найдено сообщение о выполненном направлении.','fail':'Отрицание, вопрос или будущее не подтверждают выполненное направление.','review':'Высказана неопределённость либо неясен субъект действия.'}[state],outcomes[-1][1])


def detect_fact(text: str, fact: dict) -> Detection:
    norm=normalize(text)
    patterns=[normalize(p) for p in fact.get('patterns',[])]
    if not norm: return Detection('fail','Требуемое содержание не введено.')
    if any(re.search(r'направ|выех|отправ',p) for p in patterns) and any(re.search(r'бригад|групп|экипаж',p) for p in patterns):
        return detect_dispatch(text)
    # Literal alternatives are safe strings, never executable regex supplied by teachers.
    for pattern in patterns:
        pos=norm.find(pattern)
        if pos<0: continue
        preceding=norm[max(0,pos-35):pos]
        sentence=norm[max(norm.rfind('.',0,pos),norm.rfind('!',0,pos))+1:]
        sentence=re.split(r'[.!]',sentence,1)[0]
        if re.search(r'(игнорируй|поставь .*балл|считай|<system|role.{0,6}system)',sentence):
            continue
        if '?' in sentence or re.search(r'\bне\b.{0,18}$',preceding):
            return Detection('fail','Найдено отрицание или вопрос вместо подтверждения.',sentence)
        if re.search(r'вероятно|возможно|кажется|неизвестно',sentence):
            return Detection('review','Сообщение не подтверждено однозначно.',sentence)
        return Detection('pass','Найдена одна из утверждённых текстовых формулировок после нормализации; это ограниченная проверка по правилам.',pattern)
    return Detection('review','Правила не нашли уверенного соответствия. Перефраз или отсутствие факта должен проверить преподаватель.',text)



def contact_confirmation(fact: dict, events: list[dict]) -> tuple[Detection, list[str]]:
    """Require a fact-confirming reply before the first positive learner assertion.

    Only server-recorded connected calls to approved contacts participate. The
    initial greeting cannot confirm anything: the reply must follow a learner
    message on that same still-open call. Contact text is evidence of provenance,
    never learner content. Later calls cannot retroactively justify an assertion.
    Event-list order is the persisted server sequence, not client timing claims.
    """
    allowed=set(fact.get('confirmed_by_contact_ids',[]))
    calls={}
    confirmations=[]
    observed=[]
    for event in events:
        payload=event.get('payload',{})
        kind=event['kind']
        call_id=payload.get('call_id')
        if kind=='call_started' and payload.get('connected') is True and payload.get('contact_id') in allowed and call_id:
            calls[call_id]={'start':event,'trainee':None,'ended':False}
            observed.append(event['id'])
        # Evaluate the claim before recording its outgoing message: its own future
        # reply has not yet happened and therefore cannot justify that claim.
        if kind in {'status_changed','trainee_message'}:
            text=payload.get('comment','') if kind=='status_changed' else payload.get('text','')
            assertion=detect_fact(text,fact)
            if assertion.status=='pass':
                latest=confirmations[-1] if confirmations else None
                confirmed=latest if latest and latest[0]=='pass' else None
                if confirmed:
                    return Detection('pass','Ученик подтвердил факт после содержательного ответа разрешённого учебного контакта. Порядок проверен по журналу событий.',assertion.evidence),confirmed[1]+[event['id']]
                ambiguous=latest if latest and (latest[0]=='review' or any(item[0]=='pass' for item in confirmations)) else None
                if ambiguous:
                    return Detection('review','До утверждения ученика получен ответ разрешённого контакта, но правила не подтверждают его содержание однозначно. Преподавателю нужно проверить ответ и факт.',assertion.evidence),ambiguous[1]+[event['id']]
                return Detection('fail','Факт записан учеником до подтверждающего ответа разрешённого контакта. Приветствие, ответ другого контакта и последующий звонок не подтверждают уже внесённое утверждение.',assertion.evidence),list(dict.fromkeys(observed+[event['id']]))
        call=calls.get(call_id)
        if not call or call['ended']:
            continue
        if kind=='trainee_message' and str(payload.get('text','')).strip():
            call['trainee']=event
            observed.append(event['id'])
        elif kind=='contact_message':
            observed.append(event['id'])
            if call['trainee'] and str(payload.get('text','')).strip():
                reply=detect_fact(payload['text'],fact)
                confirmations.append((reply.status,[call['start']['id'],call['trainee']['id'],event['id']]))
        elif kind=='call_ended':
            call['ended']=True
    return Detection('review','Нет отдельного однозначного утверждения ученика после ответа контакта. Содержание ответа не засчитывается за ученика.'),observed

def assess(snapshot: dict, events: list[dict], started_at: str | None, finished_at: str, stopped=False) -> dict:
    duration=max(0,(datetime.fromisoformat(finished_at)-datetime.fromisoformat(started_at)).total_seconds()) if started_at else 0
    criteria=[]
    def criterion(cid,title,category,state,max_points,actual,expected,explanation,evidence=(),critical=False):
        # Review earns no automatically confirmed points; it is visibly pending, not a final zero.
        criteria.append({'id':cid,'title':title,'category':category,'status':state,'points':max_points if state=='pass' else 0,'max_points':max_points,'critical':critical,
          'actual':str(actual),'expected':str(expected),'explanation':explanation,'evidence_ids':list(evidence),'source':SOURCE})
    opened=next((e for e in events if e['kind']=='card_opened'),None)
    reaction=opened['elapsed_seconds'] if opened else None
    offline=[e for e in events if e['kind']=='connection_restored' and e['payload'].get('offline_seconds',0)>0]
    reaction_state='review' if offline else ('pass' if reaction is not None and reaction<=snapshot['response_limit_seconds'] else 'fail')
    criterion('reaction','Открытие карточки','timing',reaction_state,15,f'{reaction:.2f} с' if reaction is not None else 'Карточка не открыта',f"≤ {snapshot['response_limit_seconds']} с",'Время до первого card_opened от начала попытки. При разрыве сети нужна проверка серверного времени доставки.',[opened['id']] if opened else [])
    first_update=next((e for e in events if e['kind']=='status_changed' and str(e['payload'].get('comment','')).strip()),None)
    first_update_seconds=first_update['elapsed_seconds'] if first_update else None
    first_update_state='review' if offline or stopped else ('pass' if first_update_seconds is not None and first_update_seconds<=snapshot['completion_limit_seconds'] else 'fail')
    criterion('duration','Первый статус с текстом','timing',first_update_state,10,
              f'{first_update_seconds:.2f} с' if first_update_seconds is not None else 'Статус с текстом не сохранён',
              f"≤ {snapshot['completion_limit_seconds']} с",
              'Время до первого сохранённого статуса с непустым комментарием от начала попытки; завершение работ может занять часы или дни. При разрыве сети требуется проверка.',
              [first_update['id']] if first_update else [])
    statuses=[e for e in events if e['kind']=='status_changed']
    actual=[e['payload']['status'] for e in statuses]
    expected=snapshot['expected_statuses']
    sequence_ok=actual==expected
    criterion('workflow','Действия с карточкой','workflow','pass' if sequence_ok else 'fail',25,' → '.join(STATUS_LABELS.get(x,x) for x in actual) or 'Нет действий',' → '.join(STATUS_LABELS.get(x,x) for x in expected),'Сравнение с последовательностью конкретного упражнения. Текст не заменяет событие изменения статуса.',[e['id'] for e in statuses],True)
    calls=[e for e in events if e['kind']=='call_started']
    connected=[e for e in calls if e['payload'].get('connected')]
    messages=[e for e in events if e['kind']=='trainee_message']
    relevant_messages=[e for e in messages if any(e['payload'].get('call_id')==x['payload'].get('call_id') for x in connected)]
    call_ok=bool(connected and relevant_messages)
    criterion('outgoing_call','Исходящий доклад должностному лицу','communication','pass' if call_ok else 'fail',15,'Доклад передан по учебному номеру' if call_ok else 'Нет завершённого текстового доклада адресату','Соединение с контактом и собственный доклад','Проверяется учебный программный телефон, не реальная SIP-связь.',[e['id'] for e in calls+relevant_messages],True)
    texts=[(e,e['payload'].get('comment','') if e['kind']=='status_changed' else e['payload'].get('text','')) for e in events if e['kind'] in {'status_changed','trainee_message'}]
    joined='\n'.join(t for _,t in texts if t)
    facts=snapshot.get('required_facts',[])
    for i,fact in enumerate(facts):
        max_points=35//len(facts)+(1 if i<35%len(facts) else 0)
        found=detect_fact(joined,fact)
        evidence_text=found.evidence or joined
        matching=[(e,t) for e,t in texts if t and normalize(evidence_text) in normalize(t)]
        ids=[e['id'] for e,t in matching] if matching else [e['id'] for e,t in texts if t]
        actual='\n'.join(t for _,t in matching) if matching else evidence_text
        expectation=' / '.join(fact['patterns'])
        if fact.get('confirmed_by_contact_ids'):
            contacts={c['id']:c for c in snapshot.get('contacts',[])}
            labels=[f"{contacts[cid]['name']} ({contacts[cid]['phone']})" if cid in contacts else cid for cid in fact['confirmed_by_contact_ids']]
            expectation+='; после подтверждения от одного из контактов: '+', '.join(labels)
            # Never upgrade a failed/ambiguous learner statement with a contact reply.
            if found.status=='pass':
                confirmation,confirmation_ids=contact_confirmation(fact,events)
                found=confirmation
                ids=confirmation_ids
        criterion('fact:'+fact['id'],fact['label'],'content',found.status,max_points,actual[:2000] or 'Нет текста',expectation,found.explanation,ids,fact.get('critical',False))
    # Approval prevents empty facts; retain total=100 for imported snapshots nonetheless.
    if not facts:
        criterion('content','Содержание доклада','content','review',35,joined[:1200],'Утверждённые смысловые критерии','У сценария нет критериев, требуется преподаватель.',[e['id'] for e,t in texts if t])
    misspellings=re.findall(r'\b(?:принета|напровлена|сообшение|проишествие)\b',normalize(joined))
    criterion('grammar','Понятность ручного текста','grammar','review' if misspellings else 'pass',0,', '.join(misspellings) if misspellings else 'Очевидных ошибок из локального словаря не найдено','Понятный текст; факты оцениваются отдельно','Ограниченная словарная проверка не является полной проверкой русского языка. Замечания не отменяют правильность фактов.',[e['id'] for e,t in texts if t])
    hints=[e for e in events if e['kind']=='hint_used']
    if hints:
        criterion('hints','Использование учебных подсказок','workflow','review',0,f'{len(hints)} подсказок','Учитывать условия практики при разборе','Результат с подсказками нельзя считать самостоятельной аттестацией.',[e['id'] for e in hints])
    if stopped:
        for c in criteria:
            if c['status']=='fail':
                c['status']='review'
                c['explanation']+=' Попытку прервал преподаватель: невыполненная часть требует ручного разбора.'
    score=sum(c['points'] for c in criteria)
    review=any(c['status']=='review' for c in criteria) or stopped
    failures=[c for c in criteria if c['status']=='fail']
    strengths=[c['title'] for c in criteria if c['status']=='pass' and c['max_points']>0]
    recommendations=[f"Повторить: {c['title'].lower()}. {c['explanation']}" for c in failures]
    if review: recommendations.append('Преподавателю: проверить неоднозначные критерии перед утверждением результата.')
    return {'score':score,'max_score':100,'requires_review':review,'critical_errors':sum(c['critical'] for c in failures),
      'summary':('Попытка остановлена преподавателем. ' if stopped else '')+('Предварительный разбор: есть критерии для проверки.' if review else 'Автоматический разбор по утверждённой учебной рубрике.'),
      'mode':'rules','reaction_seconds':reaction,'first_update_seconds':first_update_seconds,'duration_seconds':round(duration,3),'criteria':criteria,'strengths':strengths,
      'recommendations':recommendations,'teacher_review':None,'generated_at':now()}
