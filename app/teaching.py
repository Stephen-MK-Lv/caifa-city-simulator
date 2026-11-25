"""Classroom templates, grouped exercises and traceable assessment."""
import copy
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import hmac
import random
import secrets
import time
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func, or_, delete
from sqlalchemy.exc import IntegrityError
from .chapters import CHAPTERS
from .catalog import BY_KIND, CATALOG
from .database import (ClassMember, ClassCity, LoginSession, Simulation, StudentWork,
                       TeachingAssignment, TeachingAudit, TeachingClass, User,
                       BusinessEvent, Voucher)
from .engine import City, NAMES
from .engine.jingzhou import JingzhouCity
from .engine.state import load_city
from .schemas import EventInput
from .service import metadata, persist, restore, remember_snapshot, digest

router = APIRouter(prefix='/api/teaching', tags=['仿真系统'])
auth_router = APIRouter(prefix='/api/auth', tags=['平台账号'])
WEIGHTS = {'主体': 20, '账套': 20, '科目': 30, '方向': 20, '金额': 10}
DEFAULT_INSTRUCTION = '逐项阅读业务资料，独立编制完整分录，判断是否平行记账；核对初评依据，再解释财务与预算报告的变化。'
EXERCISE_TEMPLATES = [
    {'id': 'foundation', 'name': '双基础入门', 'description': '医疗服务与可退保证金，辨认收入和负债。', 'events': [
        {'kind': 'medical', 'entity': 'hospital', 'amount': '12000'},
        {'kind': 'deposit', 'entity': 'hospital', 'amount': '20000'}]},
    {'id': 'assets', 'name': '资产与财政保障', 'description': '拨款、采购、维修和折旧，追踪资产全流程。', 'events': [
        {'kind': 'grant', 'entity': 'hospital', 'amount': '100000', 'project': '资本性'},
        {'kind': 'purchase', 'entity': 'hospital', 'amount': '60000'},
        {'kind': 'repair', 'entity': 'hospital', 'amount': '8000'},
        {'kind': 'depreciation', 'entity': 'hospital', 'amount': '0'}]},
    {'id': 'comprehensive', 'name': '城市综合实训', 'description': '医院、学校和国企七项业务，联系收支、成本和税费。', 'events': [
        {'kind': 'medical', 'entity': 'hospital', 'amount': '15000'},
        {'kind': 'collect', 'entity': 'hospital', 'amount': '0'},
        {'kind': 'purchase', 'entity': 'hospital', 'amount': '35000'},
        {'kind': 'salary', 'entity': 'hospital', 'amount': '20000'},
        {'kind': 'fee', 'entity': 'school', 'amount': '6000'},
        {'kind': 'sales', 'entity': 'soe', 'amount': '50000'},
        {'kind': 'tax', 'entity': 'soe', 'amount': '1000'}]},
]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Credentials(Input):
    username: str = Field(min_length=3, max_length=50, pattern=r'^[A-Za-z0-9_.@-]+$')
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(min_length=1, max_length=80)


class Login(Input):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class ClassCreate(Input):
    name: str = Field(min_length=1, max_length=100)
    term: str = Field(default='', max_length=80)
    profile_id: Literal['textbook', 'jingzhou2025'] = 'textbook'


class StudentCreate(Credentials):
    pass


class BusinessSpec(Input):
    kind: str
    entity: Literal['fiscal', 'hospital', 'school', 'police', 'soe']
    amount: Decimal = Field(default=Decimal('0'), ge=0, le=Decimal('1000000000'), max_digits=12, decimal_places=2)
    product: Literal['供电', '供水', '汽车'] = '供电'
    project: Literal['运行', '资本性', '工资', '商品服务'] = '运行'
    fund: Literal['self', 'fiscal'] = 'self'
    asset_name: str = Field(default='仿真设备', min_length=1, max_length=60)
    life: int = Field(default=60, ge=1, le=1200)


