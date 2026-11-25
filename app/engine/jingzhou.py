"""Versioned teaching scenario, not a reconstruction of Jingzhou's accounts."""
import copy
from collections import defaultdict
from .legacy_city import City, fen, yuan

PROFILE_ID = 'jingzhou2025'
REFERENCE = {
    'id': PROFILE_ID, 'version': 1, 'title': '荆州公开数据参考 · 1∶100 仿真缩尺',
    'data_year': 2025, 'retrieved_at': '2026-10-09', 'scale_denominator': 100,
    'scope': '全市统计量用于缩尺；四个示范单位不是荆州真实单位，财政局不是四单位的行政上级。',
    'facts': [
        {'label': '常住人口', 'value': 5082900, 'unit': '人', 'basis': '2025年末全市', 'source': 'statistics', 'page': 9},
        {'label': '城镇新增就业', 'value': 67000, 'unit': '人/年', 'basis': '年度流量，不是就业岗位存量', 'source': 'statistics', 'page': 3},
        {'label': '一般公共预算收入', 'value': 19099000000, 'unit': '元/年', 'basis': '全市年度收入，不是国库存款', 'source': 'statistics', 'page': 7},
        {'label': '一般公共预算支出', 'value': 58299000000, 'unit': '元/年', 'basis': '全市年度支出，不是市本级支出', 'source': 'statistics', 'page': 7},
        {'label': '中职在校生', 'value': 26400, 'unit': '人', 'basis': '全市中等职业学校', 'source': 'statistics', 'page': 8},
        {'label': '中职教职工', 'value': 2200, 'unit': '人', 'basis': '全市中等职业学校', 'source': 'statistics', 'page': 8},
        {'label': '卫生机构人员', 'value': 49220, 'unit': '人', 'basis': '全市卫生机构，不是单家医院', 'source': 'statistics', 'page': 9},
        {'label': '实际国库存款余额', 'value': None, 'unit': '元', 'basis': '本次未检索到可核验公开值；不得以金融机构存款代替', 'source': None},
    ],
    'derived': {'population': 50829, 'students': 264, 'hospital_jobs': 492, 'school_jobs': 22,
                'annual_new_employment_reference': 670, 'opening_treasury_yuan': 48582500},
    'methods': [
        '人口=5,082,900÷100；学生=26,400÷100；医院代表岗位=49,220÷100四舍五入；学校代表岗位=2,200÷100。行业汇总缩尺不等于真实单家单位规模。',
        '期初仿真国库存款=58,299,000,000÷12÷100=48,582,500元，假设储备一个月平均支出；不是对实际国库余额的估计。',
        '公安60个、国企150个岗位为教材假设；四主体合计724个，不代表全市就业总量。670人/年仅为新增就业参考，不加到岗位存量，也不自动生成工资。',
        '年龄结构18%儿童、17%老年，其余为成人；生育、死亡、收费、薪酬、拨款、销售、税负、持股及分红均为仿真规则，不是荆州预测或真实单位数据。',
        '统计公报数据为2025年统计快报数；全市含所辖地区，不能解释为市本级财政完整账套。',
    ],
    'business_modes': [
        {'entity': 'fiscal', 'text': '预算安排→拨款→单位核算→年末结转；本模型简化为实拨资金，不声称复原全部国库集中支付流程。', 'source': None},
        {'entity': 'hospital', 'text': '诊疗、医保等应收款回款、设备采购、楼宇建设及维修；地方采购公告仅作采购业务参照，金额另设。', 'source': 'hospital'},
        {'entity': 'school', 'text': '财政保障、仿真运行、工程采购、招生；收入演示保留教材财政专户缴返流程，金额不适用于真实中职收费或免学费政策判断。', 'source': 'school'},
        {'entity': 'police', 'text': '地方业务参照2024年交警道路隐患排查、交通安全提示等公开实践（不代表2026年全部业务）。财政保障警务、装备和训练；本方案罚款由居民直接缴入国库，不确认为公安局收入，不与拨款挂钩。公安岗位和业务量均是假设。', 'source': 'police'},
        {'entity': 'soe', 'text': '供水及配套经营参考地方城发披露；供电、汽车整合为一家企业是教材虚构，不表示荆州城发经营汽车制造。按教材假设缴税、分红。', 'source': 'soe'},
    ],
    'sources': [
        {'id': 'statistics', 'title': '荆州市2025年国民经济和社会发展统计公报（湖北省统计局发布）', 'url': 'https://tjj.hubei.gov.cn/tjsj/tjgb/ndtjgb/sztjgb/202605/P020260508383487119307.pdf'},
        {'id': 'hospital', 'title': '荆州市第一人民医院体检管理系统升级项目结果公告（2026-04-01；仅核实公开检索摘要）', 'url': 'https://www.ccgp.gov.cn/cggg/dfgg/zbgg/202604/t20260401_26343389.htm'},
        {'id': 'school', 'title': '荆州职业技术学院学校运动场维修改造项目（二次）结果公告（2025-08-18）', 'url': 'https://www.hbggzy.cn/jyxx/003002/003002004/20250818/4a97571fbfe84e5fbf52c218dbba4f640000.html'},
        {'id': 'soe', 'title': '荆州城发2026年度第一期超短期融资券募集说明书', 'url': 'https://www.chinamoney.org.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3298771&mode=save&priority=0'},
        {'id': 'police', 'title': '湖北省公安厅：荆州三大队公路交通安全整治成效显著（2024-05-14）', 'url': 'https://gat.hubei.gov.cn/bmdt/dtyw/202405/t20240514_5189661.shtml'},
    ],
}


