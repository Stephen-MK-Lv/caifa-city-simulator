"""Offline teaching simulation; money is stored as integer fen. No external AI calls."""
import argparse,copy,csv,json,random
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

NAMES={'fiscal':'明川市财政局总会计','hospital':'明川市人民医院','school':'明川职业学校','police':'明川市公安局','soe':'明川城市实业有限公司'}
def fen(x):
    v=Decimal(str(x))*100
    if not v.is_finite() or v!=v.to_integral_value():raise ValueError('金额最多保留两位小数且必须有限')
    return int(v)
def yuan(x):return round(x/100,2)

class City:
    def __init__(self,seed=20260906):
        self.seed=seed;self.rng=random.Random(seed);self.month=0
        self.ledger={k:defaultdict(int) for k in NAMES};self.budget={k:defaultdict(int) for k in NAMES if k!='soe'}
        self.journals=[];self.events=[];self.seen=set();self.year_reports=[];self.closed=set();self.assets=[]
        self.population={'children':1800,'adults':6500,'seniors':1700};self.students=800
        self.jobs={'hospital':120,'school':80,'police':60,'soe':150}
        self.external={'residents':fen(200000000),'outside':fen(1000000000)}
        self.stats=defaultdict(int);self.spent=defaultdict(int)
        self.limits={'hospital':fen(16000000),'school':fen(8000000),'police':fen(4000000),'fiscal':fen(25000000)}
        self.opening_cash=0
        for entity,cash,fixed in [('fiscal',100000000,0),('hospital',2000000,4000000),('school',200000,0),('police',100000,200000),('soe',20000000,0)]:
            ac=self.cash_account(entity);l=self.ledger[entity]
            l[ac]=fen(cash)
            if fixed:l['固定资产']=fen(fixed);self.assets.append({'entity':entity,'cost':fen(fixed),'life':240,'start':1,'used':0,'name':'期初资产'})
            l['实收资本' if entity=='soe' else '累计盈余']=-fen(cash+fixed)
            if entity in self.budget:
                self.budget[entity]['资金结存']=fen(cash)
                self.budget[entity]['一般公共预算结转结余' if entity=='fiscal' else '非财政拨款结余']=-fen(cash)
        self.ledger['fiscal']['股权投资']=fen(12000000);self.ledger['fiscal']['累计盈余']-=fen(12000000)
        self.opening_cash=self.total_cash();self.check()
    def cash_account(self,e):return '国库存款' if e=='fiscal' else '银行存款'
    def total_cash(self):
        if getattr(self, 'textbook_revision', None):
            from ..textbook import money_total
            return money_total(self) + sum(self.external.values())
        return sum(self.ledger[e][self.cash_account(e)] for e in NAMES)+sum(self.external.values())
    def post(self,e,book,dr,cr,event):
        assert sum(dr.values())==sum(cr.values()),'凭证借贷不平'
        assert all(isinstance(v,int) and v>=0 for v in [*dr.values(),*cr.values()]),'金额必须为非负整数分'
        ledger=self.ledger[e] if book=='financial' else self.budget[e]
        for k,v in dr.items():ledger[k]+=v
        for k,v in cr.items():ledger[k]-=v
        self.journals.append({'voucher':len(self.journals)+1,'month':self.month,'event_id':event,'entity':e,'book':book,'debit':dr,'credit':cr})
    def budget_post(self,e,dr,cr,event):
        self.post(e,'budget',dr,cr,event)
    def pay(self,e,a,counterparty='outside'):
        if a<0:raise ValueError('付款不能为负')
        if self.ledger[e][self.cash_account(e)]<a:raise ValueError('资金不足')
        if e!='soe' and self.spent[e]+a>self.limits[e]:raise ValueError('超出本年仿真预算限额')
        self.spent[e]+=a
        if counterparty in self.external:self.external[counterparty]+=a
    def receive(self,counterparty,a):
        if self.external[counterparty]<a:raise ValueError('外部付款方资金不足')
        self.external[counterparty]-=a
    def grant(self,e,a,eid,project='运行'):
        self.pay('fiscal',a,e)
        if project=='资本性':dr={'资本性拨款费用':a}
        elif e!='police':dr={'对事业单位补助拨款费用':a}
        elif project=='工资':dr={'政府机关工资福利拨款费用':a}
        elif project=='商品服务':dr={'政府机关商品和服务拨款费用':a}
        else:
            # The standard police operating appropriation authorizes 80% payroll and 20% services.
            wage=a*80//100;dr={'政府机关工资福利拨款费用':wage,'政府机关商品和服务拨款费用':a-wage}
        self.post('fiscal','financial',dr,{'国库存款':a},eid)
        self.budget_post('fiscal',{'一般公共预算支出':a},{'资金结存':a},eid)
        self.post(e,'financial',{'银行存款':a},{'财政拨款收入':a},eid)
        self.budget_post(e,{'资金结存':a},{'财政拨款预算收入':a},eid)
    def expense(self,e,a,eid,account='业务活动费用',counterparty='outside',fund='self'):
        self.pay(e,a,counterparty);self.post(e,'financial',{account:a},{self.cash_account(e):a},eid)
        if e!='soe':self.budget_post(e,{('行政支出' if e=='police' else '事业支出')+'——'+fund:a},{'资金结存':a},eid)
    def service(self,a,eid):
        paid=a*7//10;owing=a-paid
        self.receive('residents',paid)
        self.post('hospital','financial',{'银行存款':paid,'应收账款':owing},{'事业收入':a},eid)
        self.budget_post('hospital',{'资金结存':paid},{'事业预算收入':paid},eid)
        self.stats['medical_service']+=a
    def collect(self,eid):
        a=self.ledger['hospital']['应收账款'];self.receive('outside',a)
        if a:
            self.post('hospital','financial',{'银行存款':a},{'应收账款':a},eid)
            self.budget_post('hospital',{'资金结存':a},{'事业预算收入':a},eid)
    def salary(self,e,a,eid):
        # Fixed payroll budget including the employer's contribution; no personal tax in this simplified flow.
        self.post(e,'financial',{'营业成本' if e=='soe' else '业务活动费用':a},{'应付职工薪酬':a},eid)
        self.pay(e,a,'residents');self.post(e,'financial',{'应付职工薪酬':a},{'银行存款':a},eid)
        if e!='soe':self.budget_post(e,{('行政支出' if e=='police' else '事业支出')+'——fiscal':a},{'资金结存':a},eid)
    def purchase(self,e,a,eid,name,life=60,construction=False):
        self.pay(e,a);ac='在建工程' if construction else '固定资产'
        self.post(e,'financial',{ac:a},{'银行存款':a},eid)
        self.budget_post(e,{('行政支出' if e=='police' else '事业支出')+'——fiscal':a},{'资金结存':a},eid)
        if not construction:self.assets.append({'entity':e,'cost':a,'life':life,'start':self.month,'used':0,'name':name})
    def complete(self,e,eid):
        a=self.ledger[e]['在建工程']
        if not a:return
        self.post(e,'financial',{'固定资产':a},{'在建工程':a},eid)
        self.assets.append({'entity':e,'cost':a,'life':360,'start':self.month,'used':0,'name':'新建业务楼'})
    def fine(self,a,eid):
        # Approved exceptional collection scenario. Normal direct treasury collection skips the police cash entries.
        self.receive('residents',a)
        self.post('police','financial',{'银行存款':a},{'应缴财政款':a},eid)
        self.post('police','financial',{'应缴财政款':a},{'银行存款':a},eid)
        self.post('fiscal','financial',{'国库存款':a},{'非税收入':a},eid)
        self.budget_post('fiscal',{'资金结存':a},{'一般公共预算收入':a},eid)
        self.stats['fine']+=a
    def school_fee(self,a,eid):
        # Treasury special account is tracked outside the simplified fiscal main ledger.
        self.receive('residents',a)
        self.post('school','financial',{'银行存款':a},{'应缴财政款':a},eid)
        self.external['outside']+=a
        self.post('school','financial',{'应缴财政款':a},{'银行存款':a},eid)
        self.receive('outside',a)
        self.post('school','financial',{'银行存款':a},{'事业收入':a},eid)
        self.budget_post('school',{'资金结存':a},{'事业预算收入':a},eid)
    def sales(self,a,eid,product='供电'):
        # 13% electricity/cars and 9% water: specified general VAT teaching assumptions, no concessions.
        rate=9 if product=='供水' else 13;vat=a*rate//100
        cost=a*55//100;input_vat=cost*rate//100
        self.pay('soe',cost+input_vat)
        self.post('soe','financial',{'原材料':cost,'应交税费——应交增值税':input_vat},{'银行存款':cost+input_vat},eid)
        self.post('soe','financial',{'生产成本':cost},{'原材料':cost},eid)
        self.post('soe','financial',{'库存商品':cost},{'生产成本':cost},eid)
        self.receive('residents',a+vat)
        self.post('soe','financial',{'银行存款':a+vat},{'营业收入——'+product:a,'应交税费——应交增值税':vat},eid)
        self.post('soe','financial',{'营业成本':cost},{'库存商品':cost},eid)
        self.stats['sales']+=a
    def tax(self,a,eid):
        self.pay('soe',a,'fiscal')
        self.post('soe','financial',{'应交税费——应交增值税':a},{'银行存款':a},eid)
        local=a//2;external=a-local;self.external['outside']+=external
        self.post('fiscal','financial',{'国库存款':local},{'税收收入':local},eid)
        self.budget_post('fiscal',{'资金结存':local},{'一般公共预算收入':local},eid)
        self.stats['tax']+=a
    def depreciation(self,eid):
        for asset in self.assets:
            if asset['start']<=self.month and asset['used']<asset['cost'] and asset.get('last_month',-1)<self.month:
                a=min(asset['cost']-asset['used'],(asset['cost']+asset['life']-1)//asset['life'])
                self.post(asset['entity'],'financial',{'业务活动费用':a},{'固定资产累计折旧':a},eid)
                asset['used']+=a;asset['last_month']=self.month
    def event(self,kind,amount=0,entity='hospital',event_id=None,**kw):
        if kind not in {'grant','medical','collect','salary','purchase','construction','complete','repair','expense','fine','fee','sales','tax','depreciation','deposit','birth','death','enrol'}:raise ValueError('未知业务类型')
        entity={'medical':'hospital','collect':'hospital','fee':'school','fine':'police','sales':'soe','tax':'soe'}.get(kind,entity)
        if entity not in NAMES:raise ValueError('未知主体')
        if kind in {'salary','expense','repair'} and entity=='fiscal':raise ValueError('本事件不适用于财政总会计')
        if kind=='sales' and kw.get('product','供电') not in {'供电','供水','汽车'}:raise ValueError('未知产品')
        if kind=='purchase' and (not isinstance(kw.get('life',60),int) or kw.get('life',60)<=0):raise ValueError('折旧月数必须为正整数')
        if kind in {'grant','purchase','construction','complete','deposit'} and entity not in {'hospital','school','police'}:raise ValueError('该业务限单位账主体')
        if kind in {'birth','death','enrol'} and (isinstance(amount,bool) or int(amount)!=amount):raise ValueError('人口和学生变动必须是整数')
        a=fen(amount)
        if a<0:raise ValueError('金额或人数不能为负')
        eid=event_id or f'M{self.month:03d}-E{len(self.events)+1:05d}'
        if eid in self.seen:return False
        if self.month and self.month%12==0 and self.month//12 in self.closed:raise ValueError('本年已结账，先推进下一月')
        snapshot=copy.deepcopy(self.__dict__)
        try:
            if kind=='grant':self.grant(entity,a,eid,kw.get('project','运行'))
            elif kind=='medical':self.service(a,eid)
            elif kind=='collect':self.collect(eid)
            elif kind=='salary':self.salary(entity,a,eid)
            elif kind in {'expense','repair'}:self.expense(entity,a,eid,fund=kw.get('fund','self'))
            elif kind in {'purchase','construction'}:self.purchase(entity,a,eid,kw.get('name',kind),kw.get('life',60),kind=='construction')
            elif kind=='complete':self.complete(entity,eid)
            elif kind=='fine':self.fine(a,eid)
            elif kind=='fee':self.school_fee(a,eid)
            elif kind=='sales':self.sales(a,eid,kw.get('product','供电'))
            elif kind=='tax':self.tax(a,eid)
            elif kind=='depreciation':self.depreciation(eid)
            elif kind=='deposit':
                self.receive('outside',a);self.post(entity,'financial',{'银行存款':a},{'其他应付款':a},eid)
            elif kind=='birth':self.population['children']+=int(amount);self.stats['births']+=int(amount)
            elif kind=='death':
                count=int(amount)
                if count>self.population['seniors']:raise ValueError('老年人口不足')
                self.population['seniors']-=count;self.stats['deaths']+=count
            elif kind=='enrol':
                if self.students+int(amount)>self.population['children']+self.population['adults']:raise ValueError('生源不足')
                self.students+=int(amount)
            self.seen.add(eid);self.events.append({'id':eid,'month':self.month,'kind':kind,'entity':entity,'amount_yuan_or_count':amount,'parameters':kw})
            self.check();return True
        except Exception:
            self.__dict__.clear();self.__dict__.update(snapshot);raise
    def report(self):
        out={'month':self.month,'seed':self.seed,'population':dict(self.population),'students':self.students,'jobs':self.jobs.copy(),'entities':{}}
        for e,l in self.ledger.items():
            revenue=-sum(v for k,v in l.items() if ('收入' in k or k=='投资收益') and k!='本年利润')
            cost=sum(v for k,v in l.items() if '费用' in k or k=='营业成本')
            b=self.budget.get(e,{})
            br=-sum(v for k,v in b.items() if '收入' in k)
            be=sum(v for k,v in b.items() if '支出' in k)
            out['entities'][e]={'name':NAMES[e],'financial_balance_fen':dict(l),'budget_balance_fen':dict(b),'revenue_yuan':yuan(revenue),'expense_yuan':yuan(cost),'surplus_yuan':yuan(revenue-cost),'budget_revenue_yuan':yuan(br),'budget_expenditure_yuan':yuan(be),'budget_difference_yuan':yuan(br-be),'cash_yuan':yuan(l[self.cash_account(e)])}
        out['cash_conservation_difference_fen']=self.total_cash()-self.opening_cash
        return out
    def close_year(self):
        snapshot=copy.deepcopy(self.__dict__)
        try:return self._close_year_impl()
        except Exception:
            self.__dict__.clear();self.__dict__.update(snapshot);raise
    def _close_year_impl(self):
        if self.month<=0 or self.month%12:raise ValueError('只能在年度最后一月结账')
        year=(self.month-1)//12+1
        if year in self.closed:return False
        # Tax and dividend flow uses known taxable-income and distributable-profit teaching assumptions.
        report=self.report();profit=fen(report['entities']['soe']['surplus_yuan']);tax=max(0,profit)//4
        eid=f'Y{year}-所得税及利润分配'
        if tax:
            self.post('soe','financial',{'所得税费用':tax},{'应交税费——所得税':tax},eid)
            self.pay('soe',tax,'fiscal');self.post('soe','financial',{'应交税费——所得税':tax},{'银行存款':tax},eid)
            local=tax*40//100;self.external['outside']+=tax-local
            self.post('fiscal','financial',{'国库存款':local},{'税收收入':local},eid)
            self.budget_post('fiscal',{'资金结存':local},{'一般公共预算收入':local},eid)
        after=profit-tax;government_share=after*60//100
        if government_share>0:self.post('fiscal','financial',{'股权投资':government_share},{'投资收益':government_share},eid)
        elif government_share<0:self.post('fiscal','financial',{'投资收益':-government_share},{'股权投资':-government_share},eid)
        prior_loss=max(0,self.ledger['soe']['未分配利润'])
        distributable=max(0,after-prior_loss)
        reserve=min(distributable//10,max(0,-self.ledger['soe']['实收资本']//2+self.ledger['soe']['盈余公积']))
        dividend=(distributable-reserve)*30//100;gov=dividend*60//100
        # Reserve then distribute only after explicit simulated year-end approval.
        if reserve:self.post('soe','financial',{'利润分配':reserve},{'盈余公积':reserve},eid)
        if dividend:
            self.post('soe','financial',{'利润分配':dividend},{'应付股利':dividend},eid)
            self.pay('soe',dividend,'fiscal');self.external['residents']+=dividend-gov
            self.post('soe','financial',{'应付股利':dividend},{'银行存款':dividend},eid)
            self.post('fiscal','financial',{'应收股利':gov},{'股权投资':gov},eid)
            self.post('fiscal','financial',{'国库存款':gov},{'应收股利':gov},eid)
            self.budget_post('fiscal',{'资金结存':gov},{'国有资本经营预算收入':gov},eid)
        report=self.report();report['year']=year;report['assumed_corporate_income_tax_yuan']=yuan(tax);report['approved_total_dividend_yuan']=yuan(dividend)
        self.year_reports.append(report)
        for e,l in self.ledger.items():
            target='本年利润' if e=='soe' else '本期盈余'
            for k,v in list(l.items()):
                if not v or not ('收入' in k or '费用' in k or k in {'营业成本','投资收益'}):continue
                if v>0:self.post(e,'financial',{target:v},{k:v},eid)
                else:self.post(e,'financial',{k:-v},{target:-v},eid)
            v=l[target];dest='未分配利润' if e=='soe' else '累计盈余'
            if v>0:self.post(e,'financial',{dest:v},{target:v},eid)
            elif v<0:self.post(e,'financial',{target:-v},{dest:-v},eid)
            if e=='soe' and l['利润分配']:
                v=l['利润分配'];self.post(e,'financial',{'未分配利润':v},{'利润分配':v},eid)
            if e in self.budget:
                b=self.budget[e]
                for k,v in list(b.items()):
                    if not v or not ('收入' in k or '支出' in k):continue
                    if e=='fiscal':target='国有资本经营预算结转结余' if '国有资本' in k else '一般公共预算结转结余'
                    else:target='财政拨款结转' if ('财政拨款' in k or k.endswith('——fiscal')) else '非财政拨款结余'
                    if v>0:self.budget_post(e,{target:v},{k:v},eid)
                    else:self.budget_post(e,{k:-v},{target:-v},eid)
        self.closed.add(year);self.seen.add(eid)
        self.events.append({'id':eid,'month':self.month,'kind':'year_close','entity':'fiscal','amount_yuan_or_count':0,'parameters':{'year':year,'tax_assumption':0.25,'government_share':0.6,'dividend_ratio_after_reserve':0.3}})
        self.check();return True
    def advance(self):
        self.month+=1;m=(self.month-1)%12+1;y=(self.month-1)//12
        if m==1:self.spent=defaultdict(int)
        self.event('collect')
        for e,a in [('hospital',300000),('school',200000),('police',150000)]:self.event('grant',a,e)
        if self.month==1:
            for e,a,name in [('hospital',600000,'医疗设备'),('police',100000,'警务设备')]:
                self.event('grant',a,e,project='资本性');self.event('purchase',a,e,name=name)
            for e,a in [('hospital',3000000),('school',2000000)]:self.event('grant',a,e,project='资本性');self.event('construction',a,e)
            self.event('grant',80000,'hospital');self.event('repair',80000,'hospital',fund='fiscal')
        if self.month==3:self.event('complete',entity='school')
        if self.month==9:self.event('complete',entity='hospital')
        births=self.rng.randint(8,16);deaths=self.rng.randint(3,8)
        self.event('birth',births);self.event('death',deaths)
        # Birth/death affect demographic state only. Any treatment is separately invoiced and recognized.
        if m==9:self.event('enrol',20)
        population=sum(self.population.values());visits=self.rng.randint(900,1300)*population//10000
        self.stats['visits']+=visits;self.event('medical',visits*300)
        self.event('fee',50000,'school')
        for e,a in [('hospital',300000),('school',180000),('police',120000),('soe',200000)]:self.event('salary',a,e)
        for e,a in [('hospital',100000),('school',70000),('police',30000)]:self.event('expense',a,e,fund='self' if e!='police' else 'fiscal')
        self.event('fine',self.rng.randint(5,20)*200,'police')
        for product,base in [('供电',800000),('供水',300000),('汽车',500000)]:self.event('sales',int(base*(1.03**y)*self.rng.uniform(.9,1.1)),'soe',product=product)
        tax=max(0,-self.ledger['soe']['应交税费——应交增值税']);self.event('tax',yuan(tax),'soe')
        self.event('depreciation')
        if m==12:self.close_year()
        self.check()
    def check(self):
        assert all(sum(x.values())==0 for x in self.ledger.values()),'财务试算不平'
        assert all(sum(x.values())==0 for x in self.budget.values()),'预算试算不平'
        assert all(self.ledger[e][self.cash_account(e)]>=0 for e in self.ledger),'现金为负'
        assert self.total_cash()==self.opening_cash,'现金守恒失败'
        assert all(v>=0 for v in self.population.values()),'人口为负'
        if not getattr(self, 'textbook_revision', None):
            assert self.ledger['police']['应缴财政款']==0,'模拟罚没款未缴库'
    def export(self,path):
        path=Path(path);path.mkdir(parents=True,exist_ok=True)
        for name,data in [('当前状态',self.report()),('年度报表数据',self.year_reports),('业务事件',self.events),('会计凭证',self.journals)]:
            (path/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        with (path/'会计分录.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(['凭证号','月份','业务编号','主体','账套','方向','科目','金额元'])
            for j in self.journals:
                for side in ['debit','credit']:
                    for account,a in j[side].items():w.writerow([j['voucher'],j['month'],j['event_id'],NAMES[j['entity']],j['book'],'借' if side=='debit' else '贷',account,yuan(a)])
        print('已导出',path.resolve(),'业务',len(self.events),'凭证',len(self.journals),'现金守恒差额',self.total_cash()-self.opening_cash)

def main():
    p=argparse.ArgumentParser(description='明川市政府会计仿真 原型1.0')
    p.add_argument('--months',type=int,default=12);p.add_argument('--seed',type=int,default=20260906);p.add_argument('--out',default='运行输出');p.add_argument('--events',help='手工事件JSON数组，先于自动月份运行');p.add_argument('--interactive',action='store_true')
    args=p.parse_args()
    if not 0<=args.months<=1200:p.error('months应在0至1200之间')
    city=City(args.seed)
    if args.events:
        for e in json.loads(Path(args.events).read_text(encoding='utf-8-sig')):city.event(**e)
    for _ in range(args.months):city.advance()
    if args.interactive:
        print('输入next推进一月，report查看状态，quit退出；其他输入为单笔业务JSON。')
        while True:
            s=input('明川市> ').strip()
            if s=='quit':break
            try:
                if s=='next':city.advance()
                elif s=='report':print(json.dumps(city.report(),ensure_ascii=False,indent=2))
                else:city.event(**json.loads(s))
            except Exception as ex:print('业务未执行：',ex)
    city.export(args.out)

if __name__=='__main__':main()
