import pytest
from app.seed import seed_database
from app.config import Settings


def test_switching_flag_does_not_silently_keep_demo_passwords(env):
    with env['app'].state.session_factory() as db:
        with pytest.raises(ValueError, match='demo passwords'):
            seed_database(db, Settings(demo_mode=False))
