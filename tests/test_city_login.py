import uuid
from test_api import client
from test_teaching import auth


def test_teacher_login_can_create_city_without_second_login(client, monkeypatch):
    monkeypatch.setenv('CAIFA_AUTH_REQUIRED', '1')
    client.post('/api/auth/bootstrap', json={'username':'teacher1', 'password':'Teacher#2026!', 'display_name':'测试教师'})
    teacher=auth(client,'teacher1','Teacher#2026!')
    assert client.get('/api/auth/me',headers=teacher).status_code==200
    payload={'name':'登录衔接测试','seed':20261023,'initial_months':0,'profile_id':'jingzhou2025','request_id':str(uuid.uuid4())}
    created=client.post('/api/simulations',headers=teacher,json=payload)
    assert created.status_code==201,created.text
    sid=created.json()['simulation']['id']
    assert client.get('/api/simulations/'+sid,headers=teacher).status_code==200
    assert client.post('/api/simulations',json={**payload,'request_id':str(uuid.uuid4())}).status_code==401
    assert client.get('/api/simulations',headers={'Authorization':'Bearer invalid'}).status_code==401
