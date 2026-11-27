"""Teaching cases transcribed from 1.政府会计教程正文1125-排版.docx, main text."""
from collections import defaultdict
from decimal import Decimal
from math import gcd

from .engine import City, NAMES, fen
from .engine.jingzhou import JingzhouCity

UNITS = ('hospital', 'school')
ACTORS = {k: v for k, v in NAMES.items() if k != 'soe'}
ACTORS['fiscal'] = '彩珐市财政总会计'
MONEY = '资金结存——货币资金'
QUOTA = '资金结存——零余额账户用款额度'
# 期初货币资金额度（元），按「潜在业务量」测算并覆盖每一个会计主体：
# 把教材全部例题中该主体可能发生的全部付款额加总，再按教师端 ±25% 金额浮动、
# 至少 10 轮重复练习估算峰值，向上取整到便于读账的整额。
#   全教材单轮付款额：财政总会计 3,651,650；人民医院 107,500；
#   职业学校 107,500；公安局 50,000。
# 财政总会计的货币资金账户是「国库存款」而非「银行存款」，其余主体为「银行存款」。
# 荆州方案的国库存款沿用 58,299,000,000÷12÷100 的公开数据缩尺公式，医院沿用
# 5,000,000 元参考值；两者均已高于上述潜在付款需求，故不改写参考口径。
OPENING_BANK_DEPOSITS = {
    'textbook': {
        'fiscal': 100000000,    # 国库存款 1 亿元
        'hospital': 3000000,    # 银行存款 300 万元
        'school': 3000000,      # 银行存款 300 万元
        'police': 1500000,      # 银行存款 150 万元
    },
    'jingzhou2025': {
        'fiscal': 48582500,     # 国库存款（参考缩尺公式）
        'hospital': 5000000,    # 银行存款 500 万元
        'school': 3000000,      # 银行存款 300 万元
        'police': 1500000,      # 银行存款 150 万元
    },
}


def case(kind, chapter, example, title, entities, amounts, statement, financial, budget=(), **extra):
    return dict(kind=kind, chapter=chapter, source=example, name=title, entities=entities,
                values=amounts, statement=statement, financial=financial, budget=budget, **extra)


def pair(debit, credit, amount):
    return ((debit, amount), (credit, -amount))


def fiscal_payment(amount, expense, budget='一般公共预算支出'):
    return (pair(expense, '国库存款', amount), pair(budget, '资金结存', amount))


def direct(amount, asset, expenditure):
    return (pair(asset, '财政拨款收入', amount), pair(expenditure, '财政拨款预算收入', amount))


