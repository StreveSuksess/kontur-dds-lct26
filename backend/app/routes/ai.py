import copy
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from ..models import Event
from ..ai import ModelUnavailable, local_url, review_semantics
from ..auth import get_db, roles
from ..common import scoped_session, require_active, event_json, events_for, audit

router = APIRouter(tags=['local-ai'])


@router.get('/ai/status')
async def status(request: Request, user=Depends(roles('student', 'teacher', 'admin'))):
    settings = request.app.state.settings
    result = {'language_model': {'configured': bool(settings.ai_endpoint and settings.ai_mode == 'local'), 'available': False, 'model': settings.ai_model},
              'speech': {'configured': bool(settings.speech_endpoint), 'available': False},
              'voice': {'configured': bool(settings.tts_endpoint), 'available': False}, 'assessment': 'rules_with_teacher_review'}
    async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
        for name, endpoint, path in [('speech', settings.speech_endpoint, '/health'),
                                     ('voice', settings.tts_endpoint, '/health'),
                                     ('language_model', settings.ai_endpoint if settings.ai_mode == 'local' else None, '/models')]:
            if not endpoint: continue
            try:
                response = await client.get(local_url(endpoint, path))
                if response.is_success:
                    health = response.json()
                    result[name]['available'] = bool(health.get('data')) if name == 'language_model' else health.get('status') == 'ok' and health.get('available', True) is not False
                    if name == 'speech': result[name]['model'] = health.get('model', 'local_asr')
            except (httpx.HTTPError, ValueError, ModelUnavailable): pass
    return result


@router.get('/sessions/{session_id}/events/{event_id}/audio')
async def reply_audio(session_id: str, event_id: str, request: Request, db=Depends(get_db), user=Depends(roles('student', 'teacher'))):
    scoped_session(db, session_id, user)
    event = db.get(Event, event_id)
    if not event or event.session_id != session_id or event.kind != 'contact_message':
        raise HTTPException(404, 'Реплика контакта не найдена')
    text = event.payload.get('text', '')
    if not text or len(text) > 1999: raise HTTPException(422, 'Реплика не подходит для озвучки')
    try:
        url = local_url(request.app.state.settings.tts_endpoint, '/synthesize')
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.post(url, json={'text': text})
            if response.status_code == 429: raise HTTPException(429, 'Голосовой сервер занят. Повторите через несколько секунд')
            response.raise_for_status()
            if not response.content.startswith(b'RIFF') or len(response.content) > 15*1024*1024:
                raise ValueError('invalid WAV')
    except (httpx.HTTPError, ValueError, ModelUnavailable) as exc:
        raise HTTPException(503, 'Локальная озвучка недоступна. Полный ответ доступен в тексте') from exc
    return Response(content=response.content, media_type='audio/wav', headers={'Cache-Control': 'private, no-store'})


@router.post('/sessions/{session_id}/transcribe')
async def transcribe(session_id: str, request: Request, db=Depends(get_db), user=Depends(roles('student'))):
    row = scoped_session(db, session_id, user); require_active(row)
    content_type = request.headers.get('content-type', '').split(';', 1)[0]
    if content_type not in {'audio/wav', 'audio/x-wav', 'audio/webm', 'audio/ogg', 'audio/mp4'}:
        raise HTTPException(415, 'Нужна запись WAV, WebM, Ogg или MP4')
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > 10*1024*1024: raise HTTPException(413, 'Запись больше 10 МБ')
    if not chunks: raise HTTPException(422, 'Пустая запись')
    settings = request.app.state.settings
    try:
        endpoint = local_url(settings.speech_endpoint, '/transcribe')
        async with httpx.AsyncClient(timeout=max(30, settings.ai_timeout_seconds), trust_env=False) as client:
            response = await client.post(endpoint, content=bytes(chunks), headers={'Content-Type': content_type})
            if response.status_code == 429: raise HTTPException(429, 'Распознавание занято. Повторите через несколько секунд')
            if response.status_code in {400, 413, 415, 422}: raise HTTPException(422, 'Не удалось прочитать запись; допустимо до 120 секунд')
            response.raise_for_status()
            result = response.json()
            if not isinstance(result.get('text'), str) or len(result['text']) > 10000: raise ValueError('invalid text')
    except (httpx.HTTPError, ValueError, ModelUnavailable) as exc:
        raise HTTPException(503, 'Локальное распознавание недоступно. Доклад можно ввести текстом') from exc
    # No raw audio or transcript is persisted by this endpoint. Learner reviews
    # the text and explicitly sends it through the normal, idempotent event API.
    return {k: result.get(k) for k in ('text', 'language', 'duration_seconds', 'latency_seconds', 'model')} | {
        'requires_human_review': True, 'mode': 'local_asr'}


@router.post('/sessions/{session_id}/ai-review')
def ai_review(session_id: str, request: Request, db=Depends(get_db), user=Depends(roles('teacher'))):
    row = scoped_session(db, session_id, user)
    if row.status not in {'submitted', 'reviewed', 'stopped'} or not row.report:
        raise HTTPException(409, 'Сначала завершите попытку')
    snapshot, report = copy.deepcopy(row.snapshot), copy.deepcopy(row.report)
    events = [event_json(e) for e in events_for(db, row)]
    try:
        result = review_semantics(request.app.state.settings, snapshot, events, report)
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    audit(db, user, 'ai_review_requested', 'session', row.id, {'model': result['model'], 'suggestions': len(result['suggestions'])})
    db.commit()
    return result
