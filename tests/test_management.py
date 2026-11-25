import uuid
from sqlalchemy import select,func
from test_api import client
from test_classroom_groups import setup_teacher,template
from test_shared_class_city import batch
from test_teaching import auth
from app.database import User,StudentCredential,TeachingAudit,TeachingAssignment,StudentWork,Simulation
from app.teaching import password_digest


def test_credentials_are_encrypted_scoped_and_reset(client):
    teacher=setup_teacher(client);cls,_=template(client,teacher)
    account=cls['credentials'][0]
    student=auth(client,account['username'],account['password'])
    endpoint=f"/api/teaching/classes/{cls['id']}/credentials"
    rows=client.post(endpoint,headers=teacher,json={}).json()['credentials']
    assert rows[0]['password']==account['password']
    uid=rows[0]['id']
    with client.app.state.db.transaction(write=True) as s:
        encrypted=s.get(StudentCredential,uid).encrypted_password
        assert encrypted!=account['password'] and account['password'] not in encrypted
        s.add(User(username='teacher2',display_name='其他教师',role='teacher',password_hash=password_digest('OtherPass#2026!')))
    outsider=auth(client,'teacher2','OtherPass#2026!')
    assert client.post(endpoint,headers=outsider,json={}).status_code==404
    assert client.post(endpoint,headers=student,json={}).status_code==403
    reset=f"/api/teaching/classes/{cls['id']}/students/{uid}/reset-password"
    assert client.post(reset,headers=outsider,json={}).status_code==404
    assert client.post(reset,headers=student,json={}).status_code==403
    r=client.post(reset,headers=teacher,json={});assert r.status_code==200,r.text
    password=r.json()['password'];assert password!=account['password']
    assert client.get('/api/auth/me',headers=student).status_code==401
    assert client.post('/api/auth/login',json={'username':account['username'],'password':account['password']}).status_code==401
    auth(client,account['username'],password)
    assert client.post(endpoint,headers=teacher,json={}).json()['credentials'][0]['password']==password
    with client.app.state.db.transaction() as s:
        details=str([x.detail for x in s.scalars(select(TeachingAudit))])
        assert password not in details and account['password'] not in details
    (client.app.state.db.path.parent/'student-credentials.key').unlink()
    assert client.post(endpoint,headers=teacher,json={}).json()['credentials'][0]['password'] is None


def test_legacy_password_not_invented_and_manual_student_saved(client):
    teacher=setup_teacher(client);cls,_=template(client,teacher)
    with client.app.state.db.transaction(write=True) as s:
        row=s.scalar(select(StudentCredential));s.delete(row)
    endpoint=f"/api/teaching/classes/{cls['id']}/credentials"
    assert client.post(endpoint,headers=teacher,json={}).json()['credentials'][0]['password'] is None
    r=client.post(f"/api/teaching/classes/{cls['id']}/students",headers=teacher,json={
        'username':'manual01','display_name':'手工添加','password':'ManualPass#2026!'})
    assert r.status_code==201
    rows=client.post(endpoint,headers=teacher,json={}).json()['credentials']
    assert next(x for x in rows if x['username']=='manual01')['password']=='ManualPass#2026!'


def test_template_default_no_tasks_and_class_edit(client):
    teacher=setup_teacher(client)
    r=client.post('/api/teaching/classes/from-template',headers=teacher,json={'name':'单独建班','size':2,'request_id':str(uuid.uuid4())})
    assert r.status_code==201,r.text
    cid=r.json()['id'];assert r.json()['assignment'] is None
    assert client.get('/api/teaching/dashboard',headers=teacher).json()['classes'][0]['assignments']==[]
    r=client.patch('/api/teaching/classes/'+cid,headers=teacher,json={'name':'更名班级','term':'2027春'})
    assert r.status_code==200
    with client.app.state.db.transaction() as s:
        assert all(x.name.startswith('更名班级') for x in s.scalars(select(Simulation)))


def test_delete_unposted_suffix_preserves_city_and_rejects_old_retry(client):
    teacher=setup_teacher(client);cls,_=template(client,teacher)
    body=batch(cls['id']);result=client.post('/api/teaching/assignment-batches',headers=teacher,json=body).json()
    aid=result['assignments'][0]['id'];url='/api/teaching/assignments/'+aid
    preview=client.get(url+'/delete-preview',headers=teacher).json()
    assert len(preview['tasks'])==2 and preview['can_delete']
    payload={'confirm_title':preview['title'],'scope_token':preview['scope_token']}
    assert client.request('DELETE',url,headers=teacher,json={**payload,'scope_token':'stale'}).status_code==409
    r=client.request('DELETE',url,headers=teacher,json=payload)
    assert r.status_code==200,r.text
    assert r.json()['assignments']==2
    assert (client.app.state.db.path.parent/'backups'/r.json()['backup']).is_file()
    with client.app.state.db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(StudentWork))==0
        assert s.scalar(select(func.count()).select_from(Simulation))==1
    assert client.post('/api/teaching/assignment-batches',headers=teacher,json=body).status_code==409
    body['request_id']=str(uuid.uuid4())
    assert client.post('/api/teaching/assignment-batches',headers=teacher,json=body).status_code==201


def test_posted_task_cannot_be_deleted(client):
    teacher=setup_teacher(client);cls,_=template(client,teacher,pack='foundation')
    student=auth(client,cls['credentials'][0]['username'],cls['credentials'][0]['password'])
    w=client.get('/api/teaching/dashboard',headers=student).json()['works'][0]
    client.post(f"/api/teaching/works/{w['id']}/submit",headers=student,json={'entries':[]})
    assert client.post(f"/api/teaching/works/{w['id']}/check",headers=student,json={'action':'confirm'}).status_code==200
    url='/api/teaching/assignments/'+w['assignment_id']
    p=client.get(url+'/delete-preview',headers=teacher).json();assert not p['can_delete']
    assert client.request('DELETE',url,headers=teacher,json={'confirm_title':p['title'],'scope_token':p['scope_token']}).status_code==409
