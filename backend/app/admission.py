"""Bound in-flight requests for the synchronous SQLAlchemy/threadpool stack.

Without admission control, hundreds of auth dependencies can exhaust both the
connection pool and the worker pool before already-authenticated routes run.
Hold the permit through the full ASGI response, including dependency cleanup.
"""
import asyncio


class AdmissionMiddleware:
    def __init__(self, app, limit=24):
        self.app = app
        self.permits = asyncio.Semaphore(limit)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope.get('path', '').startswith('/api/'):
            return await self.app(scope, receive, send)
        async with self.permits:
            await self.app(scope, receive, send)
