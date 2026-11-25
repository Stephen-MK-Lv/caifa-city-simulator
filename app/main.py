import asyncio
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.exc import OperationalError
from .database import Database, Simulation
from sqlalchemy import select
from .service import SimulationService, NotFound, Conflict, RuleError
from .schemas import CreateSimulation, Advance, EventInput, RunControl
from .catalog import PUBLIC_CATALOG, POLICY_NOTES
from .textbook import ACTORS
from .teaching import (auth_router, router as teaching_router, current_user,
                       visible_simulations, initialize_class_cities,
                       initialize_deployment_teacher)
from .service import metadata

ROOT=Path(__file__).resolve().parent.parent
STATIC=Path(__file__).resolve().parent/'static'


def create_app(db_path=None, scheduler=True):
    @asynccontextmanager
    async def lifespan(app):
        db=Database(db_path or os.environ.get('CAIFA_DB') or os.environ.get('MINGCHUAN_DB',str(ROOT/'data'/'mingchuan.sqlite3')))
        initialize_deployment_teacher(db)
        initialize_class_cities(db)
        service=SimulationService(db)
        app.state.db=db;app.state.service=service
        stop=asyncio.Event()

        async def run_clock():
            while not stop.is_set():
                try: await asyncio.to_thread(service.tick)
                except Exception: logging.exception('Scheduler cycle failed')
                try: await asyncio.wait_for(stop.wait(),timeout=1)
                except asyncio.TimeoutError: pass
        task=asyncio.create_task(run_clock()) if scheduler else None
        yield
        stop.set()
        if task: await task
        db.engine.dispose()

    app=FastAPI(title='彩珐市政府会计仿真',version='1.1.0',lifespan=lifespan,
                description='本地仿真版。金额请求以元输入，账簿与分录金额以整数分保存。')
    configured_hosts=os.environ.get('CAIFA_ALLOWED_HOSTS')
    if configured_hosts:
        allowed_hosts=[x.strip() for x in configured_hosts.split(',') if x.strip()]
    else:
        allowed_hosts=['127.0.0.1','localhost','[::1]','testserver']
        railway_domain=os.environ.get('RAILWAY_PUBLIC_DOMAIN')
        if railway_domain:
            allowed_hosts.append(railway_domain)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=allowed_hosts)

    @app.middleware('http')
    async def local_safety(request:Request,call_next):
        if (os.environ.get('CAIFA_AUTH_REQUIRED','0') == '1' or request.headers.get('authorization')) and request.url.path.startswith('/api/simulations'):
            try:
                identity=current_user(request,request.headers.get('authorization'))
            except Exception as exc:
                status=getattr(exc,'status_code',401)
                return JSONResponse({'detail':getattr(exc,'detail','请先登录仿真平台')},status)
            request.state.platform_user=identity
            parts=request.url.path.strip('/').split('/')
            if len(parts)>=3:
                with request.app.state.db.transaction() as session:
                    permitted=session.scalar(visible_simulations(identity).where(Simulation.id==parts[2]))
                    if not permitted:
                        return JSONResponse({'detail':'未找到可访问的城市账套'},404)
            if identity.role=='student':
                parts=request.url.path.strip('/').split('/')
                if request.url.path=='/api/simulations' and request.method=='GET':
                    pass
                elif request.url.path=='/api/simulations' and request.method=='POST':
                    return JSONResponse({'detail':'学生账套由班级管理生成'},403)
                elif len(parts)>=3:
                    with request.app.state.db.transaction() as session:
                        sim=session.get(Simulation,parts[2])
                        if not sim or sim.owner_user_id!=identity.id:
                            return JSONResponse({'detail':'无权访问其他用户的城市账套'},404)
        if request.method in {'POST','PUT','PATCH','DELETE'}:
            origin=request.headers.get('origin')
            if origin and (urlsplit(origin).netloc!=request.headers.get('host') or urlsplit(origin).scheme not in {'http','https'}):
                return JSONResponse({'detail':'拒绝跨来源修改请求'},403)
            if request.headers.get('sec-fetch-site')=='cross-site':
                return JSONResponse({'detail':'拒绝跨站修改请求'},403)
            try: content_length=int(request.headers.get('content-length','0') or 0)
            except ValueError: return JSONResponse({'detail':'无效的请求长度'},400)
            if content_length>(128000 if request.url.path.startswith('/api/teaching/') else 20000):
                return JSONResponse({'detail':'请求内容过大'},413)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(NotFound)
    async def missing(_,exc): return JSONResponse({'detail':str(exc)},404)
    @app.exception_handler(Conflict)
    async def conflict(_,exc): return JSONResponse({'detail':str(exc)},409)
    @app.exception_handler(RuleError)
    async def rule(_,exc): return JSONResponse({'detail':str(exc),'rolled_back':True},422)
    @app.exception_handler(OperationalError)
    async def busy(_,exc):
        logging.warning('Database operation failed: %s',exc)
        return JSONResponse({'detail':'数据库暂时不可用，请稍后重试。未提交的操作已回滚。'},503)

    @app.get('/api/health')
    def health(): return {'status':'ok','database':'sqlite','engine':'SQLAlchemy 2.0','release':'textbook-1125-4'}

    @app.get('/api/catalog')
    def catalog(): return {'events':PUBLIC_CATALOG,'entities':ACTORS,'notes':POLICY_NOTES}

    @app.get('/api/simulations')
    def simulations(request:Request):
        identity=getattr(request.state,'platform_user',None)
        if identity:
            with request.app.state.db.transaction() as session:
                return [metadata(s) for s in session.scalars(visible_simulations(identity).order_by(Simulation.created_at.desc())).all()]
        return request.app.state.service.list_simulations(owner_user_id=identity.id if identity and identity.role=='student' else None)

    @app.post('/api/simulations',status_code=201)
    def create(body:CreateSimulation,request:Request): return request.app.state.service.create(body)

    @app.get('/api/simulations/{sid}')
    def summary(sid:str,request:Request): return request.app.state.service.summary(sid)

    @app.post('/api/simulations/{sid}/advance')
    def advance(sid:str,body:Advance,request:Request): return request.app.state.service.execute(sid,'advance',body)

    @app.post('/api/simulations/{sid}/run')
    def run(sid:str,body:RunControl,request:Request): return request.app.state.service.execute(sid,'run',body)

    @app.post('/api/simulations/{sid}/events')
    def trigger(sid:str,body:EventInput,request:Request): return request.app.state.service.execute(sid,'event',body)

    @app.get('/api/simulations/{sid}/events')
    def events(sid:str,request:Request,entity:str|None=None,kind:str|None=None,
               month:int|None=Query(None,ge=0,le=120),search:str=Query('',max_length=80),
               offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100)):
        return request.app.state.service.events(sid,entity,kind,month,search,offset,limit)

    @app.get('/api/simulations/{sid}/events/{event_id}')
    def event_detail(sid:str,event_id:int,request:Request): return request.app.state.service.event_detail(sid,event_id)

    @app.get('/api/simulations/{sid}/vouchers')
    def vouchers(sid:str,request:Request,entity:str|None=None,book:str|None=None,
                 month:int|None=Query(None,ge=0,le=120),search:str=Query('',max_length=80),
                 offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100)):
        return request.app.state.service.vouchers(sid,entity,book,month,search,offset,limit)

    @app.get('/api/simulations/{sid}/reports')
    def reports(sid:str,request:Request,year:int|None=Query(None,ge=1,le=10)):
        return request.app.state.service.reports(sid,year)

    @app.get('/api/simulations/{sid}/monthly')
    def monthly(sid:str,request:Request):
        return request.app.state.service.monthly(sid)

    @app.get('/api/simulations/{sid}/export')
    def export(sid:str,request:Request):
        content=request.app.state.service.export_zip(sid)
        return Response(content,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="caifa-{sid[:8]}.zip"'})

    app.mount('/static',StaticFiles(directory=STATIC),name='static')

    app.include_router(auth_router)
    app.include_router(teaching_router)

    @app.get('/',include_in_schema=False)
    def home():return FileResponse(STATIC/'portal.html')
    @app.get('/city',include_in_schema=False)
    def city():return FileResponse(STATIC/'index.html')
    return app


app=create_app()
