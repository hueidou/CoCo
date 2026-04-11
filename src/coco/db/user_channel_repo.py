# -*- coding: utf-8 -*-
"""Repository for per-user channel config overrides."""

import json
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from .models import UserChannelOverride


# Fields that belong to agent-level config (admin-only), excluded from user overrides.
AGENT_LEVEL_FIELDS = frozenset({"visible_to_user"})


class UserChannelRepo:
    """Repository for user channel override operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_overrides(
        self, user_id: str, agent_id: str, channel_key: str
    ) -> Optional[dict]:
        """Get user-level overrides for a specific channel.

        Returns the overrides dict, or None if no overrides exist.
        """
        row = (
            self.db.query(UserChannelOverride)
            .filter(
                UserChannelOverride.user_id == user_id,
                UserChannelOverride.agent_id == agent_id,
                UserChannelOverride.channel_key == channel_key,
            )
            .first()
        )
        if row is None:
            return None
        return json.loads(row.overrides)

    def get_all_overrides(
        self, user_id: str, agent_id: str
    ) -> Dict[str, dict]:
        """Get all user-level overrides for an agent.

        Returns {channel_key: overrides_dict, ...}.
        """
        rows = (
            self.db.query(UserChannelOverride)
            .filter(
                UserChannelOverride.user_id == user_id,
                UserChannelOverride.agent_id == agent_id,
            )
            .all()
        )
        return {row.channel_key: json.loads(row.overrides) for row in rows}

    def save_overrides(
        self, user_id: str, agent_id: str, channel_key: str, overrides: dict
    ) -> None:
        """Save (upsert) user-level overrides for a channel.

        Agent-level fields (enabled, visible_to_user) are stripped before saving.
        """
        # Strip agent-level fields
        clean = {k: v for k, v in overrides.items() if k not in AGENT_LEVEL_FIELDS}
        if not clean:
            # No user-level fields to save — delete if exists
            self.delete_overrides(user_id, agent_id, channel_key)
            return

        overrides_json = json.dumps(clean, ensure_ascii=False)
        now = datetime.utcnow()

        row = (
            self.db.query(UserChannelOverride)
            .filter(
                UserChannelOverride.user_id == user_id,
                UserChannelOverride.agent_id == agent_id,
                UserChannelOverride.channel_key == channel_key,
            )
            .first()
        )
        if row is not None:
            row.overrides = overrides_json
            row.updated_at = now
        else:
            row = UserChannelOverride(
                user_id=user_id,
                agent_id=agent_id,
                channel_key=channel_key,
                overrides=overrides_json,
                created_at=now,
                updated_at=now,
            )
            self.db.add(row)
        self.db.commit()

    def delete_overrides(
        self, user_id: str, agent_id: str, channel_key: str
    ) -> bool:
        """Delete user-level overrides for a channel.

        Returns True if a row was deleted, False otherwise.
        """
        result = (
            self.db.query(UserChannelOverride)
            .filter(
                UserChannelOverride.user_id == user_id,
                UserChannelOverride.agent_id == agent_id,
                UserChannelOverride.channel_key == channel_key,
            )
            .delete()
        )
        self.db.commit()
        return result > 0
