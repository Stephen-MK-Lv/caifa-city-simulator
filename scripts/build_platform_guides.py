from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

OUT = Path(__file__).resolve().parents[3]
GREEN, MUTED, LIGHT = '173E38', '66776A', 'EAF0E8'


def font(run, size=10.5, bold=False, color='26372F'):
    run.font.name = 'Microsoft YaHei'
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    run.font.size = Pt(size); run.bold = bold; run.font.color.rgb = RGBColor.from_string(color)


def field(p, code):
    r = p.add_run(); b = OxmlElement('w:fldChar'); b.set(qn('w:fldCharType'), 'begin')
    i = OxmlElement('w:instrText'); i.set(qn('xml:space'), 'preserve'); i.text = code
    s = OxmlElement('w:fldChar'); s.set(qn('w:fldCharType'), 'separate')
    t = OxmlElement('w:t'); t.text = '1'; e = OxmlElement('w:fldChar'); e.set(qn('w:fldCharType'), 'end')
    r._r.extend([b, i, s, t, e])


def shade(cell, fill):
    pr = cell._tc.get_or_add_tcPr(); node = OxmlElement('w:shd'); node.set(qn('w:fill'), fill); pr.append(node)


def make_doc(title, subtitle):
    d = Document(); sec = d.sections[0]
    sec.top_margin = Inches(.68); sec.bottom_margin = Inches(.65); sec.left_margin = Inches(.76); sec.right_margin = Inches(.76)
    sec.footer_distance = Inches(.3)
    normal = d.styles['Normal']; normal.font.name = 'Microsoft YaHei'; normal.font.size = Pt(10.5)
    normal._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    normal.paragraph_format.space_after = Pt(5); normal.paragraph_format.line_spacing = 1.15
    for name, size in [('Title', 24), ('Heading 1', 16), ('Heading 2', 12.5)]:
        st = d.styles[name]; st.font.name = 'Microsoft YaHei'; st.font.size = Pt(size); st.font.bold = True
        st.font.color.rgb = RGBColor.from_string(GREEN); st._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
        st.paragraph_format.keep_with_next = True
        ppr = st._element.get_or_add_pPr(); border = ppr.find(qn('w:pBdr'))
        if border is not None: ppr.remove(border)
    p = d.add_paragraph(style='Title'); p.paragraph_format.space_after = Pt(3); font(p.add_run(title), 24, True, GREEN)
    p = d.add_paragraph(); p.paragraph_format.space_after = Pt(15); font(p.add_run(subtitle), 10.5, False, MUTED)
    f = sec.footer.paragraphs[0]; f.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(f.add_run('彩珐市政府会计仿真教学平台  ·  '), 8.5, False, MUTED); field(f, 'PAGE')
    d.core_properties.title = title; d.core_properties.subject = subtitle
    d.core_properties.author = '中国政府会计学教材配套教学资源'
    return d


def h(d, text, level=1):
    p = d.add_paragraph(style=f'Heading {level}'); p.paragraph_format.space_before = Pt(8); p.paragraph_format.space_after = Pt(4)
    font(p.add_run(text), 16 if level == 1 else 12.5, True, GREEN); return p


def p(d, text, lead=None):
    para = d.add_paragraph(); para.paragraph_format.widow_control = True
    if lead and text.startswith(lead): font(para.add_run(lead), bold=True); font(para.add_run(text[len(lead):]))
    else: font(para.add_run(text))
    return para


def bullets(d, lines):
    for line in lines:
        q = d.add_paragraph(style='List Bullet'); q.paragraph_format.space_after = Pt(3)
        font(q.add_run(line), 10.2)


def table(d, headers, rows, widths):
    t = d.add_table(rows=1, cols=len(headers)); t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.style = 'Table Grid'; t.autofit = False
    trpr = t.rows[0]._tr.get_or_add_trPr(); repeat = OxmlElement('w:tblHeader'); repeat.set(qn('w:val'), 'true'); trpr.append(repeat)
    for j, label in enumerate(headers):
        c = t.rows[0].cells[j]; c.width = Inches(widths[j]); c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER; shade(c, GREEN)
        q = c.paragraphs[0]; q.paragraph_format.space_after = Pt(0); font(q.add_run(label), 9, True, 'FFFFFF')
    for row in rows:
        cells = t.add_row().cells
        trpr = t.rows[-1]._tr.get_or_add_trPr(); trpr.append(OxmlElement('w:cantSplit'))
        for j, value in enumerate(row):
            cells[j].width = Inches(widths[j]); cells[j].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            q = cells[j].paragraphs[0]; q.paragraph_format.space_after = Pt(0); q.paragraph_format.line_spacing = 1.05
            font(q.add_run(str(value)), 8.8)
    d.add_paragraph().paragraph_format.space_after = Pt(0)


