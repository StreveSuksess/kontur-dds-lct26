import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request, Response, APIRouter
from sqlalchemy import select, delete
from .models import User, AuthSession, Audit, now
from .schemas import LoginInput

router = APIRouter(prefix='/auth', tags=['auth'])


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    result = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return 'scrypt$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(result).decode()


def password_matches(password: str, encoded: str) -> bool:
    try:
        algo, salt, expected = encoded.split('$')
        if algo != 'scrypt': return False
        result = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(result, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False


def get_db(request: Request):
    with request.app.state.session_factory() as db:
        yield db


def public_user(user: User):
    return {key:getattr(user,key) for key in ['id','username','name','role','service','group_name','active']}


def current_user(request: Request, db=Depends(get_db)) -> User:
    token = request.cookies.get(request.app.state.settings.cookie_name)
    if not token: raise HTTPException(401, 'Войдите в учебную систему')
    session = db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest())
    if not session or session.expires_at <= now():
        raise HTTPException(401, 'Сессия входа истекла')
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, 'Учётная запись недоступна')
    return user


def roles(*allowed):
    def dependency(user=Depends(current_user)):
        if user.role not in allowed: raise HTTPException(403, 'Недостаточно прав для этого действия')
        return user
    return dependency


@router.get('/me')
def me(user=Depends(current_user)):
    return public_user(user)


@router.post('/login')
def login(body: LoginInput, request: Request, response: Response, db=Depends(get_db)):
    # A small in-process limiter protects the local demo; distributed deployment needs a shared limiter.
    import time
    key = (request.client.host if request.client else '', body.username.casefold())
    with request.app.state.mutation_lock:
        attempts = request.app.state.login_attempts
        values = [t for t in attempts.get(key, []) if time.monotonic()-t < 60]
        if len(values) >= 10: raise HTTPException(429, 'Слишком много попыток входа. Повторите через минуту')
        user = db.scalar(select(User).where(User.username == body.username))
        valid = password_matches(body.password, user.password_hash if user else request.app.state.dummy_hash)
        if not user or not user.active or not valid:
            attempts[key] = values+[time.monotonic()]
            raise HTTPException(401, 'Неверный логин или пароль')
        attempts.pop(key, None)
        if len(attempts)>10000: attempts.clear()
        settings = request.app.state.settings
        old = request.cookies.get(settings.cookie_name)
        if old: db.execute(delete(AuthSession).where(AuthSession.token_hash == hashlib.sha256(old.encode()).hexdigest()))
        db.execute(delete(AuthSession).where(AuthSession.expires_at < now()))
        token = secrets.token_urlsafe(40)
        db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(),user_id=user.id,expires_at=(datetime.now(timezone.utc)+timedelta(seconds=settings.auth_ttl_seconds)).isoformat()))
        db.add(Audit(actor_id=user.id,action='login',entity_type='user',entity_id=user.id,details={}))
        db.commit()
        response.set_cookie(settings.cookie_name, token, httponly=True, secure=settings.cookie_secure, samesite='strict',max_age=settings.auth_ttl_seconds,path='/')
        return public_user(user)


@router.post('/logout')
def logout(request: Request, response: Response, db=Depends(get_db)):
    token = request.cookies.get(request.app.state.settings.cookie_name)
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hashlib.sha256(token.encode()).hexdigest()))
        db.commit()
    response.delete_cookie(request.app.state.settings.cookie_name, path='/')
    return {'ok':True}
