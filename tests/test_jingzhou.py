import io
import json
import uuid
import zipfile
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.engine import City
from app.engine.jingzhou import JingzhouCity, REFERENCE
from app.engine.state import dump_city, load_city


def test_reference_math_and_opening_balance():
    c = JingzhouCity()
    assert sum(c.population.values()) == 5082900 // 100
    assert sum(c.jobs.values()) == 724
    assert c.students == 264
    assert c.ledger['fiscal']['国库存款'] == 58299000000 // 12
    assert REFERENCE['facts'][-1]['value'] is None
    assert REFERENCE['derived']['annual_new_employment_reference'] == 670
    c.check()
    assert sum(City().population.values()) == 10000


@pytest.mark.parametrize('seed', [0, 1, 42, 20260906, 4294967295])
def test_year_and_restart_are_deterministic(seed):
    a = JingzhouCity(seed)
    for _ in range(6):
        a.advance()
    b = load_city(json.loads(json.dumps(dump_city(a))), a.events, a.journals, a.year_reports)
    assert isinstance(b, JingzhouCity)
    for _ in range(6):
        a.advance()
        b.advance()
    assert a.report() == b.report()
    assert a.events == b.events
    assert a.journals == b.journals
    assert a.closed == {1}
    assert a.budget['hospital']['财政拨款结转'] <= 0
    assert a.report()['cash_conservation_difference_fen'] == 0


def test_direct_fine_does_not_enter_police_books():
    c = JingzhouCity()
    before = dict(c.ledger['police'])
    c.event('fine', 200, 'police')
    assert dict(c.ledger['police']) == before
    assert all(v['entity'] == 'fiscal' for v in c.journals)
    c.check()


def test_hospital_payroll_has_explicit_funding_split():
    c = JingzhouCity()
    c.advance()
    eid = next(e['id'] for e in c.events if e['kind'] == 'salary' and e['entity'] == 'hospital')
    voucher = next(v for v in c.journals if v['event_id'] == eid and v['book'] == 'budget')
    assert voucher['debit'] == {'事业支出——fiscal': 50000000, '事业支出——self': 245200000}


def test_api_profile_export_and_failed_event_rollback(tmp_path):
    app = create_app(tmp_path / 'scenario.sqlite3', scheduler=False)
    with TestClient(app) as client:
        payload = {'name': '荆州缩尺测试', 'profile_id': 'jingzhou2025', 'initial_months': 12, 'request_id': str(uuid.uuid4())}
        created = client.post('/api/simulations', json=payload)
        assert created.status_code == 201, created.text
        sid = created.json()['simulation']['id']
        summary = client.get('/api/simulations/' + sid).json()
        assert summary['simulation']['profile_id'] == 'jingzhou2025'
        assert summary['reference']['version'] == 1
        assert all(v == 0 for v in summary['invariants'].values())
        result = client.get(f'/api/simulations/{sid}/export')
        with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
            data = json.loads(archive.read('仿真数据依据.json'))
            assert data['reference'] == summary['reference']
            assert data['parameters'] == summary['parameters']
        bad = client.post('/api/simulations', json=payload | {'profile_id': 'unknown'})
        assert bad.status_code == 422
        # Impossible spending remains atomic in the new profile too.
        advance = client.post(f'/api/simulations/{sid}/advance', json={
            'request_id': str(uuid.uuid4()), 'expected_version': summary['simulation']['version'], 'months': 1})
        assert advance.status_code == 200
        summary = client.get('/api/simulations/' + sid).json()
        failed = client.post(f'/api/simulations/{sid}/events', json={
            'request_id': str(uuid.uuid4()), 'expected_version': summary['simulation']['version'],
            'kind': 'purchase', 'entity': 'hospital', 'amount': 1000000000})
        assert failed.status_code == 422
        assert client.get('/api/simulations/' + sid).json() == summary


def test_peer_layout_and_profile_selector(tmp_path):
    with TestClient(create_app(tmp_path / 'ui.sqlite3', scheduler=False)) as client:
        html = client.get('/city').text
        js = client.get('/static/app.js').text
        assert 'name="profile_id"' in html
        assert '/static/reference.css' in html
        assert "node('police',25,38" in js
        assert "node('school',25,188" in js
        assert "node('hospital',600,38" in js
        assert "node('soe',600,188" in js
