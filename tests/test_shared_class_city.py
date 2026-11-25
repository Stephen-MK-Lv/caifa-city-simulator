import sqlite3
import uuid
import pytest
from sqlalchemy import select, func
from test_api import client
from test_teaching import auth
from test_classroom_groups import setup_teacher, template
from app.database import ClassCity, Simulation, StudentWork, User, TeachingClass, TeachingAssignment
from app.teaching import password_digest


def batch(cid, profile='textbook'):
    return {'class_id':cid,'request_id':str(uuid.uuid4()),'tasks':[
        {'class_id':cid,'chapter':1,'title':'医疗服务','profile_id':profile,'amount_variation_percent':0,
         'events':[{'kind':'medical','entity':'hospital','amount':12000}]},
        {'class_id':cid,'chapter':6,'title':'收款和折旧','profile_id':profile,'amount_variation_percent':0,
         'events':[{'kind':'collect','entity':'hospital','amount':0},{'kind':'depreciation','entity':'hospital','amount':0}]}]}


@pytest.mark.parametrize('profile',['textbook','jingzhou2025'])
def test_shared_city_batch_order_and_rollback(client,monkeypatch,profile):
    monkeypatch.setenv('CAIFA_AUTH_REQUIRED','1')
    teacher=setup_teacher(client); cls,_=template(client,teacher,size=2,profile=profile)
    with client.app.state.db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(ClassCity))==2
        assert s.scalar(select(func.count()).select_from(Simulation))==2
    body=batch(cls['id'],profile)
    r=client.post('/api/teaching/assignment-batches',headers=teacher,json=body)
    assert r.status_code==201,r.text
    assert client.post('/api/teaching/assignment-batches',headers=teacher,json=body).json()['duplicate']
    changed={**body,'tasks':[dict(t) for t in body['tasks']]};changed['tasks'][0]['title']='changed'
    assert client.post('/api/teaching/assignment-batches',headers=teacher,json=changed).status_code==409
    student=auth(client,cls['credentials'][0]['username'],cls['credentials'][0]['password'])
    works=sorted(client.get('/api/teaching/dashboard',headers=student).json()['works'],key=lambda w:w['chapter'])
    assert len(works)==2
    sid=works[0]['simulation']['simulation']['id']
    assert {w['simulation']['simulation']['id'] for w in works}=={sid}
    assert client.post(f'/api/simulations/{sid}/advance',headers=teacher,json={'months':1,'request_id':str(uuid.uuid4())}).status_code==409
    for w in works:
        with client.app.state.db.transaction() as s:
            refs=[{**x,'amount_yuan':str(x['amount_fen']/100)} for x in s.get(StudentWork,w['id']).reference_entries]
        result=client.post(f"/api/teaching/works/{w['id']}/submit",headers=student,json={'entries':refs})
        assert result.json()['assessment']['score']==100
    url=lambda w:f"/api/teaching/works/{w['id']}/check"
    assert client.post(url(works[1]),headers=student,json={'action':'confirm'}).status_code==409
    for w in works:
        result=client.post(url(w),headers=student,json={'action':'confirm'})
        assert result.status_code==200,result.text
        assert client.post(url(w),headers=student,json={'action':'confirm'}).json()['duplicate']
    with client.app.state.db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(Simulation))==2
    bad=batch(cls['id'],profile);bad['tasks'][1]['events'][0]['kind']='not-real'
    assert client.post('/api/teaching/assignment-batches',headers=teacher,json=bad).status_code==422
    with client.app.state.db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(TeachingAssignment))==2
    late=client.post(f"/api/teaching/classes/{cls['id']}/students",headers=teacher,
        json={'username':'late_student','display_name':'补录学生','password':'LatePass#2026!'})
    assert late.status_code==201,late.text
    with client.app.state.db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(ClassCity))==3
        assert s.scalar(select(func.count()).select_from(Simulation))==3


def test_delete_permissions_backup_and_preservation(client):
    teacher=setup_teacher(client); cls,_=template(client,teacher,pack='foundation')
    other,_=template(client,teacher)
    student=auth(client,cls['credentials'][0]['username'],cls['credentials'][0]['password'])
    with client.app.state.db.transaction(write=True) as s:
        s.add(User(username='other_teacher',display_name='另一教师',password_hash=password_digest('OtherPass#2026!'),role='teacher'))
    outsider=auth(client,'other_teacher','OtherPass#2026!')
    url=f"/api/teaching/classes/{cls['id']}"
    assert client.get(url+'/delete-preview',headers=outsider).status_code==404
    assert client.request('DELETE',url,headers=student,json={'confirm_name':cls['name']}).status_code==403
    assert client.request('DELETE',url,headers=teacher,json={'confirm_name':'wrong'}).status_code==422
    r=client.request('DELETE',url,headers=teacher,json={'confirm_name':cls['name']})
    assert r.status_code==200,r.text
    assert r.json()['cities']==1
    backup=client.app.state.db.path.parent/'backups'/r.json()['backup']
    with sqlite3.connect(backup) as c:
        assert c.execute('select count(*) from teaching_classes where id=?',(cls['id'],)).fetchone()[0]==1
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
    with client.app.state.db.transaction() as s:
        assert s.get(TeachingClass,cls['id']) is None
        assert s.get(TeachingClass,other['id']) is not None
        assert s.scalar(select(func.count()).select_from(Simulation))==1
        assert s.scalar(select(func.count()).select_from(User))==4
    assert client.get('/api/auth/me',headers=student).status_code==200


def test_profile_cannot_change_with_task(client):
    teacher=setup_teacher(client); cls,_=template(client,teacher)
    assert client.post('/api/teaching/assignment-batches',headers=teacher,json=batch(cls['id'],'jingzhou2025')).status_code==422


def test_backup_failure_does_not_delete(client,monkeypatch):
    teacher=setup_teacher(client); cls,_=template(client,teacher)
    def failed(db): raise OSError('disk full')
    monkeypatch.setattr('app.class_cleanup.backup_database',failed)
    assert client.request('DELETE',f"/api/teaching/classes/{cls['id']}",headers=teacher,json={'confirm_name':cls['name']}).status_code==503
    with client.app.state.db.transaction() as s:
        assert s.get(TeachingClass,cls['id']) is not None
