# wechat_robot / 微信 bridge 适配说明

本目录是上游 [`menglimi/astrbot_plugin_memory_companion`](https://github.com/menglimi/astrbot_plugin_memory_companion)（v2.3.1）的 **微信 bridge 适配 fork**。

**本 fork 发布仓库：** [`CyL-Cly/astrbot_plugin_memory_companion_wechat`](https://github.com/CyL-Cly/astrbot_plugin_memory_companion_wechat)

这里的「微信 bridge」指：

```
微信 ↔ wechat-robot-client（服务端+客户端）
         ↕ webhook / HTTP
      AstrBot 平台适配器 `wechat_robot`
         （插件目录 astrbot_plugin_wechat_robot）
         ↕ AstrBot 事件 / LLM
      本插件 astrbot_plugin_memory_companion
```

**不是** dsh-wechat-bridge（8787）那条旧桥。

## 为什么要改

上游 `metadata.yaml` 只声明 `support_platforms: [aiocqhttp]`，管理桶把纯数字 ID 标成 QQ。微信会话 ID 是：

| 场景 | AstrBot UMO（unified_msg_origin） | 裸 session_id（适配器） |
|------|-----------------------------------|-------------------------|
| 私聊 | `wechat_robot:FriendMessage:wxid_xxx` | `wxid_xxx` |
| 群聊 | `wechat_robot:GroupMessage:123@chatroom` | `123@chatroom` |

记忆、权限、Companion 桥都以 **UMO / platform / user_id / group_id** 为键。若不认 `wechat_robot` 平台族，私聊记忆会在跨别名时被当成「其他平台」挡掉；群 `@chatroom` 虽本就能被 `:GroupMessage:` 解析，但裸 ID 回落路径原先会落到 `unknown`。

## 本 fork 改动（相对上游 2.3.1）

1. **metadata**：`support_platforms` 增加 `wechat_robot`；版本 `2.3.1-wechat.2`；**插件 `name` 仍为 `astrbot_plugin_memory_companion`**（Companion 协议认这个 ID）。
2. **`core/visibility.py`**：`wechat` / `wechat_robot` / `wechat-robot` 等归一为平台族 `wechat`（不与 QQ 合并）。
3. **`core/identity.py`**：解析裸 `wxid_*` / `gh_*` / `*@chatroom`；UMO 为空时回落 `event.session_id`；裸 ID 提升为标准 UMO。
4. **`core/store.py`**：管理桶 `_bucket_target_kind` 识别微信私聊/群。
5. **命令帮助**：`clear_scope` 文案改为「用户ID/wxid/QQ」「群号/@chatroom」。

**未改、仍可用：** Companion Page / Bot Personal / 记忆工具 / 主链注入 / 文件历史导入。  
**仍不可用（微信侧无 OneBot 历史接口）：** 「QQ 直接读取」历史（`core/qq_history.py`）。请用 TXT/Markdown/JSON 文件导入，或让对话自然沉淀。


## 公众号（gh_*）策略

微信 **公众号 / 系统号不是私聊好友**：

1. `wechat_robot` 适配器默认 `ignore_official=true`：`gh_*` 与系统 stub **不进入** AstrBot FriendMessage / LLM 主链 / Companion observe / Memory 私聊窗口。
2. 适配器会把近期公众号推送放进进程内缓冲；LLM 仅可通过工具查询：
   - `wechat_official_list` — 列出近期出现过的公众号
   - `wechat_official_lookup` — 按 `gh_wxid` / 关键词查正文
3. Companion 绑定、会话目录、主动私信都会拒绝 `gh_*` 作为 participant。
4. 需要公众号内容时，在正常私聊里让模型调用上述工具，而不是把公众号当成陪伴对象。

## 安装到 AstrBot（home）

1. 确认已启用平台插件 `astrbot_plugin_wechat_robot`，且 wechat-robot 系统设置 `webhook_url` 指向 AstrBot（如 `http://astrbot:6196/wechat-robot/callback`）。
2. 将本目录部署为：

   ```text
   /opt/astrbot/data/plugins/astrbot_plugin_memory_companion/
   ```

   目录名必须与插件 `name` 一致，不要用 `..._wechat` 作为 AstrBot 插件目录名（否则 Companion 可能找不到）。
3. 仪表盘 → 插件 → 启用「我会牢牢记住你」；按需配置 Provider / 记忆注入。
4. **重启或重载 AstrBot** 使插件生效：`docker restart astrbot`。
5. 若使用 `astrbot_plugin_private_companion`：保持其官方插件 ID，本 fork 仍通过 `MEMORY_PLUGIN_ID=astrbot_plugin_memory_companion` 对接；先启 Memory 再启 Companion 更稳妥。

## 配置注意

- 关掉 wechat-robot **客户端内置 AI**，否则与 AstrBot 双回。
- 群聊连续记忆依赖群消息事件；需 @ 机器人或配置唤醒规则时，按 AstrBot 全局唤醒设置来。
- 私聊记忆键是 **wxid**，换微信号 / 换机器人 `robot_wxid` 不会自动合并旧库。
- QQ 与微信记忆 **不会串台**（平台族隔离）；同一人两边要分别沉淀。

## 自检

```bash
# 在插件目录
python3 -c "
from core.identity import parse_scope_from_session, normalize_session_context_fields
from core.visibility import _platform_family
assert parse_scope_from_session('wechat_robot:GroupMessage:1@chatroom')[0]=='group'
assert parse_scope_from_session('wxid_ab')[0]=='private'
assert _platform_family('wechat_robot')=='wechat'
print('ok')
"
```

私聊发一句非命令文本，AstrBot 日志应出现 `[MemoryCompanion]`；拓展页可看会话桶是否标成 wechat。
