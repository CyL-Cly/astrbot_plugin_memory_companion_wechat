from __future__ import annotations

import inspect
import re
from typing import Any, Callable

from .models import EntityRef, SessionContext, clean_text


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _is_wechat_official_wxid(value: str) -> bool:
    return str(value or "").strip().lower().startswith("gh_")


def parse_scope_from_session(session_id: str) -> tuple[str, str]:
    normalized = session_id.lower()
    if ":groupmessage:" in normalized:
        return "group", _tail_after_token(session_id, normalized, ":groupmessage:")
    if ":group:" in normalized:
        return "group", session_id.rsplit(":", 1)[-1]
    if ":friendmessage:" in normalized:
        target = _tail_after_token(session_id, normalized, ":friendmessage:")
        # UMO FriendMessage:gh_* must not become a private memory window.
        if _is_wechat_official_wxid(target):
            return "unknown", ""
        return "private", target
    if ":privatemessage:" in normalized:
        target = _tail_after_token(session_id, normalized, ":privatemessage:")
        if _is_wechat_official_wxid(target):
            return "unknown", ""
        return "private", target
    if ":friend:" in normalized or ":private:" in normalized:
        target = session_id.rsplit(":", 1)[-1]
        if _is_wechat_official_wxid(target):
            return "unknown", ""
        return "private", target
    # wechat_robot adapter may expose raw session_id (wxid / xxx@chatroom)
    # when unified_msg_origin is empty; treat bare ids as private/group.
    bare = session_id.strip()
    if bare.lower().endswith("@chatroom"):
        return "group", bare
    if bare.startswith("wxid_"):
        return "private", bare
    # gh_* 是公众号，不是私聊好友；留给 wechat_official_* 工具，不进入记忆私聊窗口。
    if bare.startswith("gh_"):
        return "unknown", ""
    return "unknown", ""


def session_target_id(session_id: str, expected_scope: str = "") -> str:
    """Return the stable window target carried by an AstrBot session key."""
    scope, target_id = parse_scope_from_session(clean_text(session_id, 200))
    expected_scope = clean_text(expected_scope, 40)
    if expected_scope and scope != expected_scope:
        return ""
    return clean_text(target_id, 120)


def normalize_session_context_fields(
    *,
    session_id: str = "",
    scope: str = "",
    platform: str = "",
    user_id: str = "",
    group_id: str = "",
) -> dict[str, str]:
    session_id = clean_text(session_id, 200)
    scope = clean_text(scope, 40) or "unknown"
    platform = clean_text(platform, 80)
    user_id = clean_text(user_id, 120)
    group_id = clean_text(group_id, 120)
    parsed_scope, parsed_target = parse_scope_from_session(session_id)
    if scope == "unknown" and parsed_scope != "unknown":
        scope = parsed_scope
    if not platform and session_id and ":" in session_id:
        platform = clean_text(session_id.split(":", 1)[0], 80)
    if scope == "private" and not user_id and parsed_target:
        user_id = clean_text(parsed_target, 120)
    if scope == "group" and not group_id and parsed_target:
        group_id = clean_text(parsed_target, 120)
    return {
        "session_id": session_id,
        "scope": scope,
        "platform": platform,
        "user_id": user_id,
        "group_id": group_id,
    }


def _tail_after_token(original: str, normalized: str, token: str) -> str:
    index = normalized.rfind(token)
    if index < 0:
        return ""
    return original[index + len(token) :]


