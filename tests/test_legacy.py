"""Regression checks for the preserved textbook accounting engine."""
import copy
from app.engine import City, fen


def test_legacy_two_year_replay():
    a, b = City(13), City(13)
    for _ in range(24):
        a.advance(); b.advance()
    assert a.journals == b.journals
    assert a.year_reports == b.year_reports
    assert a.total_cash() == a.opening_cash
    assert all(j['event_id'] in a.seen for j in a.journals)


def test_legacy_fine_is_not_police_income():
    c = City(); before = copy.deepcopy(c.budget['police'])
    c.event('fine', 200)
    assert c.budget['police'] == before
    assert c.ledger['police']['应缴财政款'] == 0
    assert c.ledger['fiscal']['非税收入'] == -fen(200)


def test_legacy_depreciation_once_per_month():
    c = City(); c.month = 1; c.event('purchase', 60000)
    before = copy.deepcopy(c.budget)
    c.event('depreciation')
    assert c.budget == before
    amount = c.ledger['hospital']['固定资产累计折旧']
    assert amount < 0
    c.event('depreciation')
    assert c.ledger['hospital']['固定资产累计折旧'] == amount


def test_legacy_fiscal_appropriation_categories():
    c = City(); c.advance(); ledger = c.ledger['fiscal']
    assert ledger['资本性拨款费用'] == fen(5700000)
    assert ledger['对事业单位补助拨款费用'] == fen(580000)
    assert ledger['政府机关工资福利拨款费用'] == fen(120000)
    assert ledger['政府机关商品和服务拨款费用'] == fen(30000)
    assert '业务活动费用' not in ledger
    assert '一般公共预算收入' in c.budget['fiscal']
