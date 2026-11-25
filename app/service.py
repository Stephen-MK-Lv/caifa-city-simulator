import copy
import csv
import hashlib
import io
import json
import re
import time
import uuid
import zipfile
from decimal import Decimal
from sqlalchemy import select, func, false
from .database import (Simulation, BusinessEvent, Voucher, JournalLine, YearReport,
                       MonthSnapshot, Command, StudentWork)
from .engine.state import dump_city, load_city, ENGINE_VERSION
from .catalog import LABELS
from .branding import account_name, report_names, command_result
from .textbook import ACTORS, advance, display_report, new_city, post_case, sections


class NotFound(Exception): pass
class Conflict(Exception): pass
class RuleError(Exception): pass


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def metadata(s):
    result = {k: getattr(s, k) for k in ('id', 'name', 'seed', 'month', 'version', 'running',
                                      'interval', 'pause_at_year', 'last_error', 'created_at', 'updated_at')}
    result['name'] = account_name(result['name'])
    result['profile_id'] = s.state.get('profile_id', 'textbook')
    result['is_shared'] = s.owner_user_id is None
    return result


def get_sim(session, sid):
    s = session.get(Simulation, sid)
    if s is None: raise NotFound('未找到该账套')
    return s


def restore(session, s):
    events = session.scalars(select(BusinessEvent).where(BusinessEvent.simulation_id==s.id)
                             .order_by(BusinessEvent.sequence)).all()
    journals = session.scalars(select(Voucher).where(Voucher.simulation_id==s.id)
                               .order_by(Voucher.number)).all()
    years = session.scalars(select(YearReport).where(YearReport.simulation_id==s.id)
                            .order_by(YearReport.year)).all()
    return load_city(s.state, [e.payload for e in events], [j.payload for j in journals], [y.payload for y in years])


def remember_snapshot(session, s, report):
    from .monthly import snapshot_payload
    snap = session.scalar(select(MonthSnapshot).where(MonthSnapshot.simulation_id==s.id,
                                                      MonthSnapshot.month==report['month']))
    payload = snapshot_payload(report)
    if snap: snap.payload = payload
    else: session.add(MonthSnapshot(simulation_id=s.id, month=report['month'], payload=payload))


def persist(session, s, city, counts):
    ne, nj, ny = counts
    event_ids = {}
    for index, e in enumerate(city.events[ne:], ne+1):
        row = BusinessEvent(simulation_id=s.id, event_key=e['id'], sequence=index, month=e['month'],
                            entity=e['entity'], kind=e['kind'], payload=e)
        session.add(row); session.flush(); event_ids[e['id']] = row.id
    for j in city.journals[nj:]:
        event_pk = event_ids.get(j['event_id'])
        if not event_pk:
            event_pk = session.scalar(select(BusinessEvent.id).where(BusinessEvent.simulation_id==s.id,
                                                                    BusinessEvent.event_key==j['event_id']))
        row = Voucher(simulation_id=s.id, event_id=event_pk, number=j['voucher'], month=j['month'],
                      entity=j['entity'], book=j['book'], payload=j)
        session.add(row); session.flush()
        for part in sections(j):
            for side in ('debit', 'credit'):
                for account, amount in part[side].items():
                    session.add(JournalLine(voucher_id=row.id, side=side, account=account, amount_fen=amount,
                                            entity=part['entity'], book=part['book']))
    for report in city.year_reports[ny:]:
        session.add(YearReport(simulation_id=s.id, year=report['year'], payload=report))
    s.state = dump_city(city)
    s.month = city.month
    s.version += 1
    s.updated_at = time.time()
    city.check()