CASES = [
    case('ex3-1', 3, '例3-1', '购入物资，款未付', UNITS, (50000,),
         '购买一批物资，已验收入库，货款{0}元，尚未支付。',
         pair('库存物品', '应付账款', 50000)),
    case('ex3-3a', 3, '例3-3（1）', '收到押金', UNITS, (1000,),
         '银行存款账户收到押金{0}元。', pair('银行存款', '其他应付款', 1000)),
    case('ex3-3b', 3, '例3-3（2）', '归还押金', UNITS, (1000,),
         '以银行存款归还押金{0}元。', pair('其他应付款', '银行存款', 1000),
         prerequisite=('ex3-3a', 1000)),
    case('ex3-4', 3, '例3-4', '购入教学用具', ('school',), (30000,),
         '购入一批教学用具{0}元，物资验收入库，在预算管理一体化系统中使用财政资金支付。',
         *direct(30000, '库存物品', '事业支出'),
         fiscal=fiscal_payment(30000, '对事业单位补助拨款费用'), payment='direct'),
    case('ex3-5', 3, '例3-5', '取得应上缴财政的租金', UNITS, (10000,),
         '收到应上缴财政的租金{0}元，存入银行。',
         pair('银行存款', '应缴财政款', 10000)),
    case('ex4-1', 4, '例4-1', '提取现金', UNITS, (500,),
         '经批准从银行提取现金{0}元。', pair('库存现金', '银行存款', 500)),
    case('ex4-8', 4, '例4-8', '以银行存款支付业务活动费用', UNITS, (50000,),
         '以银行存款支付业务活动费用{0}元。', pair('业务活动费用', '银行存款', 50000),
         pair('事业支出', MONEY, 50000)),
    case('ex4-13', 4, '例4-13', '收到财政授权支付到账通知书', UNITS, (400000,),
         '收到财政授权支付到账通知书，到账额度为{0}元。',
         pair('零余额账户用款额度', '财政拨款收入', 400000),
         pair(QUOTA, '财政拨款预算收入', 400000), payment='authorization'),
    case('ex4-35', 4, '例4-35', '支付预付款项', UNITS, (30000, 100000),
         '与A公司签订购买合同，采购用于专业业务活动的原材料，价款{1}元。在预算管理一体化系统中使用财政资金预付30%，即{0}元。',
         *direct(30000, '预付账款', '事业支出'),
         fiscal=fiscal_payment(30000, '对事业单位补助拨款费用'), payment='direct'),
    case('ex4-36', 4, '例4-36', '结算预付款项', UNITS, (70000, 30000, 100000),
         '承例4-35，原材料已验收入库，价款{2}元，其中已预付{1}元。在预算管理一体化系统中使用财政资金支付余款{0}元。',
         (('库存物品', 100000), ('预付账款', -30000), ('财政拨款收入', -70000)),
         pair('事业支出', '财政拨款预算收入', 70000),
         fiscal=fiscal_payment(70000, '对事业单位补助拨款费用'), payment='direct',
         prerequisite=('ex4-35', 30000)),
    case('ex4-68', 4, '例4-68', '购入不需安装的固定资产', UNITS, (210000, 200000, 10000),
         '购买不需安装的固定资产，价款{1}元、相关费用{2}元，合计{0}元，在预算管理一体化系统中使用财政资金支付。',
         *direct(210000, '固定资产', '事业支出'), asset='不需安装的固定资产',
         fiscal=fiscal_payment(210000, '资本性拨款费用'), payment='direct'),
    case('ex4-69a', 4, '例4-69（1）', '购入需要安装的固定资产', UNITS, (55000, 50000, 5000),
         '购买需安装的固定资产，价款{1}元、相关费用{2}元，合计{0}元，以银行存款支付。',
         pair('在建工程', '银行存款', 55000), pair('事业支出', MONEY, 55000)),
    case('ex4-69b', 4, '例4-69（2）', '安装完毕交付使用', UNITS, (55000,),
         '承例4-69，固定资产安装完毕交付使用，在建工程成本{0}元。',
         pair('固定资产', '在建工程', 55000), asset='安装完毕交付使用的固定资产',
         prerequisite=('ex4-69a', 55000)),
    case('ex4-77', 4, '例4-77', '固定资产日常维护', UNITS, (10000,),
         '事业单位对固定资产进行日常维护，在预算管理一体化系统中使用财政资金支付维护费用{0}元。',
         *direct(10000, '业务活动费用', '事业支出'),
         fiscal=fiscal_payment(10000, '对事业单位补助拨款费用'), payment='direct'),
    case('ex4-82', 4, '例4-82', '固定资产盘盈', ('police',), (3000,),
         '行政单位在固定资产清查中盘盈打印机一台，重置成本为{0}元。',
         pair('固定资产', '待处理财产损溢', 3000), asset='盘盈打印机', asset_pending=True),
    case('ex5-1', 5, '例5-1', '取得短期借款', UNITS, (500000,),
         '经批准取得银行借款{0}元，期限为半年，年利率为3%。',
         pair('银行存款', '短期借款', 500000), pair(MONEY, '债务预算收入', 500000)),
    case('ex5-3', 5, '例5-3', '提供经营服务并收款', ('school',), (106000, 100000, 6000),
         '职业学校开展经批准的独立经营活动，当日收到服务款{0}元。适用6%税率，价款{1}元，增值税{2}元。',
         (('银行存款', 106000), ('经营收入', -100000), ('应交增值税——应交税金（销项税额）', -6000)),
         pair(MONEY, '经营预算收入', 106000)),
    case('ex6-4a', 6, '例6-4（1）', '无偿调入资产', UNITS, (31000, 30000, 1000),
         '无偿调入存货，调出方账面价值{1}元，以银行存款支付相关费用{2}元。',
         (('库存物品', 31000), ('无偿调拨净资产', -30000), ('银行存款', -1000)),
         pair('其他支出', '资金结存', 1000)),
    case('ex7-1a', 7, '例7-1（1）', '财政直接支付采购办公设备款', UNITS, (100000,),
         '采用财政直接支付方式支付采购办公设备价款{0}元。',
         *direct(100000, '固定资产', '事业支出'), asset='办公设备',
         fiscal=fiscal_payment(100000, '资本性拨款费用'), payment='direct'),
    case('ex7-3', 7, '例7-3', '实拨方式收到财政拨款', ('school',), (300000,),
         '学校的银行存款账户收到通过实拨方式拨付的财政拨款{0}元。',
         pair('银行存款', '财政拨款收入', 300000), pair(MONEY, '财政拨款预算收入', 300000),
         fiscal=fiscal_payment(300000, '对事业单位补助拨款费用'), payment='transfer'),
    case('ex7-9a', 7, '例7-9（1）', '确认应收住院治疗款', ('hospital',), (1000000,),
         '医院月末计算住院病人应交未交的治疗款{0}元。',
         pair('应收账款', '事业收入', 1000000)),
    case('ex7-9b', 7, '例7-9（2）', '结清住院治疗款', ('hospital',), (1500000, 1000000, 500000),
         '病人结清住院治疗款{0}元，其中以前已确认应收账款{1}元。',
         (('银行存款', 1500000), ('应收账款', -1000000), ('事业收入', -500000)),
         pair(MONEY, '事业预算收入', 1500000), prerequisite=('ex7-9a', 1000000)),
    case('ex7-39', 7, '例7-39', '收回已核销的其他应收款', ('police',), (160000,),
         '行政单位收回已核销的其他应收款{0}元，存入银行。',
         pair('银行存款', '其他收入', 160000), pair(MONEY, '其他预算收入', 160000)),
    case('ex8-1', 8, '例8-1', '计提职工薪酬', UNITS, (500000,),
         '事业单位为开展业务活动的员工计提当月职工薪酬{0}元。',
         pair('业务活动费用', '应付职工薪酬', 500000)),
    case('ex8-3', 8, '例8-3', '领用库存物品', ('police',), (5000,),
         '行政单位业务部门领用库存材料，账面余额为{0}元。',
         pair('业务活动费用', '库存物品', 5000)),
    case('ex8-4', 8, '例8-4', '计提固定资产折旧', ('police',), (3000,),
         '行政单位为开展业务活动使用的固定资产计提折旧{0}元。',
         pair('业务活动费用', '固定资产累计折旧', 3000), depreciation=True),
    case('ex10-1', 10, '例10-1', '财政直接支付办公用品款', ('police',), (20000,),
         '行政单位采用财政直接支付方式购入一批办公用品，款项为{0}元。',
         *direct(20000, '库存物品', '行政支出'),
         fiscal=fiscal_payment(20000, '政府机关商品和服务拨款费用'), payment='direct'),
    case('ex10-3', 10, '例10-3', '收到财政授权支付额度', ('police',), (200000,),
         '行政单位收到财政授权支付额度到账通知书，额度为{0}元。',
         pair('零余额账户用款额度', '财政拨款收入', 200000),
         pair(QUOTA, '财政拨款预算收入', 200000), payment='authorization'),
    case('ex10-5', 10, '例10-5', '收到财政部门实拨预算经费', UNITS, (120000,),
         '事业单位接到开户银行收款通知，收到财政部门拨入的本年预算经费{0}元。',
         pair('银行存款', '财政拨款收入', 120000), pair(MONEY, '财政拨款预算收入', 120000),
         fiscal=fiscal_payment(120000, '对事业单位补助拨款费用'), payment='transfer'),
    case('ex11-3', 11, '例11-3', '使用财政资金购入低值易耗品', ('police',), (85500,),
         '行政单位购入低值易耗品{0}元，在预算管理一体化系统中使用本年度财政资金支付。',
         *direct(85500, '库存物品', '行政支出'),
         fiscal=fiscal_payment(85500, '政府机关商品和服务拨款费用'), payment='direct'),
    case('ex11-4', 11, '例11-4', '以银行存款预付账款', ('police',), (50000,),
         '行政单位采购办公用品，以银行存款向供应方预付{0}元。',
         pair('预付账款', '银行存款', 50000), pair('行政支出', MONEY, 50000)),
    case('ex11-6', 11, '例11-6', '支付行政活动水费和电费', ('police',), (4350,),
         '行政单位在预算管理一体化系统中使用本年度财政资金，支付为开展行政活动而发生的水费和电费共计{0}元。',
         *direct(4350, '业务活动费用', '行政支出'),
         fiscal=fiscal_payment(4350, '政府机关商品和服务拨款费用'), payment='direct'),
    case('ex12-1', 12, '例12-1', '收到财政授权支付额度到账通知书', UNITS, (300000,),
         '事业单位收到财政授权支付额度到账通知书，到账额度为{0}元。',
         pair('零余额账户用款额度', '财政拨款收入', 300000),
         pair(QUOTA, '财政拨款预算收入', 300000), payment='authorization'),
    case('ex12-2', 12, '例12-2', '收取专业业务预付款项', UNITS, (220000,),
         '事业单位拟提供专业业务服务，收到预付款项{0}元，存入开户银行。',
         pair('银行存款', '预收账款', 220000), pair(MONEY, '事业预算收入', 220000)),
    case('ex12-3', 12, '例12-3', '使用零余额账户购买办公用品', UNITS, (800,),
         '事业单位采购随买随用的办公用品用于专业业务活动，使用零余额账户支付{0}元。',
         pair('业务活动费用', '零余额账户用款额度', 800), pair('事业支出', QUOTA, 800),
         fiscal=fiscal_payment(800, '对事业单位补助拨款费用'), payment='authorized'),
    case('ex12-4', 12, '例12-4', '从零余额账户提取现金', UNITS, (1000,),
         '事业单位从零余额账户提取现金{0}元，以备日常零星开支。',
         pair('库存现金', '零余额账户用款额度', 1000), pair(MONEY, QUOTA, 1000),
         fiscal=fiscal_payment(1000, '对事业单位补助拨款费用'), payment='authorized'),
    case('ex12-9', 12, '例12-9', '调入财政拨款结转资金', UNITS, (20000,),
         '事业单位按照规定从外部单位调入财政拨款结转资金{0}元，款项已存入银行。',
         pair('银行存款', '累计盈余', 20000), pair(MONEY, '财政拨款结转——归集调入', 20000)),
    case('ex14-1', 14, '例14-1', '收到增值税收入', ('fiscal',), (400000,),
         '市财政收到国库报来的预算收入日报表，当日收到增值税收入{0}元。',
         pair('国库存款', '税收收入', 400000), pair('资金结存', '一般公共预算收入', 400000)),
    case('ex14-2', 14, '例14-2', '支付政府机关服务费用', ('fiscal',), (210000,),
         '市财政总会计收到国库支付机构报来的为政府机关支付的服务费用{0}元。',
         *fiscal_payment(210000, '政府机关商品和服务拨款费用')),
    case('ex14-7', 14, '例14-7', '使用国有资本经营预算资金投入资本金', ('fiscal',), (2100000,),
         '市财政按批准的预算，用国有资本经营预算资金向国有企业投入资本金{0}元。',
         pair('股权投资', '国库存款', 2100000), pair('国有资本经营预算支出', '资金结存', 2100000)),
    case('ex14-12', 14, '例14-12', '收到一般公共预算收入', ('fiscal',),
         (1261300, 880000, 367000, 8700, 5600),
         '国库收入日报表列有增值税{1}元、企业所得税{2}元、行政事业性收费{3}元、罚没收入{4}元。',
         (('国库存款', 1261300), ('税收收入', -1247000), ('非税收入', -14300)),
         pair('资金结存', '一般公共预算收入', 1261300)),
    case('ex14-13', 14, '例14-13', '收到政府性基金预算收入', ('fiscal',),
         (13500000, 10000000, 3500000),
         '国库报来的政府性基金收入日报表列有国有土地使用权出让收入{1}元、铁路建设基金收入{2}元。',
         pair('国库存款', '非税收入', 13500000),
         pair('资金结存', '政府性基金预算收入', 13500000)),
    case('ex14-16', 14, '例14-16', '以财政直接支付方式支付单位款项', ('fiscal',),
         (360000, 60000, 300000),
         '市财政通过国库直接支付一般公共预算资金{0}元，其中行政运行费用{1}元，工资福利费{2}元。',
         (('政府机关商品和服务拨款费用', 60000), ('政府机关工资福利拨款费用', 300000), ('国库存款', -360000)),
         pair('一般公共预算支出', '资金结存', 360000)),
]

