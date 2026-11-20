const plan=JSON.parse(document.getElementById('plan').textContent);
const message=document.getElementById('message');
const nameInput=document.getElementById('pharmacist');
nameInput.value=localStorage.getItem('pharmacist')||'';
nameInput.addEventListener('change',()=>localStorage.setItem('pharmacist',nameInput.value.trim()));
let orders=[],ledger=[],pending=null;
const STATE_CLASS={'已放行':'st-ok','待补签':'st-warn','被拦下':'st-bad','待首签':'st-mute'};
const ACTIONS_BY_STATE={'待首签':['首签通过','首签驳回'],'待补签':['补签通过','补签驳回','撤回首签'],'已放行':['撤回补签','撤回首签'],'被拦下':[]};
function uuid(){return crypto.randomUUID?crypto.randomUUID():'xxxxxxxx-xxxx-4xxx-yxxx'.replace(/[xy]/g,c=>{const r=Math.random()*16|0;return(c=='y'?(r&3|8):r).toString(16)})}
async function api(path,body){const init=body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{};const r=await fetch(path,init),j=await r.json();if(r.status>=400){const e=new Error(j.message||'请求失败');e.code=j.code;throw e}return j}
async function refresh(){
  const[o,l]=await Promise.all([api('/api/release/orders?run_id='+encodeURIComponent(plan.run_id)),api('/api/release/ledger?run_id='+encodeURIComponent(plan.run_id))]);
  orders=o.orders;ledger=l.ledger;render();
}
function cell(text){const td=document.createElement('td');td.textContent=text==null?'—':text;return td}
function render(){
  const counts={'已放行':0,'待补签':0,'被拦下':0,'待首签':0};orders.forEach(o=>counts[o.state]++);
  const lateCount=orders.filter(o=>o.late).length;
  document.getElementById('kpis').innerHTML=[['已放行',counts['已放行'],'单'],['待补签',counts['待补签'],'单'],['被拦下',counts['被拦下'],'单'],['待首签',counts['待首签'],'单'],['晚到补签',lateCount,'单']].map(([k,v,u])=>`<div class="kpi"><span>${k}</span><b>${v} <small>${u}</small></b></div>`).join('');
  document.getElementById('order-count').textContent=orders.length+' 单';
  const box=document.getElementById('orders');box.innerHTML='';
  if(!orders.length){box.innerHTML='<p class="empty">当前批次没有调拨单。</p>'}
  else{
    const table=document.createElement('table');
    table.innerHTML='<thead><tr><th>#</th><th>需求单</th><th>门店</th><th>药品</th><th>批号</th><th>数量</th><th>到期日</th><th>放行结论</th><th>首签</th><th>补签</th><th>操作</th></tr></thead>';
    const body=document.createElement('tbody');
    orders.forEach((o,i)=>{
      const tr=document.createElement('tr');
      tr.append(cell(i+1),cell(o['需求单']),cell(o['门店']),cell(o['药品']),cell(o['批号']),cell(o['调拨数量']),cell(o['到期日']));
      const st=document.createElement('td');st.innerHTML=`<span class="badge ${STATE_CLASS[o.state]}">${o.state}</span>`;tr.append(st);
      tr.append(cell(o.first_signer?`${o.first_signer} ${o.first_at}`:'—'));
      const cs=document.createElement('td');
      if(o.countersigner){cs.textContent=`${o.countersigner} ${o.countersign_at} `;if(o.late){const m=document.createElement('span');m.className='late';m.textContent='晚到';cs.append(m)}}
      else cs.textContent='—';
      tr.append(cs);
      const op=document.createElement('td');const bar=document.createElement('div');bar.className='actions';
      (ACTIONS_BY_STATE[o.state]||[]).forEach(a=>{const b=document.createElement('button');b.textContent=a;b.addEventListener('click',()=>sign(o,a));bar.append(b)});
      op.append(bar);tr.append(op);body.append(tr);
    });
    table.append(body);box.append(table);
  }
  const lg=document.getElementById('ledger');lg.innerHTML='';
  if(!ledger.length){lg.innerHTML='<p class="empty">尚无签核记录。</p>'}
  else{
    const table=document.createElement('table');
    table.innerHTML='<thead><tr><th>#</th><th>时间</th><th>需求单</th><th>批号</th><th>动作</th><th>药师</th><th>晚到</th><th>结论</th></tr></thead>';
    const body=document.createElement('tbody');
    ledger.forEach(e=>{
      const tr=document.createElement('tr');
      tr.append(cell(e.seq),cell(e.at),cell(e['需求单']),cell(e['批号']),cell(e.action),cell(e.pharmacist));
      const late=document.createElement('td');if(e.late){const m=document.createElement('span');m.className='late';m.textContent='晚到';late.append(m)}else late.textContent='—';
      tr.append(late);
      const st=document.createElement('td');st.innerHTML=`<span class="badge ${STATE_CLASS[e.state_after]}">${e.state_after}</span>`;tr.append(st);
      body.append(tr);
    });
    table.append(body);lg.append(table);
  }
}
function sign(order,action){
  const pharmacist=nameInput.value.trim();
  if(!pharmacist){message.textContent='先登记当班药师姓名。';nameInput.focus();return}
  pending={run_id:plan.run_id,order_id:order.order_id,action,pharmacist,version:order.version,action_id:uuid()};
  attempt();
}
async function attempt(){
  message.textContent='正在签核…';
  try{
    const r=await api('/api/release/sign',pending);
    const done=pending.action;pending=null;
    await refresh();
    message.textContent=r.replayed?`「${done}」已签核过，按原结论展示，未新增签核。`:'';
  }catch(e){
    if(e.code==='VERSION')await refresh();
    const current=orders.find(o=>pending&&o.order_id===pending.order_id);
    if(current)pending.version=current.version;
    message.textContent='';
    message.append(document.createTextNode(e.message+' '));
    const b=document.createElement('button');b.textContent='重试';b.addEventListener('click',attempt);message.append(b);
  }
}
refresh().catch(e=>message.textContent=e.message);
