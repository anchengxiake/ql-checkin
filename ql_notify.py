"""Per-script notification adapter for QingLong's built-in notify.py.

The adapter keeps QingLong's notification implementation as the transport.
If variables with the script prefix exist, they override the global channels;
otherwise the normal QingLong global configuration is used.
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import Any


_PREFIX_BY_SCRIPT = {
    "baiduwangpan_checkin.py": "BAIDU",
    "jm_punch.py": "JM",
    "laowang_sign_ql.py": "LAOWANG",
    "mcloud.py": "MCLOUD",
    "pica_punch.py": "PICA",
    "quark_punch.py": "QUARK",
    "rainyun_checkin.py": "RAINYUN",
    "south.py": "SOUTHPLUS",
    "ty_netdisk_checkin.py": "TY",
}

# These are the QingLong push_config keys. Keeping the list here makes the
# adapter independent from private implementation details of notify.py.
_CHANNEL_KEYS = (
    "HITOKOTO", "CONSOLE", "BARK_PUSH", "BARK_ARCHIVE", "BARK_GROUP",
    "BARK_SOUND", "BARK_ICON", "BARK_LEVEL", "BARK_URL", "DD_BOT_SECRET",
    "DD_BOT_TOKEN", "FSKEY", "FSSECRET", "GOBOT_URL", "GOBOT_QQ",
    "GOBOT_TOKEN", "GOTIFY_URL", "GOTIFY_TOKEN", "GOTIFY_PRIORITY",
    "IGOT_PUSH_KEY", "PUSH_KEY", "DEER_KEY", "DEER_URL", "CHAT_URL",
    "CHAT_TOKEN", "PUSH_PLUS_TOKEN", "PUSH_PLUS_USER", "PUSH_PLUS_TEMPLATE",
    "PUSH_PLUS_CHANNEL", "PUSH_PLUS_WEBHOOK", "PUSH_PLUS_CALLBACKURL",
    "PUSH_PLUS_TO", "WE_PLUS_BOT_TOKEN", "WE_PLUS_BOT_RECEIVER",
    "WE_PLUS_BOT_VERSION", "QMSG_KEY", "QMSG_TYPE", "QYWX_ORIGIN",
    "QYWX_AM", "QYWX_KEY", "TG_BOT_TOKEN", "TG_USER_ID", "TG_API_HOST",
    "TG_PROXY_AUTH", "TG_PROXY_HOST", "TG_PROXY_PORT", "AIBOTK_KEY",
    "AIBOTK_TYPE", "AIBOTK_NAME", "SMTP_SERVER", "SMTP_SSL", "SMTP_EMAIL",
    "SMTP_EMAIL_TO", "SMTP_PASSWORD", "SMTP_NAME", "PUSHME_KEY", "PUSHME_URL",
    "CHRONOCAT_QQ", "CHRONOCAT_TOKEN", "CHRONOCAT_URL", "WEBHOOK_URL",
    "WEBHOOK_BODY", "WEBHOOK_HEADERS", "WEBHOOK_METHOD", "WEBHOOK_CONTENT_TYPE",
    "NTFY_URL", "NTFY_TOPIC", "NTFY_PRIORITY", "NTFY_TOKEN", "NTFY_USERNAME",
    "NTFY_PASSWORD", "NTFY_ACTIONS", "WXPUSHER_APP_TOKEN", "WXPUSHER_TOPIC_IDS",
    "WXPUSHER_UIDS", "WXPUSHER_SPT_LIST", "OPENILINK_APP_TOKEN",
    "OPENILINK_HUB_URL", "OPENILINK_CONTEXT_TOKEN",
)


def _script_name() -> str:
    for frame in inspect.stack()[1:]:
        name = Path(frame.filename).name
        if name in _PREFIX_BY_SCRIPT:
            return name
    return Path(inspect.stack()[-1].filename).name


def _prefix(prefix: str | None) -> str:
    if prefix:
        return prefix.strip().upper()
    override = os.getenv("QL_NOTIFY_PREFIX", "").strip()
    return override.upper() or _PREFIX_BY_SCRIPT.get(_script_name(), "")


def _overrides(prefix: str) -> dict[str, Any]:
    if not prefix:
        return {}
    values: dict[str, Any] = {}
    for key in _CHANNEL_KEYS:
        env_name = f"{prefix}_{key}"
        if env_name in os.environ:
            values[key] = os.environ[env_name]
    return values


def send(title: str, content: str, prefix: str | None = None) -> None:
    """Send through QingLong notify.py with optional per-script overrides."""
    try:
        from notify import send as ql_send
    except ImportError:
        print("未找到青龙 notify.py，跳过通知")
        return

    overrides = _overrides(_prefix(prefix))
    if overrides:
        print(f"使用脚本专属通知配置: {_prefix(prefix)}")
        ql_send(title, content, ignore_default_config=True, **overrides)
    else:
        ql_send(title, content)