def system_manual():
    d = make_doc('彩珐市仿真系统整体介绍与使用说明', '中国政府会计学教材配套数字平台｜教师操作与课堂运行手册')
    p(d, '本平台将彩珐市城市运行仿真和章节教学实训整合在同一入口。教师可观察财政与公共服务主体的业务、凭证和报表，并为班级生成独立练习；学生每人使用自己的城市账套完成分录、核对规则初评，再分析业务对财务与预算信息的影响。')
    h(d, '一 平台定位与组成')
    p(d, '城市图景由财政局、公安局、职业学校、人民医院、城市实业有限公司及居民活动构成。财政局居中表示资金枢纽；公安局、学校、医院和企业为同层级场景主体，不表示行政隶属。教师查看其所管理班级及教学账套，学生仅查看本人任务和个人账套。')
    table(d, ['模块', '主要用途', '入口'], [
        ('统一总览', '汇总当前账号可见账套、人口、业务事件、凭证和财政现金指标。', '登录首页'),
        ('彩珐市运行图景', '按主体浏览业务事件、凭证、账簿、年度报告和资产台账。', '“彩珐市运行图景”或 /city'),
        ('仿真教学工作台', '管理班级、学生、章节任务、分录初评、学生核查和教师复核。', '“班级与任务”“我的章节实训”'),
    ], [1.2, 3.8, 1.45])
    h(d, '二 启动与首次初始化')
    bullets(d, [
        '在“数字资源”目录双击“启动统一教学平台.cmd”。默认浏览器地址为 http://127.0.0.1:8765；关闭启动窗口会停止本地服务。',
        '首次访问创建首位教师账号，密码不少于10位。首位账号仅允许初始化一次，请妥善保管。之后教师、学生均使用各自账号登录。',
        '系统使用彩珐市 Web 仿真目录下的 SQLite 数据库保存账套与教学记录；启动不会覆盖已有账套。未分配给学生的既有账套仅教师可见。',
        '默认只监听本机。若需校内多终端访问，应由管理员配置监听地址、允许主机名和防火墙，并先完成部署安全评估；不要直接暴露到公网。',
    ])
    h(d, '三 教师使用流程')
    table(d, ['步骤', '操作', '结果与检查点'], [
        ('1 创建班级', '输入班级名称和学期。', '班级出现在当前班级列表。'),
        ('2 添加学生', '填写登录名、姓名和至少10位初始密码。', '名单显示账号；教师通过可信渠道告知初始密码。'),
        ('3 发布任务', '选择章节、业务类型、主体、金额/数量、随机差异幅度、基准数据和说明。', '系统为每名学生生成独立场景和城市账套。'),
        ('4 查看进度', '查看任务提交数、确认数、规则初评均分。', '进入“查看作答与复核”阅读学生作答及共同差异。'),
        ('5 教师复核', '结合业务实质、制度版本和学生说明录入评分、结论及理由。', '教师复核状态保存到教学记录。'),
    ], [.9, 3.35, 2.2])
    h(d, '四 学生作答与初评核查')
    p(d, '学生进入“我的章节实训”，先读案例、业务资料与学习重点，再自行确定主体、财务或预算账套、科目、借贷方向和金额。提交后系统逐行比较本题仿真规则生成的参考分录，展示初评分、差异字段、遗漏分录和评分依据。')
    table(d, ['维度', '权重', '核查重点'], [
        ('主体', '20%', '实际承担业务的主体；财政拨款时区分财政与收款单位。'),
        ('账套', '20%', '财务会计、预算会计的适用边界及平行记账判断。'),
        ('科目', '30%', '业务实质、确认条件和制度口径。'),
        ('方向', '20%', '账户性质以及增减方向。'),
        ('金额', '10%', '单位、数量、金额及舍入；多余分录另按规则扣分。'),
    ], [1.1, .65, 4.7])
    bullets(d, [
        '本版本的初评为可解释的规则辅助反馈：仿真引擎执行题目业务后，将参考分录与学生答案逐项比对；当前不调用外部大语言模型。初评不是规范意见或教师最终成绩。',
        '学生可以修改分录后重交，或填写核查说明并提出异议。确认后才将业务写入学生个人城市账套，避免初评前提前改变账簿。',
        '教师可查看异议、学生核查说明及初评依据，并作最终复核。遇到制度版本或业务实质争议，应以教师结合现行有效规范的判断为准。',
    ])
    h(d, '五 城市运行页与教材配合')
    p(d, '在城市运行页选择账套，先观察业务事件，再沿业务追踪凭证、账簿和年度报告。教师可用示范账套讲解；学生在确认作答后查看个人账套中对应的事件、凭证与财务/预算报告变化。')
    bullets(d, [
        '第1—2章讨论双功能、双基础、双报告及制度适用；第3—8章追踪财务会计要素和财务报表；第9—12章分析预算收入、支出、结转结余与预算报表；第13—14章从财政总会计角度分析收支与报告。',
        '不同主体的账簿属于各自会计主体，未经抵销和口径转换不得直接相加。企业收入、税费和分红均为教学模型，不等同于政府综合财务报告口径。',
    ])
    h(d, '六 数据边界与常见问题')
    table(d, ['现象', '处理建议'], [
        ('无法连接', '确认统一启动窗口仍在运行，访问 http://127.0.0.1:8765。'),
        ('登录失败/过期', '核对账号密码；登录令牌8小时失效，重新登录。忘记密码需按部署维护方案处理。'),
        ('学生看不到账套', '确认教师已将学生加入班级并发布任务；学生仅看本人任务和账套。'),
        ('初评不符合判断', '检查逐字段差异和规则依据，提交异议并请教师复核；不要将初评直接当作规范解释。'),
        ('现实报送需求', '系统不连接国库、预算一体化或现实单位业务，不替代法定系统、真实账簿与正式报告。'),
    ], [1.35, 5.1])
    p(d, '人口、医疗教育服务、公共安全、企业经营、税费和就业均由教学模型生成。相关比率与业务规则只适用于课堂仿真，不构成现实城市预测或财政数据。')
    path = OUT / '彩珐市仿真系统整体介绍与使用说明.docx'; d.save(path); return path


