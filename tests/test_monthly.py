from decimal import Decimal
from sqlalchemy import select
import pytest
from test_api import client,create,mutate
from test_classroom_groups import setup_teacher,template
from test_teaching import auth
from app.database import MonthSnapshot


def test_monthly_stocks_flows_and_year_close(client):
    sid=create(client,months=12)
    result=client.get(f'/api/simulations/{sid}/monthly')
    assert result.status_code==200,result.text
    points=result.json()['points'];assert [p['month'] for p in points]==list(range(13))
    summary=client.get('/api/simulations/'+sid).json()
    for entity in summary['entities']:
        key=entity['id'];last=points[-1]['entities'][key]
        assert last['cash_yuan']==entity['cash_yuan']
        for prev,p in zip(points,points[1:]):
            e=p['entities'][key]
            delta=round(e['cash_yuan']-prev['entities'][key]['cash_yuan'],2)
            assert delta==round(e['cash_in_yuan']-e['cash_out_yuan'],2)
        # Closing entries must not turn December revenue/expense into negative annual totals.
        yearly=client.get(f'/api/simulations/{sid}/reports?year=1').json()['report']['entities'][key]
        for field in ['revenue_yuan','expense_yuan']:
            assert sum(Decimal(str(p['entities'][key][field])) for p in points)==Decimal(str(yearly[field]))
        assert last['fixed_assets_net_yuan']==round((entity['financial_balance_fen'].get('固定资产',0)+entity['financial_balance_fen'].get('固定资产累计折旧',0))/100,2)
    assert sum(p['event_count'] for p in points)==summary['event_count']
    assert sum(p['voucher_count'] for p in points)==summary['voucher_count']
    assert points[-1]['entities']['hospital']['revenue_yuan']>0
    assert points[-1]['entities']['soe']['budget_revenue_yuan'] is None


def test_legacy_missing_snapshots_are_not_fabricated(client):
    sid=create(client,months=3)
    with client.app.state.db.transaction(write=True) as s:
        row=s.scalar(select(MonthSnapshot).where(MonthSnapshot.simulation_id==sid,MonthSnapshot.month==1))
        row.payload={k:v for k,v in row.payload.items() if k in ['month','population','students','fiscal_cash_yuan']}
        row=s.scalar(select(MonthSnapshot).where(MonthSnapshot.simulation_id==sid,MonthSnapshot.month==2));s.delete(row)
    points=client.get(f'/api/simulations/{sid}/monthly').json()['points']
    assert points[1]['entities']['hospital']['cash_yuan'] is None
    assert points[1]['entities']['fiscal']['cash_yuan'] is not None
    assert points[1]['entities']['hospital']['revenue_yuan']>0
    assert points[2]['population'] is None and not points[2]['snapshot_recorded']
    assert points[3]['change']['population'] is None
    assert points[3]['entities']['hospital']['cash_yuan'] is not None


def test_manual_events_update_same_month_not_fake_new_month(client):
    sid=create(client)
    assert mutate(client,sid,'events',kind='birth',entity='hospital',amount=10).status_code==200
    assert mutate(client,sid,'events',kind='medical',entity='hospital',amount=1000).status_code==200
    data=client.get(f'/api/simulations/{sid}/monthly').json()['points']
    assert len(data)==1 and data[0]['population']==10010
    assert data[0]['event_count']==2
    assert data[0]['entities']['hospital']['revenue_yuan']==1000
    assert data[0]['entities']['hospital']['cash_in_yuan']==700


def test_monthly_student_isolation(client,monkeypatch):
    monkeypatch.setenv('CAIFA_AUTH_REQUIRED','1')
    teacher=setup_teacher(client);cls,_=template(client,teacher,size=2)
    accounts=cls['credentials'];a=auth(client,accounts[0]['username'],accounts[0]['password']);b=auth(client,accounts[1]['username'],accounts[1]['password'])
    sid=client.get('/api/simulations',headers=a).json()[0]['id']
    assert client.get(f'/api/simulations/{sid}/monthly',headers=a).status_code==200
    assert client.get(f'/api/simulations/{sid}/monthly',headers=b).status_code==404
    assert client.get(f'/api/simulations/{sid}/monthly').status_code==401