class PublishBase(Input):
    class_id: str
    chapter: int = Field(ge=1, le=14)
    title: str = Field(min_length=1, max_length=160)
    instruction: str = Field(default=DEFAULT_INSTRUCTION, min_length=1, max_length=3000)
    amount_variation_percent: int = Field(default=8, ge=0, le=25)
    profile_id: Literal['textbook', 'jingzhou2025'] = 'textbook'
    request_id: str | None = Field(default=None, min_length=8, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')


class AssignmentCreate(PublishBase, BusinessSpec):
    """Compatibility with previously published single-business clients."""


class AssignmentGroupCreate(PublishBase):
    events: list[BusinessSpec] = Field(min_length=1, max_length=18)


class AssignmentBatch(Input):
    class_id: str
    request_id: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    tasks: list[AssignmentGroupCreate] = Field(min_length=1, max_length=14)


class ClassDelete(Input):
    confirm_name: str


class TemplateClassCreate(ClassCreate):
    size: int = Field(ge=1, le=100)
    username_prefix: str = Field(default='caifa', min_length=3, max_length=20, pattern=r'^[A-Za-z0-9_-]+$')
    request_id: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    chapter: int = Field(default=1, ge=1, le=14)
    exercise_template_id: Literal['none', 'foundation', 'assets', 'comprehensive'] = 'none'
    amount_variation_percent: int = Field(default=8, ge=0, le=25)
    profile_id: Literal['textbook', 'jingzhou2025'] = 'textbook'


class Submission(Input):
    entries: list[dict] = Field(max_length=400)
    student_note: str = Field(default='', max_length=2000)
    analysis: str = Field(default='', max_length=4000)


class StudentCheck(Input):
    action: Literal['confirm', 'dispute']
    note: str = Field(default='', max_length=2000)


class TeacherReview(Input):
    score: int = Field(ge=0, le=100)
    decision: Literal['confirmed', 'needs_revision']
    rationale: str = Field(min_length=5, max_length=2000)


def password_digest(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    result = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310_000)
    return 'pbkdf2_sha256$310000$%s$%s' % (salt.hex(), result.hex())


def check_password(password, encoded):
    try:
        algorithm, rounds, salt, expected = encoded.split('$')
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return algorithm == 'pbkdf2_sha256' and hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class UserIdentity:
    def __init__(self, id, username, display_name, role, active):
        self.id, self.username, self.display_name, self.role, self.active = id, username, display_name, role, active


def current_user(request: Request, authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(401, '请先登录仿真平台')
    token_hash = hashlib.sha256(authorization[7:].strip().encode()).hexdigest()
    with request.app.state.db.transaction() as session:
        login = session.get(LoginSession, token_hash)
        if not login or login.expires_at <= time.time():
            raise HTTPException(401, '登录已过期，请重新登录')
        u = session.get(User, login.user_id)
        if not u or not u.active:
            raise HTTPException(403, '账号已停用')
        return UserIdentity(u.id, u.username, u.display_name, u.role, u.active)


def role(user, expected):
    if user.role != expected:
        raise HTTPException(403, '此操作不适用于当前账号角色')


def user_view(u):
    return {'id': u.id, 'username': u.username, 'display_name': u.display_name, 'role': u.role}


def audit(session, actor, action, target, detail=None):
    session.add(TeachingAudit(actor_id=actor.id, action=action, target_id=str(target), detail=detail or {}))


def initialize_deployment_teacher(db):
    """Seed the first teacher from private deployment variables before serving requests."""
    username = os.environ.get('CAIFA_INITIAL_TEACHER_USERNAME', '').strip()
    password = os.environ.get('CAIFA_INITIAL_TEACHER_PASSWORD', '')
    display_name = os.environ.get('CAIFA_INITIAL_TEACHER_NAME', '教师管理员').strip()
    deployment_mode = bool(os.environ.get('RAILWAY_ENVIRONMENT_ID'))
    bootstrap_disabled = os.environ.get('CAIFA_DISABLE_BOOTSTRAP', '0') == '1' or deployment_mode

    if bool(username) != bool(password):
        raise RuntimeError('首次教师初始化需要同时设置用户名和密码。')

    with db.transaction(write=True) as session:
        user_count = session.scalar(select(func.count()).select_from(User)) or 0
        if user_count:
            return
        if username and password:
            credentials = Credentials(username=username, password=password, display_name=display_name)
            user = User(username=credentials.username,
                        password_hash=password_digest(credentials.password),
                        display_name=credentials.display_name, role='teacher')
            session.add(user)
            session.flush()
            audit(session, user, 'bootstrap_teacher', user.id, {'source': 'deployment_environment'})
            return
        if bootstrap_disabled:
            raise RuntimeError('公网部署的数据库尚无教师账号；请设置首次教师初始化变量后重启服务。')


def load_class(session, class_id, teacher_id):
    row = session.get(TeachingClass, class_id)
    if not row or row.teacher_id != teacher_id:
        raise HTTPException(404, '未找到该班级')
    return row


def visible_simulations(user):
    statement = select(Simulation)
    if user.role == 'student':
        return statement.where(Simulation.owner_user_id == user.id)
    student_ids = select(ClassMember.user_id).join(TeachingClass, ClassMember.class_id == TeachingClass.id).where(
        TeachingClass.teacher_id == user.id)
    return statement.where(or_(Simulation.owner_user_id.is_(None), Simulation.owner_user_id == user.id,
                               Simulation.owner_user_id.in_(student_ids)))


@auth_router.get('/status')
def auth_status(request: Request):
    with request.app.state.db.transaction() as session:
        count = session.scalar(select(func.count()).select_from(User)) or 0
    return {'setup_required': count == 0, 'login_available': count > 0}


@auth_router.post('/bootstrap', status_code=201)
def bootstrap(body: Credentials, request: Request):
    if os.environ.get('CAIFA_DISABLE_BOOTSTRAP', '0') == '1' or os.environ.get('RAILWAY_ENVIRONMENT_ID'):
        raise HTTPException(403, '公网部署已关闭首位教师自助初始化，请由管理员完成安全初始化。')
    with request.app.state.db.transaction(write=True) as session:
        if session.scalar(select(func.count()).select_from(User)):
            raise HTTPException(409, '教师账号已初始化')
        u = User(username=body.username, password_hash=password_digest(body.password),
                 display_name=body.display_name, role='teacher')
        session.add(u); session.flush(); audit(session, u, 'bootstrap_teacher', u.id)
        return {'user': user_view(u)}


@auth_router.post('/login')
def login(body: Login, request: Request):
    with request.app.state.db.transaction(write=True) as session:
        u = session.scalar(select(User).where(User.username == body.username))
        if not u or not u.active or not check_password(body.password, u.password_hash):
            raise HTTPException(401, '账号或密码不正确')
        token = secrets.token_urlsafe(36)
        session.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(),
                                 user_id=u.id, expires_at=time.time() + 28800))
        return {'access_token': token, 'token_type': 'bearer', 'expires_in': 28800, 'user': user_view(u)}


@auth_router.get('/me')
def whoami(user=Depends(current_user)):
    return user_view(user)


@auth_router.post('/logout')
def logout(request: Request, user=Depends(current_user), authorization: str | None = Header(default=None)):
    with request.app.state.db.transaction(write=True) as session:
        row = session.get(LoginSession, hashlib.sha256(authorization[7:].strip().encode()).hexdigest())
        if row:
            session.delete(row)
    return {'ok': True}


def canonical_event(body):
    spec = BY_KIND.get(body.kind)
    if not spec:
        raise HTTPException(422, '未知业务类型，请刷新页面重试')
    values = {'kind': body.kind, 'entity': body.entity, 'amount': body.amount,
              'product': body.product, 'project': body.project, 'fund': body.fund,
              'name': body.asset_name, 'life': body.life}
    try:
        checked = EventInput.model_validate({'request_id': 'validate-scenario', 'expected_version': 0, **values})
    except ValueError as exc:
        raise HTTPException(422, f"{spec['name']}：主体、金额或业务参数无效，请检查适用主体和计量单位。") from exc
    return {'kind': checked.kind, 'entity': checked.entity, 'amount': str(checked.amount),
            'parameters': {k: values[k] for k in spec['fields']}}


def new_city(profile, seed):
    return JingzhouCity(seed) if profile == 'jingzhou2025' else City(seed)


def execute_event(city, event):
    amount = float(event['amount_yuan_or_count'])
    if event['kind'] == 'tax':
        available = max(0, -city.ledger['soe']['应交税费——应交增值税'])
        if Decimal(str(amount)) * 100 > available:
            raise ValueError('缴税金额超过当前应交增值税余额')
    city.event(event['kind'], amount, event['entity'], event_id=event['event_id'], **event['parameters'])


def expected_entries(city, start):
    rows = []
    for v in city.journals[start:]:
        for side in ('debit', 'credit'):
            for account, amount in v[side].items():
                if amount:
                    rows.append({'event_id': v['event_id'], 'entity': v['entity'], 'book': v['book'],
                                 'side': side, 'account': account, 'amount_fen': int(amount)})
    return rows