BY_CASE = {c['kind']: c for c in CASES}
REPORT_TABLES = {
    9: ('表9-2 资产负债表', '表9-3 收入费用表'),
    13: ('表13-2 预算收入支出表', '表13-3 预算结转结余变动表', '表13-4 财政拨款预算收入支出表'),
    15: ('表15-1 资产负债表', '表15-2 收入费用表', '表15-4 本年预算结余与本期盈余调节表', '表15-5 预算收入支出表'),
}
CHAPTER_REFERENCES = {
    1: ('ex3-1', 'ex3-4', 'ex10-1'), 2: ('ex3-3a', 'ex3-4', 'ex10-3'),
    9: ('ex7-9a', 'ex7-9b', 'ex5-1', 'ex8-1', 'ex8-4'),
    13: ('ex10-5', 'ex11-3', 'ex11-6', 'ex12-2', 'ex12-9'),
    15: ('ex14-1', 'ex14-2', 'ex14-12', 'ex14-13', 'ex14-16'),
}


def catalog_entry(c):
    return {k: c[k] for k in ('kind', 'name', 'entities', 'source', 'chapter')} | {
        'chapters': [c['chapter']] + [n for n, kinds in CHAPTER_REFERENCES.items() if c['kind'] in kinds],
        'amount': str(c['values'][0]), 'unit': '元', 'fields': [],
        'hint': f"{c['source']} · " + c['statement'].format(*[f'{v:,}' for v in c['values']])}


