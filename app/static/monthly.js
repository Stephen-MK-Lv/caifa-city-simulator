'use strict';
const monthlyState={sid:'',data:null,scope:'city',month:null,metric:'population',timer:null};
const monthlyLabels={population:'人口（人）',students:'在校生（人）',jobs:'示范岗位（个）',fiscal_cash_yuan:'国库存款（元）',event_count:'当月业务（项）',voucher_count:'当月凭证（张）',cash_yuan:'资金余额（元）',cash_in_yuan:'当月现金流入（元）',cash_out_yuan:'当月现金流出（元）',revenue_yuan:'当月财务收入（元）',expense_yuan:'当月财务费用（元）',surplus_yuan:'当月盈余/利润（元）',budget_revenue_yuan:'当月预算收入（元）',budget_expenditure_yuan:'当月预算支出（元）',fixed_assets_net_yuan:'固定资产净值（元）',construction_yuan:'在建工程（元）',receivables_yuan:'应收账款（元）'};
function monthlyNumber(v){return v===null||v===undefined?'—':Number(v).toLocaleString('zh-CN',{maximumFractionDigits:2})}
function monthValues(p){return monthlyState.scope==='city'?p:p.entities[monthlyState.scope]}
function stopMonthlyPlayback(){if(monthlyState.timer)clearInterval(monthlyState.timer);monthlyState.timer=null}
function monthlyDate(m){return m===0?'仿真期初':`仿真第 ${Math.ceil(m/12)} 年 · ${String((m-1)%12+1).padStart(2,'0')} 月`}
let monthlyHoverTimer=null;
document.addEventListener?.('keydown',e=>{if(e.key==='Escape')closeMonthlyPopup()});
function layoutMonthlyFlow(){const scenes=[...document.querySelectorAll('.month-scene')];scenes.forEach((scene,i)=>{const arrow=scene.querySelector('.month-flow'),next=scenes[i+1];if(!arrow||!next)return;const wraps=next.offsetTop>scene.offsetTop;arrow.classList.toggle('row-turn',wraps);arrow.textContent=wraps?'↙':'➜'})}
if(typeof window!=='undefined')window.addEventListener?.('resize',()=>{closeMonthlyPopup();layoutMonthlyFlow()});
function monthlyPopupContent(p){
 const n=monthlyNumber;
 return `<h2 id="monthly-popup-title">彩珐市 · ${monthlyDate(p.month)}</h2><p>城市概况：人口 ${n(p.population)} 人；国库存款 ${n(p.fiscal_cash_yuan)} 元；财政预算收入 ${n(p.entities.fiscal.budget_revenue_yuan)} 元；业务 ${n(p.event_count)} 项；凭证 ${n(p.voucher_count)} 张；在校生 ${n(p.students)} 人；岗位 ${n(p.jobs)} 个。</p><p class="monthly-note">${p.current?'当前月最新状态':'历史月度快照'}。收支和业务数为当月发生额；“—”为未记录或不适用。</p>`;
}
function closeMonthlyPopup(){clearTimeout(monthlyHoverTimer);const popup=$('#monthly-popup');if(popup)popup.hidden=true}
function deferMonthlyPopupClose(){clearTimeout(monthlyHoverTimer);monthlyHoverTimer=setTimeout(closeMonthlyPopup,220)}
function openMonthlyPopup(month,anchor){
 const p=monthlyState.data?.points.find(p=>p.month===month);if(!p)return;
 clearTimeout(monthlyHoverTimer);stopMonthlyPlayback();
 const popup=$('#monthly-popup');popup.dataset.sid=monthlyState.sid;popup.dataset.month=String(month);
 $('#monthly-popup-content').innerHTML=monthlyPopupContent(p);popup.hidden=false;
 $('#monthly-popup-close').onclick=closeMonthlyPopup;
 popup.onmouseenter=()=>clearTimeout(monthlyHoverTimer);popup.onmouseleave=deferMonthlyPopupClose;
 popup.onfocusin=()=>clearTimeout(monthlyHoverTimer);popup.onfocusout=e=>{if(!popup.contains(e.relatedTarget))deferMonthlyPopupClose()};
 popup.onkeydown=e=>{if(e.key==='Escape'){closeMonthlyPopup();anchor?.focus()}};
 const r=anchor?.getBoundingClientRect();
 if(r){const w=popup.offsetWidth,h=popup.offsetHeight;popup.style.left=Math.max(12,Math.min(r.right+12,window.innerWidth-w-12))+'px';popup.style.top=Math.max(12,Math.min(r.top,window.innerHeight-h-12))+'px'}
 const play=$('#monthly-play');if(play)play.textContent='▶ 回放历史';
}

