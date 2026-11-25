import copy
import io
import json
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import create_app
from app.database import Simulation, BusinessEvent, Voucher, JournalLine, Command
from app.engine import City, fen
from app.engine.state import dump_city, load_city


@pytest.fixture
def client(tmp_path):
    app=create_app(tmp_path/'test.sqlite3',scheduler=False)
    with TestClient(app) as c:yield c


def create(c,months=0,seed=20260906,name='测试账套'):
    r=c.post('/api/simulations',json={'name':name,'seed':seed,'initial_months':months,'request_id':str(uuid.uuid4())})
    assert r.status_code==201,r.text
    return r.json()['simulation']['id']


def summary(c,sid):
    r=c.get('/api/simulations/'+sid);assert r.status_code==200,r.text
    return r.json()


def mutate(c,sid,action,**payload):
    version=summary(c,sid)['simulation']['version']
    return c.post(f'/api/simulations/{sid}/{action}',json={
        'request_id':str(uuid.uuid4()),'expected_version':version,**payload})


def test_home_and_catalog(client):
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    assert client.get('/api/health').json()['status']=='ok'
    assert len(client.get('/api/catalog').json()['events'])==18
    assert client.get('/docs').status_code==200


def test_opening_state_and_isolation(client):
    a=create(client);b=create(client)
    assert sum(summary(client,a)['population'].values())==10000
    assert mutate(client,a,'events',kind='birth',entity='hospital',amount=10).status_code==200
    assert summary(client,a)['population']['children']==1810
    assert summary(client,b)['population']['children']==1800


def test_create_idempotence(client):
    body={'name':'重复创建','request_id':'creation-once-001','initial_months':1}
    a=client.post('/api/simulations',json=body)
    b=client.post('/api/simulations',json=body)
    assert a.json()['simulation']['id']==b.json()['simulation']['id']
    assert b.json()['duplicate']
    body['name']='不同内容'
    assert client.post('/api/simulations',json=body).status_code==409
    assert len(client.get('/api/simulations').json())==1


def test_one_year_exactly_matches_original(client):
    sid=create(client)
    r=mutate(client,sid,'advance',months=12)
    assert r.status_code==200,r.text
    expected=City()
    for _ in range(12): expected.advance()
    actual=client.get(f'/api/simulations/{sid}/reports').json()['report']
    assert actual==expected.report()
    annual=client.get(f'/api/simulations/{sid}/reports?year=1').json()['report']
    assert annual==expected.year_reports[0]
    with client.app.state.db.transaction() as db:
        rows=db.scalars(select(Voucher).where(Voucher.simulation_id==sid).order_by(Voucher.number)).all()
        assert [v.payload for v in rows]==expected.journals
        assert db.scalar(select(func.count()).select_from(JournalLine))>len(rows)
    assert summary(client,sid)['invariants']=={'financial_balance_fen':0,'budget_balance_fen':0,'cash_difference_fen':0}


def test_rng_survives_database_restart(tmp_path):
    path=tmp_path/'persist.sqlite3'
    with TestClient(create_app(path,scheduler=False)) as c:
        sid=create(c,months=3,seed=79)
    with TestClient(create_app(path,scheduler=False)) as c:
        assert mutate(c,sid,'advance',months=3).status_code==200
        actual=c.get(f'/api/simulations/{sid}/reports').json()['report']
    expected=City(79)
    for _ in range(6):expected.advance()
    assert actual==expected.report()


def test_medical_collect_and_deposit(client):
    sid=create(client)
    assert mutate(client,sid,'events',kind='medical',entity='hospital',amount='1000.01').status_code==200
    r=client.get(f'/api/simulations/{sid}/reports').json()['report']['entities']['hospital']
    assert r['financial_balance_fen']['应收账款']==30001
    assert r['budget_revenue_yuan']==700
    assert mutate(client,sid,'events',kind='collect',entity='hospital',amount=0).status_code==200
    before=client.get(f'/api/simulations/{sid}/reports').json()['report']['entities']['hospital']['budget_balance_fen']
    assert mutate(client,sid,'events',kind='deposit',entity='hospital',amount=20000).status_code==200
    r=client.get(f'/api/simulations/{sid}/reports').json()['report']['entities']['hospital']
    assert r['budget_balance_fen']==before
    assert r['financial_balance_fen']['其他应付款']==-2000000
    assert r['revenue_yuan']==1000.01


def test_retry_and_event_idempotency(client):
    sid=create(client);v=summary(client,sid)['simulation']['version']
    body={'request_id':'one-request-001','expected_version':v,'kind':'medical','entity':'hospital','amount':1000,'event_id':'课堂医疗001'}
    a=client.post(f'/api/simulations/{sid}/events',json=body);assert a.status_code==200
    before=summary(client,sid)
    b=client.post(f'/api/simulations/{sid}/events',json=body);assert b.json()['duplicate']
    assert summary(client,sid)==before
    r=mutate(client,sid,'events',kind='medical',entity='hospital',amount=1000,event_id='课堂医疗001')
    assert r.json()['duplicate']
    assert summary(client,sid)==before
    assert mutate(client,sid,'events',kind='medical',entity='hospital',amount=2000,event_id='课堂医疗001').status_code==409


