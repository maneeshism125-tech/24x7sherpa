from __future__ import annotations

import logging

from api.auth_crypto import hash_password
from api.user_store import count_users, create_user, init_db
from sherpa.config import Settings

logger = logging.getLogger(__name__)


def run_auth_startup(settings: Settings) -> None:
    init_db(settings.data_dir)
    if count_users(settings.data_dir) > 0:
        return
    pwd = settings.bootstrap_admin_password or "changeme"
    create_user(
        settings.data_dir,
        user_id="admin",
        password_hash=hash_password(pwd),
        is_admin=True,
    )
    logger.warning(
        "No users in database: created admin user 'admin'. "
        "Set SHERPA_BOOTSTRAP_ADMIN_PASSWORD for a non-default password, then change it in Admin."
    )