CHAPTERS = [
('政府会计理论体系','《政府会计准则——基本准则》颁布对政府会计理论体系的影响','医疗服务 / 人民医院 / 15,000元','比较财务收入与预算收入确认，解释双功能、双基础与分录组合。'),
('中国政府会计制度变迁、标准体系与未来发展','“十三五”以来中国政府会计改革大事记讨论','财政拨款 / 职业学校 / 24,000元','结合教师指定版本辨认主体、事项、生效时间和拨款用途。'),
('资产','财政部青海监管局跨级次调剂共享国有资产','设备购置 / 人民医院 / 86,000元','从验收、资产确认、预算记录和服务潜力分析固定资产。'),
('负债','安徽省铜陵市财政局利用数智技术对债券资金实施穿透式监测','可退保证金 / 人民医院 / 30,000元','判断退款义务、其他应付款确认和不确认收入的理由。'),
('净资产','八〇一水文地质工程地质大队净资产核算实践','日常维修 / 职业学校 / 18,000元','追踪费用、预算支出对净资产及预算结余的影响。'),
('收入','上海国家会计学院财政拨款收入与事业收入分类核算实践','医疗服务 / 人民医院 / 15,000元','区分服务收入、应收款、实收款与预算收入确认。'),
('费用','上海市长宁区 AI 智能辅助自动生成绩效分析评价报告','薪酬确认与支付 / 人民医院 / 72,000元','核对薪酬费用、应付职工薪酬、支付和预算记录。'),
('财务报表','海南省政府综合财务报告编制','医疗服务 / 人民医院 / 15,000元','比较报表前后变化，检查收入、应收款及预算收支勾稽。'),
('预算收入','湖南省桃源县医疗保障局预算收入执行分析','职业教育收费 / 职业学校 / 6,000元','区分事业收入与事业预算收入，追踪收缴与资金结存。'),
('预算支出','山东省滨州经济技术开发区数智驱动预算支出全流程管控','财政拨款 / 公安局 / 42,000元','区分财政拨款和单位实际支出的确认时点。'),
('预算结余','湖南省浏阳市盘活财政存量资金','财政拨款 / 职业学校 / 28,000元','分析拨款后资金结存和年末结转；结合年度推进观察变化。'),
('预算会计报表','常德市预算管理一体化系统上线“定制报表”模块','设备购置 / 公安局 / 35,000元','将预算记录映射到预算报表项目并校验变动。'),
('财政总会计核算体系','四川省财政总会计制度改革试点','财政拨款 / 人民医院 / 54,000元','辨认财政与收款单位的核算对象、预算收支和往来关系。'),
('财政总会计报表','全国财政总会计报表体系建设','财政拨款 / 人民医院 / 54,000元','比较财政与单位报告，解释调节和不可直接加总边界。'),
]


