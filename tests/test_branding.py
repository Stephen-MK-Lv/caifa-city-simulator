import copy
import io
import json
import zipfile
from sqlalchemy import select
from test_api import client, create, summary
from app.database import Simulation, YearReport
from app.engine import NAMES


def test_caifa_interface_and_entities(client):
    html = client.get('/').text
    assert '彩珐' in html and '明川' not in html
    assert 'CAIFA / CITY SIMULATION' in html
    assert '政府会计仿真平台' in html
    assert '教学' not in html
    assert '彩珐市运行图景' in html or client.get('/city').status_code == 200
    assert client.get('/openapi.json').json()['info']['title'] == '彩珐市政府会计仿真'
    assert all('彩珐' in name for name in client.get('/api/catalog').json()['entities'].values())
    sid = create(client, name='彩珐市 · 新账套')
    assert all('彩珐' in item['name'] for item in summary(client, sid)['entities'])


def test_legacy_names_are_presented_without_rewriting_records(client):
    sid = create(client, months=12, name='明川市 · 历史教学')
    with client.app.state.db.transaction(write=True) as db:
        row = db.scalar(select(YearReport).where(YearReport.simulation_id == sid))
        old = copy.deepcopy(row.payload)
        for key, item in old['entities'].items():
            item['name'] = NAMES[key].replace('彩珐', '明川')
        row.payload = old
        saved_state = copy.deepcopy(db.get(Simulation, sid).state)
    assert summary(client, sid)['simulation']['name'] == '彩珐市 · 历史教学'
    report = client.get(f'/api/simulations/{sid}/reports?year=1').json()['report']
    assert all('彩珐' in item['name'] for item in report['entities'].values())
    response = client.get(f'/api/simulations/{sid}/export')
    assert 'caifa-' in response.headers['content-disposition']
    z = zipfile.ZipFile(io.BytesIO(response.content))
    exported = json.loads(z.read('年度报表数据.json'))[0]
    assert exported == report
    with client.app.state.db.transaction() as db:
        assert db.get(Simulation, sid).name == '明川市 · 历史教学'
        assert db.get(Simulation, sid).state == saved_state
        assert db.scalar(select(YearReport).where(YearReport.simulation_id == sid)).payload == old
