// Regression probes for durable queue coordination across workspace instances.
// Build with scripts/test_client.sh, then: node --test tests/event_queue_races.test.cjs
const {test,beforeEach}=require('node:test');
const assert=require('node:assert/strict');
const {EventQueue}=require('../runtime/client-tests/eventQueue.js');
let storage;
beforeEach(()=>{
  storage=new Map();
  global.localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k),key:i=>[...storage.keys()][i]??null,get length(){return storage.size}};
});
function success(body){return {ok:true,status:200,json:async()=>({event:body,session:{status:'active',events:[body]},reply:null})};}

test('two offline instances preserve both unsent actions for the same attempt',
 ()=>{
  const tabA=new EventQueue('same-user','same-attempt');
  const tabB=new EventQueue('same-user','same-attempt');
  const a=tabA.enqueue('status_changed',{status:'accepted',comment:'first tab'});
  const b=tabB.enqueue('status_changed',{status:'responding',comment:'second tab'});
  const recovered=new EventQueue('same-user','same-attempt');
  assert.deepEqual(new Set(recovered.events.map(e=>e.client_event_id)),new Set([a.client_event_id,b.client_event_id]));
 });

test('completion in an unmounted workspace does not erase new workspace work',
 async()=>{
  let release, requests=0;const acknowledged=[];
  global.fetch=async(_,options)=>{
    if(++requests===1)await new Promise(resolve=>release=resolve);
    const body=JSON.parse(options.body);acknowledged.push(body.client_event_id);return success(body);
  };
  const oldWorkspace=new EventQueue('same-user','same-attempt');
  oldWorkspace.enqueue('card_opened');
  const inFlight=oldWorkspace.flush();
  oldWorkspace.onChange=undefined;oldWorkspace.onResult=undefined; // actual Workspace cleanup
  const newWorkspace=new EventQueue('same-user','same-attempt');
  const unsent=newWorkspace.enqueue('status_changed',{status:'accepted',comment:'after navigation back'});
  release();await inFlight;
  const recovered=new EventQueue('same-user','same-attempt');
  assert.ok(acknowledged.includes(unsent.client_event_id) || recovered.events.some(e=>e.client_event_id===unsent.client_event_id),'new work must remain durable until its own acknowledgement');
 });

test('independent attempts and authenticated-user keys do not share pending actions',()=>{
 const a=new EventQueue('user-a','attempt-a');const event=a.enqueue('card_opened');
 const b=new EventQueue('user-a','attempt-b');b.enqueue('status_changed',{status:'accepted'});
 assert.equal(new EventQueue('user-b','attempt-a').count,0);
 assert.deepEqual(new EventQueue('user-a','attempt-a').events.map(e=>e.client_event_id),[event.client_event_id]);
 assert.equal(new EventQueue('user-a','attempt-b').events[0].kind,'status_changed');
});


test('legacy migration preserves original UUID order before new same-millisecond actions',()=>{
 const legacy=[{client_event_id:'legacy-1',kind:'card_opened',payload:{}},{client_event_id:'legacy-2',kind:'status_changed',payload:{status:'accepted'}}];
 localStorage.setItem('kontur:events:u:s',JSON.stringify(legacy));
 const a=new EventQueue('u','s');const b=new EventQueue('u','s');
 const originalNow=Date.now;Date.now=()=>1700000000000;
 try{
  const c=a.enqueue('status_changed',{status:'responding'});
  const d=b.enqueue('status_changed',{status:'arrived'});
  assert.deepEqual(new EventQueue('u','s').events.map(e=>e.client_event_id),['legacy-1','legacy-2',c.client_event_id,d.client_event_id]);
  assert.equal(localStorage.getItem(a.key),null);
 }finally{Date.now=originalNow;}
});

test('concurrent instances may retry but preserve ordered exactly-once server application',async()=>{
 const cached=new Map(),applied=[];
 global.fetch=async(_,options)=>{
  const body=JSON.parse(options.body);await Promise.resolve();
  if(!cached.has(body.client_event_id)){cached.set(body.client_event_id,body);applied.push(body.client_event_id);}
  assert.deepEqual(cached.get(body.client_event_id),body);
  return success(cached.get(body.client_event_id));
 };
 const a=new EventQueue('u','s');const b=new EventQueue('u','s');
 const first=a.enqueue('status_changed',{status:'accepted'});
 const second=b.enqueue('status_changed',{status:'responding'});
 await Promise.all([a.flush(),b.flush()]);
 assert.deepEqual(applied,[first.client_event_id,second.client_event_id]);
 assert.equal(new EventQueue('u','s').count,0);
});