def teaching_manual():
    d = make_doc('仿真教学系统整体介绍与各章使用说明', '中国政府会计学 14 章教学场景｜教师任务设计与学生实训手册')
    p(d, '本手册说明如何把教材章节、课堂业务和个人城市账套连接起来。教师选定章节和情境后发布任务，系统为每名学生生成独立数据。学生独立作答，阅读规则初评及依据，核查、修订或提出异议后再确认过账，最后解释个人账套和报告变化。教师查看班级进度、共性问题并作最终复核。')
    h(d, '一 教学组织与评价边界')
    table(d, ['阶段', '教师组织', '学生任务', '系统留痕'], [
        ('课前准备', '选择章节、业务、主体、金额范围与说明。', '阅读案例和规范范围。', '班级、任务、个人场景与账套。'),
        ('独立实训', '提醒先独立判断，不提前展示答案。', '填制主体、账套、科目、方向和金额。', '答案、时间、备注和规则初评。'),
        ('核查复盘', '回应异议并说明制度依据。', '修改重交或提出异议；核对后确认过账。', '学生核查记录和账簿变化。'),
        ('教师评价', '结合教材、现行规范和学生说明复核。', '完善判断和报表分析。', '教师分数、结论和理由。'),
    ], [1.0, 2.0, 2.1, 1.65])
    p(d, '初评按主体20%、账套20%、科目30%、借贷方向20%、金额10%逐项比对参考分录，额外分录依规则扣分。它是可解释的规则辅助反馈，不调用外部大语言模型，也不自动替代教师评分。复杂业务须以当次教学适用的现行准则制度、解释和问答为准。')
    h(d, '二 每章通用操作')
    bullets(d, [
        '教师：创建班级并添加学生；发布任务时选章节，检查默认业务类型、主体和金额，设置随机差异幅度、基准数据和说明。产品、项目、资产名称等未开放参数使用平台默认值。',
        '学生：进入“我的章节实训”，阅读案例、资料和本章重点；独立确定是否平行记账并填写完整分录。提交后核对字段差异、遗漏行及评分依据。',
        '核查与过账：依据教材和规范修订、重交或提出异议。学生确认后，系统才将业务写入该生专属城市账套；随后查看事件、凭证与财务/预算报告变化。',
        '教师复核：查看学生作答、备注、初评依据和异议，录入分数、结论及理由；根据共同差异组织讲评。',
    ])
    h(d, '三 14章场景与课堂用法')
    for n, (title, case, scenario, focus) in enumerate(CHAPTERS, 1):
        if n == 1 or n % 2 == 1: d.add_page_break()
        h(d, f'第{n}章 {title}', 2)
        chapter_paras = [
            p(d, '引导案例：' + case, lead='引导案例：'),
            p(d, '建议默认情境：' + scenario + '。教师可根据本章目标调整系统提供的业务类型和主体；学生取得独立参数。'),
            p(d, '任务一 规定业务核算：' + focus + ' 学生提交完整分录后，核对系统指出的主体、账套、科目、借贷方向和金额差异。'),
            p(d, '任务二 影响与报告分析：确认前后比较个人账套的关键余额；确认后查看业务事件、凭证和财务/预算报告，解释本章相关项目变动。涉及年末结转的内容，可由教师另行安排月份推进与年度观察。'),
        ]
        for q in chapter_paras: q.paragraph_format.keep_together = True
        for q in chapter_paras[:-1]: q.paragraph_format.keep_with_next = True
    d.add_page_break()
    h(d, '四 分章讲评建议')
    table(d, ['章节范围', '课堂观察焦点', '建议学习成果'], [
        ('第1—2章 理论与制度', '双功能、双基础、双报告；规范主体、事项和生效时间。', '平行记账判断与制度适用说明。'),
        ('第3—8章 财务会计', '资产、负债、净资产、收入费用确认及财务报表联系。', '分录、账户变化和财务报表解释。'),
        ('第9—12章 预算会计', '预算收入、支出、结转结余与预算报表。', '预算执行分析和报表勾稽说明。'),
        ('第13—14章 财政总会计', '财政主体和单位主体边界、报告口径与调节。', '财政与单位双侧分析及合并边界。'),
    ], [1.55, 3.1, 2.0])
    h(d, '五 使用边界与备课提示')
    bullets(d, [
        '教材案例标题对应章节引导情境，不代表案例所涉单位的全部现实事实。教师课前应核实所授事项适用的准则制度、解释、问答及生效版本。',
        '当前任务配置主要包括章节、业务类型、主体、金额/数量、随机差异、数据基准和说明。业务规则中未开放到页面的产品、项目、资产名称与使用年限使用系统默认参数。',
        '系统参考答案是仿真规则产物，不是规范条文。学生应先判断再查看反馈，并核实业务实质与会计口径；遇有争议由教师复核。',
        '学生数据按账号隔离，教师查看本班数据。人口、就业、公共服务和企业经营均是教学模型，不用于现实城市预测、国库支付或法定财务报送。',
    ])
    path = OUT / '仿真教学系统整体介绍与各章使用说明.docx'; d.save(path); return path


if __name__ == '__main__':
    print(system_manual()); print(teaching_manual())