class JingzhouCity(City):
    def __init__(self, seed=20260906):
        super().__init__(seed)
        self.profile_id = PROFILE_ID
        self.reference = copy.deepcopy(REFERENCE)
        self.population = {'children': 9149, 'adults': 33039, 'seniors': 8641}
        self.students = 264
        self.jobs = {'hospital': 492, 'school': 22, 'police': 60, 'soe': 150}
        self.parameters = {
            'monthly_grants_yuan': {'hospital': 500000, 'school': 200000, 'police': 450000},
            'monthly_salary_per_job_yuan': 6000,
            'monthly_expenses_yuan': {'hospital': 600000, 'school': 70000, 'police': 90000},
            'monthly_school_fee_yuan': 26400,
            'monthly_visits_range': [9000, 13000], 'fee_per_visit_yuan': 300,
            'monthly_births_range': [20, 35], 'monthly_deaths_range': [30, 45],
            'annual_enrolment': 20, 'monthly_fine_count_range': [5, 20], 'fine_yuan': 200,
            'monthly_sales_base_yuan': {'供电': 1500000, '供水': 600000, '汽车': 1000000},
            'sales_annual_growth': 0.03, 'sales_random_range': [0.9, 1.1],
            'opening_cash_yuan': {'fiscal': 48582500, 'hospital': 5000000, 'school': 1000000, 'police': 1000000, 'soe': 20000000},
            'annual_budget_limits_yuan': {'hospital': 60000000, 'school': 8000000, 'police': 8000000, 'fiscal': 30000000},
            'initial_equipment_yuan': {'hospital': 600000, 'police': 100000},
            'initial_construction_yuan': {'hospital': 3000000, 'school': 2000000},
            'initial_repair_yuan': 80000,
            'note': '除期初国库储备公式、行业缩尺人口学生岗位外，全部金额和随机区间为仿真假设；年终税利、固定资产及外部资金沿用教材基准规则。医院工资按可用财政资金与自有资金拆分预算支出；无项目级资金追踪。',
        }
        for e, cash in self.parameters['opening_cash_yuan'].items():
            delta = fen(cash) - self.ledger[e][self.cash_account(e)]
            self.ledger[e][self.cash_account(e)] += delta
            self.ledger[e]['实收资本' if e == 'soe' else '累计盈余'] -= delta
            if e in self.budget:
                self.budget[e]['资金结存'] += delta
                self.budget[e]['一般公共预算结转结余' if e == 'fiscal' else '非财政拨款结余'] -= delta
        self.limits = {e: fen(v) for e, v in self.parameters['annual_budget_limits_yuan'].items()}
        self.opening_cash = self.total_cash()
        self.check()

    def fine(self, a, eid):
        # Direct collection: no police revenue, receivable, cash or budget entry.
        self.receive('residents', a)
        self.post('fiscal', 'financial', {'国库存款': a}, {'非税收入': a}, eid)
        self.budget_post('fiscal', {'资金结存': a}, {'一般公共预算收入': a}, eid)
        self.stats['fine'] += a

    def salary(self, e, a, eid):
        if e != 'hospital':
            return super().salary(e, a, eid)
        # Mixed hospital funding: do not label its entire payroll as fiscal spending.
        b = self.budget[e]
        available = max(0, -b['财政拨款预算收入'] - b['财政拨款结转']
                        - sum(v for k, v in b.items() if k.endswith('——fiscal')))
        fiscal = min(a, available)
        self.post(e, 'financial', {'业务活动费用': a}, {'应付职工薪酬': a}, eid)
        self.pay(e, a, 'residents')
        self.post(e, 'financial', {'应付职工薪酬': a}, {'银行存款': a}, eid)
        debit = {}
        if fiscal:
            debit['事业支出——fiscal'] = fiscal
        if a > fiscal:
            debit['事业支出——self'] = a - fiscal
        self.budget_post(e, debit, {'资金结存': a}, eid)

    def report(self):
        return super().report() | {'reference': copy.deepcopy(self.reference), 'parameters': copy.deepcopy(self.parameters)}

    def advance(self):
        self.month += 1
        m = (self.month - 1) % 12 + 1
        y = (self.month - 1) // 12
        p = self.parameters
        if m == 1:
            self.spent = defaultdict(int)
        self.event('collect')
        for e, a in p['monthly_grants_yuan'].items():
            self.event('grant', a, e)
        if self.month == 1:
            for e, a in p['initial_equipment_yuan'].items():
                self.event('grant', a, e, project='资本性')
                self.event('purchase', a, e, name='医疗设备' if e == 'hospital' else '警务设备')
            for e, a in p['initial_construction_yuan'].items():
                self.event('grant', a, e, project='资本性')
                self.event('construction', a, e)
            self.event('grant', p['initial_repair_yuan'], 'hospital')
            self.event('repair', p['initial_repair_yuan'], 'hospital', fund='fiscal')
        if self.month == 3:
            self.event('complete', entity='school')
        if self.month == 9:
            self.event('complete', entity='hospital')
        self.event('birth', self.rng.randint(*p['monthly_births_range']))
        self.event('death', min(self.population['seniors'], self.rng.randint(*p['monthly_deaths_range'])))
        if m == 9:
            self.event('enrol', p['annual_enrolment'])
        visits = self.rng.randint(*p['monthly_visits_range']) * sum(self.population.values()) // 50829
        self.stats['visits'] += visits
        self.event('medical', visits * p['fee_per_visit_yuan'])
        self.event('fee', p['monthly_school_fee_yuan'], 'school')
        for e, jobs in self.jobs.items():
            self.event('salary', jobs * p['monthly_salary_per_job_yuan'], e)
        for e, a in p['monthly_expenses_yuan'].items():
            self.event('expense', a, e, fund='fiscal' if e == 'police' else 'self')
        self.event('fine', self.rng.randint(*p['monthly_fine_count_range']) * p['fine_yuan'], 'police')
        for product, base in p['monthly_sales_base_yuan'].items():
            self.event('sales', int(base * (1 + p['sales_annual_growth']) ** y * self.rng.uniform(*p['sales_random_range'])), 'soe', product=product)
        self.event('tax', yuan(max(0, -self.ledger['soe']['应交税费——应交增值税'])), 'soe')
        self.event('depreciation')
        if m == 12:
            self.close_year()
        self.check()
