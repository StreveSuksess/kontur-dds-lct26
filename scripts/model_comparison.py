#!/usr/bin/env python3
"""Research-only frozen local model comparison. Does not change application code."""
from __future__ import annotations
import argparse, collections, hashlib, json, math, platform, random, statistics, subprocess, threading, time, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'research/model-comparison'


def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def post(url,payload):
 request=urllib.request.Request(url+'/v1/chat/completions',json.dumps(payload,ensure_ascii=False).encode(),{'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)


def get(url):
 with urllib.request.urlopen(url,timeout=5) as response:return json.load(response)


def percentile(values,p):
 return sorted(values)[max(0,math.ceil(len(values)*p)-1)] if values else None


def summarize(rows):
 exact=[r for r in rows if r['exact']]
 pair_ok={pid:all(r['exact'] for r in rows if r['pair_id']==pid) for pid in {r['pair_id'] for r in rows}}
 return {'total':len(rows),'exact':len(exact),'exact_fraction':len(exact)/len(rows),'schema_valid':sum(r['schema_valid'] for r in rows),
  'both_pair_members_exact':sum(pair_ok.values()),'pairs_total':len(pair_ok),
  'false_satisfied':sum(r['gold']!='satisfied' and r.get('verdict')=='satisfied' for r in rows),
  'false_violated':sum(r['gold']=='satisfied' and r.get('verdict')=='violated' for r in rows),
  'unknown_predictions':sum(r.get('verdict')=='unknown' for r in rows),'api_errors':sum(bool(r.get('error')) for r in rows),
  'p50_seconds':round(statistics.median(r['latency_seconds'] for r in rows),3),'p95_seconds':round(percentile([r['latency_seconds'] for r in rows],.95),3),
  'max_seconds':max(r['latency_seconds'] for r in rows),'by_category':{cat:{'total':sum(r['category']==cat for r in rows),'exact':sum(r['category']==cat and r['exact'] for r in rows)} for cat in sorted({r['category'] for r in rows})},
  'confusion':dict(collections.Counter(r['gold']+' -> '+str(r.get('verdict','error')) for r in rows))}


def main():
 p=argparse.ArgumentParser();p.add_argument('--baseline-pid',type=int,required=True);p.add_argument('--candidate-pid',type=int,required=True);args=p.parse_args()
 prereg=json.loads((DATA/'preregistration.json').read_text())
 for file,digest in prereg['files'].items():assert sha(DATA/file)==digest, f'Frozen data changed: {file}'
 holdout=json.loads((DATA/'holdout.json').read_text());prompt=(DATA/'system-prompt.txt').read_text()
 order=[{**case,'pair_id':pair['pair_id'],'category':pair['category']} for pair in holdout['pairs'] for case in pair['cases']]
 random.Random(190926).shuffle(order)
 models=[{'name':'qwen3-1.7b','url':'http://127.0.0.1:11434','pid':args.baseline_pid,'path':ROOT/'models/local-ai/qwen3-1.7b-q4_k_m.gguf'},
 {'name':'qwen3-4b-research','url':'http://127.0.0.1:11437','pid':args.candidate_pid,'path':ROOT/'models/model-comparison/qwen3-4b-q4_k_m.gguf'}]
 result={'preregistration':prereg,'holdout':holdout,'system_prompt':prompt,'script_sha256':sha(__file__),
 'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'hardware':{'platform':platform.platform(),'processor':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
 'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),'target_i5_measured':False},
 'runtime':{'threads':4,'gpu_layers':0,'context':4096,'parallel':1,'quantization':'Q4_K_M','calls':'serial, alternating model order by case index; same sample order per model','production_service_restarted':False},'models':{},'rows':[]}
 peak={m['name']:0 for m in models};rss_samples=[];stop=threading.Event()
 def monitor():
  while not stop.is_set():
   output=subprocess.run(['ps','-p',','.join(str(m['pid']) for m in models),'-o','pid=,rss='],capture_output=True,text=True).stdout
   sample={'elapsed':round(time.perf_counter()-started,3)}
   for line in output.splitlines():
    pid,rss=map(int,line.split())
    for m in models:
     if m['pid']==pid:peak[m['name']]=max(peak[m['name']],rss*1024);sample[m['name']]=rss*1024
   rss_samples.append(sample);stop.wait(.5)
 started=time.perf_counter();thread=threading.Thread(target=monitor,daemon=True);thread.start()
 def payload(m,user):
  return {'model':m['name'],'messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps(user,ensure_ascii=False,separators=(',',':'))}],
   'temperature':.1,'top_p':.8,'top_k':20,'seed':190926,'max_tokens':256,'response_format':{'type':'json_object'},'chat_template_kwargs':{'enable_thinking':False},'cache_prompt':False}
 try:
  for m in models:
   result['models'][m['name']]={'health':get(m['url']+'/health'),'api_models':get(m['url']+'/v1/models'),'model_sha256':sha(m['path']),'model_bytes':m['path'].stat().st_size}
   # Warmup is unrelated to address/role/causal holdout and is not scored.
   warm={'criterion':'Учащийся произнёс слово «Здравствуйте».','reference':{},'journal_complete':True,'events':[{'id':'warm','sequence':1,'actor':'student','kind':'report','text':'Здравствуйте.'}]}
   begin=time.perf_counter();result['models'][m['name']]['warmup']=post(m['url'],payload(m,warm));result['models'][m['name']]['warmup_seconds']=round(time.perf_counter()-begin,3)
  for i,case in enumerate(order):
   for m in models if i%2==0 else reversed(models):
    begin=time.perf_counter();row={'case_id':case['id'],'pair_id':case['pair_id'],'category':case['category'],'model':m['name'],'gold':case['gold']['verdict'],'schema_valid':False,'exact':False}
    try:
     raw=post(m['url'],payload(m,case['input']));row['raw_response']=raw
     obj=json.loads(raw['choices'][0]['message']['content']);row['parsed']=obj
     ids={e['id'] for e in case['input']['events']}
     valid=(isinstance(obj,dict) and set(obj)=={'verdict','evidence_event_ids','reason'} and obj['verdict'] in {'satisfied','violated','unknown'} and isinstance(obj['reason'],str) and isinstance(obj['evidence_event_ids'],list) and all(isinstance(x,str) and x in ids for x in obj['evidence_event_ids']))
     row['schema_valid']=valid;row['verdict']=obj.get('verdict');row['exact']=valid and obj['verdict']==case['gold']['verdict']
    except Exception as error:row['error']=type(error).__name__+': '+str(error)
    row['latency_seconds']=round(time.perf_counter()-begin,3);result['rows'].append(row)
    print(len(result['rows']),case['id'],m['name'],row.get('verdict','ERROR'),row['exact'],row['latency_seconds'],flush=True)
    (DATA/'results.partial.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 finally:
  stop.set();thread.join(3)
 for m in models:
  name=m['name'];rows=[r for r in result['rows'] if r['model']==name]
  result['models'][name]['summary']=summarize(rows)
  result['models'][name]['peak_rss_bytes']=peak[name]
 result['rss_sampling']={'interval_seconds':.5,'method':'macOS ps RSS; shared mappings counted per process, not peak allocated or total machine memory','samples':len(rss_samples),'trace_path':'research/model-comparison/rss.json'}
 result['elapsed_seconds']=round(time.perf_counter()-started,3);result['completed_at']=time.strftime('%Y-%m-%dT%H:%M:%S%z')
 base=result['models'][models[0]['name']]['summary'];candidate=result['models'][models[1]['name']]['summary'];gate=prereg['research_gate']
 checks={'exact_at_least_44':candidate['exact']>=gate['min_exact'],'improvement_at_least_5':candidate['exact']-base['exact']>=gate['min_improvement_cases'],'zero_false_satisfied':candidate['false_satisfied']==0,'p95_at_most_15s':candidate['p95_seconds']<=gate['max_p95_seconds'],'rss_at_most_8GiB':peak[models[1]['name']]<=gate['max_peak_rss_gib']*1024**3}
 result['research_screen']={'checks':checks,'passed':all(checks.values()),'autograding_allowed':False,'human_validated':False,'production_changed':False}
 (DATA/'rss.json').write_text(json.dumps(rss_samples,indent=2)+'\n')
 (ROOT/'docs/model-comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({m['name']:result['models'][m['name']]['summary'] for m in models},ensure_ascii=False,indent=2),flush=True)
 print(json.dumps(result['research_screen'],ensure_ascii=False),flush=True)

if __name__=='__main__':main()
