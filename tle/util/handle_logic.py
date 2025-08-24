"""Platform-agnostic helpers for linking Codeforces handles to users.

This module centralises the business rules that were previously baked into
`handles.py` (Discord-specific) so that both Discord and Telegram front-ends can
reuse them.
"""
from __future__ import annotations

import logging
from typing import Optional

from tle.util import codeforces_api as cf, codeforces_common as cf_common, db

logger = logging.getLogger(__name__)


class HandleError(Exception):
    """Base error for handle ops."""


async def resolve_handle(handle: str) -> cf.User:
    """Resolve *handle* via Codeforces API, returning cf.User or raising HandleError."""
    try:
        (user,) = await cf.user.info(handles=[handle])
        return user
    except cf.NotFoundError:
        raise HandleError(f"Handle '{handle}' not found on Codeforces")


async def link_handle(user_id: int, chat_id: int, handle: str) -> cf.User:
    """Link *handle* to *(user_id, chat_id)* in DB and return the cf.User.

    Raises HandleError on failure (duplicate, etc.).
    """

    if handle in cf_common.HandleIsVjudgeError.HANDLES:
        raise HandleError("VJudge handles are not supported")

    user = await resolve_handle(handle)

    try:
        cf_common.user_db.set_handle(user_id, chat_id, user.handle)
    except db.UniqueConstraintFailed:
        raise HandleError(
            f"The handle '{handle}' is already associated with another user in this chat."
        )

    cf_common.user_db.cache_cf_user(user)
    return user


def fetch_handle(user_id: int, chat_id: int) -> Optional[cf.User]:
    """Return cf.User linked to (user_id, chat_id) or None."""
    handle = cf_common.user_db.get_handle(user_id, chat_id)
    if not handle:
        return None
    return cf_common.user_db.fetch_cf_user(handle)
