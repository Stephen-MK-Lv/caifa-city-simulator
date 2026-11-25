"""Chapter order from the 1125 main text, before the older appendix."""
from .textbook import CATALOG, REPORT_TABLES

TITLES = (
    '中国政府会计理论与制度体系', '中国政府会计改革实践', '行政事业单位会计概述',
    '资产', '负债', '净资产', '收入', '费用', '财务报表', '预算收入', '预算支出',
    '预算结余', '预算会计报表', '财政总会计核算体系', '财政总会计报表',
)
NOTES = {
    1: '结合正文第一章的政府会计核算范围与平行记账，引用第三章及第十章例题观察两类会计处理。',
    2: '结合正文第二章的政府会计改革历程，引用第三章及第十章例题观察改革后的核算方式。',
    9: '用下列例题生成账簿基础数据，对照第九章表式观察财务报表项目。',
    13: '用下列例题生成账簿基础数据，对照第十三章表式观察预算会计报表项目。',
    15: '用第十四章财政总会计例题生成数据，对照第十五章表式观察财政总会计报表项目。',
}
CHAPTERS = [
    {'chapter': number, 'title': title, 'note': NOTES.get(number, ''),
     'report_tables': REPORT_TABLES.get(number, ()),
     'business_kinds': [c['kind'] for c in CATALOG if number in c['chapters']]}
    for number, title in enumerate(TITLES, 1)
]
