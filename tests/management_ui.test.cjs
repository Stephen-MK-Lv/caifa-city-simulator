const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const elements={},forms={};let sent;
const ctx={dashboard:{classes:[{id:'one',name:'一班',term:'秋',students:[{id:1,username:'student1',display_name:'甲'}],assignments:[]}]},classId:'one',credentials:[],draft:null,chapterDrafts:{},selectedChapters:{1:true},pending:{},
 course:{class_templates:[{size:30,name:'30人班'}],profiles:[{id:'textbook',name:'教材方案'}]},
 $:id=>elements[id]??=( {innerHTML:'',hidden:false} ),document:{querySelectorAll:()=>[]},esc:String,options:()=>'',newDraft:()=>({chapter:1}),renderComposer:()=>{},
 bindForm:(id,fn)=>forms[id]=fn,requestId:()=> 'template-test-id',refresh:async()=>{},notice:()=>{},post:async(url,b)=>{sent={url,b};return {id:'one',size:30}},confirm:()=>true};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/management.js'),'utf8'),ctx);
ctx.renderTeacher();const html=elements['#class'].innerHTML;
assert.match(html,/班级管理/);assert.match(html,/任务分配/);assert.match(html,/查询本班账号与密码/);
assert.doesNotMatch(html,/对应章节|同时布置的业务样品|name="chapter"|name="exercise_template_id"/);
assert.equal(elements['#task-allocation'].hidden,true);ctx.showTeacherPane('assign');assert.equal(elements['#class-management'].hidden,true);
ctx.credentials=[{username:'secret'}];ctx.showTeacherPane('assign');assert.equal(ctx.credentials.length,0);
(async()=>{await forms['template-form']({name:'新班',size:'30',profile_id:'textbook'});assert.equal(sent.b.exercise_template_id,'none');assert.equal(sent.b.size,30);console.log('Management separation, no task template fields, credential hiding and create-only submit passed.');})().catch(e=>{console.error(e);process.exitCode=1});
