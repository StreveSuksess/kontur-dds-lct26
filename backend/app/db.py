from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def create_database(url: str):
    opts = {'pool_pre_ping': True}
    if url.startswith('sqlite'):
        if ':memory:' not in url:
            location = url.split('///', 1)[-1]
            Path(location).parent.mkdir(parents=True, exist_ok=True)
        opts['connect_args'] = {'check_same_thread': False, 'timeout': 30}
        if ':memory:' in url:
            opts['poolclass'] = StaticPool
    engine = create_engine(url, **opts)
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine, 'connect')
        def sqlite_options(connection, _):
            cursor = connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA busy_timeout=30000')
            cursor.close()
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
