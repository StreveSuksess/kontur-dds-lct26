import json
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from .config import Settings
from .db import Base, create_database
from .auth import router as auth_router, password_hash
from .schemas import STATUS_LABELS
from .seed import seed_database
from .admission import AdmissionMiddleware
from .routes import scenarios, sessions, admin, reference, ai, recommendations, intake112


def create_app(settings:Settings | None=None) -> FastAPI:
    settings=settings or Settings()
    engine,factory=create_database(settings.database_url)
    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        with factory() as db:seed_database(db,settings)
        yield
        engine.dispose()
    app=FastAPI(title='Контур ДДС — учебный API',version=settings.version,lifespan=lifespan)
    app.state.settings=settings;app.state.engine=engine;app.state.session_factory=factory
    app.state.mutation_lock=threading.RLock();app.state.login_attempts={};app.state.dummy_hash=password_hash('unusable-dummy-password')
    app.state.started_monotonic=time.monotonic()
    def read_data(name,default):
        path=settings.data_dir/name
        return json.loads(path.read_text()) if path.exists() else default
    app.state.classifier=read_data('classifier.json',{'version':'не загружен','items':[],'warnings':['Классификатор ещё не установлен']})
    app.state.knowledge=read_data('knowledge.json',[])

    @app.middleware('http')
    async def security_headers(request,call_next):
        if request.method not in {'GET','HEAD','OPTIONS'}:
            origin=request.headers.get('origin')
            own_origin=str(request.base_url).rstrip('/')
            allowed={v.strip() for v in settings.allowed_origins.split(',') if v.strip()}|{own_origin}
            if (origin and origin not in allowed) or request.headers.get('sec-fetch-site')=='cross-site':
                return JSONResponse({'detail':'Запрос с постороннего сайта запрещён'},403)
            length=request.headers.get('content-length')
            max_body = 10*1024*1024 if request.url.path.startswith('/api/sessions/') and request.url.path.endswith('/transcribe') else 262144
            if length and (not length.isdigit() or int(length)>max_body):
                return JSONResponse({'detail':'Запрос слишком большой'},413)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['X-Frame-Options']='DENY'
        if request.url.path.startswith('/api'):response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request,exc):
        errors=exc.errors()
        return JSONResponse({'detail':'Некорректные данные: '+str(errors[0].get('msg','проверьте поля'))},422)

    @app.exception_handler(IntegrityError)
    async def conflict(request,exc):
        return JSONResponse({'detail':'Конфликт данных. Обновите страницу и повторите действие'},409)

    app.include_router(auth_router,prefix='/api')
    for route in [scenarios.router,sessions.router,admin.router,reference.router,ai.router,recommendations.router,intake112.router]:app.include_router(route,prefix='/api')

    @app.get('/api/meta')
    def meta():
        services=sorted({i['primary_service'] for i in app.state.classifier.get('items',[]) if i.get('primary_service')}|{'Учебная ДДС','Мосводоканал','Мослифт','Гормост'})
        return {'name':'Контур ДДС','demo_mode':settings.demo_mode,'version':settings.version,'ai_mode':settings.ai_mode if settings.ai_endpoint else 'rules','status_labels':STATUS_LABELS,'services':services}

    @app.get('/api/health')
    def health():
        try:
            with engine.connect() as connection:connection.execute(text('SELECT 1'))
        except Exception:raise HTTPException(503,'База данных недоступна')
        return {'status':'ok','database':'ok','version':settings.version,'ai':{'configured':bool(settings.ai_endpoint and settings.ai_mode == 'local'),'mode':settings.ai_mode if settings.ai_endpoint else 'rules'},'uptime_seconds':round(time.monotonic()-app.state.started_monotonic,2)}

    @app.get('/{path:path}',include_in_schema=False)
    def frontend(path:str):
        if path=='api' or path.startswith('api/'):raise HTTPException(404,'API маршрут не найден')
        root=settings.static_dir.resolve()
        candidate=(root/path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():return FileResponse(candidate)
        if (root/'index.html').is_file():return FileResponse(root/'index.html')
        raise HTTPException(404,'Клиент ещё не собран. Запустите frontend или используйте /docs')
    app.add_middleware(AdmissionMiddleware, limit=24)
    return app


app=create_app()
