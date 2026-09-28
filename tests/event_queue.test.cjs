const {test,beforeEach}=require('node:test');
const assert=require('node:assert/strict');
const {EventQueue}=require('../runtime/client-tests/eventQueue.js');
let storage;
beforeEach(()=>{
  storage=new Map();
  global.localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k),key:i=>[...storage.keys()][i]??null,get length(){return storage.size}};
});
function success(body){return {ok:true,status:200,json:async()=>({event:body,session:{},reply:null})};}

test('network failure preserves UUID and survives a queue reconstruction',async()=>{
  global.fetch=async()=>{throw new TypeError('offline')};
  const first=new EventQueue('u','s');const event=first.enqueue('status_changed',{status:'accepted',comment:'Принято'});
  await assert.rejects(first.flush());
  const resumed=new EventQueue('u','s');assert.equal(resumed.events[0].client_event_id,event.client_event_id);
  let sent=[];global.fetch=async(_,opts)=>{const e=JSON.parse(opts.body);sent.push(e);return success(e)};
  await resumed.flush();
  assert.equal(sent[0].client_event_id,event.client_event_id);
  assert.equal(sent[1].kind,'connection_restored');assert.equal(resumed.count,0);
  assert.equal(localStorage.getItem(first.key+':outage'),null);
});

test('concurrent flush calls send one in-flight event',async()=>{
  let count=0,release;
  global.fetch=async(_,opts)=>{count++;await new Promise(r=>release=r);return success(JSON.parse(opts.body))};
  const queue=new EventQueue('u','s');queue.enqueue('card_opened');
  const a=queue.flush(),b=queue.flush();assert.equal(a,b);assert.equal(count,1);
  release();await a;assert.equal(queue.count,0);assert.equal(count,1);
});

test('different users do not replay each others pending actions',()=>{
  const first=new EventQueue('a','s');first.enqueue('card_opened');
  assert.equal(new EventQueue('b','s').count,0);assert.equal(new EventQueue('a','s').count,1);
});

test('server rejection remains visible and does not silently discard work',async()=>{
  global.fetch=async()=>({ok:false,status:409,json:async()=>({detail:'Попытка остановлена'})});
  const queue=new EventQueue('u','s');queue.enqueue('card_opened');
  await assert.rejects(queue.flush(),/Попытка остановлена/);assert.equal(queue.count,1);
  assert.equal(localStorage.getItem(queue.key+':outage'),null);
});