function monthlyBuilding(x,y,h,color,label,active){
 return `<g transform="translate(${x} ${y})" class="city-building ${active?'is-focus':''}"><path d="M0 0L24 -12L48 0L24 12Z" fill="${color}"/><path d="M0 0V${h}L24 ${h+12}V12Z" fill="${color}"/><path d="M24 12L48 0V${h}L24 ${h+12}Z" fill="#315d58"/><path d="M5 12L19 19M5 22L19 29M30 20L42 14M30 30L42 24" stroke="#fff8d9" stroke-width="3"/><text x="24" y="${h+26}" text-anchor="middle">${label}</text></g>`
}
function monthlyCity(p,selected){
 const e=monthValues(p),global=monthlyState.scope==='city';
 const income=global?p.entities.fiscal.budget_revenue_yuan:e.revenue_yuan;
 const block=(x,y,h,c)=>monthlyBuilding(x,y,h,c,'',true);
 return `<button class="month-city ${selected?'selected':''}" data-month="${p.month}" aria-pressed="${selected}" aria-label="查看${monthlyDate(p.month)}"><svg class="city-icon" viewBox="0 0 300 252" aria-hidden="true"><text x="150" y="22" class="city-svg-date" text-anchor="middle">${monthlyDate(p.month)}</text><g transform="translate(40 28)"><path d="M10 112L110 59L210 112V128L110 177L10 128Z" fill="#608577"/><path d="M10 112L110 59L210 112L110 163Z" fill="#dbe6d1"/><path d="M30 122L128 72M64 141L163 89" stroke="#fffbee" stroke-width="7"/>${block(48,78,32,'#8aafa0')}${block(94,37,62,'#48786c')}${block(140,83,36,'#c6a362')}${block(82,112,20,'#9ab9aa')}<circle cx="29" cy="113" r="7" fill="#7e9c70"/><circle cx="190" cy="123" r="7" fill="#7e9c70"/></g><text x="150" y="230" class="city-svg-data" text-anchor="middle" textLength="284" lengthAdjust="spacingAndGlyphs">人口：${monthlyNumber(p.population)}人 · ${global?'财政收入':'主体收入'}：${monthlyNumber(income==null?null:income/10000)}万元 · 业务：${monthlyNumber(e.event_count)}项</text></svg></button>`;
}