def test_event_and_month_rollback(client):
    sid=create(client);before=summary(client,sid)
    r=mutate(client,sid,'events',kind='grant',entity='hospital',amount=30000000)
    assert r.status_code==422 and r.json()['rolled_back']
    assert summary(client,sid)==before
    # A lowered teaching limit forces failure after advance() has already changed month and posted entries.
    with client.app.state.db.transaction(write=True) as db:
        s=db.get(Simulation,sid);data=copy.deepcopy(s.state);data['limits']['hospital']=1;s.state=data
    before=summary(client,sid)
    r=mutate(client,sid,'advance',months=1)
    assert r.status_code==422
    assert summary(client,sid)==before
    with client.app.state.db.transaction() as db:
        assert db.scalar(select(func.count()).select_from(BusinessEvent))==0
        assert db.scalar(select(func.count()).select_from(Voucher))==0


@pytest.mark.parametrize('patch',[
    {'amount':'.001'},{'amount':-1},{'amount':True},{'amount':'NaN'},
    {'entity':'soe'},{'kind':'hack'},{'unknown_field':1},
    {'kind':'birth','amount':1.2},{'kind':'purchase','life':0},
    {'kind':'sales','entity':'soe','product':'未知'},
    {'kind':'collect','amount':100}, {'kind':'expense','entity':'soe'},
])
def test_invalid_input(client,patch):
    sid=create(client);before=summary(client,sid)
    payload={'kind':'medical','entity':'hospital','amount':100,**patch}
    assert mutate(client,sid,'events',**payload).status_code==422
    assert summary(client,sid)==before


def test_stale_version_and_concurrent_writes(client):
    sid=create(client);v=summary(client,sid)['simulation']['version']
    def send(index):
        return client.post(f'/api/simulations/{sid}/events',json={
            'request_id':f'concurrent-{index:08}', 'expected_version':v,
            'kind':'medical','entity':'hospital','amount':100}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes=list(pool.map(send,[1,2]))
    assert sorted(codes)==[200,409]
    assert summary(client,sid)['event_count']==1


def test_event_detail_filters_and_cross_account_guard(client):
    sid=create(client,months=1);other=create(client)
    events=client.get(f'/api/simulations/{sid}/events?kind=grant&entity=hospital&limit=2').json()
    assert events['total']>=3 and len(events['items'])==2
    eid=events['items'][0]['id'];assert isinstance(eid,int)
    detail=client.get(f'/api/simulations/{sid}/events/{eid}').json()
    assert len(detail['vouchers'])==4
    assert {v['entity'] for v in detail['vouchers']}=={'fiscal','hospital'}
    assert client.get(f'/api/simulations/{other}/events/{eid}').status_code==404
    rows=client.get(f'/api/simulations/{sid}/vouchers?book=budget&entity=hospital&search=事业支出').json()
    assert rows['total']>0
    assert all(r['book']=='budget' and r['entity']=='hospital' for r in rows['items'])


def test_export_and_annual_boundary(client):
    sid=create(client,months=12)
    assert mutate(client,sid,'events',kind='medical',entity='hospital',amount=100).status_code==422
    z=zipfile.ZipFile(io.BytesIO(client.get(f'/api/simulations/{sid}/export').content))
    assert len(z.namelist())==6
    assert z.read('会计分录.csv').startswith(b'\xef\xbb\xbf')
    assert len(json.loads(z.read('年度报表数据.json')))==1
    assert mutate(client,sid,'advance',months=1).status_code==200
    assert summary(client,sid)['simulation']['month']==13


def test_auto_clock_and_manual_guard(client):
    sid=create(client)
    assert mutate(client,sid,'run',running=True,interval=3,pause_at_year=True).status_code==200
    assert mutate(client,sid,'events',kind='birth',entity='hospital',amount=1).status_code==409
    with client.app.state.db.transaction(write=True) as db:
        db.get(Simulation,sid).next_tick=time.time()-1
    client.app.state.service.tick()
    assert summary(client,sid)['simulation']['month']==1
    client.app.state.service.tick()
    assert summary(client,sid)['simulation']['month']==1
    assert mutate(client,sid,'run',running=False,interval=3,pause_at_year=True).status_code==200


def test_auto_pauses_on_year_boundary(client):
    sid=create(client,months=11)
    mutate(client,sid,'run',running=True,interval=3,pause_at_year=True)
    with client.app.state.db.transaction(write=True) as db: db.get(Simulation,sid).next_tick=time.time()-1
    client.app.state.service.tick()
    s=summary(client,sid)
    assert s['simulation']['month']==12 and not s['simulation']['running']
    assert s['closed_years']==[1]


def test_auto_failure_pauses_without_partial_month(client):
    sid=create(client)
    mutate(client,sid,'run',running=True,interval=3,pause_at_year=True)
    with client.app.state.db.transaction(write=True) as db:
        s=db.get(Simulation,sid);state=copy.deepcopy(s.state);state['limits']['hospital']=1;s.state=state;s.next_tick=time.time()-1
    client.app.state.service.tick()
    s=summary(client,sid)
    assert not s['simulation']['running'] and s['simulation']['last_error']
    assert s['simulation']['month']==0 and s['event_count']==0


def test_tax_cannot_overpay(client):
    sid=create(client)
    assert mutate(client,sid,'events',kind='tax',entity='soe',amount=1).status_code==422


def test_local_origin_and_host_restrictions(client):
    assert client.post('/api/simulations',json={},headers={'Origin':'https://foreign.example'}).status_code==403
    assert client.get('/api/health',headers={'Host':'foreign.example'}).status_code==400
    assert client.get('/api/simulations/missing').status_code==404
