"""Chapter-aligned scenarios; task amounts are generated for each student."""

CHAPTERS = [
    {'chapter': 1, 'title': '政府会计理论体系', 'case': '《政府会计准则——基本准则》颁布对政府会计理论体系的影响', 'focus': '识别同一业务的财务会计与预算会计边界，说明双功能、双基础、双报告。', 'kind': 'medical', 'entity': 'hospital', 'amount': 12000, 'question': '比较服务收入确认与预算收入确认时点，并解释形成的差异。'},
    {'chapter': 2, 'title': '中国政府会计制度变迁、标准体系与未来发展', 'case': '“十三五”以来中国政府会计改革大事记讨论', 'focus': '辨认规范适用主体、事项和生效时间，说明制度衔接的证据链。', 'kind': 'grant', 'entity': 'school', 'amount': 24000, 'question': '按本章任务所给制度版本判断拨款用途、核算主体和双基础记录。'},
    {'chapter': 3, 'title': '资产', 'case': '财政部青海监管局跨级次调剂共享国有资产', 'focus': '资产取得、建设、折旧、调拨、维修和处置的完整链条。', 'kind': 'purchase', 'entity': 'hospital', 'amount': 86000, 'question': '说明设备验收、资产确认及预算支出的处理。'},
    {'chapter': 4, 'title': '负债', 'case': '安徽省铜陵市财政局利用数智技术对债券资金实施穿透式监测', 'focus': '识别现时义务、债券业务主体及偿付责任，区分预算执行与债务余额。', 'kind': 'deposit', 'entity': 'hospital', 'amount': 30000, 'question': '判断该款项是否形成收入，并说明退款义务和预算会计边界。'},
    {'chapter': 5, 'title': '净资产', 'case': '八〇一水文地质工程地质大队净资产核算实践', 'focus': '联系累计盈余、专用基金和净资产变动原因。', 'kind': 'repair', 'entity': 'school', 'amount': 18000, 'question': '分析费用确认和预算支出对净资产及预算结余的影响。'},
    {'chapter': 6, 'title': '收入', 'case': '上海国家会计学院财政拨款收入与事业收入分类核算实践', 'focus': '区分财政拨款、事业收入、应收款和预算收入确认。', 'kind': 'medical', 'entity': 'hospital', 'amount': 15000, 'question': '解释收入来源、收款比例和财务/预算收入差异。'},
    {'chapter': 7, 'title': '费用', 'case': '上海市长宁区 AI 智能辅助自动生成绩效分析评价报告', 'focus': '费用归集、薪酬确认、成本对象及绩效信息。', 'kind': 'salary', 'entity': 'hospital', 'amount': 72000, 'question': '列示应付职工薪酬确认和支付分录，并解释预算记录。'},
    {'chapter': 8, 'title': '财务报表', 'case': '海南省政府综合财务报告编制', 'focus': '资产负债表、收入费用表和附注，检查报表勾稽。', 'kind': 'medical', 'entity': 'hospital', 'amount': 15000, 'question': '比较业务发生前后的报表项目，检查应收款、收入和预算收支之间的勾稽。'},
    {'chapter': 9, 'title': '预算收入', 'case': '湖南省桃源县医疗保障局预算收入执行分析', 'focus': '预算收入的确认、资金结存和预算收入执行。', 'kind': 'fee', 'entity': 'school', 'amount': 6000, 'question': '区分事业收入和事业预算收入，并追踪现金收缴过程。'},
    {'chapter': 10, 'title': '预算支出', 'case': '山东省滨州经济技术开发区数智驱动预算支出全流程管控', 'focus': '预算授权、支出确认、项目用途和执行进度。', 'kind': 'grant', 'entity': 'police', 'amount': 42000, 'question': '判断拨款与单位实际支出的不同核算时点。'},
    {'chapter': 11, 'title': '预算结余', 'case': '湖南省浏阳市盘活财政存量资金', 'focus': '财政拨款结转结余、资金结存及年终结转。', 'kind': 'grant', 'entity': 'school', 'amount': 28000, 'question': '分析收入、支出发生后预算资金结存和年末结转的变化。'},
    {'chapter': 12, 'title': '预算会计报表', 'case': '常德市预算管理一体化系统上线“定制报表”模块', 'focus': '预算收入支出表、预算结转结余变动和勾稽校验。', 'kind': 'purchase', 'entity': 'police', 'amount': 35000, 'question': '编制该业务对预算会计报表项目的影响并校验分录。'},
    {'chapter': 13, 'title': '财政总会计核算体系', 'case': '四川省财政总会计制度改革试点', 'focus': '一级政府财政主体的预算收支、资产负债和结算业务。', 'kind': 'grant', 'entity': 'hospital', 'amount': 54000, 'question': '分别说明财政总会计与收款单位的会计处理。'},
    {'chapter': 14, 'title': '财政总会计报表', 'case': '全国财政总会计报表体系建设', 'focus': '预算执行、资产负债、收入费用、现金流量与调节表。', 'kind': 'grant', 'entity': 'hospital', 'amount': 54000, 'question': '分析财政拨款业务在财政总会计与单位报表之间的对应关系，并说明不可直接加总的口径。'},
]

for item in CHAPTERS:
    item['task1'] = '规定业务核算：根据生成的业务资料独立确定会计科目，判断是否平行记账，填制完整分录并提交初评。'
    item['task2'] = '影响与报表分析：查看业务过账前后财务和预算数据，解释报表项目变动并完成勾稽核对。'
