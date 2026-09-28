"""Bounded three-field draft generation experiment; source facts stay immutable."""
import json
from pathlib import Path
import time
import urllib.request

SYSTEM = '''Ты пишешь учебные сценарии тренажёра ДДС на русском языке. Диспетчер уже получил карточку и делает исходящий доклад.
Верни ТОЛЬКО JSON с тремя строками: title, card_description, contact_reply.
Правила:
1. title — краткое понятное название происшествия, 3–6 слов. Без слов JSON, ScenarioPatch, schema, сценарий, карточка.
2. card_description — полное фактическое описание: адрес и ВСЕ известные факты входа. Сохрани адрес, числа, имена и отрицания БУКВАЛЬНО. Нельзя менять факты или дополнять их догадками.
3. contact_reply — одна короткая реплика принимающего доклад руководителя: он подтверждает получение информации, но НЕ придумывает распоряжений, отправленных служб и новых событий.
4. Не обращайся к гражданину. Не задавай вопросы. Не создавай новых телефонов или нормативов.
Пример входа: {"address":"улица Мира, дом 7","facts":"Повреждение водопровода. Пострадавших нет. Аварийная бригада пока не направлена."}
Пример ответа: {"title":"Повреждение водопровода на улице Мира","card_description":"Адрес: улица Мира, дом 7. Повреждение водопровода. Пострадавших нет. Аварийная бригада пока не направлена.","contact_reply":"Доклад принят. Информация получена."}
/no_think'''
CASES = [
 {'id':'water','address':'Москва, Дубнинская улица, дом 10','facts':'Повреждение водопровода. Вода поступает на проезжую часть. Пострадавших нет. Аварийная бригада пока не направлена.'},
 {'id':'tree','address':'Москва, улица Академика Королёва, дом 15','facts':'Дерево упало на припаркованный автомобиль. Проезд частично перекрыт. Наличие пострадавших неизвестно.'},
 {'id':'power','address':'Москва, улица Лесная, дом 22','facts':'Отключение электроснабжения в 3 жилых домах. В лифте находятся 2 человека. Аварийная служба уведомлена.'},
]


def main():
 result={'prompt':SYSTEM,'model':'qwen3-1.7b','cases':[],'note':'Synthetic convenience sample, teacher approval remains mandatory.'}
 for case in CASES:
  data={k:v for k,v in case.items() if k!='id'}
  payload={'model':'qwen3-1.7b','messages':[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(data,ensure_ascii=False)}], 'temperature':0,'max_tokens':400,'stream':False,'response_format':{'type':'json_object'},'chat_template_kwargs':{'enable_thinking':False}}
  start=time.monotonic()
  raw=json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:11434/v1/chat/completions',json.dumps(payload).encode(),{'Content-Type':'application/json'}),timeout=60))
  content=raw['choices'][0]['message']['content']; parsed=json.loads(content)
  checks={'keys_and_types':set(parsed)=={'title','card_description','contact_reply'} and all(isinstance(v,str) and v for v in parsed.values()),'literal_address':case['address'] in parsed.get('card_description',''),'all_literal_facts':all(s.strip() in parsed.get('card_description','') for s in case['facts'].split('.') if s.strip()),'no_schema_title':not any(t in parsed.get('title','').lower() for t in ('schema','json','scenario','сценарий','карточка'))}
  row={'input':case,'output':parsed,'latency_seconds':round(time.monotonic()-start,3),'checks':checks,'passed':all(checks.values()),'finish_reason':raw['choices'][0]['finish_reason']}
  result['cases'].append(row); print(row,flush=True)
 Path('docs/local-ai-generation-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