CATALOG = [catalog_entry(c) for c in CASES]
CATALOG_BY_KIND = {c['kind']: c for c in CATALOG}


def scale(c, value, amount_fen):
    numerator = amount_fen * value
    divisor = c['values'][0]
    if numerator % divisor:
        raise ValueError(f"{c['source']}的分项比例不能精确到分，请调整金额")
    return numerator // divisor


def amount_step(c):
    values = list(c['values']) + [v for book in (c['financial'], c['budget']) for _, v in book]
    return c['values'][0] // gcd(c['values'][0], *values)


def statement(kind, amount):
    c = BY_CASE[kind]
    values = [f'{Decimal(scale(c, v, fen(amount))) / 100:,.2f}'.removesuffix('.00') for v in c['values']]
    return c['statement'].format(*values)


def sections(voucher):
    return voucher.get('sections', [voucher])


def money_total(city, accounts=None):
    return sum(value for ledger in (accounts if accounts is not None else city.ledger.values())
               for account, value in ledger.items()
               if account in {'国库存款', '其他财政存款', '库存现金', '银行存款'} or account.startswith('银行存款——'))


def activate(city):
    if getattr(city, 'textbook_revision', None) == '1125':
        return city
    if not city.events and not city.journals:
        city.ledger.pop('soe', None)
        city.jobs.pop('soe', None)
        for entity in ('hospital', 'school', 'police'):
            city.budget[entity][MONEY] = city.budget[entity].pop('资金结存', 0)
    city.textbook_revision = '1125'
    city.opening_cash = money_total(city) + sum(city.external.values())
    city.case_consumptions = {}
    return city


