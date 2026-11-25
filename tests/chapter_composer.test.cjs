const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../app/static/portal.js'),'utf8');
const composer={innerHTML:'',querySelectorAll:()=>[]};
const form={elements:Object.fromEntries(['title','instruction','amount_variation_percent','profile_id'].map(k=>[k,{}])),querySelectorAll:()=>[]};
let submitted,send;
const ctx={course:{chapters:[{chapter:1,title:'理论',kind:'medical',entity:'hospital',amount:12000},{chapter:3,title:'资产',kind:'purchase',entity:'hospital',amount:60000}],
 business_types:[{kind:'medical',name:'诊疗',entities:['hospital'],unit:'元',fields:[],amount:12000},{kind:'purchase',name:'购置',entities:['hospital'],unit:'元',fields:[],amount:60000}],
 exercise_templates:[],profiles:[{id:'textbook',name:'教材'}]},
 dashboard:{classes:[{id:'class-a',name:'指定班级',profile_id:'textbook'}]},classId:'class-a',selectedChapters:{1:true,3:true},chapterDrafts:{},
 names:{hospital:'人民医院'},esc:String,options:()=>'',
 $:id=>id==='#composer'?composer:id==='#assignment-form'?form:{},
 bindForm:(id,callback)=>send=callback,requestId:()=> 'request-test',post:async(url,body)=>{submitted={url,body};return {assignments:body.tasks}},refresh:async()=>{},notice:()=>{}};
vm.createContext(ctx);
vm.runInContext(source.slice(source.indexOf('function newDraft('),source.indexOf('function renderComposer(')),ctx);
vm.runInContext(source.slice(source.indexOf('function renderComposer('),source.indexOf('function entriesTable(')),ctx);
ctx.chapterDrafts[1]=ctx.newDraft(1);ctx.chapterDrafts[3]=ctx.newDraft(3);ctx.draft=ctx.chapterDrafts[3];
ctx.renderComposer();assert.match(composer.innerHTML,/data-chapter="1" checked/);assert.match(composer.innerHTML,/data-chapter="3" checked/);
assert.match(composer.innerHTML,/所选2章/);
(async()=>{await send();assert.equal(submitted.url,'/teaching/assignment-batches');assert.equal(submitted.body.class_id,'class-a');
 assert.equal(submitted.body.tasks.length,2);assert.equal(submitted.body.tasks[0].chapter,1);assert.equal(submitted.body.tasks[1].events[0].kind,'purchase');
 assert.ok(submitted.body.tasks.every(t=>t.class_id==='class-a'));
 console.log('Multi-chapter composer renders and submits chapter-specific tasks for one class.');
})().catch(e=>{console.error(e);process.exitCode=1});
