"""Causal contract of a particular teacher-authored exercise, not real dispatch rules."""
import copy
import pytest
from app.assessment import contact_confirmation, assess, detect_dispatch
from app.schemas import FactInput

FACT={'id':'dispatch','label':'Направление','patterns':['Бригада направлена'],'critical':True,'confirmed_by_contact_ids':['allowed']}


def event(identifier,kind,**payload):
    return {'id':identifier,'kind':kind,'elapsed_seconds':0,'payload':payload}


def connection(call='call',contact='allowed'):
    return [event('start-'+call,'call_started',call_id=call,contact_id=contact,connected=True),
            event('greeting-'+call,'contact_message',call_id=call,text='Бригада направлена — это пример фразы, представьтесь.')]


def exchange(call='call',reply='Бригада направлена.'):
    return [event('request-'+call,'trainee_message',call_id=call,text='Сообщите результат реагирования.'),
            event('answer-'+call,'contact_message',call_id=call,text=reply)]


def claim(identifier='claim'):
    return event(identifier,'status_changed',status='responding',comment='Бригада направлена.')


def test_confirmed_fact_contains_call_request_reply_and_learner_evidence():
    outcome,evidence=contact_confirmation(FACT,connection()+exchange()+[claim()])
    assert outcome.status=='pass'
    assert evidence==['start-call','request-call','answer-call','claim']


@pytest.mark.parametrize('events',[
    [claim()],
    connection()+[claim()],  # even a fact-containing greeting is not confirmation
    connection()+[event('request','trainee_message',call_id='call',text='Бригада направлена.')]+exchange()+[claim()],
    connection(contact='different')+exchange()+[claim()],
    connection()+[event('other-request','trainee_message',call_id='another',text='Проверьте.')]+[event('answer','contact_message',call_id='call',text='Бригада направлена.'),claim()],
    connection()+[claim()]+exchange()+[claim('later-claim')],
    connection()+[event('end','call_ended',call_id='call')]+exchange()+[claim()],
])
def test_premature_wrong_contact_greeting_and_wrong_call_do_not_pass(events):
    outcome,evidence=contact_confirmation(FACT,events)
    assert outcome.status=='fail'
    assert any(identifier in evidence for identifier in ['claim','request'])


def test_negative_or_uncertain_contact_response_does_not_confirm_fact():
    for reply,expected in [('Бригада не направлена.','fail'),('Возможно, бригада направлена.','review'),('Информация принята.','review')]:
        outcome,evidence=contact_confirmation(FACT,connection()+exchange(reply=reply)+[claim()])
        assert outcome.status==expected
        assert 'answer-call' in evidence


def test_later_negative_response_does_not_reuse_stale_positive_confirmation():
    events=connection()+exchange()+exchange(reply='Бригада не направлена.')+[claim()]
    assert contact_confirmation(FACT,events)[0].status=='review'


def test_any_approved_contact_can_confirm_but_learner_must_still_state_fact():
    fact={**FACT,'confirmed_by_contact_ids':['allowed','backup']}
    assert contact_confirmation(fact,connection(contact='backup')+exchange()+[claim()])[0].status=='pass'
    snapshot={'response_limit_seconds':30,'completion_limit_seconds':180,'expected_statuses':['responding'],'contacts':[{'id':'allowed','name':'Учебный дежурный','phone':'2001'}],'required_facts':[fact]}
    events=connection()+exchange()+[event('state','status_changed',status='responding',comment='Сведения получены.')]
    report=assess(snapshot,events,'2026-09-19T10:00:00+00:00','2026-09-19T10:01:00+00:00')
    assert next(c for c in report['criteria'] if c['id']=='fact:dispatch')['status']!='pass'


def test_confirmation_field_is_optional_and_validated():
    old=copy.deepcopy(FACT);old.pop('confirmed_by_contact_ids')
    assert FactInput.model_validate(old).confirmed_by_contact_ids==[]
    for values in [[''],['a'*81],['same','same'],list(map(str,range(11)))]:
        with pytest.raises(ValueError):FactInput.model_validate({**FACT,'confirmed_by_contact_ids':values})


@pytest.mark.parametrize('text',['Уточните направление бригады.','Запрашиваю сведения о направлении бригады.','Проверьте отправление бригады.'])
def test_dispatch_noun_or_request_does_not_assert_completed_action(text):
    assert detect_dispatch(text).status!='pass'