def new_city(profile, seed):
    city = activate(JingzhouCity(seed) if profile == 'jingzhou2025' else City(seed))
    for entity, amount in OPENING_BANK_DEPOSITS[profile].items():
        if entity not in city.ledger:
            continue  # 教材账套不含国企主体
        ledger = city.ledger[entity]
        cash = '国库存款' if entity == 'fiscal' else '银行存款'
        equity = '实收资本' if entity == 'soe' else '累计盈余'
        difference = fen(amount) - ledger[cash]
        if not difference:
            continue
        ledger[cash] += difference
        ledger[equity] -= difference
        if entity in city.budget:
            budget = city.budget[entity]
            money = '资金结存' if entity == 'fiscal' else MONEY
            reserve = '一般公共预算结转结余' if entity == 'fiscal' else '非财政拨款结余'
            budget[money] += difference
            budget[reserve] -= difference
    city.opening_cash = money_total(city) + sum(city.external.values())
    city.check()
    return city


def prerequisite(city, kind, entity, amount):
    c = BY_CASE[kind]
    if not c.get('prerequisite'):
        return None
    parent, raw = c['prerequisite']
    required = scale(c, raw, fen(amount))
    event = next((e for e in reversed(city.events) if e['kind'] == parent and e['entity'] == entity
                  and fen(e['amount_yuan_or_count']) == required and e['id'] not in city.case_consumptions), None)
    return (parent, Decimal(required)/100, event)