function monthlyTrend(points,key){const values=points.map(p=>monthValues(p)[key]);const valid=values.filter(v=>v!=null);if(!valid.length)return '<p class="monthly-note">这一指标尚无历史记录。</p>';let low=Math.min(...valid),high=Math.max(...valid);if(high===low){low-=1;high+=1}let segments=[],current=[];values.forEach((v,i)=>{if(v==null){if(current.length)segments.push(current);current=[];return}current.push([70+i*620/Math.max(1,values.length-1),145-(v-low)*110/(high-low)])});if(current.length)segments.push(current);return `<svg class="monthly-chart" viewBox="0 0 730 190" role="img" aria-label="${escapeHTML(monthlyLabels[key])}月度趋势，空缺月份断线"><path d="M70 25V150H700" fill="none" stroke="#afbea4"/><text x="8" y="35">${monthlyNumber(high)}</text><text x="8" y="150">${monthlyNumber(low)}</text>${segments.map(s=>`<polyline points="${s.map(p=>p.join(',')).join(' ')}" fill="none" stroke="#357253" stroke-width="2.5"/>${s.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="#b68a45"/>`).join('')}`).join('')}<text x="70" y="178">期初</text><text x="630" y="178">第${points.at(-1).month}月</text></svg>`}
async function renderMonthly(){const sid=state.sid;const data=await api('/simulations/'+sid+'/monthly');if(sid!==state.sid||state.view!=='monthly')return;if(monthlyState.sid!==sid){stopMonthlyPlayback();Object.assign(monthlyState,{sid,month:null,scope:'city',metric:'population'})}monthlyState.data=data;paintMonthly()}
function paintMonthly(scroll=false){
 const points=monthlyState.data.points;if(!points.length){$('#view-content').innerHTML='<p>暂无月度数据。</p>';return}
 const visiblePoints=points.filter(p=>p.month>0);
 const chosen=points.find(p=>p.month===monthlyState.month)||points.at(-1),index=points.indexOf(chosen),previous=points[index-1];
 const city=monthlyState.scope==='city',values=monthValues(chosen),prev=previous?monthValues(previous):null;
 const keys=city?['population','fiscal_cash_yuan','event_count','jobs']:['cash_yuan','revenue_yuan','expense_yuan','event_count'];
 const metrics=city?['population','fiscal_cash_yuan','event_count','students','jobs']:['cash_yuan','revenue_yuan','expense_yuan','event_count','jobs','fixed_assets_net_yuan'];
 if(!metrics.includes(monthlyState.metric))monthlyState.metric=metrics[0];
 const oldScroll=$('#month-track')?.scrollTop||0;
 $('#view-content').innerHTML=`
 <div class="monthly-toolbar"><label>观察范围 <select id="monthly-scope">${option('city','全市',monthlyState.scope)}${Object.entries(shortNames).map(([id,name])=>option(id,name,monthlyState.scope)).join('')}</select></label><button class="button secondary" id="monthly-play">${monthlyState.timer?'暂停回放':'▶ 回放历史'}</button><button class="button secondary" id="monthly-latest">查看最新月</button><button class="button secondary" id="monthly-csv">导出当前范围月度表</button></div>
 <div class="monthly-layout"><section class="monthly-gallery" aria-label="城市月景时间序列"><div class="monthly-track" id="month-track">${visiblePoints.map((p,i)=>'<div class="month-scene">'+monthlyCity(p,p.month===chosen.month)+(i<visiblePoints.length-1?'<span class="month-flow" aria-hidden="true">➜</span>':'')+'</div>').join('')||'<p class="monthly-note">尚未推进月份；推进后将逐月生成城市图。</p>'}</div><label class="monthly-note">月份位置 <input id="monthly-range" class="monthly-slider" aria-label="选择月份" type="range" min="0" max="${points.length-1}" value="${index}"></label>
 </section><section class="monthly-detail" aria-label="所选月份详情"><h2 class="monthly-selected">${city?'全市':escapeHTML(shortNames[monthlyState.scope])} · ${monthlyDate(chosen.month)}${chosen.current?'（当前最新）':''}</h2>
 <div class="month-kpis">${keys.map(key=>{const diff=prev&&values[key]!=null&&prev[key]!=null?values[key]-prev[key]:null;return `<div class="month-kpi"><small>${monthlyLabels[key]}</small><strong>${monthlyNumber(values[key])}</strong><span>${diff==null?'上月缺失或无可比基期':'较上月 '+(diff>0?'+':'')+monthlyNumber(diff)}</span></div>`}).join('')}</div>
 <section class="panel"><div class="monthly-toolbar"><label>趋势指标 <select id="monthly-metric">${metrics.map(k=>option(k,monthlyLabels[k],monthlyState.metric)).join('')}</select></label><span class="monthly-note">存量看余额，流量看当月；缺失值断线。</span></div>${monthlyTrend(points,monthlyState.metric)}</section>
 <section class="panel"><h2>${city?'五个主体 · 当月业务与资金':'主体月度全貌'}</h2><div class="table-scroll"><table class="monthly-table">${city?`<tr><th>会计主体</th><th>资金余额（元）</th><th>较上月（元）</th><th>现金流入</th><th>现金流出</th><th>发起业务</th><th>凭证</th></tr>${Object.entries(shortNames).map(([k,name])=>{const e=chosen.entities[k],old=previous?.entities[k];return `<tr><td>${escapeHTML(name)}</td><td>${monthlyNumber(e.cash_yuan)}</td><td>${monthlyNumber(old&&e.cash_yuan!=null&&old.cash_yuan!=null?e.cash_yuan-old.cash_yuan:null)}</td><td>${monthlyNumber(e.cash_in_yuan)}</td><td>${monthlyNumber(e.cash_out_yuan)}</td><td>${e.event_count}</td><td>${e.voucher_count}</td></tr>`}).join('')}`:`<tr><th>指标</th><th>本月</th><th>上月</th></tr>${['cash_yuan','cash_in_yuan','cash_out_yuan','revenue_yuan','expense_yuan','surplus_yuan','budget_revenue_yuan','budget_expenditure_yuan','fixed_assets_net_yuan','construction_yuan','receivables_yuan','jobs','event_count','voucher_count'].map(k=>`<tr><td>${monthlyLabels[k]}</td><td>${monthlyNumber(values[k])}</td><td>${monthlyNumber(prev?.[k])}</td></tr>`).join('')}`}</table></div>
 ${city?`<p class="monthly-note">当月出生：${monthlyNumber(chosen.births)}人；死亡：${monthlyNumber(chosen.deaths)}人；新入学：${monthlyNumber(chosen.enrolments)}人。在校生：${monthlyNumber(chosen.students)}人；财政当月预算收入：${monthlyNumber(chosen.entities.fiscal.budget_revenue_yuan)}元；预算支出：${monthlyNumber(chosen.entities.fiscal.budget_expenditure_yuan)}元。主体现金流不可直接加总为合并政府现金流。</p><div class="monthly-business">${Object.entries(chosen.business_types).map(([kind,count])=>`<span>${escapeHTML(state.catalog.events.find(e=>e.kind===kind)?.name||kind)} ${count}项</span>`).join('')||'<span>本月暂无业务事件</span>'}</div>`:''}</section>
 <details class="panel"><summary>数据口径与缺失说明</summary><ul class="monthly-note">${monthlyState.data.notes.map(n=>`<li>${escapeHTML(n)}</li>`).join('')}</ul></details></section></div>`;
 const selectMonth=m=>{monthlyState.month=m;paintMonthly(true)};
 document.querySelectorAll('[data-month]').forEach(b=>{b.onmouseenter=()=>openMonthlyPopup(Number(b.dataset.month),b);b.onmouseleave=deferMonthlyPopupClose;b.onfocus=()=>openMonthlyPopup(Number(b.dataset.month),b);b.onblur=e=>{if(!$('#monthly-popup').contains(e.relatedTarget))deferMonthlyPopupClose()};b.onkeydown=e=>{if(e.key==='Escape')closeMonthlyPopup()};b.onclick=()=>selectMonth(Number(b.dataset.month))});
 $('#monthly-range').oninput=e=>{stopMonthlyPlayback();selectMonth(points[Number(e.target.value)].month)};
 $('#monthly-scope').onchange=e=>{monthlyState.scope=e.target.value;paintMonthly()};
 $('#monthly-metric').onchange=e=>{monthlyState.metric=e.target.value;paintMonthly()};
 $('#monthly-latest').onclick=()=>{stopMonthlyPlayback();monthlyState.month=null;paintMonthly(true)};
 $('#monthly-play').onclick=()=>{if(monthlyState.timer){stopMonthlyPlayback();paintMonthly();return}if(!visiblePoints.length)return;monthlyState.month=visiblePoints[0].month;monthlyState.timer=setInterval(()=>{if(state.view!=='monthly'||state.sid!==monthlyState.sid||document.hidden){stopMonthlyPlayback();return}const list=monthlyState.data.points.filter(p=>p.month>0),i=list.findIndex(p=>p.month===monthlyState.month);if(i>=list.length-1){stopMonthlyPlayback();paintMonthly();return}selectMonth(list[i+1].month)},1400);paintMonthly(true)};
 $('#monthly-csv').onclick=()=>{const fields=city?['population','students','jobs','fiscal_cash_yuan','event_count','voucher_count']:['cash_yuan','jobs','revenue_yuan','expense_yuan','budget_revenue_yuan','budget_expenditure_yuan','cash_in_yuan','cash_out_yuan','fixed_assets_net_yuan','event_count','voucher_count'];const rows=[['月份',...fields.map(k=>monthlyLabels[k])],...points.map(p=>[monthlyDate(p.month),...fields.map(k=>monthValues(p)[k]??'')])];const csv='\uFEFF'+rows.map(r=>r.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='城市发展-'+monthlyState.scope+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
 const track=$('#month-track');track.scrollTop=oldScroll;if(scroll){const b=track.querySelector('.selected');if(b)track.scrollTop=Math.max(0,b.offsetTop-track.offsetTop-track.clientHeight/2+b.clientHeight/2)}
 layoutMonthlyFlow();
 const popup=$('#monthly-popup');if(popup&&!popup.hidden){if(popup.dataset.sid!==monthlyState.sid)closeMonthlyPopup();else{const p=points.find(p=>p.month===Number(popup.dataset.month));if(p)$('#monthly-popup-content').innerHTML=monthlyPopupContent(p);else closeMonthlyPopup()}}
}