def prepare_case(assignment, student, work_id, base_city=None):
    config = assignment.scenario
    specs = config.get('events') or [{k: config[k] for k in ('kind', 'entity', 'amount', 'parameters')}]
    seed = int.from_bytes(hashlib.sha256(f'{assignment.id}:{student.id}'.encode()).digest()[:4], 'big')
    rng = random.Random(seed)
    events = []
    for n, spec in enumerate(specs, 1):
        unit = BY_KIND[spec['kind']]['unit']
        amount = Decimal(spec['amount'])
        if amount and config['variation']:
            amount *= Decimal(str(rng.uniform(1-config['variation']/100, 1+config['variation']/100)))
        amount = amount.quantize(Decimal('1') if unit == '人' else Decimal('.01'), rounding=ROUND_HALF_UP)
        if unit != '无':
            amount = max(Decimal('1') if unit == '人' else Decimal('.01'), amount)
        events.append({'event_id': f'CASE-{work_id}-{n}', 'kind': spec['kind'], 'entity': spec['entity'],
                       'amount_yuan_or_count': str(amount), 'parameters': copy.deepcopy(spec['parameters']),
                       'business': BY_KIND[spec['kind']]['name'], 'entity_name': NAMES[spec['entity']], 'unit': unit})
    base = copy.deepcopy(base_city) if base_city is not None else new_city(config['profile_id'], seed)
    preparations = []
    preparation_events = []

    def add_preparation(kind, amount, entity='hospital', **parameters):
        eid = f'PREP-{work_id}-{len(preparations)+1}'
        base.event(kind, float(amount), entity, event_id=eid, **parameters)
        preparation_events.append({'event_id':eid, 'kind':kind, 'entity':entity,
                                   'amount_yuan_or_count':str(amount), 'parameters':parameters})
        preparations.append(f"{NAMES[entity]}：{BY_KIND[kind]['name']} {amount}元（期初仿真准备，不列入本题待答分录）")

    # Dependencies are actual, persisted opening transactions, not unexplained ledger edits.
    for _ in range(len(events)*3 + 3):
        probe = copy.deepcopy(base)
        restart = False
        for event in events:
            kind, entity = event['kind'], event['entity']
            if kind == 'collect' and probe.ledger['hospital']['应收账款'] <= 0:
                add_preparation('medical', 10000); restart = True; break
            if kind == 'complete' and probe.ledger[entity]['在建工程'] <= 0:
                add_preparation('construction', 50000, entity, name='待交付工程'); restart = True; break
            if kind == 'depreciation' and not any(a['start'] <= probe.month and a.get('last_month', -1) < probe.month
                                                and a['used'] < a['cost'] for a in probe.assets):
                add_preparation('purchase', 10000, name='折旧实训设备', life=60); restart = True; break
            if kind == 'tax':
                short = Decimal(event['amount_yuan_or_count']) - Decimal(max(0, -probe.ledger['soe']['应交税费——应交增值税']))/100
                if short > 0:
                    add_preparation('sales', (short*25+1000).quantize(Decimal('.01')), 'soe', product='供电')
                    restart = True; break
            start = len(probe.journals)
            try:
                execute_event(probe, event)
            except ValueError as exc:
                if str(exc) == '资金不足' and entity in {'hospital', 'school', 'police'}:
                    add_preparation('grant', Decimal(event['amount_yuan_or_count']), entity)
                    restart = True; break
                raise
            event['reference_line_count'] = len(expected_entries(probe, start))
        if not restart:
            break
    else:
        raise ValueError('本组业务前置条件存在冲突，请调整业务顺序或金额')
    before = base.report()
    refs = expected_entries(probe, len(base.journals))
    ch = CHAPTERS[assignment.chapter-1]
    statements = []
    for n, event in enumerate(events, 1):
        quantity = '按当前余额计算' if event['unit'] == '无' else f"{event['amount_yuan_or_count']}{event['unit']}"
        statements.append(f"业务{n}：{event['entity_name']}发生{event['business']}，{quantity}。")
    case = {'preparation_events': preparation_events, 'chapter': assignment.chapter, 'chapter_title': ch['title'], 'case_title': ch['case'],
            'focus': ch['focus'], 'question': ch['question'], 'events': events, 'preparation': preparations,
            'statement': ' '.join(statements), 'business': '、'.join(e['business'] for e in events),
            'entity': events[0]['entity'], 'entity_name': events[0]['entity_name'],
            'amount_yuan_or_count': events[0]['amount_yuan_or_count'], 'event_id': events[0]['event_id'],
            'parameters': events[0]['parameters'],
            'basis': '参考分录依据本组业务资料、各业务核算规则及个人城市期初账簿生成；前置交易已在资料中单独列示。'}
    return seed, base, case, refs, before


def assignment_view(a):
    return {'id': a.id, 'class_id': a.class_id, 'chapter': a.chapter, 'title': a.title,
            'instruction': a.instruction, 'scenario': a.scenario, 'created_at': a.created_at}


def ensure_class_city(session, cls, student):
    link = session.scalar(select(ClassCity).where(ClassCity.class_id == cls.id, ClassCity.student_id == student.id))
    if link:
        return session.get(Simulation, link.simulation_id)
    old = list(session.scalars(select(StudentWork.simulation_id).join(TeachingAssignment).where(
        TeachingAssignment.class_id == cls.id, StudentWork.student_id == student.id).distinct()))
    if len(old) > 1:
        raise HTTPException(409, '该旧班级仍有多账套历史，请先备份并清理后重新建班；不能自动合并已记账数据')
    if old:
        sim = session.get(Simulation, old[0])
    else:
        seed = int.from_bytes(hashlib.sha256(f'{cls.id}:{student.id}'.encode()).digest()[:4], 'big')
        city = new_city(cls.profile_id, seed)
        sim = Simulation(id=str(uuid.uuid4()), owner_user_id=student.id,
                         name=f'{cls.name[:25]} · {student.display_name[:16]} · {student.id}',
                         seed=seed, month=0, version=0, state={}, running=False, interval=8, pause_at_year=True)
        session.add(sim); session.flush()
        persist(session, sim, city, (0, 0, 0)); remember_snapshot(session, sim, city.report())
    session.add(ClassCity(class_id=cls.id, student_id=student.id, simulation_id=sim.id)); session.flush()
    return sim


def pending_works(session, sid):
    return list(session.scalars(select(StudentWork).where(StudentWork.simulation_id == sid,
        StudentWork.confirmed_at.is_(None)).order_by(StudentWork.created_at, StudentWork.id)))


def initialize_class_cities(db):
    """Backfill memberships without historic task cities; never merge posted ledgers."""
    with db.transaction(write=True) as session:
        for cls, student in session.execute(select(TeachingClass, User).join(
            ClassMember, ClassMember.class_id == TeachingClass.id).join(User, User.id == ClassMember.user_id)):
            if session.scalar(select(ClassCity.id).where(ClassCity.class_id==cls.id, ClassCity.student_id==student.id)):
                continue
            old = list(session.scalars(select(StudentWork.simulation_id).join(TeachingAssignment).where(
                TeachingAssignment.class_id==cls.id, StudentWork.student_id==student.id).distinct()))
            if len(old) <= 1:
                ensure_class_city(session, cls, student)


def apply_preparations(city, case):
    if not case.get('preparation_posted'):
        for event in case.get('preparation_events', []):
            execute_event(city, event)