def post_case(city, kind, entity, amount, event_id):
    activate(city)
    c = BY_CASE[kind]
    if entity not in c['entities']:
        raise ValueError('会计主体与教材例题不符')
    if event_id in city.seen:
        return False
    cents = fen(amount)
    if cents <= 0:
        raise ValueError('业务金额必须大于零')
    description = statement(kind, amount)
    dependency = prerequisite(city, kind, entity, amount)
    if dependency and dependency[2] is None:
        raise ValueError(f"请先完成对应的{BY_CASE[dependency[0]]['source']}，金额{dependency[1]}元")
    payment = c.get('payment')
    lines = []
    for subject, books in [(entity, (c['financial'], c['budget'])), ('fiscal', c.get('fiscal', ((), ())))]:
        for book, rows in zip(('financial', 'budget'), books):
            if rows:
                debit, credit = {}, {}
                for account, value in rows:
                    (debit if value > 0 else credit)[account] = abs(scale(c, value, cents))
                if sum(debit.values()) != sum(credit.values()):
                    raise ValueError(f"{c['source']}的分录借贷不平")
                lines.append(dict(entity=subject, book=book, debit=debit, credit=credit,
                                  automatic=subject != entity))
    projected = {}
    for line in lines:
        key = (line['entity'], line['book'])
        if key not in projected:
            ledgers = city.ledger if line['book'] == 'financial' else city.budget
            projected[key] = defaultdict(int, ledgers[line['entity']])
        for account, value in line['debit'].items():
            projected[key][account] += value
        for account, value in line['credit'].items():
            projected[key][account] -= value
    for (subject, book), balances in projected.items():
        if book != 'financial':
            continue
        for account in ('国库存款', '银行存款', '库存现金', '零余额账户用款额度', '库存物品', '在建工程',
                        '预付账款', '应收账款'):
            if balances.get(account, 0) < 0:
                raise ValueError(f'{ACTORS[subject]}的{account}余额不足')
    if c.get('depreciation'):
        assets = [a for a in city.assets if a['entity'] == entity and a['start'] <= max(1, city.month)
                  and not a.get('pending')]
        if sum(a['cost'] - a['used'] for a in assets) < cents:
            raise ValueError('固定资产可计提折旧余额不足')
    before = money_total(city)
    combined = dict(city.ledger)
    combined.update({subject: balances for (subject, book), balances in projected.items() if book == 'financial'})
    cash_change = money_total(city, combined.values()) - before
    if payment:
        expected_change = -cents if payment == 'direct' or kind == 'ex12-3' else 0
        if cash_change != expected_change:
            raise ValueError('单位现金与国库资金的对应关系不平')
    fiscal_lines = {line['book']: line for line in lines if line['automatic']}
    if payment in {'direct', 'transfer', 'authorized'}:
        financial = fiscal_lines.get('financial', {})
        budget = fiscal_lines.get('budget', {})
        if (financial.get('credit', {}).get('国库存款') != cents
                or budget.get('credit', {}).get('资金结存') != cents
                or budget.get('debit', {}).get('一般公共预算支出') != cents):
            raise ValueError('财政总会计国库支付额与预算支出不一致')
        if payment in {'direct', 'transfer'}:
            unit_credits = {part['book']: part['credit'] for part in lines if not part['automatic']}
            if (unit_credits.get('financial', {}).get('财政拨款收入') != cents
                    or unit_credits.get('budget', {}).get('财政拨款预算收入') != cents):
                raise ValueError('单位财政拨款收入与财政总会计支付额不一致')
    if city.external['outside'] < cash_change:
        raise ValueError('外部结算资金余额不足')
    for (subject, book), balances in projected.items():
        (city.ledger if book == 'financial' else city.budget)[subject] = balances
    city.external['outside'] -= cash_change
    if c.get('asset'):
        city.assets.append({'entity': entity, 'cost': cents, 'start': city.month,
                            'used': 0, 'name': c['asset'], 'pending': c.get('asset_pending', False)})
    if c.get('depreciation'):
        remaining = cents
        for asset in assets:
            value = min(remaining, asset['cost'] - asset['used'])
            asset['used'] += value
            remaining -= value
            if not remaining:
                break
    if dependency:
        city.case_consumptions[dependency[2]['id']] = event_id
    number = len(city.journals) + 1
    city.journals.append(dict(voucher=number, month=city.month, event_id=event_id, entity=entity,
                              book=lines[0]['book'], sections=lines))
    city.events.append(dict(id=event_id, month=city.month, kind=kind, entity=entity,
                            amount_yuan_or_count=cents/100, parameters={}, source=c['source'],
                            statement=description, payment=payment,
                            prerequisite_event_id=dependency[2]['id'] if dependency else None))
    city.seen.add(event_id)
    city.check()
    return True


