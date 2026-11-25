const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../app/static/app.js'),'utf8');
let token='logged-in-teacher',request,status=200;
const ctx={Headers,AbortSignal,localStorage:{getItem:()=>token},fetch:async(url,options)=>{request={url,...options};return {ok:status===200,status,json:async()=>({detail:'请先登录教学平台'})}}};
vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('async function api('),source.indexOf('function option(')),ctx);
(async()=>{
 await ctx.api('/simulations',{method:'POST',body:'{}',headers:{Authorization:'Bearer stale'}});
 assert.equal(request.headers.get('Authorization'),'Bearer logged-in-teacher');assert.equal(request.method,'POST');
 token='refreshed-teacher';await ctx.api('/simulations');assert.equal(request.headers.get('Authorization'),'Bearer refreshed-teacher');
 status=401;await assert.rejects(ctx.api('/simulations'),/未被服务接受/);
 token='';await assert.rejects(ctx.api('/simulations'),/未取得登录凭据/);
 console.log('City authentication request tests passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