class SimulationService:
    def __init__(self, db): self.db = db

    def list_simulations(self, owner_user_id=None):
        with self.db.transaction() as session:
            statement = select(Simulation).order_by(Simulation.created_at.desc())
            if owner_user_id is not None:
                statement = statement.where(Simulation.owner_user_id == owner_user_id)
            return [metadata(s) for s in session.scalars(statement)]

    def create(self, body):
        payload = body.model_dump(mode='json')
        # Preserve fingerprints of pre-profile creation requests.
        if payload.get('profile_id') == 'textbook':
            payload.pop('profile_id')
        sid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'mingchuan-create/'+body.request_id))
        fp = digest(payload)
        with self.db.transaction(write=True) as session:
            existing = session.get(Simulation, sid)
            if existing:
                cmd = session.scalar(select(Command).where(Command.simulation_id==sid, Command.request_id==body.request_id))
                if not cmd or cmd.fingerprint!=fp: raise Conflict('此创建请求编号已用于不同内容')
                return command_result(cmd.result) | {'duplicate': True}
            city = new_city(body.profile_id, body.seed)
            s = Simulation(id=sid, name=body.name, seed=body.seed, month=0, version=0,
                           running=False, interval=8, pause_at_year=True, state=dump_city(city))
            session.add(s); session.flush()
            remember_snapshot(session, s, display_report(city.report()))
            try:
                for _ in range(body.initial_months):
                    advance(city); remember_snapshot(session, s, display_report(city.report()))
            except (ValueError, AssertionError) as exc:
                raise RuleError(str(exc)) from exc
            persist(session, s, city, (0,0,0))
            result = {'simulation': metadata(s), 'new_events': len(city.events), 'new_vouchers': len(city.journals), 'duplicate': False}
            session.add(Command(simulation_id=sid, request_id=body.request_id, fingerprint=fp, result=result))
            return result

    def execute(self, sid, action, body):
        payload = body.model_dump(mode='json')
        fp = digest({'action':action, 'body':payload})
        with self.db.transaction(write=True) as session:
            s = get_sim(session, sid)
            previous = session.scalar(select(Command).where(Command.simulation_id==sid, Command.request_id==body.request_id))
            if previous:
                if previous.fingerprint!=fp: raise Conflict('请求编号已用于不同内容，请勿改写后重复提交')
                return command_result(previous.result) | {'duplicate':True}
            if body.expected_version != s.version:
                raise Conflict('账套已被其他窗口或自动运行更新，请刷新后重试')
            waiting = session.scalar(select(StudentWork.id).where(StudentWork.simulation_id == sid,
                StudentWork.case_data['revision'].as_string() == '1125', StudentWork.confirmed_at.is_(None)).limit(1))
            if waiting and not (action == 'run' and not body.running):
                raise Conflict('该账套有待确认的实训任务，请按发布顺序完成入账后继续运行城市')
            if action!='run' and action!='auto' and s.running:
                raise Conflict('请先暂停自动运行，再进行手动业务或月份推进')
            city = restore(session, s)
            counts = (len(city.events), len(city.journals), len(city.year_reports))
            duplicate = False
            try:
                if action=='run':
                    if body.running and city.month>=120: raise ValueError('当前仿真版本最多运行120个月，请新建账套')
                    s.running = body.running
                    s.interval = body.interval
                    s.pause_at_year = body.pause_at_year
                    s.next_tick = time.time()+body.interval if body.running else None
                    s.last_error = None
                elif action in {'advance','auto'}:
                    if action=='auto' and (not s.running or not s.next_tick or s.next_tick>time.time()):
                        return {'simulation': metadata(s), 'skipped': True}
                    if city.month+body.months>120: raise ValueError('当前仿真版本最多运行120个月，请新建账套')
                    for _ in range(body.months):
                        advance(city)
                        remember_snapshot(session, s, display_report(city.report()))
                    if action=='auto':
                        if (s.pause_at_year and city.month%12==0) or city.month>=120:
                            s.running=False; s.next_tick=None
                        else: s.next_tick=time.time()+s.interval
                    s.last_error=None
                elif action=='event':
                    eid = 'W-'+body.event_id if body.event_id else 'W-'+body.request_id
                    old = next((e for e in city.events if e['id']==eid), None)
                    event_payload = {'kind':body.kind, 'entity':body.entity, 'amount_yuan_or_count':float(body.amount)}
                    if old:
                        if any(old[k]!=v for k,v in event_payload.items()): raise Conflict('业务编号已经使用，且原业务内容不同')
                        duplicate=True
                    else:
                        post_case(city, body.kind, body.entity, body.amount, eid)
                        remember_snapshot(session,s,display_report(city.report()))
                else: raise ValueError('未知操作')
                if not duplicate: persist(session, s, city, counts)
            except (ValueError, AssertionError) as exc:
                raise RuleError(str(exc)) from exc
            # Any exception rolls back ALL tables, checkpoint and RNG state.
            result = {'simulation':metadata(s), 'new_events':len(city.events)-counts[0],
                      'new_vouchers':len(city.journals)-counts[1], 'duplicate':duplicate}
            session.add(Command(simulation_id=sid, request_id=body.request_id, fingerprint=fp, result=result))
            return result

    def tick(self):
        from .schemas import Advance
        with self.db.transaction() as session:
            due = [metadata(s)|{'next_tick':s.next_tick} for s in session.scalars(select(Simulation).where(
                Simulation.running==True, Simulation.next_tick<=time.time()).limit(8))]
        for s in due:
            body=Advance(request_id=f"auto-{int(s['next_tick']*1000000)}", expected_version=s['version'], months=1)
            try: self.execute(s['id'],'auto',body)
            except Conflict: continue
            except Exception as exc:
                # Failed automatic month was rolled back. Persist only the pause/error.
                with self.db.transaction(write=True) as session:
                    current=get_sim(session,s['id'])
                    if current.version==s['version']:
                        current.running=False; current.next_tick=None; current.version+=1
                        current.last_error=str(exc)[:450] if isinstance(exc,RuleError) else '自动运行失败，数据未提交，请查看服务器日志'
                        current.updated_at=time.time()
                if not isinstance(exc,RuleError):
                    import logging; logging.exception('Automatic simulation failed')

    def summary(self,sid):
        with self.db.transaction() as session:
            s=get_sim(session,sid); c=restore(session,s); r=display_report(c.report())
            entities=[]
            for key, value in r['entities'].items():
                entities.append({'id':key, **value, 'jobs':c.jobs.get(key,0),
                                 'limit_fen':c.limits.get(key), 'spent_fen':c.spent.get(key,0)})
            return {'simulation':metadata(s), 'population':c.population, 'students':c.students, 'jobs':r['jobs'],
                    'entities':entities, 'event_count':sum(e['entity'] in ACTORS for e in c.events),
                    'voucher_count':sum(j['entity'] in ACTORS for j in c.journals),
                    'assets':c.assets, 'stats':dict(c.stats), 'closed_years':sorted(c.closed),
                    'engine_version':ENGINE_VERSION, 'reference':r.get('reference'), 'parameters':r.get('parameters'),
                    'invariants':{'financial_balance_fen':sum(abs(sum(v.values())) for v in c.ledger.values()),
                                  'budget_balance_fen':sum(abs(sum(v.values())) for v in c.budget.values()),
                                  'cash_difference_fen':r['cash_conservation_difference_fen']},
                    'history':[v.payload for v in session.scalars(select(MonthSnapshot).where(MonthSnapshot.simulation_id==sid).order_by(MonthSnapshot.month))],
                    'recent_events':[event_view(e) for e in session.scalars(select(BusinessEvent).where(BusinessEvent.simulation_id==sid, BusinessEvent.entity.in_(ACTORS)).order_by(BusinessEvent.sequence.desc()).limit(6))]}

    def monthly(self,sid):
        from .monthly import monthly_series
        with self.db.transaction() as session:
            s=get_sim(session,sid)
            current=display_report(load_city(s.state,[],[],[]).report())
            return monthly_series(session,s,current)

    def events(self,sid,entity=None,kind=None,month=None,search='',offset=0,limit=25):
        with self.db.transaction() as session:
            get_sim(session,sid)
            criteria=[BusinessEvent.simulation_id==sid, BusinessEvent.entity.in_(ACTORS)]
            if entity: criteria.append(BusinessEvent.entity==entity)
            if kind: criteria.append(BusinessEvent.kind==kind)
            if month is not None: criteria.append(BusinessEvent.month==month)
            search = search.strip()
            code = re.fullmatch(r'(?:业-)?([0-9]+)', search)
            if code:
                digits = code.group(1).lstrip('0') or '0'
                criteria.append(BusinessEvent.sequence == int(digits) if len(digits) <= 18 else false())
            elif search:
                criteria.append(BusinessEvent.event_key.contains(search, autoescape=True))
            total=session.scalar(select(func.count()).select_from(BusinessEvent).where(*criteria))
            rows=session.scalars(select(BusinessEvent).where(*criteria).order_by(BusinessEvent.sequence.desc()).offset(offset).limit(limit)).all()
            return {'total':total,'offset':offset,'limit':limit,'items':[event_view(e) for e in rows]}

    def event_detail(self,sid,event_id):
        with self.db.transaction() as session:
            get_sim(session,sid)
            e=session.scalar(select(BusinessEvent).where(BusinessEvent.simulation_id==sid,BusinessEvent.id==event_id,
                                                         BusinessEvent.entity.in_(ACTORS)))
            if not e: raise NotFound('未找到该业务')
            rows=session.scalars(select(Voucher).where(Voucher.simulation_id==sid,Voucher.event_id==e.id,
                                                       Voucher.entity.in_(ACTORS)).order_by(Voucher.number)).all()
            return {**event_view(e),'vouchers':[voucher_view(v, e.business_code) for v in rows]}

    def vouchers(self,sid,entity=None,book=None,month=None,search='',offset=0,limit=25):
        with self.db.transaction() as session:
            get_sim(session,sid)
            criteria=[Voucher.simulation_id==sid, Voucher.entity.in_(ACTORS)]
            line_filters = []
            if entity: line_filters.append(func.coalesce(JournalLine.entity, Voucher.entity)==entity)
            if book: line_filters.append(func.coalesce(JournalLine.book, Voucher.book)==book)
            if month is not None: criteria.append(Voucher.month==month)
            if search:
                line_filters.append(JournalLine.account.contains(search,autoescape=True))
            if line_filters:
                criteria.append(select(JournalLine.id).where(JournalLine.voucher_id==Voucher.id, *line_filters).exists())
            total=session.scalar(select(func.count()).select_from(Voucher).where(*criteria))
            rows=session.execute(select(Voucher, BusinessEvent.business_code).join(
                BusinessEvent, BusinessEvent.id == Voucher.event_id).where(*criteria)
                .order_by(Voucher.number.desc()).offset(offset).limit(limit)).all()
            return {'total':total,'offset':offset,'limit':limit,
                    'items':[voucher_view(v, code) for v, code in rows]}

    def reports(self,sid,year=None):
        with self.db.transaction() as session:
            s=get_sim(session,sid)
            years=session.scalars(select(YearReport).where(YearReport.simulation_id==sid).order_by(YearReport.year)).all()
            if year is None: report=restore(session,s).report()
            else:
                row=next((y for y in years if y.year==year),None)
                if not row: raise NotFound('该年度尚未完成结账')
                report=report_names(row.payload)
            return {'report':display_report(report),'years':[y.year for y in years],
                    'basis':'current' if year is None else report.get('basis', 'before_closing')}

    def export_zip(self,sid):
        with self.db.transaction() as session:
            s=get_sim(session,sid); c=restore(session,s)
            codes = dict(session.execute(select(BusinessEvent.event_key, BusinessEvent.business_code).where(
                BusinessEvent.simulation_id == sid, BusinessEvent.entity.in_(ACTORS))).all())
            events = [e | {'id': codes[e['id']], 'prerequisite_event_id': codes.get(e.get('prerequisite_event_id'))}
                      for e in c.events if e['id'] in codes]
            journals = [j | {'event_id': codes[j['event_id']]}
                        for j in c.journals if j['entity'] in ACTORS and j['event_id'] in codes]
            data={'当前状态.json':display_report(c.report()),'年度报表数据.json':[display_report(r) for r in c.year_reports],
                  '业务事件.json':events,'会计凭证.json':journals}
            if hasattr(c, 'reference'):
                data['仿真数据依据.json'] = {'reference': c.reference, 'parameters': c.parameters}
            text=io.StringIO(newline='');w=csv.writer(text)
            w.writerow(['凭证号','月份','业务编号','会计主体','会计核算','方向','会计科目','金额（元）'])
            def safe(v):
                v=str(v)
                return "'"+v if v[:1] in ('=','+','-','@','\t','\r') else v
            for j in journals:
                for part in sections(j):
                    for side in ('debit','credit'):
                        for account,a in part[side].items():
                            w.writerow([j['voucher'],j['month'],safe(j['event_id']),ACTORS[part['entity']],
                                        '财务会计' if part['book']=='financial' else '预算会计',
                                        '借' if side=='debit' else '贷',safe(account),str(Decimal(a)/100)])
            target=io.BytesIO()
            with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
                for name,value in data.items():z.writestr(name,json.dumps(value,ensure_ascii=False,indent=2))
                z.writestr('会计分录.csv',text.getvalue().encode('utf-8-sig'))
                z.writestr('使用说明.txt','虚拟仿真数据。JSON账簿以整数分表示，借正贷负。CSV以元表示。年度报告为结账前快照，当前状态为结账后余额。该导出包用于分析，不是完整数据库恢复备份。')
            return target.getvalue()


def event_view(e):
    return {**e.payload,'id':e.id,'event_key':e.event_key,'event_number':e.sequence,'business_code':e.business_code,
            'label':LABELS.get(e.kind,e.kind),
            'legacy': not bool(e.payload.get('source'))}


def voucher_view(v, business_code):
    parts = sections(v.payload)
    return {'id':v.id,'event_pk':v.event_id,**v.payload,'sections':parts,'business_code':business_code,
            'legacy': 'sections' not in v.payload,
            'total_fen':sum(sum(p['debit'].values()) for p in parts if p['entity']==v.entity and p['book']==v.book)}