def display_report(report):
    entities = {}
    for key, name in ACTORS.items():
        if key not in report['entities']:
            continue
        entity = report['entities'][key]
        cash = entity['cash_yuan'] if key == 'fiscal' else money_total(None, [entity['financial_balance_fen']])/100
        entities[key] = {**entity, 'name': name, 'cash_yuan': cash}
    return {**report, 'entities': entities,
            'jobs': {key: value for key, value in report.get('jobs', {}).items() if key in ACTORS}}


def advance(city):
    activate(city)
    city.month += 1
    # Non-accounting demographic changes do not create accounting vouchers.
    city.population['children'] += city.rng.randint(8, 20)
    city.population['seniors'] -= min(city.population['seniors'], city.rng.randint(3, 12))
    if city.month % 12 == 9:
        city.students += city.rng.randint(10, 25)

    def post(kind, subject, amount):
        eid = f'M{city.month:03d}-E{len(city.events)+1:05d}'
        post_case(city, kind, subject, amount, eid)

    if city.month > 1:
        last = next((e for e in reversed(city.events) if e['kind'] == 'ex7-9a'
                     and e['id'].startswith('M') and e['id'] not in city.case_consumptions), None)
        if last:
            post('ex7-9b', 'hospital', Decimal(str(last['amount_yuan_or_count'])) * Decimal('1.5'))
    post('ex14-12', 'fiscal', 1261300)
    post('ex10-5', 'hospital', 120000)
    post('ex7-3', 'school', 300000)
    post('ex10-1', 'police', 20000)
    post('ex8-3', 'police', 5000)
    post('ex11-6', 'police', 4350)
    post('ex7-9a', 'hospital', city.rng.randint(80, 120) * 10000)
    post('ex4-8', 'hospital', 50000)
    if city.month == 1:
        post('ex4-68', 'hospital', 210000)
        post('ex4-69a', 'school', 55000)
    if city.month == 2 and any(e['kind'] == 'ex4-69a' and e['entity'] == 'school'
                              and e['id'] not in city.case_consumptions for e in city.events):
        post('ex4-69b', 'school', 55000)
    if city.month % 12 == 9:
        post('ex4-77', 'hospital', 10000)
    if city.month % 12 == 0:
        city.year_reports.append(display_report(city.report()) | {'year': city.month // 12, 'basis': 'textbook_snapshot'})
    city.check()
