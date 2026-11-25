import uuid
import pytest
from test_api import client
from test_teaching import auth
from app.database import StudentWork
from sqlalchemy import select


def setup_teacher(client):
    r = client.post('/api/auth/bootstrap', json={'username':'teacher1','password':'Teacher#2026!','display_name':'测试教师'})
    assert r.status_code == 201, r.text
    return auth(client, 'teacher1', 'Teacher#2026!')


def template(client, teacher, size=1, pack='none', profile='textbook'):
    body = {'name':f'{size}人样品班','size':size,'exercise_template_id':pack,'request_id':str(uuid.uuid4()),'profile_id':profile}
    r = client.post('/api/teaching/classes/from-template', headers=teacher, json=body)
    assert r.status_code == 201, r.text
    return r.json(), body


@pytest.mark.parametrize('size', [30,40,50])
def test_class_templates_and_retry(client, size):
    teacher=setup_teacher(client)
    data,body=template(client,teacher,size,'foundation')
    assert len(data['credentials']) == size
    assert len({x['username'] for x in data['credentials']}) == size
    retry=client.post('/api/teaching/classes/from-template',headers=teacher,json=body)
    assert retry.json()['duplicate'] and retry.json()['credentials']==[]
    d=client.get('/api/teaching/dashboard',headers=teacher).json()['classes'][0]
    assert len(d['students'])==size and d['assignments'][0]['count']==size
    account=data['credentials'][-1]
    student=auth(client,account['username'],account['password'])
    assert len(client.get('/api/teaching/dashboard',headers=student).json()['works'])==1


@pytest.mark.parametrize('profile', ['textbook','jingzhou2025'])
@pytest.mark.parametrize('kind', ['collect','complete','depreciation','tax','birth','death','enrol'])
def test_individual_dependencies_and_complete_answer(client, profile, kind):
    teacher=setup_teacher(client)
    data,_=template(client,teacher,profile=profile)
    catalog=client.get('/api/teaching/catalog',headers=teacher).json()['business_types']
    c=next(x for x in catalog if x['kind']==kind)
    body={'class_id':data['id'],'chapter':1,'title':'前置条件测试','profile_id':profile,
          'events':[{'kind':kind,'entity':c['entities'][0],'amount':c['amount']}]}
    r=client.post('/api/teaching/assignments',headers=teacher,json=body)
    assert r.status_code==201,r.text
    account=data['credentials'][0]
    student=auth(client,account['username'],account['password'])
    w=client.get('/api/teaching/dashboard',headers=student).json()['works'][0]
    with client.app.state.db.transaction() as session:
        refs=[{**r,'amount_yuan':str(r['amount_fen']/100)} for r in session.get(StudentWork,w['id']).reference_entries]
    answer=client.post(f"/api/teaching/works/{w['id']}/submit",headers=student,json={'entries':refs})
    assert answer.status_code==200,answer.text
    assert answer.json()['assessment']['score']==100
    assert all(isinstance(x['fields'],list) for x in answer.json()['assessment']['line_feedback'])
    before=w['simulation']['voucher_count']
    confirm=client.post(f"/api/teaching/works/{w['id']}/check",headers=student,json={'action':'confirm'})
    assert confirm.status_code==200,confirm.text
    retry=client.post(f"/api/teaching/works/{w['id']}/check",headers=student,json={'action':'confirm'})
    assert retry.json()['duplicate']
    w2=client.get('/api/teaching/dashboard',headers=student).json()['works'][0]
    assert w2['simulation']['voucher_count']>=before
    if kind in ['birth','death','enrol']:
        assert float(w['case']['amount_yuan_or_count']).is_integer()


