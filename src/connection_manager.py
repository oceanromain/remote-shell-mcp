"""
ConnectionManager: 管理 SSH/Telnet 会话的生命周期
"""

import uuid
from datetime import datetime
from typing import Dict, Optional, Any


class ConnectionManager:
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def generate_id(self, prefix: str = "session") -> str:
        short = uuid.uuid4().hex[:8]
        return f"{prefix}-{short}"

    def add(self, session_id: str, conn_type: str, handler, host: str, username: str):
        self._sessions[session_id] = {
            "type": conn_type,
            "handler": handler,
            "host": host,
            "username": username,
            "connected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get(self, session_id: str) -> Optional[Dict]:
        return self._sessions.get(session_id)

    def remove(self, session_id: str):
        self._sessions.pop(session_id, None)

    def list_all(self) -> Dict[str, Dict]:
        # 返回不含 handler 对象的摘要
        return {
            sid: {k: v for k, v in info.items() if k != "handler"}
            for sid, info in self._sessions.items()
        }

