"""Monthly snapshot stocks and voucher-derived flows, without replaying randomness."""
from collections import Counter, defaultdict
from sqlalchemy import select
from .database import MonthSnapshot, BusinessEvent, Voucher
from .textbook import ACTORS, sections


def snapshot_payload(report):
    entities = {}
    for key, e in report['entities'].items():
        ledger = e['financial_balance_fen']
        entities[key] = {'cash_yuan':e['cash_yuan'], 'jobs':report.get('jobs',{}).get(key),
            'receivables_yuan':round(ledger.get('应收账款',0)/100,2),
            'fixed_assets_net_yuan':round((ledger.get('固定资产',0)+ledger.get('固定资产累计折旧',0))/100,2),
            'construction_yuan':round(ledger.get('在建工程',0)/100,2)}
    return {'schema_version':2, 'month':report['month'], 'population':sum(report['population'].values()),
        'population_groups':report['population'], 'students':report['students'],
        'jobs':sum(report.get('jobs',{}).values()),
        'fiscal_cash_yuan':report['entities']['fiscal']['cash_yuan'], 'entities':entities}


def monthly_series(session, sim, current_report):
    snapshots = {s.month:s.payload for s in session.scalars(select(MonthSnapshot).where(MonthSnapshot.simulation_id==sim.id))}
    # Current report is authoritative for the current month, even for legacy databases.
    snapshots[sim.month] = snapshot_payload(current_report)
    events=Counter(); by_entity=Counter(); types=defaultdict(Counter); people=defaultdict(Counter)
    for e in session.scalars(select(BusinessEvent).where(BusinessEvent.simulation_id==sim.id, BusinessEvent.entity.in_(ACTORS))):
        events[e.month]+=1;by_entity[e.month,e.entity]+=1;types[e.month][e.kind]+=1
        if e.kind in {'birth','death','enrol'}:
            people[e.month][e.kind]+=int(e.payload['amount_yuan_or_count'])
    vouchers=Counter(); flows=defaultdict(lambda:Counter())
    voucher_totals = Counter()
    for v in session.scalars(select(Voucher).where(Voucher.simulation_id==sim.id, Voucher.entity.in_(ACTORS))):
        parts = sections(v.payload)
        voucher_totals[v.month] += 1
        for subject in {part['entity'] for part in parts}:
            vouchers[v.month, subject] += 1
        for part in parts:
            debit, credit = part['debit'], part['credit']
            accounts = set(debit) | set(credit)
            f = flows[v.month, part['entity']]
            if part['book']=='financial':
                cash = {'国库存款', '其他财政存款'} if part['entity']=='fiscal' else {'银行存款', '库存现金'}
                cash_delta = sum(debit.get(a, 0) - credit.get(a, 0) for a in cash)
                f['cash_in_yuan'] += max(0, cash_delta)
                f['cash_out_yuan'] += max(0, -cash_delta)
                if not accounts.intersection({'本年利润','本期盈余'}):
                    for account in accounts:
                        net = credit.get(account,0)-debit.get(account,0)
                        if '收入' in account or account=='投资收益': f['revenue_yuan'] += net
                        if '费用' in account: f['expense_yuan'] -= net
            elif not any('结转' in a or '结余' in a for a in accounts):
                for account in accounts:
                    net = credit.get(account,0)-debit.get(account,0)
                    if '收入' in account: f['budget_revenue_yuan'] += net
                    if '支出' in account: f['budget_expenditure_yuan'] -= net
    fields=['cash_in_yuan','cash_out_yuan','revenue_yuan','expense_yuan','budget_revenue_yuan','budget_expenditure_yuan']
    points=[]
    for month in range(sim.month+1):
        snap=snapshots.get(month,{})
        entities={}
        for key in ACTORS:
            stock=snap.get('entities',{}).get(key,{})
            flow={name:round(flows[month,key][name]/100,2) for name in fields}
            entities[key]={**{name:stock.get(name) for name in ['cash_yuan','jobs','receivables_yuan','fixed_assets_net_yuan','construction_yuan']},
                **flow,'surplus_yuan':round(flow['revenue_yuan']-flow['expense_yuan'],2),
                'event_count':by_entity[month,key],'voucher_count':vouchers[month,key], 'stock_recorded':bool(stock)}
        # Fiscal cash was retained in version 1 snapshots.
        if entities['fiscal']['cash_yuan'] is None:entities['fiscal']['cash_yuan']=snap.get('fiscal_cash_yuan')
        point={'month':month, 'current':month==sim.month,'snapshot_recorded':bool(snap),
            'population':snap.get('population'),'population_groups':snap.get('population_groups'),
            'students':snap.get('students'),'jobs':snap.get('jobs'), 'fiscal_cash_yuan':snap.get('fiscal_cash_yuan'),
            'births':people[month]['birth'],'deaths':people[month]['death'],'enrolments':people[month]['enrol'],
            'event_count':events[month],'voucher_count':voucher_totals[month],
            'business_types':dict(types[month]), 'entities':entities}
        previous=points[-1] if points else None
        if previous and previous.get('population_groups') and point.get('population_groups'):
            if not people[month]:
                old, new = previous['population_groups'], point['population_groups']
                point['births'] = max(0, new['children'] - old['children'])
                point['deaths'] = max(0, old['seniors'] - new['seniors'])
                if previous.get('students') is not None and point.get('students') is not None:
                    point['enrolments'] = max(0, point['students'] - previous['students'])
        point['change']={name:(round(point[name]-previous[name],2) if previous and point[name] is not None and previous[name] is not None else None)
            for name in ['population','students','jobs','fiscal_cash_yuan','event_count']}
        points.append(point)
    return {'simulation_id':sim.id,'current_month':sim.month,'points':points,
        'notes':['存量来自各月最后一次保存的快照；当前月是最新状态，并不一定已结束。月内多次业务合并在同一张城市月景图。',
                 '收入、费用、预算收支与现金收付为当月凭证发生额，剔除收支结转；不是年内累计余额。',
                 '旧快照未保存的主体余额及岗位数显示缺失；不使用当前值倒推历史。',
                 '全市业务按业务事件去重计数；主体业务数按发起主体归属，跨主体会计影响看凭证及现金收付。',
                 '岗位为模型配置的示范岗位，不是全市就业统计；未设置的财政局岗位显示缺失。',
                 '财政和单位收入包含内部拨款，不能直接加总成合并政府收入；此页不计算这种合计。']}
