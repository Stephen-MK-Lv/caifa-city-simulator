'use strict';
const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const tokenKey='caifa.platform.token';
let token=localStorage.getItem(tokenKey)||'',me,course,dashboard,classId='',activeWork='',draft=null,credentials=[],pending={},chapterDrafts={},selectedChapters={1:true};
const names={fiscal:'财政总会计',hospital:'人民医院',school:'职业学校',police:'公安局'};
function notice(message,error=false){let n=$('#notice');if(!n){n=document.createElement('div');n.id='notice';n.setAttribute('role','status');$('.wrap').prepend(n)}n.className=error?'notice error':'notice';n.textContent=message}
async function api(path,options={}){const r=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`,'X-Caifa-Token':`Bearer ${token}`}:{})},signal:AbortSignal.timeout(180000)});let d={};try{d=await r.json()}catch{}if(!r.ok)throw Error(Array.isArray(d.detail)?d.detail.map(x=>`${x.loc.slice(1).join(' · ')}：${x.msg}`).join('；'):(d.detail||`请求失败 ${r.status}`));return d}
const post=(path,data)=>api(path,{method:'POST',body:JSON.stringify(data)});
const obj=f=>Object.fromEntries(new FormData(f));
function requestId(key,body){const fingerprint=JSON.stringify(body);if(pending[key]?.fingerprint!==fingerprint)pending[key]={fingerprint,id:crypto.randomUUID()};return pending[key].id}
async function run(element,fn){if(element.dataset.busy)return;element.dataset.busy='1';const buttons=[...(element.matches('button')?[element]:element.querySelectorAll('button'))];buttons.forEach(b=>b.disabled=true);notice('正在处理，请稍候…');try{await fn()}catch(e){notice(e.message,true)}finally{delete element.dataset.busy;buttons.forEach(b=>b.disabled=false)}}
function bindForm(id,fn){const f=$('#'+id);f.onsubmit=e=>{e.preventDefault();const body=obj(f);run(f,()=>fn(body,f))}}
function options(items,value){return items.map(([v,t])=>`<option value="${esc(v)}" ${String(v)===String(value)?'selected':''}>${esc(t)}</option>`).join('')}
function chapterOptions(value=1){return options(course.chapters.map(c=>[c.chapter,`第${c.chapter}章 · ${c.title}`]),value)}
function showTab(id){document.querySelectorAll('.panel').forEach(p=>p.hidden=p.id!==id);document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===id))}
function statusText(s){return ({assigned:'待作答',submitted:'待核查',student_disputed:'已提出异议',confirmed:'已核查入账',teacher_approved:'教师已确认',needs_revision:'请修改'})[s]||s}
async function boot(){try{const status=await api('/auth/status');if(!token)return showAuth(status.setup_required);try{me=await api('/auth/me')}catch{token='';localStorage.removeItem(tokenKey);return showAuth(status.setup_required)}course=await api('/teaching/catalog');$('#auth').hidden=true;$('#app').hidden=false;$('#identity').innerHTML=`${esc(me.display_name)} · ${me.role==='teacher'?'教师':'学生'} <button id="logout" class="quiet">退出</button>`;$('#logout').onclick=async()=>{await post('/auth/logout',{}).catch(()=>{});token='';credentials=[];classId='';draft=null;chapterDrafts={};selectedChapters={1:true};activeWork='';pending={};localStorage.removeItem(tokenKey);showAuth(false)};document.querySelectorAll('[data-tab]').forEach(b=>{b.hidden=(b.dataset.tab==='class'&&me.role==='student')||(b.dataset.tab==='work'&&me.role==='teacher');b.onclick=()=>showTab(b.dataset.tab)});await refresh();showTab('overview')}catch(e){notice(e.message,true)}}
function showAuth(setup){$('#app').hidden=true;for(const id of ['class','work','overview'])$('#'+id).innerHTML='';$('#auth-form').reset();$('#auth').hidden=false;$('#identity').textContent='';$('#auth-title').textContent=setup?'创建首位教师账号':'登录仿真平台';$('#display-field').hidden=!setup;$('#display-field input').required=setup;$('#auth-submit').textContent=setup?'创建教师账号':'登录';bindForm('auth-form',async body=>{if(setup)await post('/auth/bootstrap',body);const d=await post('/auth/login',{username:body.username,password:body.password});token=d.access_token;localStorage.setItem(tokenKey,token);await boot();notice('登录成功')})}
async function refresh(){const [d,o]=await Promise.all([api('/teaching/dashboard'),api('/teaching/overview')]);dashboard=d;renderOverview(o);if(me.role==='teacher')renderTeacher();else renderStudent()}
function renderOverview(d){$('#overview').innerHTML=`<div class="card hero"><div><p class="eyebrow">彩珐市 · 政府会计学习空间</p><h1>基于城市发展，动态理解一座城市</h1><p>选择班级、发布章节业务，追踪每位学生的独立练习。</p></div></div><div class="metrics">${Object.entries({可见城市账套:d.summary.city_accounts,业务事件:d.summary.total_city_events,会计凭证:d.summary.total_vouchers,仿真任务:d.summary.teaching_assignments}).map(([k,v])=>`<div class="metric"><strong>${v}</strong><span>${k}</span></div>`).join('')}</div><div class="card"><h2>城市账套</h2><div class="table-scroll"><table class="table"><tr><th>名称</th><th>人口</th><th>业务</th><th>凭证</th><th>查看</th></tr>${d.city_simulations.map(x=>`<tr><td>${esc(x.simulation.name)}</td><td>${x.population}</td><td>${x.event_count}</td><td>${x.voucher_count}</td><td><a href="/city" target="_blank" data-city="${x.simulation.id}">运行图景 ↗</a></td></tr>`).join('')}</table></div></div>`;renderCityEntry(d);bindCity()}
function bindCity(){document.querySelectorAll('[data-city]').forEach(a=>{const view=a.dataset.view==='monthly'?'&view=monthly':'';a.href='/city?sid='+encodeURIComponent(a.dataset.city)+view;a.removeAttribute('target');a.onclick=()=>localStorage.setItem('mingchuan.sid',a.dataset.city)})}
function renderCityEntry(d){
 const teacher=me.role==='teacher',shared=d.city_simulations.find(x=>x.simulation.is_shared);
 const nav=document.querySelector('.tabs a[href="/city"]')||document.querySelector('#city-nav');
 if(nav){nav.id='city-nav';nav.textContent=teacher?'进入演示城市 →':'选择任务城市 →';nav.href=teacher?(shared?'/city?sid='+encodeURIComponent(shared.simulation.id)+'&view=monthly':'/city?mode=create&view=monthly'):'#work';nav.removeAttribute('target');nav.onclick=teacher?null:e=>{e.preventDefault();showTab('work')};}
 const box=document.createElement('div');box.className='card city-entry';
 box.innerHTML=teacher?`<h2>课堂演示城市</h2><p>演示城市与学生任务账套分开，避免课堂操作改变学生作答环境。</p>${shared?`<p class="hint">即将打开：${esc(shared.simulation.name)}</p><a class="primary" data-city="${esc(shared.simulation.id)}" data-view="monthly">进入演示城市 →</a>`:'<p class="hint">尚无可识别的公共演示城市。可创建独立账套；不会修改学生城市。</p><a class="primary" href="/city?mode=create&view=monthly">创建演示城市 →</a>'}`:`<h2>我的任务城市</h2><p>每名学生在本班共用一套城市，多章任务按发布顺序累计入账。</p>${dashboard.works.length?dashboard.works.map(w=>`<div class="row"><span>${esc(w.title)}</span><a class="secondary" data-city="${esc(w.simulation.simulation.id)}">进入本任务城市 →</a></div>`).join(''):'<p class="empty">尚未分配实训任务，请等待教师发布章节业务；已建立的本班个人账套可在下方城市列表查看。</p>'}`;
 $('#overview .hero').after(box);
}
let assignmentEntityFilter='';
function newDraft(chapter=1){
 const ch=course.chapters.find(x=>x.chapter===Number(chapter));
 return {chapter:Number(chapter),title:`第${chapter}章 · ${ch.title}实训`,
  instruction:'按教材例题填写会计凭证，提交后核查初评。',amount_variation_percent:0,
  profile_id:'textbook',events:{}};
}
function renderComposer(){const ch=course.chapters[draft.chapter-1];const available=course.business_types.filter(c=>ch.business_kinds.includes(c.kind)
  &&(!assignmentEntityFilter||c.entities.includes(assignmentEntityFilter)));const cls=dashboard.classes.find(c=>c.id===classId);draft.profile_id=cls?.profile_id||'textbook';chapterDrafts[draft.chapter]=draft;const selected=Object.keys(draft.events).length;$('#composer').innerHTML=`<fieldset><legend>第一步：选择章节（可多选）</legend><div class="choices">${course.chapters.map(c=>`<label><input type="checkbox" data-chapter="${c.chapter}" ${selectedChapters[c.chapter]?'checked':''}>第${c.chapter}章 ${esc(c.title)}${selectedChapters[c.chapter]?` <button type="button" data-edit-chapter="${c.chapter}" class="secondary">配置任务（${Object.keys(chapterDrafts[c.chapter]?.events||{}).length}项）</button>`:''}</label>`).join('')}</div></fieldset><p class="hint">目标班级：${esc(cls?.name||'请先选择班级')}。每名学生一套账，多章共用；按章节编号依次发布并顺序入账。</p><form id="assignment-form" class="form-grid"><h3 class="wide">第二步：配置第${draft.chapter}章任务或任务包</h3><p class="wide hint">${esc(ch.note)} ${esc(ch.report_tables.join('、'))}</p><label>任务标题<input name="title" required maxlength="160" value="${esc(draft.title)}"></label><label>按会计主体筛选<select id="assignment-entity-filter">${options([['','全部会计主体'],...Object.entries(course.entities)],assignmentEntityFilter)}</select></label><label>个体差异幅度 %<input name="amount_variation_percent" type="number" min="0" max="25" value="${draft.amount_variation_percent}"></label><label>班级固定方案<select name="profile_id" disabled>${options(course.profiles.map(p=>[p.id,p.name]),draft.profile_id)}</select></label><label class="wide">任务说明<textarea name="instruction" required>${esc(draft.instruction)}</textarea></label><div class="wide choices">${course.exercise_templates.filter(p=>p.chapter===draft.chapter).map(p=>`<button type="button" data-pack="${p.id}" class="secondary" ${available.length?"":"disabled"}>${assignmentEntityFilter?"选用当前主体任务包":esc(p.name)}</button>`).join('')}<button type="button" id="clear-types">清空选择</button></div><fieldset class="wide"><legend>可多选业务 · 本章已选 ${selected} 项</legend>
<p class="hint">${Object.values(draft.events).map(e=>`${names[e.entity]} · ${course.business_types.find(c=>c.kind===e.kind)?.name||''}`).map(esc).join('、')||'请勾选业务。'}</p>
${available.length?'':'<p>本章没有适用于所选主体的教材例题。请选择其他章节或主体。</p>'}<div class="business-grid">${available.map(c=>{const e=draft.events[c.kind];return `<div class="business-card ${e?'selected':''}"><label><input type="checkbox" data-kind="${c.kind}" ${e?'checked':''}><b>${esc(c.name)}</b></label><p class="hint">${esc(c.hint)}</p>${e?`<div data-config="${c.kind}" class="form-grid"><label>会计主体<select data-field="entity">${options(c.entities.map(k=>[k,names[k]]),e.entity)}</select></label>${c.unit!=='无'?`<label>${c.unit==='人'?'人数':'金额（元）'}<input data-field="amount" type="number" min="1" step="${c.unit==='人'?'1':'0.01'}" required value="${e.amount}"></label>`:'<p>按个人城市当前余额计算</p>'}</div>`:''}</div>`}).join('')}</div></fieldset><div class="form-actions"><button class="primary" ${!classId||!Object.keys(selectedChapters).length?'disabled':''}>将所选${Object.keys(selectedChapters).length}章任务发布给全班</button><span class="hint">按卡片顺序执行，缺少的前置交易自动补充为期初资料。</span></div></form>`;
const form=$('#assignment-form');
$('#assignment-entity-filter').onchange=e=>{assignmentEntityFilter=e.target.value;renderComposer()};
for(const field of ['title','instruction','amount_variation_percent','profile_id'])form.elements[field].oninput=e=>draft[field]=field==='amount_variation_percent'?Number(e.target.value):e.target.value;
$('#composer').querySelectorAll('[data-chapter]').forEach(input=>input.onchange=()=>{const ch=Number(input.dataset.chapter);if(input.checked){selectedChapters[ch]=true;chapterDrafts[ch]??=newDraft(ch);draft=chapterDrafts[ch]}else{delete selectedChapters[ch];const next=Object.keys(selectedChapters)[0];if(next)draft=chapterDrafts[next]}renderComposer()});
$('#composer').querySelectorAll('[data-edit-chapter]').forEach(b=>b.onclick=()=>{draft=chapterDrafts[b.dataset.editChapter];renderComposer()});
form.querySelectorAll('[data-kind]').forEach(input=>input.onchange=()=>{const c=course.business_types.find(c=>c.kind===input.dataset.kind);if(input.checked)draft.events[c.kind]={kind:c.kind,entity:assignmentEntityFilter||c.entities[0],amount:c.amount};else delete draft.events[c.kind];renderComposer()});
form.querySelectorAll('[data-config] [data-field]').forEach(input=>input.oninput=()=>{
 draft.events[input.closest('[data-config]').dataset.config][input.dataset.field]=input.value;
 if(input.dataset.field==='entity')renderComposer();
});
form.querySelectorAll('[data-pack]').forEach(button=>button.onclick=()=>{
 const pack=course.exercise_templates.find(item=>item.id===button.dataset.pack);
 const kinds=new Set(available.map(item=>item.kind));
 for(const entry of pack.events){
   if(kinds.has(entry.kind))draft.events[entry.kind]={...entry,entity:assignmentEntityFilter||entry.entity};
 }
 renderComposer();
});
$('#clear-types').onclick=()=>{draft.events={};renderComposer()};
bindForm('assignment-form',async()=>{
 const tasks=Object.keys(selectedChapters).map(Number).sort((a,b)=>a-b).map(ch=>{const d=chapterDrafts[ch];return {...d,class_id:classId,profile_id:cls.profile_id,events:course.business_types.filter(c=>d.events[c.kind]).map(c=>d.events[c.kind])}});
 if(tasks.some(t=>!t.title.trim()||!t.events.length))throw Error('请为每个所选章节填写标题并选择至少一项任务或任务包');
 const body={class_id:classId,tasks};body.request_id=requestId('publish-batch',body);const result=await post('/teaching/assignment-batches',body);await refresh();notice(result.duplicate?'这批任务已发布，未重复创建。':`已向当前班级发布${result.assignments.length}章任务。每名学生沿用本班同一账套。`);
})}
function entriesTable(entries,postings=[]){
 const labels=new Map(postings.map(p=>[p.key,p.business_code??('第'+p.task_number+'项业务')]));

return `<div class="table-scroll"><table class="table"><tr><th>业务编号</th><th>主体</th><th>会计核算</th><th>方向</th><th>科目</th><th>金额</th></tr>${entries.map(e=>`<tr><td>${esc(labels.get(e.event_id)??'—')}</td><td>${esc(names[e.entity]||e.entity)}</td><td>${e.book==='budget'?'预算会计':'财务会计'}</td><td>${e.side==='debit'?'借':'贷'}</td><td>${esc(e.account)}</td><td>${esc(e.amount_yuan)}</td></tr>`).join('')}</table></div>`}
function feedback(a,w={}){return `<div class="feedback"><h2>规则初评 ${a.score} 分 · ${esc(w.status?statusText(w.status):"待核查")}</h2><p>${esc(w.case?.revision==='1125'?w.case.basis:a.basis)}</p>${(a.line_feedback||[]).map(x=>{const fields=Array.isArray(x.fields)?x.fields:[];return `<p>${esc(x.result)} · ${esc(x.submitted?.account)}：${fields.map(f=>`${esc(f.item)} ${f.correct?'✓':'应为 '+esc(f.expected)}`).join('；')}</p>`}).join('')}<details><summary>查看参考分录与核对依据</summary>${entriesTable(a.reference_entries||a.missing_reference_lines||[],w.postings)}</details></div>`}
function renderStudent(){const works=dashboard.works;if(activeWork){const w=works.find(w=>w.id===activeWork);if(w)return renderWork(w);activeWork=''}$('#work').innerHTML=`<div class="card"><h1>我的章节实训</h1><p>独立作答 → 检查初评依据 → 核查或提出异议 → 教师复核</p></div><div class="split">${works.map(w=>`<div class="card"><span class="pill">${esc(statusText(w.status))}</span><h2>${esc(w.title)}</h2><p class="hint">${esc(w.class_name||"")} · 按发布顺序确认入账</p><p>${esc(w.case.statement)}</p><button class="primary" data-open="${w.id}">进入实训</button> <a class="secondary" data-city="${esc(w.simulation.simulation.id)}">进入本任务城市 →</a></div>`).join('')||'<p>暂无任务，请等待教师发布。</p>'}</div>`;document.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>{activeWork=b.dataset.open;renderStudent();showTab('work')});bindCity()}
function entryRow(event, book, row={}){
 return `<div class="entry entry-row" data-event="${esc(event.event_id)}" data-entity="${esc(event.entity)}" data-book="${book}">
 <select name="side" aria-label="借贷方向">${options([['debit','借'],['credit','贷']],row.side||'debit')}</select>
 <input name="account" value="${esc(row.account||'')}" placeholder="会计科目">
 <input name="amount" aria-label="金额（元）" type="number" min="0.01" step="0.01" value="${esc(row.amount_yuan||'')}" placeholder="金额（元）">
 <button type="button" class="remove-line">删除</button></div>`;
}
function fiscalPostingSummary(w){
 if(w.chapter>=14)return '';
 const format=fen=>(fen/100).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2});
 const rows=(w.postings||[]).map(p=>{
   const number=p.business_code?`业务编号 ${esc(p.business_code)}`:p.task_number!=null?`第${p.task_number}项业务`:'前置业务';
   const heading=`<h3>${number} · ${esc(p.business)}</h3>`;
   if(p.fiscal_sections.length){
     const lines=p.fiscal_sections.flatMap(part=>['debit','credit'].flatMap(side=>Object.entries(part[side]).map(([account,amount])=>`<tr><td>${part.book==='financial'?'财务会计':'预算会计'}</td><td>${side==='debit'?'借':'贷'}</td><td>${esc(account)}</td><td>${format(amount)}</td></tr>`)));
     return heading+`<p class="hint">与单位分录共用会计凭证号 记-${String(p.voucher_number).padStart(5,'0')}。以下分录已入账。</p>
       <div class="table-scroll"><table class="table"><tr><th>会计核算</th><th>方向</th><th>会计科目</th><th>金额（元）</th></tr>${lines.join('')}</table></div>`;
   }
   if(p.payment==='authorization')return heading+'<p>本项为授权额度下达。单位登记到账额度，财政总会计在实际国库结算时登记对应支出。</p>';
   if(p.payment){
     const note=w.confirmed?'该业务应联动财政总会计。未查到已入账分录，请联系教师核查。':'确认入账时，系统将同步登记财政总会计的财务会计和预算会计分录。';
     return heading+`<p>${note}</p>`;
   }
   return heading+`<p>${p.source==='例4-8'?'按教材例4-8，以单位银行存款支付。该笔支付只登记单位账簿。':'本项按教材登记指定单位账簿，本次业务不发生国库拨款。'}</p>`;
 });
 return rows.length?`<section class="fiscal-posting"><h2>财政总会计处理</h2>${rows.join('')}</section>`:'';
}
function compareBalances(w){
 const tables=w.case.report_tables||[];
 const subjects=[...new Set(w.case.events.map(e=>e.entity))];
 const fiscalChanged=w.postings?.some(p=>p.fiscal_sections.length);
 if(fiscalChanged&&!subjects.includes('fiscal'))subjects.push('fiscal');
 const comparisons=w.confirmed?subjects.map(key=>{
   const before=w.before_report.entities[key], after=w.after_report.entities[key];
   const books=[['财务会计','financial_balance_fen'],['预算会计','budget_balance_fen']];
   const format=v=>v?`${v>0?'借':'贷'} ${(Math.abs(v)/100).toLocaleString('zh-CN')}`:'0';
   return `<h3>${esc(names[key])}</h3>${books.map(([label,field])=>{
     const prev=before[field], next=after[field];
     const changed=[...new Set([...Object.keys(prev),...Object.keys(next)])].filter(k=>(prev[k]||0)!==(next[k]||0));
     return `<h4>${label}</h4>${changed.length?`<table class="table"><tr><th>会计科目</th><th>处理前（元）</th><th>处理后（元）</th></tr>${changed.map(k=>`<tr><td>${esc(k)}</td><td>${format(prev[k])}</td><td>${format(next[k])}</td></tr>`).join('')}</table>`:'<p>余额无变动。</p>'}`;
   }).join('')}`;
 }).join(''):'<p class="hint">入账后可查看本任务处理前后的科目余额及变动。</p>';
 return `<h2>账簿余额对照</h2>${tables.length?`<p>教材表式：${esc(tables.join('、'))}。按表式查找下列科目对应的报表项目。</p>`:''}${comparisons}`;
}
function renderWork(w){
 const a=w.assessment, saved=a?.entries||[];
 const legacy=w.case.revision!=='1125';
 const editable=!legacy&&(!w.confirmed||w.status==='needs_revision');
 const head=`<div class="card"><button id="back-work">← 返回任务列表</button><h1>${esc(w.title)}</h1>`;
 if(legacy){
   $('#work').innerHTML=head+`<p>原版任务记录。新版实训由教师按教材1125版布置。</p><div class="case">${esc(w.case.statement)}</div>${a?feedback(a,w):''}</div>`;
   $('#back-work').onclick=()=>{activeWork='';renderStudent()}; return;
 }
 const books=[['financial','财务会计'],['budget','预算会计']];
 $('#work').innerHTML=head+`<p>${esc(w.instruction)}</p>${w.case.preparation?.length?`<details open><summary>前置业务资料</summary>${w.case.preparation.map(x=>`<p>${esc(x)}</p>`).join('')}</details>`:''}
 <form id="answer-form"><fieldset ${editable?'':'disabled'}>${w.case.events.map((e,i)=>`
 <section class="answer-event" data-event="${esc(e.event_id)}">
 <h3>第${i+1}张会计凭证 · ${esc(e.business)}</h3><p class="hint">${esc(e.source)} · ${esc(e.entity_name)}${w.postings?.find(p=>p.key===e.event_id)?.business_code?` · 业务编号 ${esc(w.postings.find(p=>p.key===e.event_id).business_code)}`:''}</p><p>${esc(e.statement)}</p>
 ${books.map(([book,label])=>{
   const rows=saved.filter(r=>r.event_id===e.event_id&&r.book===book);
   return `<div class="answer-book" data-book="${book}"><h4>${label}</h4><div class="entry-lines">${(rows.length?rows:[{}, {side:'credit'}]).map(row=>entryRow(e,book,row)).join('')}</div>
   <button type="button" class="add-line secondary">增加分录行</button></div>`;
 }).join('')}<p class="hint">无需进行账务处理时，留空相应分录区域。</p></section>`).join('')}
 ${editable?'<button class="primary">提交并查看初评</button>':''}</fieldset></form>
 ${a?feedback(a,w):''}
 ${a&&!w.confirmed?`<label>核查或异议理由<textarea id="check-note">${esc(a.student_check?.note||'')}</textarea></label>
 <button id="confirm-work" class="primary" ${w.can_confirm===false?'disabled':''}>${w.can_confirm===false?'请先完成前序任务':'已核查，按参考分录入账'}</button> <button id="dispute-work">提出异议</button>`:''}
 ${w.teacher_review?`<div class="feedback">教师评分 ${w.teacher_review.score} · ${esc(w.teacher_review.rationale)}</div>`:''}
 ${fiscalPostingSummary(w)}${compareBalances(w)}<a href="/city" data-city="${w.simulation.simulation.id}" target="_blank">查看个人城市完整账簿 ↗</a></div>`;
 $('#back-work').onclick=()=>{activeWork='';renderStudent()};
 $('#answer-form').onclick=e=>{
   if(e.target.classList.contains('remove-line'))e.target.closest('.entry-row').remove();
   if(e.target.classList.contains('add-line')){
     const area=e.target.closest('.answer-book');
     const event=w.case.events.find(item=>item.event_id===area.closest('.answer-event').dataset.event);
     area.querySelector('.entry-lines').insertAdjacentHTML('beforeend',entryRow(event,area.dataset.book));
   }
 };
 if(editable)bindForm('answer-form',async()=>{
   const entries=[...$('#answer-form').querySelectorAll('.entry-row')].map(r=>({
      event_id:r.dataset.event,entity:r.dataset.entity,book:r.dataset.book,
      side:r.querySelector('[name=side]').value,account:r.querySelector('[name=account]').value,
      amount_yuan:r.querySelector('[name=amount]').value
   })).filter(r=>r.account||r.amount_yuan);
   await post(`/teaching/works/${w.id}/submit`,{entries});
   await refresh();notice('初评已生成，请检查参考分录与逐行反馈');
 });
 for(const action of ['confirm','dispute']){
   const button=$('#'+action+'-work');
   if(button)button.onclick=()=>run(button,async()=>{
     await post(`/teaching/works/${w.id}/check`,{action,note:$('#check-note').value});
     await refresh();notice(action==='confirm'?'业务已入账':'异议与理由已送交教师复核');
   });
 }
 bindCity();
}
async function showReviews(id){const d=await api(`/teaching/assignments/${id}/works`);$('#review-box').innerHTML=`<div class="card"><h2>${esc(d.assignment.title)} · 学生作答</h2>${d.works.map(w=>`<details><summary>${esc(w.student.display_name)} · ${esc(statusText(w.status))} · ${w.attempt?.score??'待作答'}分</summary>${w.attempt?`<p>核查记录：${esc(w.attempt.student_check?.note||'尚未核查')}</p>${entriesTable(w.attempt.entries||[],w.postings)}${feedback(w.attempt,w)}<form class="review-form form-grid" data-work="${w.id}"><label>评分<input name="score" type="number" min="0" max="100" value="${w.attempt.score}"></label><label>结论<select name="decision"><option value="confirmed">确认</option><option value="needs_revision">退回修改</option></select></label><label class="wide">复核依据<textarea name="rationale" minlength="5" required></textarea></label><button class="secondary">保存教师复核</button></form>`:'尚未提交'}</details>`).join('')}</div>`;document.querySelectorAll('.review-form').forEach(f=>f.onsubmit=e=>{e.preventDefault();const b=obj(f);b.score=Number(b.score);run(f,async()=>{await post(`/teaching/works/${f.dataset.work}/teacher-review`,b);await refresh();await showReviews(id);notice('教师复核已保存')})});$('#review-box').scrollIntoView({behavior:'smooth'})}
boot();
