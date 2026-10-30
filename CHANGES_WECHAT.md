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

## 2.3.1-wechat.4 (2026-10-30)
- Fix: 记忆面板「清空记忆」只转圈——确认框 `.inline-confirm-overlay` z-index 低于忙闲层，确认被挡在 spinner 后面；确认改到 withBusy 外，并抬高 z-index。
- Clear: `_cancel_background_tasks_for_clear` 同步取消 summary workers；备份/清库加 45s 写锁超时，避免假死。
- Clear: 一并清空 summary_batch_*、画像附属表、revision、FTS 等残留表；文案说明捕获仍开时时间线会再写入。

## 2.3.1-wechat.3 (2026-10-30)
- H3: `parse_scope_from_session` returns unknown for UMO `FriendMessage:gh_*` / `PrivateMessage:gh_*`; `resolve_event_context` never promotes gh_ to private (capture/observe inherit).
