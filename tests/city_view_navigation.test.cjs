const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../app/static/app.js'),'utf8');
const ids=['overview','monthly','events','vouchers','reports','assets','guide'];
const links=ids.map(id=>({dataset:{view:id},active:false,attributes:{},classList:{toggle(name,value){links.find(x=>x.dataset.view===id).active=value}},setAttribute(k,v){this.attributes[k]=v},removeAttribute(k){delete this.attributes[k]}}));
const elements={};let refreshes=0,stops=0;
const ctx={state:{},document:{querySelectorAll(selector){assert.equal(selector,'nav a[data-view]');return links}},
 $:selector=>elements[selector]??={textContent:''},refresh:async force=>{assert.equal(force,true);refreshes++},showError:e=>{throw e},stopMonthlyPlayback:()=>stops++};
vm.createContext(ctx);
vm.runInContext(source.slice(source.indexOf('const views='),source.indexOf('const types=')),ctx);
vm.runInContext(source.slice(source.indexOf('function navigate('),source.indexOf('function showError(')),ctx);
for(const id of ids){ctx.navigate(id);assert.equal(ctx.state.view,id);assert.equal(links.filter(x=>x.active).length,1);assert.equal(links.find(x=>x.active).dataset.view,id);assert.equal(links.find(x=>x.active).attributes['aria-current'],'page');assert.ok(elements['#page-title'].textContent)}
ctx.navigate('not-a-view');assert.equal(ctx.state.view,'overview');
ctx.navigate('constructor');assert.equal(ctx.state.view,'overview');
assert.equal(refreshes,9);assert.equal(stops,8);
console.log('Actual city navigation: all seven views, active links, titles, refresh and fallback passed.');