def add_work(session, assignment, student, cls):
    sim = ensure_class_city(session, cls, student)
    if sim.running:
        raise HTTPException(409, '请先暂停班级城市自动运行，再发布任务')
    city = restore(session, sim)
    pending = pending_works(session, sim.id)
    for earlier in pending:
        apply_preparations(city, earlier.case_data)
        for event in earlier.case_data['events']:
            execute_event(city, event)
    work_id = str(uuid.uuid4())
    seed, prepared, case, reference, before = prepare_case(assignment, student, work_id, city)
    if not pending:
        counts = (len(city.events), len(city.journals), len(city.year_reports))
        persist(session, sim, prepared, counts); remember_snapshot(session, sim, before)
        case['preparation_posted'] = True
    case['statement'] = '本班每名学生共用一套城市，请按任务发布顺序确认入账。' + case['statement']
    work = StudentWork(id=work_id, assignment_id=assignment.id, student_id=student.id,
                       simulation_id=sim.id, case_data=case, reference_entries=reference,
                       rubric=assignment.rubric, before_report=before, status='assigned')
    session.add(work); session.flush()
    return work


def publish(session, body, user):
    cls = load_class(session, body.class_id, user.id)
    if body.profile_id != cls.profile_id:
        raise HTTPException(422, '本班账套方案已固定，请使用班级创建时的方案，不能随任务切换')
    specs = body.events if isinstance(body, AssignmentGroupCreate) else [body]
    events = [canonical_event(s) for s in specs]
    scenario = {'events': events, 'variation': body.amount_variation_percent, 'profile_id': body.profile_id}
    fingerprint = digest({'class_id': body.class_id, 'chapter': body.chapter, 'title': body.title,
                          'instruction': body.instruction, 'scenario': scenario})
    aid = str(uuid.uuid5(uuid.NAMESPACE_URL, f'caifa-publish/{user.id}/{body.request_id}')) if body.request_id else str(uuid.uuid4())
    existing = session.get(TeachingAssignment, aid)
    if not existing and session.scalar(select(TeachingAudit.id).where(
        TeachingAudit.action=='publish_assignment', TeachingAudit.target_id==aid).limit(1)):
        raise HTTPException(409, '该发布请求对应任务已删除，请刷新后重新发布')
    if existing:
        if existing.scenario.get('fingerprint') != fingerprint:
            raise HTTPException(409, '同一发布请求编号已用于不同任务，请重新发布')
        count = session.scalar(select(func.count()).select_from(StudentWork).where(StudentWork.assignment_id == aid))
        return {'id': aid, 'class_id': cls.id, 'chapter': existing.chapter, 'student_count': count,
                'event_count': len(events), 'title': existing.title, 'duplicate': True}
    members = session.scalars(select(User).join(ClassMember, ClassMember.user_id == User.id).where(
        ClassMember.class_id == cls.id, User.role == 'student', User.active.is_(True)).order_by(User.id)).all()
    if not members:
        raise HTTPException(422, '请先为当前班级添加学生')
    scenario['fingerprint'] = fingerprint
    assignment = TeachingAssignment(id=aid, class_id=cls.id, teacher_id=user.id, chapter=body.chapter,
                                    title=body.title, instruction=body.instruction, scenario=scenario,
                                    rubric={'weights': WEIGHTS, 'extra_line_penalty': 5})
    session.add(assignment); session.flush()
    for student in members:
        try:
            add_work(session, assignment, student, cls)
        except (ValueError, AssertionError) as exc:
            raise HTTPException(422, f'发布未完成，已回滚整组任务：{exc}。请调整业务金额、顺序或适用主体。') from exc
    audit(session, user, 'publish_assignment', aid, {'class_id': cls.id, 'students': len(members), 'events': len(events)})
    return {'id': aid, 'class_id': cls.id, 'chapter': body.chapter, 'student_count': len(members),
            'event_count': len(events), 'title': body.title, 'duplicate': False}


@router.get('/catalog')
def catalog(user=Depends(current_user)):
    return {'chapters': CHAPTERS, 'business_types': CATALOG, 'entities': NAMES,
            'class_templates': [{'size': n, 'name': f'{n}人实训班'} for n in (20, 30, 40, 50, 60)],
            'exercise_templates': EXERCISE_TEMPLATES,
            'profiles': [{'id': 'textbook', 'name': '彩珐市教材基准'},
                         {'id': 'jingzhou2025', 'name': '荆州公开数据参考（1∶100）'}],
            'assessment': {'kind': '可复核的规则初评', 'weights': WEIGHTS}}


@router.post('/classes', status_code=201)
def create_class(body: ClassCreate, request: Request, user=Depends(current_user)):
    role(user, 'teacher')
    row = TeachingClass(id=str(uuid.uuid4()), teacher_id=user.id, name=body.name, term=body.term, profile_id=body.profile_id)
    with request.app.state.db.transaction(write=True) as session:
        session.add(row); audit(session, user, 'create_class', row.id)
    return {'id': row.id, 'name': row.name, 'term': row.term}


@router.post('/classes/from-template', status_code=201)
def template_class(body: TemplateClassCreate, request: Request, user=Depends(current_user)):
    role(user, 'teacher')
    cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f'caifa-template/{user.id}/{body.request_id}'))
    fingerprint = digest(body.model_dump(mode='json', exclude={'request_id'}))
    with request.app.state.db.transaction() as session:
        existing = session.get(TeachingClass, cid)
        if existing:
            record = session.scalar(select(TeachingAudit).where(TeachingAudit.target_id == cid,
                                     TeachingAudit.action == 'template_class').order_by(TeachingAudit.id.desc()))
            if not record or record.detail.get('fingerprint') != fingerprint:
                raise HTTPException(409, '同一模板请求编号已用于不同配置')
            return {'id': cid, 'name': existing.name, 'size': body.size, 'duplicate': True,
                    'credentials': [], 'message': '班级已生成，未重复创建；请在班级管理中查询学生账号与密码。'}
    credentials = []
    users = []
    for n in range(1, body.size+1):
        username = f'{body.username_prefix}_{cid[:8]}_{n:03d}'
        password = 'C!' + secrets.token_urlsafe(9)
        name = f'学生{n:03d}'
        credentials.append({'username': username, 'display_name': name, 'password': password})
        users.append(User(username=username, password_hash=password_digest(password), display_name=name, role='student'))
    try:
        with request.app.state.db.transaction(write=True) as session:
            # Check again after password preparation to prevent concurrent duplicate generation.
            if session.get(TeachingClass, cid):
                raise HTTPException(409, '该模板请求正在或已经完成，请刷新班级列表')
            cls = TeachingClass(id=cid, teacher_id=user.id, name=body.name, term=body.term, profile_id=body.profile_id)
            session.add(cls); session.add_all(users); session.flush()
            from .credential_vault import save_password
            for student, credential in zip(users, credentials):
                save_password(request.app.state.db, session, student, credential['password'])
            for student in users:
                session.add(ClassMember(class_id=cid, user_id=student.id))
            session.flush()
            for student in users:
                ensure_class_city(session, cls, student)
            assigned = None
            if body.exercise_template_id != 'none':
                tpl = next(t for t in EXERCISE_TEMPLATES if t['id'] == body.exercise_template_id)
                assigned = publish(session, AssignmentGroupCreate(
                    class_id=cid, chapter=body.chapter, title=f"第{body.chapter}章 · {tpl['name']}",
                    events=[BusinessSpec.model_validate(e) for e in tpl['events']],
                    amount_variation_percent=body.amount_variation_percent, profile_id=body.profile_id,
                    request_id=f'template-{cid}'), user)
            audit(session, user, 'template_class', cid, {'fingerprint': fingerprint, 'size': body.size})
    except IntegrityError as exc:
        raise HTTPException(409, '账号名称发生冲突，班级生成已回滚，请更换账号前缀') from exc
    return {'id': cid, 'name': body.name, 'size': body.size, 'credentials': credentials,
            'assignment': assigned, 'duplicate': False,
            'message': '班级和账号已生成，可在班级管理中查询账号与密码，再到任务分配中布置练习。'}


