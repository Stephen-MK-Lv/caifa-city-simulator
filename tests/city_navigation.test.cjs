const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.join(__dirname,'../app/static');
const portal=fs.readFileSync(path.join(root,'portal.js'),'utf8');
const city=fs.readFileSync(path.join(root,'app.js'),'utf8');
const nav={removeAttribute(){}};
let card, selectedTab;
const links=[{dataset:{city:'task city/1'},removeAttribute(){}}];
const context={document:{querySelector:()=>nav,querySelectorAll:()=>links,createElement:()=>({})},
  $:()=>({after:x=>card=x}),me:{role:'teacher'},dashboard:{works:[]},
  esc:x=>String(x),encodeURIComponent,localStorage:{setItem(){}},showTab:x=>selectedTab=x};
vm.createContext(context);
vm.runInContext(portal.slice(portal.indexOf('function bindCity()'),portal.indexOf('function newDraft(')),context);
context.renderCityEntry({city_simulations:[{simulation:{id:'demo',name:'课堂演示',is_shared:true}},{simulation:{id:'student',name:'学生账套'}}]});
assert.equal(nav.href,'/city?sid=demo');assert.match(card.innerHTML,/进入演示城市/);
context.renderCityEntry({city_simulations:[]});assert.equal(nav.href,'/city?mode=create');
context.me.role='student';context.renderCityEntry({city_simulations:[]});assert.match(card.innerHTML,/尚未分配/);
nav.onclick({preventDefault(){}});assert.equal(selectedTab,'work');
context.dashboard.works=[{title:'第1章',simulation:{simulation:{id:'task-1'}}}];
context.renderCityEntry({city_simulations:[]});assert.match(card.innerHTML,/data-city="task-1"/);
context.bindCity();assert.equal(links[0].href,'/city?sid=task%20city%2F1');
async function checkCity(requested,sims){
 const ctx={requestedCity:requested,state:{sid:requested||'old'},api:async()=>sims,$:()=>({}),localStorage:{setItem(){}},option:()=>''};
 vm.createContext(ctx);vm.runInContext(city.slice(city.indexOf('async function loadSimulations('),city.indexOf('function setControls(')),ctx);
 return {ctx,run:()=>ctx.loadSimulations()};
}
(async()=>{
 let t=await checkCity('task-1',[{id:'other'},{id:'task-1'}]);await t.run();assert.equal(t.ctx.state.sid,'task-1');
 t=await checkCity('forbidden',[{id:'other'}]);await assert.rejects(t.run(),/无权访问/);
 t=await checkCity(null,[]);await t.run();assert.equal(t.ctx.state.sid,'');
 console.log('City navigation: teacher, student, empty state, explicit link and access failure passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