class IdentityResolver:
    def __init__(self, bot_id_fallback: Callable[[Any], Any] | None = None):
        # Some adapters/wrappers do not expose get_self_id().  The fallback is
        # deliberately supplied by the host service so identity.py stays
        # independent from AstrBot internals.
        self.bot_id_fallback = bot_id_fallback

    async def resolve_event_context(self, event: Any) -> SessionContext:
        session_id = clean_text(getattr(event, "unified_msg_origin", "") or "", 200)
        if not session_id:
            # AstrBot normally fills UMO; wechat_robot events still carry session_id.
            session_id = clean_text(getattr(event, "session_id", "") or "", 200)
            message_obj = getattr(event, "message_obj", None)
            if not session_id and message_obj is not None:
                session_id = clean_text(getattr(message_obj, "session_id", "") or "", 200)
        platform = await self._call(event, "get_platform_name")
        if not platform and session_id and ":" in session_id:
            platform = session_id.split(":", 1)[0]

        scope, parsed_target = parse_scope_from_session(session_id)
        group_id = await self._call(event, "get_group_id")
        if group_id:
            scope = "group"
        elif scope == "group" and parsed_target:
            group_id = parsed_target
        group_name = await self._call(event, "get_group_name")
        if not group_name:
            message_obj = getattr(event, "message_obj", None)
            for source in (event, message_obj):
                if source is None:
                    continue
                for attr in ("group_name", "groupname", "group"):
                    value = getattr(source, attr, "")
                    if value:
                        group_name = clean_text(value, 80)
                        break
                if group_name:
                    break
            raw = getattr(message_obj, "raw_message", None)
            if not group_name and isinstance(raw, dict):
                group_name = clean_text(raw.get("group_name") or raw.get("group") or "", 80)

        user_id = await self._call(event, "get_sender_id")
        if not user_id and scope == "private" and parsed_target:
            user_id = parsed_target

        user_name = await self._call(event, "get_sender_name")
        bot_id = await self._call(event, "get_self_id")
        if not bot_id and callable(self.bot_id_fallback):
            try:
                bot_id = await maybe_await(self.bot_id_fallback(event))
            except Exception:
                bot_id = ""
        persona_id = clean_text(
            getattr(event, "private_companion_persona_id", "")
            or getattr(event, "persona_id", ""),
            96,
        )
        text = await self._message_text(event)
        message_id = self._message_id(event)

        # Official accounts are never private companion/memory windows.
        if _is_wechat_official_wxid(user_id) or _is_wechat_official_wxid(parsed_target):
            user_id = ""
            if scope == "private":
                scope = "unknown"

        if not session_id:
            if scope == "group" and group_id:
                session_id = f"{platform or 'unknown'}:GroupMessage:{group_id}"
            elif user_id and not _is_wechat_official_wxid(user_id):
                session_id = f"{platform or 'unknown'}:FriendMessage:{user_id}"
        elif ":" not in session_id and (platform or group_id or user_id):
            # Promote bare wechat wxid/@chatroom into AstrBot UMO form for stable storage.
            if scope == "group" and (group_id or session_id.endswith("@chatroom")):
                gid = group_id or session_id
                session_id = f"{platform or 'wechat_robot'}:GroupMessage:{gid}"
            elif scope in {"private", "unknown"} and (user_id or session_id.startswith("wxid_")):
                uid = user_id or session_id
                if not _is_wechat_official_wxid(uid):
                    session_id = f"{platform or 'wechat_robot'}:FriendMessage:{uid}"

        if scope == "unknown" and user_id and not _is_wechat_official_wxid(user_id):
            scope = "private"

        return SessionContext(
            session_id=session_id,
            scope=scope,
            platform=clean_text(platform, 80),
            user_id=clean_text(user_id, 120),
            user_name=clean_text(user_name, 80),
            group_id=clean_text(group_id, 120),
            group_name=clean_text(group_name, 80),
            bot_id=clean_text(bot_id, 120),
            persona_id=persona_id,
            message_id=clean_text(message_id, 120),
            message_text=clean_text(text, 2000),
        )

    async def _call(self, event: Any, name: str) -> str:
        func = getattr(event, name, None)
        if not callable(func):
            return ""
        try:
            value = await maybe_await(func())
        except Exception:
            return ""
        return "" if value is None else str(value)

    async def _message_text(self, event: Any) -> str:
        getter = getattr(event, "get_message_str", None)
        if callable(getter):
            try:
                value = await maybe_await(getter())
                if isinstance(value, str):
                    return self._original_wake_message_text(event, value)
            except Exception:
                pass
        value = getattr(event, "message_str", "")
        return self._original_wake_message_text(event, value) if isinstance(value, str) else ""

    @staticmethod
    def _original_wake_message_text(event: Any, current: str) -> str:
        # Companion validates the active wake prefix without rewriting AstrBot's
        # routing text. Consume only a snapshot that still describes this event.
        snapshot = getattr(event, "_private_companion_wake_message_context", None)
        if not isinstance(snapshot, dict) or bool(getattr(event, "private_companion_proactive_framework", False)):
            return current
        original = snapshot.get("original_text")
        routed = snapshot.get("routed_text")
        prefix = snapshot.get("wake_prefix")
        source = getattr(getattr(event, "message_obj", None), "message_str", None)
        if (
            isinstance(original, str) and isinstance(routed, str)
            and isinstance(prefix, str) and any(char.isalnum() for char in prefix)
            and isinstance(source, str) and source.strip() == original
            and current.strip() == routed and original.startswith(prefix)
            and original[len(prefix):].strip() == routed
        ):
            return original
        return current

    def _message_id(self, event: Any) -> str:
        message_obj = getattr(event, "message_obj", None)
        for source in (message_obj, event):
            if source is None:
                continue
            for attr in ("message_id", "id"):
                value = getattr(source, attr, None)
                if value:
                    return str(value)
        raw = getattr(message_obj, "raw_message", None)
        if isinstance(raw, dict):
            for key in ("message_id", "id"):
                if raw.get(key):
                    return str(raw.get(key))
        return ""


def entity_for_user(ctx: SessionContext) -> EntityRef:
    return EntityRef(kind="user", id=ctx.user_id, name=ctx.user_name, role="current_sender")


def entity_for_current_target(ctx: SessionContext) -> EntityRef:
    if ctx.scope == "group":
        return EntityRef(kind="group", id=ctx.group_id, name=ctx.group_name, role="current_group")
    return EntityRef(kind="user", id=ctx.user_id, name=ctx.user_name, role="current_private_user")


def looks_like_command(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True

    def _strip_leading_message_decorations(value: str) -> str:
        current = value.strip()
        for _ in range(8):
            previous = current
            current = re.sub(r"^(?:\[CQ:at,[^\]]+\]|\[At:[^\]]+\]|\[at:[^\]]+\])\s*", "", current, flags=re.I)
            current = re.sub(r"^(?:\[Reply:[^\]]+\]|\[reply:[^\]]+\]|\[引用消息[^\]]*\])\s*", "", current, flags=re.I)
            current = re.sub(r"^(?:<at\b[^>]*>|<reply\b[^>]*>)\s*", "", current, flags=re.I)
            current = re.sub(r"^@\S{1,64}\s+", "", current)
            if current == previous:
                break
        return current.strip()

    command_prefixes = ("/", "／", "!", "！", "#", "＃", "﹟")
    candidates = (stripped, _strip_leading_message_decorations(stripped))
    if any(candidate.startswith(command_prefixes) for candidate in candidates):
        return True
    if re.fullmatch(r"[\W_]+", stripped):
        return True
    return False