@pytest.mark.parametrize('profile', ['textbook','jingzhou2025'])
def test_all_types_group_late_student_and_isolation(client,profile):
    teacher=setup_teacher(client)
    data,_=template(client,teacher,profile=profile)
    catalog=client.get('/api/teaching/catalog',headers=teacher).json()['business_types']
    body={'class_id':data['id'],'chapter':3,'title':'全业务组合','profile_id':profile,
          'request_id':str(uuid.uuid4()),'events':[{'kind':c['kind'],'entity':c['entities'][0],'amount':c['amount']} for c in catalog]}
    r=client.post('/api/teaching/assignments',headers=teacher,json=body)
    assert r.status_code==201,r.text
    assert r.json()['event_count']==18
    assert client.post('/api/teaching/assignments',headers=teacher,json=body).json()['duplicate']
    body['title']='冲突配置'
    assert client.post('/api/teaching/assignments',headers=teacher,json=body).status_code==409
    added=client.post(f"/api/teaching/classes/{data['id']}/students",headers=teacher,json={'username':'late_student','password':'Student#2026!','display_name':'补充学生'})
    assert added.status_code==201,added.text
    late=auth(client,'late_student','Student#2026!')
    works=client.get('/api/teaching/dashboard',headers=late).json()['works']
    assert len(works)==1
    w=works[0]
    with client.app.state.db.transaction() as session:
        refs=[{**r,'amount_yuan':str(r['amount_fen']/100)} for r in session.get(StudentWork,w['id']).reference_entries]
    assessment=client.post(f"/api/teaching/works/{w['id']}/submit",headers=late,json={'entries':refs,'analysis':'检查所有业务及报告变化'}).json()['assessment']
    assert assessment['score']==100
    assert client.post(f"/api/teaching/works/{w['id']}/check",headers=late,json={'action':'dispute','note':'请核查该项处理依据'}).status_code==200
    reviewed=client.get(f"/api/teaching/assignments/{r.json()['id']}/works",headers=teacher).json()['works']
    assert any(x['attempt'] and x['attempt'].get('student_check',{}).get('note')=='请核查该项处理依据' for x in reviewed)
    confirm=client.post(f"/api/teaching/works/{w['id']}/check",headers=late,json={'action':'confirm'})
    assert confirm.status_code==200,confirm.text
    account=data['credentials'][0]
    other=auth(client,account['username'],account['password'])
    assert client.get(f"/api/simulations/{w['simulation']['simulation']['id']}",headers=other).status_code==404
    assert client.get(f"/api/teaching/works/{w['id']}/history",headers=other).status_code==404
    visible=client.get('/api/simulations',headers=late).json()
    assert len(visible)==1


def test_invalid_group_rolls_back(client):
    teacher=setup_teacher(client)
    data,_=template(client,teacher)
    r=client.post('/api/teaching/assignments',headers=teacher,json={'class_id':data['id'],'chapter':1,'title':'无效任务','events':[{'kind':'medical','entity':'police','amount':100}]})
    assert r.status_code==422,r.text
    assert client.get('/api/teaching/dashboard',headers=teacher).json()['classes'][0]['assignments']==[]

@pytest.mark.parametrize('profile',['textbook','jingzhou2025'])
@pytest.mark.parametrize('pack',['foundation','assets','comprehensive'])
def test_each_exercise_pack(client,profile,pack):
    teacher=setup_teacher(client)
    r=client.post('/api/teaching/classes/from-template',headers=teacher,json={
        'name':'业务样品测试','size':2,'exercise_template_id':pack,'profile_id':profile,'request_id':str(uuid.uuid4())})
    assert r.status_code==201,r.text
    assert r.json()['assignment']['student_count']==2


def test_all_chapter_defaults_and_failure_rollback(client):
    teacher=setup_teacher(client)
    data,_=template(client,teacher)
    chapters=client.get('/api/teaching/catalog',headers=teacher).json()['chapters']
    for ch in chapters:
        r=client.post('/api/teaching/assignments',headers=teacher,json={
            'class_id':data['id'],'chapter':ch['chapter'],'title':ch['title'],
            'events':[{'kind':ch['kind'],'entity':ch['entity'],'amount':ch['amount']}]})
        assert r.status_code==201,(ch,r.text)
    failed=client.post('/api/teaching/assignments',headers=teacher,json={
        'class_id':data['id'],'chapter':1,'title':'不可执行业务组',
        'events':[{'kind':'medical','entity':'hospital','amount':100},
                  {'kind':'grant','entity':'hospital','amount':999999999}]})
    assert failed.status_code==422,failed.text
    assert len(client.get('/api/teaching/dashboard',headers=teacher).json()['classes'][0]['assignments'])==14


