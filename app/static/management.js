'use strict';
let teacherPane='manage';
function showTeacherPane(pane){teacherPane=pane;$('#class-management').hidden=pane!=='manage';$('#task-allocation').hidden=pane!=='assign';document.querySelectorAll('[data-teacher-pane]').forEach(b=>b.classList.toggle('active',b.dataset.teacherPane===pane));if(pane==='assign'){credentials=[];$('#credentials').innerHTML=''}}
function renderTeacher(){
 const classes=dashboard.classes;if(!classes.some(c=>c.id===classId))classId=classes[0]?.id||'';
 const cls=classes.find(c=>c.id===classId);draft??=newDraft();chapterDrafts[draft.chapter]=draft;
 const classOptions=options(classes.map(c=>[c.id,`${c.name} · ${c.students.length}人`]),classId);
 const profiles=options(course.profiles.map(p=>[p.id,p.name]),'textbook');
 const openingBalances=course.profiles.filter(p=>p.opening_bank_deposits).map(p=>{
  const {hospital,school}=p.opening_bank_deposits;
  return `<p class="hint">${esc(p.name)}期初银行存款：人民医院 ${(hospital/10000).toLocaleString('zh-CN')} 万元，职业学校 ${(school/10000).toLocaleString('zh-CN')} 万元。</p>`;
 }).join('');
 $('#class').innerHTML=`
 <nav class="tabs" aria-label="教师工作区"><button class="tab" data-teacher-pane="manage">班级管理</button><button class="tab" data-teacher-pane="assign">任务分配</button></nav>
 <section id="class-management">
 <div class="card"><p class="eyebrow">班级模板</p><h1>先建班，再分配任务</h1><p class="hint">只创建班级、学生账号和每生一个账套，不自动布置练习。</p>
 ${openingBalances}<form id="template-form" class="form-grid"><label>班级名称<input name="name" required value="政府会计学实训班" maxlength="100"></label><label>学期<input name="term" value="2026秋"></label>
 <fieldset class="wide"><legend>班级人数</legend><div class="choices">${course.class_templates.map(c=>`<label><input type="radio" name="size" value="${c.size}" ${c.size===30?'checked':''}>${c.name}</label>`).join('')}</div></fieldset>
 <label>账号前缀<input name="username_prefix" value="caifa" required pattern="[A-Za-z0-9_-]{3,20}"></label><label>班级账套方案<select name="profile_id">${profiles}</select></label><button class="primary">创建班级与学生账号</button></form>
 <details><summary>创建空白班级</summary><form id="class-form" class="form-grid"><label>名称<input name="name" required></label><label>学期<input name="term"></label><label>账套方案<select name="profile_id">${profiles}</select></label><button>创建班级</button></form></details></div>
 <div class="card"><h2>管理当前班级</h2><label>选择管理班级<select id="class-select">${classOptions}</select></label><button id="refresh-class" class="secondary">刷新名单</button> <button id="delete-class" class="danger-btn" ${cls?'':'disabled'}>删除当前班级及账套</button>
 ${cls?`<details><summary>修改班级信息</summary><form id="edit-class-form" class="form-grid"><label>班级名称<input name="name" required maxlength="100" value="${esc(cls.name)}"></label><label>学期<input name="term" maxlength="80" value="${esc(cls.term)}"></label><button>保存班级信息</button></form></details>`:''}
 <h3>补充学生</h3><form id="student-form" class="form-grid"><label>登录名<input name="username" required minlength="3" pattern="[A-Za-z0-9_.@-]+"></label><label>姓名<input name="display_name" required></label><label>初始密码<input type="password" name="password" required minlength="10" autocomplete="new-password"></label><button class="secondary" ${cls?'':'disabled'}>添加学生</button></form>
 <p class="hint">新增学生自动补领本班任务。旧密码若未留存只能重置；新建或重置后的密码可由本班教师查询。</p><h3>学生账号 · ${cls?.students.length||0}人</h3><button id="query-accounts" class="secondary" ${cls?'':'disabled'}>查询本班账号与密码</button>
 <div class="roster">${cls?.students.map(st=>`<div class="row"><span>${esc(st.display_name)}</span><span>${esc(st.username)}</span><button class="secondary" data-reset-student="${st.id}">重置密码</button></div>`).join('')||'暂无学生'}</div><div id="credentials"></div></div>
 <div class="card"><h2>已布置任务管理</h2><p class="hint">删除未入账任务时，连同依赖它的后续未入账任务一起删除；保留共用账套。已入账历史不能直接删除。</p>${cls?.assignments.map(a=>`<div class="row"><div><b>${esc(a.title)}</b><p class="hint">${a.event_count}项业务 · 提交${a.submitted}/${a.count} · 入账${a.confirmed} · 复核${a.reviewed}</p></div><div><button data-review="${a.id}" class="secondary">查看作答</button> <button data-delete-assignment="${a.id}" class="danger-btn">删除任务</button></div></div>`).join('')||'<p>尚未发布任务</p>'}</div></section>
 <section id="task-allocation" hidden><div class="card"><p class="eyebrow">任务分配</p><h1>选择班级，布置任务或任务包</h1><label>接收任务的班级<select id="assignment-class-select">${classOptions}</select></label><p class="hint">勾选多个章节，再逐章配置任务或任务包，整批发给所选班级。</p><div id="composer"></div></div></section><div id="review-box"></div>`;
 function changeClass(value){classId=value;credentials=[];draft=null;chapterDrafts={};selectedChapters={1:true};renderTeacher()}
 $('#class-select').onchange=e=>changeClass(e.target.value);$('#assignment-class-select').onchange=e=>changeClass(e.target.value);
 document.querySelectorAll('[data-teacher-pane]').forEach(b=>b.onclick=()=>{showTeacherPane(b.dataset.teacherPane);$('#review-box').innerHTML=''});
 $('#refresh-class').onclick=e=>run(e.currentTarget,async()=>{credentials=[];await refresh();notice('名单已更新')});
 bindForm('class-form',async b=>{const c=await post('/teaching/classes',b);classId=c.id;credentials=[];await refresh();notice('班级已创建，请到任务分配中布置练习')});
 if(cls)bindForm('edit-class-form',async b=>{await api('/teaching/classes/'+classId,{method:'PATCH',body:JSON.stringify(b)});await refresh();notice('班级信息已更新')});
 bindForm('student-form',async b=>{if(!classId)throw Error('请先创建班级');await post('/teaching/classes/'+classId+'/students',b);credentials=[];await refresh();notice('学生已添加，可查询账号与密码')});
 bindForm('template-form',async b=>{b.size=Number(b.size);b.exercise_template_id='none';b.request_id=requestId('template',b);const c=await post('/teaching/classes/from-template',b);classId=c.id;credentials=[];await refresh();notice(c.duplicate?'班级已存在，未重复创建。':`已创建${c.size}人班级及个人账套。请查询账号并前往任务分配。`)});
 $('#query-accounts').onclick=e=>run(e.currentTarget,async()=>{if(!confirm('即将显示本班学生密码，请避免投屏或向无关人员展示。继续？'))return;await loadCredentials()});
 document.querySelectorAll('[data-reset-student]').forEach(b=>b.onclick=()=>run(b,async()=>{if(!confirm('重置后旧密码及学生的已登录会话立即失效。确定重置并显示新密码？'))return;await post('/teaching/classes/'+classId+'/students/'+b.dataset.resetStudent+'/reset-password',{});await loadCredentials();notice('密码已重置，请单独告知对应学生')}));
 document.querySelectorAll('[data-review]').forEach(b=>b.onclick=()=>run(b,()=>showReviews(b.dataset.review)));
 document.querySelectorAll('[data-delete-assignment]').forEach(b=>b.onclick=()=>run(b,async()=>{const id=b.dataset.deleteAssignment,p=await api('/teaching/assignments/'+id+'/delete-preview');if(!p.can_delete)throw Error('本任务或后续任务已入账，不能直接删除历史凭证。');const title=prompt(p.note+'\n将删除：'+p.tasks.map(t=>t.title).join('；')+'\n涉及'+p.works+'份作答。请输入当前任务完整标题：\n'+p.title);if(title===null)return;if(title!==p.title)throw Error('标题不匹配，未删除');const result=await api('/teaching/assignments/'+id,{method:'DELETE',body:JSON.stringify({confirm_title:title,scope_token:p.scope_token})});pending={};await refresh();notice(result.message+' 备份：'+result.backup)}));
 $('#delete-class').onclick=e=>run(e.currentTarget,async()=>{const id=classId,p=await api('/teaching/classes/'+id+'/delete-preview');const name=prompt('将删除班级“'+p.name+'”：'+p.assignments+'项任务、'+p.works+'份作答、'+p.cities+'套城市及账簿。\n保留登录账号；删除前自动备份。\n请输入完整班级名称确认：');if(name===null)return;if(name!==p.name)throw Error('名称不匹配，未删除');const result=await api('/teaching/classes/'+id,{method:'DELETE',body:JSON.stringify({confirm_name:name})});classId='';draft=null;chapterDrafts={};selectedChapters={1:true};credentials=[];pending={};await refresh();notice(result.message+' 备份：'+result.backup)});
 renderCredentials();renderComposer();showTeacherPane(teacherPane);
}
async function loadCredentials(){const id=classId;const result=await post('/teaching/classes/'+id+'/credentials',{});if(id!==classId||teacherPane!=='manage')return;credentials=result.credentials;renderCredentials()}
function renderCredentials(){
 if(!credentials.length){$('#credentials').innerHTML='';return}
 $('#credentials').innerHTML=`<div class="feedback"><b>本班账号与密码 · 仅限教师查看</b><p>仅单独分发给对应学生，不要向全班展示。旧密码未留存时请重置。</p><button id="hide-accounts" class="secondary">隐藏密码</button> <button id="download-accounts" class="secondary">下载账号清单 CSV</button><div class="table-scroll"><table class="table"><tr><th>姓名</th><th>登录名</th><th>当前仿真密码</th></tr>${credentials.map(c=>`<tr><td>${esc(c.display_name)}</td><td>${esc(c.username)}</td><td>${esc(c.password||c.password_status||'旧密码未保存，请重置')}</td></tr>`).join('')}</table></div></div>`;
 $('#hide-accounts').onclick=()=>{credentials=[];renderCredentials()};
 $('#download-accounts').onclick=()=>{const quote=v=>'"'+(/^[=+@-]/.test(String(v))?"'":'')+String(v??'').replace(/"/g,'""')+'"';const csv='\uFEFF'+[['姓名','登录名','仿真密码'],...credentials.map(c=>[c.display_name,c.username,c.password||'旧密码未保存，请重置'])].map(r=>r.map(quote).join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='彩珐市班级账号.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
}
