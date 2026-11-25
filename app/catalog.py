from .engine import NAMES

UNITS = ['hospital', 'school', 'police']
CATALOG = [
    dict(kind='grant', name='财政拨款', entities=UNITS, unit='元', amount='300000', hint='财政与收款单位分别记账，受财政年度仿真限额约束。', fields=['project']),
    dict(kind='medical', name='医疗服务', entities=['hospital'], unit='元', amount='10000', hint='本期收款70%，其余形成应收账款。', fields=[]),
    dict(kind='collect', name='医疗应收结算', entities=['hospital'], unit='无', amount='0', hint='收回当前全部医疗应收款，不重复确认财务收入。', fields=[]),
    dict(kind='purchase', name='设备购置', entities=UNITS, unit='元', amount='60000', hint='形成固定资产，原引擎预算资金标签固定为财政资金。自有资金购置需扩展规则。', fields=['name', 'life']),
    dict(kind='construction', name='工程投入', entities=UNITS, unit='元', amount='100000', hint='形成在建工程，原引擎预算资金标签固定为财政资金。', fields=['name']),
    dict(kind='complete', name='工程交付', entities=UNITS, unit='无', amount='0', hint='将该主体全部在建工程转入固定资产，仿真假设折旧360个月。', fields=[]),
    dict(kind='salary', name='薪酬确认与支付', entities=UNITS+['soe'], unit='元', amount='20000', hint='经过应付职工薪酬。原教材单位工资标记财政资金；荆州方案医院工资按可用财政资金与自有资金拆分预算支出。企业仅作财务处理。', fields=[]),
    dict(kind='repair', name='日常维修', entities=UNITS, unit='元', amount='8000', hint='假设不符合资本化条件，直接计入费用。', fields=['fund']),
    dict(kind='expense', name='日常费用', entities=UNITS, unit='元', amount='5000', hint='单位事业或行政活动支出。国企费用不使用这一单位账规则。', fields=['fund']),
    dict(kind='fine', name='依法收缴罚款', entities=['police'], unit='元', amount='200', hint='荆州方案：居民直接缴库，公安局无收款分录。原教材方案：特设经允许代收后立即缴库。均不确认为公安收入，不以罚款收入为执法目标。', fields=[]),
    dict(kind='fee', name='职业教育收费', entities=['school'], unit='元', amount='5000', hint='学校为公立职业学校。收缴专户、返还与服务确认按原型简化为一组动作。', fields=[]),
    dict(kind='sales', name='国企生产销售', entities=['soe'], unit='元', amount='50000', hint='输入不含税价款。供电与汽车13%、供水9%为既有仿真假设。', fields=['product']),
    dict(kind='tax', name='缴纳增值税', entities=['soe'], unit='元', amount='1000', hint='不得超过当前模拟应交增值税余额。所得税由年终流程处理。', fields=[]),
    dict(kind='deposit', name='收到可退保证金', entities=UNITS, unit='元', amount='20000', hint='财务会计确认其他应付款，不记预算收入。', fields=[]),
    dict(kind='depreciation', name='全市计提折旧', entities=['hospital'], unit='无', amount='0', hint='按原引擎遍历全市单位资产，每资产每月仅提一次；非仅医院。', fields=[]),
    dict(kind='birth', name='人口出生', entities=['hospital'], unit='人', amount='10', hint='改变儿童人口，不自动产生会计分录。医院仅为场景承载单位。', fields=[]),
    dict(kind='death', name='老年人口减少', entities=['hospital'], unit='人', amount='3', hint='模拟自然死亡，只改变老年人口。医疗业务须另行触发。', fields=[]),
    dict(kind='enrol', name='学生入学', entities=['school'], unit='人', amount='20', hint='增加在校生人数，本事件本身不自动产生收费分录。', fields=[]),
]
BY_KIND = {c['kind']: c for c in CATALOG}
LABELS = {c['kind']: c['name'] for c in CATALOG} | {'year_close': '年度结账与利润分配'}

POLICY_NOTES = [
    '虚拟仿真数据，不是现实城市数字孪生，也不是法定财政报送系统。',
    '规则沿用教材离线原型，未连接外部AI模型。税率、股权60%、利润分配比例等均为既有仿真假设。',
    '财政总会计与单位机关会计分别看待，国企只有企业财务账。各主体收入费用未经抵销，不能直接加总为全市财政或GDP。',
    '每12个月自动结账。当前余额显示结账后的状态；全年收支请选“年度结账前报告”。',
    '自动运行由本地服务器调度，关闭网页仍可推进；关闭服务器会停止。默认年末自动暂停，重启不补跑错过的时间。',
    '原型资金来源标签、学校专户清算与资产汇总交付均作了简化，不支持完整项目审批、专项债、基金会计及法定报表。',
]