@router.post('/classes/{class_id}/students', status_code=201)
def create_student(class_id: str, body: StudentCreate, request: Request, user=Depends(current_user)):
    role(user, 'teacher')
    try:
        with request.app.state.db.transaction(write=True) as session:
            cls = load_class(session, class_id, user.id)
            student = User(username=body.username, password_hash=password_digest(body.password),
                           display_name=body.display_name, role='student')
            session.add(student); session.flush()
            from .credential_vault import save_password
            save_password(request.app.state.db, session, student, body.password)
            session.add(ClassMember(class_id=cls.id, user_id=student.id))
            session.flush()
            ensure_class_city(session, cls, student)
            # New members also receive all already-published class tasks.
            assignments = session.scalars(select(TeachingAssignment).where(TeachingAssignment.class_id == cls.id).order_by(TeachingAssignment.created_at, TeachingAssignment.id)).all()
            for assignment in assignments:
                add_work(session, assignment, student, cls)
            audit(session, user, 'add_student', student.id, {'class_id': cls.id, 'assigned_tasks': len(assignments)})
            result = {'student': user_view(student), 'class_id': cls.id, 'assigned_tasks': len(assignments)}
    except IntegrityError as exc:
        raise HTTPException(409, '该登录名已存在，请使用其他登录名') from exc
    except (ValueError, AssertionError) as exc:
        raise HTTPException(422, f'该学生的历史任务生成失败，操作已回滚：{exc}') from exc
    return result


@router.post('/assignments', status_code=201)
def create_assignment(body: AssignmentGroupCreate | AssignmentCreate, request: Request, user=Depends(current_user)):
    role(user, 'teacher')
    with request.app.state.db.transaction(write=True) as session:
        return publish(session, body, user)


@router.post('/classes/{class_id}/credentials')
def class_credentials(class_id: str, request: Request, user=Depends(current_user)):
    from .credential_vault import reveal_password
    role(user, 'teacher')
    with request.app.state.db.transaction(write=True) as session:
        cls = load_class(session, class_id, user.id)
        students = session.scalars(select(User).join(ClassMember, ClassMember.user_id==User.id).where(
            ClassMember.class_id==cls.id, User.role=='student').order_by(User.id)).all()
        rows = []
        for student in students:
            password = reveal_password(request.app.state.db, session, student)
            if password and not check_password(password, student.password_hash):
                password = None
            rows.append({**user_view(student), 'password':password,
                         'password_status':'可查询' if password else '旧密码未保存或密钥不可用，可重置'})
        audit(session, user, 'view_student_credentials', class_id, {'count':len(rows)})
        return {'class_id':class_id,'class_name':cls.name,'credentials':rows}


@router.post('/classes/{class_id}/students/{student_id}/reset-password')
def reset_student_password(class_id: str, student_id: int, request: Request, user=Depends(current_user)):
    from .credential_vault import save_password
    role(user, 'teacher')
    with request.app.state.db.transaction(write=True) as session:
        load_class(session, class_id, user.id)
        student = session.scalar(select(User).join(ClassMember, ClassMember.user_id==User.id).where(
            ClassMember.class_id==class_id, User.id==student_id, User.role=='student'))
        if not student:
            raise HTTPException(404, '未找到本班学生')
        password='C!'+secrets.token_urlsafe(12)
        student.password_hash=password_digest(password)
        save_password(request.app.state.db, session, student, password)
        session.execute(delete(LoginSession).where(LoginSession.user_id==student.id))
        audit(session, user, 'reset_student_password', student.id, {'class_id':class_id})
        return {'student':user_view(student), 'password':password, 'message':'密码已重置，旧登录会话已失效。'}


def assignment_delete_scope(session, assignment_id, user):
    assignment=session.get(TeachingAssignment, assignment_id)
    if not assignment or assignment.teacher_id!=user.id:
        raise HTTPException(404, '未找到本班任务')
    assignments=list(session.scalars(select(TeachingAssignment).where(TeachingAssignment.class_id==assignment.class_id)
        .order_by(TeachingAssignment.created_at, TeachingAssignment.id)))
    selected=assignments[assignments.index(assignment):]
    aids=[a.id for a in selected]
    works=list(session.scalars(select(StudentWork).where(StudentWork.assignment_id.in_(aids))))
    return assignment, selected, works


def assignment_scope_token(selected, works):
    return digest({'tasks':[a.id for a in selected],
        'works':sorted((w.id,w.updated_at,w.confirmed_at) for w in works)})


@router.get('/assignments/{assignment_id}/delete-preview')
def assignment_delete_preview(assignment_id: str, request: Request, user=Depends(current_user)):
    role(user, 'teacher')
    with request.app.state.db.transaction() as session:
        a, selected, works=assignment_delete_scope(session, assignment_id, user)
        return {'title':a.title, 'tasks':[{'id':x.id,'title':x.title} for x in selected],
                'scope_token':assignment_scope_token(selected,works),
                'works':len(works), 'can_delete':not any(w.confirmed_at for w in works),
                'note':'删除本项及之后的未入账任务（后续答案依赖前序余额）。保留学生账号、共用账套与已记账的仿真准备。已入账任务不能直接删除。'}


class AssignmentDelete(Input):
    confirm_title: str
    scope_token: str


