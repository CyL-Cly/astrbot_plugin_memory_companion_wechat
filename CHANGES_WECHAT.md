# Changes vs menglimi/astrbot_plugin_memory_companion@2.3.1

| File | Change |
|------|--------|
| `metadata.yaml` | +`wechat_robot`; version `2.3.1-wechat.1`; keep name `astrbot_plugin_memory_companion` |
| `core/visibility.py` | platform family aliases → `wechat` |
| `core/identity.py` | bare wxid/@chatroom parse; session_id fallback; promote to UMO |
| `core/store.py` | `_bucket_target_kind` → `wechat` for wxid/UMO |
| `core/commands.py` | clear_scope help text |
| `WECHAT_BRIDGE.md` | Chinese install / protocol notes |
| `README.md` | fork banner |

Not changed: companion_page_bridge protocol, qq_history (still QQ-only), core memory/RAG logic.

## 2.3.1-wechat.3 (2026-10-30)
- H3: `parse_scope_from_session` returns unknown for UMO `FriendMessage:gh_*` / `PrivateMessage:gh_*`; `resolve_event_context` never promotes gh_ to private (capture/observe inherit).