@router.delete('/assignments/{assignment_id}')
def delete_assignment(assignment_id: str, body: AssignmentDelete, request: Request, user=Depends(current_user)):
    from .class_cleanup import backup_database
    role(user, 'teacher')
    with request.app.state.db.transaction(write=True) as session:
        a, selected, works=assignment_delete_scope(session, assignment_id, user)
        if body.confirm_title!=a.title:
            raise HTTPException(422, '请输入完整任务标题确认删除')
        if body.scope_token!=assignment_scope_token(selected,works):
            raise HTTPException(409, '任务或学生作答已变化，请重新查看删除范围并确认')
        if any(w.confirmed_at for w in works):
            raise HTTPException(409, '本任务或后续任务已入账，不允许删除历史凭证；如需清空整个班级，请使用班级删除并保留备份')
        try:
            backup=backup_database(request.app.state.db)
        except (OSError, RuntimeError) as exc:
            raise HTTPException(503, '备份失败，未删除任务') from exc
        aids=[x.id for x in selected]
        session.execute(delete(StudentWork).where(StudentWork.assignment_id.in_(aids)))
        session.execute(delete(TeachingAssignment).where(TeachingAssignment.id.in_(aids)))
        audit(session,user,'delete_assignments',assignment_id,{'assignments':aids,'backup':backup})
        return {'assignments':len(aids),'works':len(works),'backup':backup,
                'message':'任务已删除，学生账号、共用账套及已记账仿真准备保留。'}


@router.post('/assignment-batches', status_code=201)
def create_assignment_batch(body: AssignmentBatch, request: Request, user=Depends(current_user)):
    role(user, 'teacher')
    if any(t.class_id != body.class_id for t in body.tasks):
        raise HTTPException(422, '所有章节任务必须属于当前班级')
    if len({t.chapter for t in body.tasks}) != len(body.tasks):
        raise HTTPException(422, '每章配置一组业务，可在组内选择多项任务或任务包')
    batch_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'caifa-batch/{user.id}/{body.request_id}'))
    fingerprint = digest(body.model_dump(mode='json'))
    with request.app.state.db.transaction(write=True) as session:
        load_class(session, body.class_id, user.id)
        record = session.scalar(select(TeachingAudit).where(TeachingAudit.action == 'publish_batch', TeachingAudit.target_id == batch_id))
        if record:
            if record.detail['fingerprint'] != fingerprint:
                raise HTTPException(409, '该请求编号已用于不同发布内容')
            if any(session.get(TeachingAssignment, a['id']) is None for a in record.detail['result']['assignments']):
                raise HTTPException(409, '该批任务已有删除，请刷新后重新发布，不能重放旧请求')
            return {**record.detail['result'], 'duplicate': True}
        results = []
        for task in sorted(body.tasks, key=lambda t: t.chapter):
            results.append(publish(session, task.model_copy(update={'request_id':f'{batch_id}-{task.chapter}'}), user))
        result = {'class_id':body.class_id, 'assignments':results, 'duplicate':False}
        audit(session, user, 'publish_batch', batch_id, {'fingerprint':fingerprint, 'result':result})
        return result


@router.get('/classes/{class_id}/delete-preview')
def delete_preview(class_id: str, request: Request, user=Depends(current_user)):
    from .class_cleanup import class_scope
    role(user, 'teacher')
    with request.app.state.db.transaction() as session:
        cls = load_class(session, class_id, user.id)
        aids, works, sids = class_scope(session, class_id)
        return {'name':cls.name, 'assignments':len(aids), 'works':len(works), 'cities':len(sids),
                'note':'删除班级、任务、作答、账套及账簿；保留登录账号和历史审计。自动备份失败则不删除。'}


class ClassEdit(Input):
    name: str = Field(min_length=1, max_length=100)
    term: str = Field(default='', max_length=80)


@router.patch('/classes/{class_id}')
def edit_class(class_id: str, body: ClassEdit, request: Request, user=Depends(current_user)):
    role(user, 'teacher')
    with request.app.state.db.transaction(write=True) as session:
        cls=load_class(session,class_id,user.id)
        cls.name=body.name;cls.term=body.term
        for link in session.scalars(select(ClassCity).where(ClassCity.class_id==class_id)):
            student=session.get(User,link.student_id)
            session.get(Simulation,link.simulation_id).name=f'{cls.name[:25]} · {student.display_name[:16]} · {student.id}'
        audit(session,user,'edit_class',class_id,{'name':cls.name,'term':cls.term})
        return {'id':class_id,'name':cls.name,'term':cls.term}


@router.delete('/classes/{class_id}')
def delete_class(class_id: str, body: ClassDelete, request: Request, user=Depends(current_user)):
    from .class_cleanup import backup_database, erase_class
    role(user, 'teacher')
    with request.app.state.db.transaction(write=True) as session:
        cls = load_class(session, class_id, user.id)
        if body.confirm_name != cls.name:
            raise HTTPException(422, '请输入完整班级名称确认删除')
        try:
            backup = backup_database(request.app.state.db)
        except (OSError, RuntimeError) as exc:
            raise HTTPException(503, '备份未完成，未删除任何数据。请检查磁盘空间和备份目录权限。') from exc
        try:
            result = erase_class(session, class_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        audit(session, user, 'delete_class', class_id, {**result, 'backup':backup, 'name':body.confirm_name})
        return {**result, 'backup':backup, 'message':'班级及关联账套已删除，登录账号保留；管理员可从本地备份恢复。'}


def actual_line(row):
    if not isinstance(row, dict):
        raise HTTPException(422, '每条分录须为对象')
    entity, book, side, account = (row.get(k) for k in ('entity', 'book', 'side', 'account'))
    if entity not in NAMES or book not in {'financial', 'budget'} or side not in {'debit', 'credit'}:
        raise HTTPException(422, '请检查主体、账套和借贷方向')
    if book == 'budget' and entity == 'soe':
        raise HTTPException(422, '国有企业不设置行政事业单位预算会计账')
    if not isinstance(account, str) or not account.strip() or len(account) > 160:
        raise HTTPException(422, '请输入有效会计科目')
    try:
        amount = Decimal(str(row.get('amount_yuan')))
        if not amount.is_finite() or amount <= 0 or amount.quantize(Decimal('.01')) != amount or amount > 10**9:
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(422, '金额须为大于零、最多两位小数的数值')
    return {'event_id': row.get('event_id'), 'entity': entity, 'book': book, 'side': side,
            'account': account.strip(), 'amount_fen': int(amount*100)}


def grade(entries, expected, rubric):
    candidates = [actual_line(row) for row in entries]
    weights = rubric['weights']
    fields = {'主体': 'entity', '账套': 'book', '科目': 'account', '方向': 'side', '金额': 'amount_fen'}
    event_ids = {r.get('event_id') for r in expected if r.get('event_id')}
    for row in candidates:
        if len(event_ids) > 1 and row['event_id'] not in event_ids:
            raise HTTPException(422, '请为每条分录指定所属业务')
        if len(event_ids) == 1 and not row['event_id']:
            row['event_id'] = next(iter(event_ids))
    edges = []
    for i, actual in enumerate(candidates):
        for j, reference in enumerate(expected):
            if reference.get('event_id') and actual.get('event_id') != reference['event_id']:
                continue
            matches = {key: actual[field] == reference[field] for key, field in fields.items()}
            score = sum(weights[key] for key, yes in matches.items() if yes)
            # Exact pairs are assigned first, so partial rows cannot steal a later exact answer.
            edges.append((-score, tuple(str(actual.get(k, '')) for k in fields.values()),
                          tuple(str(reference.get(k, '')) for k in fields.values()), i, j, matches))
    used_actual, used_reference, pairs = set(), set(), {}
    for neg_score, _, _, i, j, matches in sorted(edges, key=lambda x: x[:5]):
        if i not in used_actual and j not in used_reference:
            used_actual.add(i); used_reference.add(j); pairs[i] = (j, -neg_score, matches)
    detail, total, exact = [], 0, 0
    for i, actual in enumerate(candidates):
        if i in pairs:
            j, score, matches = pairs[i]
            reference = expected[j]; total += score; exact += score == 100
            feedback = [{'item': key, 'correct': yes, 'expected':
                         (str(Decimal(reference[fields[key]])/100)+'元' if key == '金额' else reference[fields[key]])}
                        for key, yes in matches.items()]
        else:
            score, feedback = 0, [{'item': '多余分录', 'correct': False, 'expected': '本题无对应分录'}]
        detail.append({'submitted': actual, 'score': score,
                       'result': '完全匹配' if score == 100 else '请核对差异', 'fields': feedback})
    extras = max(0, len(candidates)-len(expected))
    score = max(0, min(100, round((total-extras*rubric.get('extra_line_penalty', 5))/max(1, len(expected)))))
    if not expected:
        score = 100 if not candidates else 0
    reference_rows = [{**r, 'amount_yuan': str(Decimal(r['amount_fen'])/100)} for r in expected]
    return {'score': score, 'provisional': True, 'weights': weights, 'matched_lines': exact,
            'expected_line_count': len(expected), 'submitted_line_count': len(candidates),
            'line_feedback': detail, 'entries': entries, 'reference_entries': reference_rows,
            'missing_reference_lines': [reference_rows[j] for j in range(len(expected)) if j not in used_reference],
            'excess_line_count': extras, 'no_financial_entry': not expected,
            'method': '先按所属业务配对，完整匹配优先，再按主体、账套、科目、方向与金额逐项计分。',
            'basis': '依据本题业务资料、已披露的期初准备和仿真规则参考分录。实物变动业务无会计分录时，空分录为正确处理；分析内容由教师复核。'}


def owned_work(session, work_id, user):
    w = session.get(StudentWork, work_id)
    if not w:
        raise HTTPException(404, '未找到该练习')
    if user.role == 'student' and w.student_id == user.id:
        return w
    assignment = session.get(TeachingAssignment, w.assignment_id)
    if user.role == 'teacher' and assignment.teacher_id == user.id:
        return w
    raise HTTPException(404, '未找到该练习')


@router.post('/works/{work_id}/submit')
def submit(work_id: str, body: Submission, request: Request, user=Depends(current_user)):
    role(user, 'student')
    with request.app.state.db.transaction(write=True) as session:
        w = owned_work(session, work_id, user)
        if w.confirmed_at and w.status != 'needs_revision':
            raise HTTPException(409, '已确认的练习请先由教师退回修改')
        attempt = grade(body.entries, w.reference_entries, w.rubric)
        attempt.update(student_note=body.student_note, analysis=body.analysis, submitted_at=time.time(),
                       attempt_no=(w.latest_attempt or {}).get('attempt_no', 0)+1)
        w.latest_attempt = attempt; w.teacher_review = None; w.status = 'submitted'; w.updated_at = time.time()
        audit(session, user, 'submit_work', work_id, attempt)
        return {'assessment': attempt, 'status': w.status, 'student_action_required': True}


@router.post('/works/{work_id}/check')
def check_work(work_id: str, body: StudentCheck, request: Request, user=Depends(current_user)):
    role(user, 'student')
    with request.app.state.db.transaction(write=True) as session:
        w = owned_work(session, work_id, user)
        if not w.latest_attempt:
            raise HTTPException(409, '请先提交作答并查看初评')
        check = {'action': body.action, 'note': body.note, 'checked_at': time.time()}
        w.latest_attempt = {**w.latest_attempt, 'student_check': check}
        if body.action == 'dispute':
            if not body.note:
                raise HTTPException(422, '请填写异议理由，方便教师复核')
            w.status = 'student_disputed'; w.updated_at = time.time()
            audit(session, user, 'dispute_assessment', work_id, check)
            return {'status': w.status, 'message': '异议已保存，教师可查看理由。'}
        sim = session.get(Simulation, w.simulation_id)
        if w.confirmed_at:
            audit(session, user, 'confirm_again', work_id, check)
            return {'status': w.status, 'simulation': metadata(sim), 'duplicate': True}
        if sim.running:
            raise HTTPException(409, '个人城市正在自动运行，请先暂停，再确认入账')
        waiting = pending_works(session, sim.id)
        if waiting and waiting[0].id != w.id:
            earlier = session.get(TeachingAssignment, waiting[0].assignment_id)
            raise HTTPException(409, f'请先完成前序任务：{earlier.title}。同一班级共用一个学生账套，须按发布顺序入账')
        city = restore(session, sim)
        counts = (len(city.events), len(city.journals), len(city.year_reports))
        case = w.case_data
        assignment = session.get(TeachingAssignment, w.assignment_id)
        events = case.get('events') or [{'kind': assignment.scenario['kind'], 'entity': assignment.scenario['entity'],
                    'amount_yuan_or_count': case['amount_yuan_or_count'], 'parameters': assignment.scenario['parameters'],
                    'event_id': case['event_id']}]
        try:
            apply_preparations(city, case)
            before = city.report()
            reference_start = len(city.journals)
            for event in events:
                execute_event(city, event)
            if expected_entries(city, reference_start) != w.reference_entries:
                raise HTTPException(409, '账套余额与本题参考依据不一致，未入账；请教师核查，不会强行使用旧参考答案')
            city.check()
            persist(session, sim, city, counts); remember_snapshot(session, sim, city.report())
        except (ValueError, AssertionError) as exc:
            raise HTTPException(422, f'整组业务未入账，所有改动已回滚：{exc}') from exc
        w.status = 'confirmed'; w.confirmed_at = time.time(); w.updated_at = time.time()
        w.before_report = before
        audit(session, user, 'confirm_and_post', work_id, {**check, 'events': len(events)})
        return {'status': w.status, 'simulation': metadata(sim), 'duplicate': False,
                'message': '整组业务已一次性计入个人城市账套，可比较前后报表。'}


def work_view(w, assignment=None, student=None):
    result = {'id': w.id, 'student_id': w.student_id, 'status': w.status, 'case': w.case_data,
              'attempt': w.latest_attempt, 'assessment': w.latest_attempt, 'confirmed': bool(w.confirmed_at),
              'teacher_review': w.teacher_review, 'updated_at': w.updated_at, 'before_report': w.before_report}
    if assignment:
        result.update(assignment_id=assignment.id, chapter=assignment.chapter, title=assignment.title,
                      instruction=assignment.instruction, score=(w.latest_attempt or {}).get('score'))
    if student:
        result['student'] = user_view(student)
    return result


@router.get('/dashboard')
def dashboard(request: Request, user=Depends(current_user)):
    with request.app.state.db.transaction() as session:
        if user.role == 'teacher':
            classes = session.scalars(select(TeachingClass).where(TeachingClass.teacher_id == user.id).order_by(
                TeachingClass.created_at.desc(), TeachingClass.id)).all()
            result = []
            for cls in classes:
                students = session.scalars(select(User).join(ClassMember, ClassMember.user_id == User.id).where(
                    ClassMember.class_id == cls.id).order_by(User.id)).all()
                assignments = session.scalars(select(TeachingAssignment).where(
                    TeachingAssignment.class_id == cls.id).order_by(TeachingAssignment.created_at.desc())).all()
                summaries = []
                for assignment in assignments:
                    works = session.scalars(select(StudentWork).where(StudentWork.assignment_id == assignment.id)).all()
                    submitted = [w for w in works if w.latest_attempt]
                    summaries.append({'id': assignment.id, 'chapter': assignment.chapter, 'title': assignment.title,
                        'count': len(works), 'submitted': len(submitted), 'confirmed': sum(bool(w.confirmed_at) for w in works),
                        'reviewed': sum(w.teacher_review is not None for w in works),
                        'event_count': len(assignment.scenario.get('events', [1])),
                        'mean_score': round(sum(w.latest_attempt['score'] for w in submitted)/max(1, len(submitted)), 1)})
                result.append({'id': cls.id, 'name': cls.name, 'term': cls.term, 'profile_id':cls.profile_id,
                               'students': [user_view(s) for s in students], 'assignments': summaries})
            return {'role': 'teacher', 'classes': result}
        role(user, 'student')
        rows = session.scalars(select(StudentWork).where(StudentWork.student_id == user.id).order_by(
            StudentWork.created_at, StudentWork.id)).all()
        items = []
        for w in rows:
            assignment = session.get(TeachingAssignment, w.assignment_id)
            sim = session.get(Simulation, w.simulation_id)
            item = work_view(w, assignment)
            waiting = pending_works(session, sim.id)
            item['can_confirm'] = not waiting or waiting[0].id == w.id
            item['class_name'] = session.get(TeachingClass, assignment.class_id).name
            c = load_city(sim.state, [], [], [])
            item['after_report'] = c.report()
            item['simulation'] = {'simulation': metadata(sim), 'population': c.population,
                'event_count': session.scalar(select(func.count()).select_from(BusinessEvent).where(BusinessEvent.simulation_id == sim.id)),
                'voucher_count': session.scalar(select(func.count()).select_from(Voucher).where(Voucher.simulation_id == sim.id))}
            items.append(item)
        return {'role': 'student', 'works': items}


@router.get('/assignments/{assignment_id}/works')
def assignment_works(assignment_id: str, request: Request, user=Depends(current_user)):
    role(user, 'teacher')
    with request.app.state.db.transaction() as session:
        a = session.get(TeachingAssignment, assignment_id)
        if not a or a.teacher_id != user.id:
            raise HTTPException(404, '未找到该任务')
        works = session.scalars(select(StudentWork).where(StudentWork.assignment_id == a.id).order_by(StudentWork.student_id)).all()
        return {'assignment': assignment_view(a),
                'works': [work_view(w, a, session.get(User, w.student_id)) for w in works]}


@router.get('/works/{work_id}/history')
def work_history(work_id: str, request: Request, user=Depends(current_user)):
    with request.app.state.db.transaction() as session:
        owned_work(session, work_id, user)
        records = session.scalars(select(TeachingAudit).where(TeachingAudit.target_id == work_id).order_by(TeachingAudit.id)).all()
        return {'items': [{'action': r.action, 'detail': r.detail, 'created_at': r.created_at} for r in records]}


@router.post('/works/{work_id}/teacher-review')
def review_work(work_id: str, body: TeacherReview, request: Request, user=Depends(current_user)):
    role(user, 'teacher')
    with request.app.state.db.transaction(write=True) as session:
        w = owned_work(session, work_id, user)
        if not w.latest_attempt:
            raise HTTPException(409, '学生尚未提交作答，暂不能复核评分')
        review = {'score': body.score, 'decision': body.decision, 'rationale': body.rationale,
                  'reviewer': user.display_name, 'reviewed_at': time.time()}
        w.teacher_review = review; w.status = 'teacher_approved' if body.decision == 'confirmed' else 'needs_revision'
        w.updated_at = time.time(); audit(session, user, 'teacher_review', work_id, review)
        return {'status': w.status, 'review': review}


@router.get('/overview')
def combined_overview(request: Request, user=Depends(current_user)):
    teaching = dashboard(request, user)
    with request.app.state.db.transaction() as session:
        sims = session.scalars(visible_simulations(user).order_by(Simulation.created_at.desc())).all()
        ids = [s.id for s in sims]
        def counts(model):
            return dict(session.execute(select(model.simulation_id, func.count()).where(
                model.simulation_id.in_(ids)).group_by(model.simulation_id)).all()) if ids else {}
        ec, vc = counts(BusinessEvent), counts(Voucher)
        cities = [{'simulation': metadata(s), 'population': sum(s.state['population'].values()),
                   'entities': len(s.state['ledger']), 'event_count': ec.get(s.id, 0), 'voucher_count': vc.get(s.id, 0),
                   'closing_cash_yuan': s.state['ledger']['fiscal'].get('国库存款', 0)/100,
                   'profile_id': s.state.get('profile_id', 'textbook')} for s in sims]
    assignments = sum(len(c['assignments']) for c in teaching['classes']) if user.role == 'teacher' else len(teaching['works'])
    students = sum(len(c['students']) for c in teaching['classes']) if user.role == 'teacher' else 1
    return {'role': user.role, 'user': user_view(user), 'city_simulations': cities, 'teaching': teaching,
            'summary': {'city_accounts': len(cities), 'student_or_assigned_count': students,
                        'teaching_assignments': assignments, 'total_city_events': sum(ec.values()),
                        'total_vouchers': sum(vc.values())}}
