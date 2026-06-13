---
name: freellmapi-usage-check
description: 登录 FreeLLMAPI dashboard，查看用量详情（请求数/token/延迟/节省），分析各模型成功率，智能优化路由，总结后回复。
---

# FreeLLMAPI 用量检查 + 智能优化

每次用户问 FreeLLMAPI 用量/额度/性能时执行此 skill。

## 步骤

### 0. 前置：确保能登录 Dashboard

如果遇到登录问题，检查以下情况：

- **密码错误或想改密码**：参考 `references/freellmapi-auth.md`
- **"Too many failed attempts"**：重启服务 `sudo systemctl restart freellmapi.service` 可清除内存锁
- **Session 过期**：重新登录即可（输入邮箱密码），无需重建 browser

### 1. 打开 Analytics 页面

```bash
browser-act browser list  # 找到可用 browser ID（通常是 100287258835473970）
browser-act --session freellmapi-usage browser open <browser_id> http://localhost:3001/analytics
browser-act --session freellmapi-usage get markdown
```

### 2. 提取关键数据并总结

从 Analytics 页面提取：
- **总量**：请求数、成功率、输入/输出 token、平均延迟、预估节省金额
- **Top 模型**：请求量最多的前 5 个模型（名称、请求数、成功率、延迟、输入/输出 token）
- **失败模型**：成功率低于 50% 或 0% 的模型列表
- **主要错误来源**：Recent errors 中的高频错误

### 3. 分析优化方向

检查以下问题：
- **有数据（obs > 0）** 且成功率 < 50% 的模型 → 应手动禁用
- **有数据（obs > 0）** 且成功率 = 0% 的模型 → 应手动禁用（已确认失败）
- 延迟 > 60s 的模型 → 考虑禁用
- **无数据（obs = 0）的模型不要禁用** — 可能从未被调用过，路由策略会自动处理
  
特别注意：\n- **Cloudflare 模型如果有数据且 = 0% 则禁用**（API 401 认证问题）\n  - 但 0% 的根因通常是 token 权限不够而非服务不可用\n  - 如果用户愿意修复而非禁用：先修 token 权限再重新测试\n  - 参考 `skill_view(name='freellmapi-usage-check', file_path='references/cloudflare-workers-ai-setup.md')` 的完整诊断和修复步骤\n- Google models 低成功率且 obs > 0 → 禁用\n- NVIDIA 超时频繁 → 禁用心跳超时的模型\n- 区分「0 obs（从未调用）」和「0%（调用但全失败）」

### 4. 切换到 Models 页面并优化

```bash
browser-act --session freellmapi-optimize browser open <browser_id> http://localhost:3001/models/chat
sleep 2
browser-act --session freellmapi-optimize state
# 等待页面加载完成
browser-act --session freellmapi-optimize wait stable
```

**先切换路由策略**：找到「Most reliable」按钮（通常是 #16），点击它。

**再手动禁用失败模型**（逐个来，每点一个等0.5秒）：

注意：99个模型分布在约 **5-6屏** scroll 范围内，需要多次 scroll down 才能看到全部。

```bash
# 读取当前可见模型 → 找到 aria-checked=true 但成功率<50%的 toggle → 点击禁用
# 注意：click 参数是纯数字（如 16），不是 '@e16' 格式
browser-act --session freellmapi-optimize click <ref_id>

# 滚动查看下一批模型
browser-act --session freellmapi-optimize scroll down
sleep 1
# 获取最新状态以获得正确的 ref ID（滚动后 ref ID 会变化）
browser-act --session freellmapi-optimize state
```

需要禁用的模型规则：
- **Cloudflare (CF) 模型**：API 401 认证问题。先检查是否为 token 权限问题（参考 cloudflare-workers-ai-setup.md）。如果已确认 token 权限正确但依然 0%，则禁用。
- **Google gemini-3 系列**：function_call 参数错误，成功率 <50% → 禁用
- **NVIDIA 0% 模型**：超时或返回错误 → 禁用
- **其他 0%**：Groq/Cerebras/SambaNova 中测试失败的

**⚠️ 关键注意点：**
- 每个 toggle 的 ref ID 会随 scroll 重新渲染而变化，每滚动一次需要重新 `state` 获取最新 ref
- 点过的 toggle 状态会保持（不用重复点击）
- 有 Unsaved changes 提示时才能 Save，否则无需保存

**保存**：
```bash
browser-act --session freellmapi-optimize click <save_button_ref>
```

### 5. 关闭 session

```bash
browser-act session close freellmapi-usage
browser-act session close freellmapi-optimize
```

### 6. 回复用户

用中文回复，包含：
- 当前用量概览（请求数、成功率、输入/输出 token、平均延迟、预估节省金额）
- Top 5 模型（名称、请求数、成功率、延迟）
- 优化操作总结（切换了什么策略、禁用了哪些模型、禁用模型的总额度）
- 额度影响：禁用模型的总月额度 / 总预算 1.6B 的比例
- 优化后预期效果

不需要冗余解释，直接给出数据 + 操作结果。

## REST API 方式（替代 browser-act）

FreeLLMAPI 的 key 管理和健康检查都可通过 REST API 完成，**优先于 browser-act**（用户偏好 turnkey 自动化，浏览器操作易中断）。

**关键发现：⚠️ 健康检查 ≠ 模型可用性**  
FreeLLMAPI 的健康检查只测试 key 的 base URL 是否可达，不测试具体模型能否成功调用。一个 provider 可能显示 `healthy` 但其所有模型都在返回 401/429/500。**不要只依赖健康检查状态做决策**，结合 `/api/analytics/error-distribution` 的实际错误数据。

### 认证

```bash
# 登录获取 dashboard token
LOGIN_RESP=$(curl -s -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"<密码>"}')
TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# Token 通过 x-dashboard-token 或 Authorization: Bearer 头发送
```

**⚠️ Shell 引号坑**：在 Hermes `terminal()` 中，`$()` 和反引号极易与 Bearer token 中的特殊字符冲突，导致 `unexpected EOF` 或 `syntax error`。推荐模式：

```bash
# 先把 token 保存到文件再引用
curl -s -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"<密码>"}' | jq -r '.token' > /tmp/freellmapi_token.txt

# 用 $(cat ...) 引用，避免 inline 变量展开冲突
curl -s http://localhost:3001/api/keys \
  -H "Authorization: Bearer ***(cat /tmp/freellmapi_token.txt)"
```

如果 curl 还是报语法错误，改用 Python `execute_code()` + `urllib.request`（最干净）。

### 常用操作

```bash
# 列出所有 keys
curl -s http://localhost:3001/api/keys -H "Authorization: Bearer ***

# 添加内置平台 key
curl -s -X POST http://localhost:3001/api/keys \
  -H "Authorization: Bearer *** -H "Content-Type: application/json" \
  -d '{"platform":"cloudflare","key":"account_id:token","label":"Workers AI"}'
```

### 禁用/启用 provider（PATCH）

不同于删除 key 或禁单个模型，PATCH 可以禁用整个 provider 使其不出现在 auto 路由中。**推荐用于彻底坏掉的上游**：

```bash
# 禁用某个 key（软禁用，保留配置可恢复）
curl -s -X PATCH http://localhost:3001/api/keys/<id> \
  -H "Authorization: Bearer *** \
  -H "Content-Type: application/json" \
  -d '{"enabled":false}'

# 重新启用
curl -s -X PATCH http://localhost:3001/api/keys/<id> \
  -H "Authorization: Bearer *** \
  -H "Content-Type: application/json" \
  -d '{"enabled":true}'
```

响应示例：`{"success":true,"enabled":false}`

### 按 platform 名批量启用/禁用

用 `/api/keys/platform/:platform` 替代按 id，适合已知平台名的场景：

```bash
curl -s -X PATCH http://localhost:3001/api/keys/platform/opencode \
  -H "Authorization: Bearer $(cat /tmp/freellmapi_token.txt)" \
  -H "Content-Type: application/json" \
  -d '{"enabled":true}'
```

注意：platform 名就是 `/api/keys` 返回的 `platform` 字段值（小写）。PATCH 后立即生效，无需重启。

### 更新 API Key 的限制

`PATCH /api/keys/<id>` **只接受 `enabled` 或 `label` 字段**，不接受 `apiKey`。想更新 key 必须 DELETE 旧 key 再 POST 创建新的。

```bash
# 1. DELETE 旧 key
curl -s -X DELETE http://localhost:3001/api/keys/<id> \
  -H "Authorization: Bearer $(cat /tmp/freellmapi_token.txt)"

# 2. POST 新 key
curl -s -X POST http://localhost:3001/api/keys/custom \
  -H "Authorization: Bearer $(cat /tmp/freellmapi_token.txt)" \
  -H "Content-Type: application/json" \
  -d '{"baseUrl":"https://apihub.agnes-ai.com/v1","model":"auto","displayName":"Agnes AI","apiKey":"sk-xxx"}'
```

### 分析错误分布（替代 browser-act 提取）

优先用 REST API 获取结构化错误数据，比浏览器视觉提取更可靠：

```bash
# 错误分布（by category / by platform / detailed）
curl -s "http://localhost:3001/api/analytics/error-distribution" \
  -H "Authorization: Bearer ***

# 用量摘要
curl -s "http://localhost:3001/api/analytics/summary" \
  -H "Authorization: Bearer ***

# 按平台统计
curl -s "http://localhost:3001/api/analytics/by-platform" \
  -H "Authorization: Bearer ***
```

**决策规则**（基于实际错误数据，非健康检查）：
- **错误数 > 50 且成功率 < 70%** → 考虑禁用整个 provider（PATCH enabled=false）
- **大量 401/403 认证错误** → token 过期，可直接禁用，不是临时故障
- **429 为主** → 可能只是限流，先留着观望
- **Provider 健康检查 healthy 但模型全挂** → 是 provider 端模型下架/改名，不是连接问题

### 添加 Custom（OpenAI 兼容）provider

每个模型单独注册一次，共享相同 baseUrl 的自动绑定到同一 key。

方式 A — REST API（推荐）：
```bash
curl -s -X POST http://localhost:3001/api/keys/custom \
  -H "Authorization: Bearer *** -H "Content-Type: application/json" \
  -d '{
    "baseUrl": "https://apihub.agnes-ai.com/v1",
    "model": "agnes-2.0-flash",
    "displayName": "Agnes-2.0-Flash",
    "apiKey": "sk-xxx",
    "label": "Agnes AI"
  }'
```

方式 B — 可复用脚本（推荐用于批量添加）：
```bash
# 编辑脚本填入 API key 和 password
python3 ~/.hermes/skills/devops/freellmapi-usage-check/scripts/add-custom-provider.py
```

⚠️ Custom provider 的 model 名必须与上游 API 完全一致（**大小写敏感**）

```bash
# 删除 key（彻底移除）
curl -s -X DELETE http://localhost:3001/api/keys/<id> \
  -H "Authorization: Bearer ***

# 触发单 key 健康检查
curl -s -X POST http://localhost:3001/api/health/check/<keyId> \
  -H "Authorization: Bearer ***

# 检查所有 keys
curl -s -X POST http://localhost:3001/api/health/check-all \
  -H "Authorization: Bearer ***

# 查看模型列表（按 platform 筛选）
curl -s "http://localhost:3001/api/models?platform=custom" \
  -H "Authorization: Bearer ***
```

### 📋 Provider 批量维护流程

需要检查并恢复此前禁用的 provider 时，按此流程：

```python
import urllib.request, json

BASE = "http://111.231.114.102:3001"

# 1. 登录拿 token
login = json.dumps({"email": "your@email.com", "password": "<密码>"}).encode()
req = urllib.request.Request(f"{BASE}/api/auth/login", data=login,
    headers={"Content-Type": "application/json"})
token = json.loads(urllib.request.urlopen(req).read())["token"]

# 2. 列出所有 provider，找出禁用的
req = urllib.request.Request(f"{BASE}/api/keys",
    headers={"Authorization": f"Bearer {token}"})
keys = json.loads(urllib.request.urlopen(req).read())
disabled = [k for k in keys if not k.get("enabled")]
print(f"禁用: {len(disabled)}, 启用: {len(keys) - len(disabled)}")

# 3. 逐个健康检查
for k in disabled:
    req = urllib.request.Request(f"{BASE}/api/health/check/{k['id']}",
        method="POST", headers={"Authorization": f"Bearer {token}"})
    status = json.loads(urllib.request.urlopen(req, timeout=30).read())
    print(f"  {k['platform']:20s} → {status.get('status','?')}")
    
    # 4. 如果健康，重新启用
    if status.get("status") in ("healthy", "ok"):
        patch = json.dumps({"enabled": True}).encode()
        req = urllib.request.Request(
            f"{BASE}/api/keys/platform/{k['platform']}",
            data=patch, method="PATCH",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        urllib.request.urlopen(req)
        print(f"    → 已启用")
```

**注意**：健康检查只测 key 的 base URL 可达性，不保证具体模型能成功调用。启用后需要监控实际错误率。

FreeLLMAPI 使用 SQLite，数据库路径：`~/freellmapi/server/data/freeapi.db`

```bash
# 查看 unified API key（用于 /v1 代理认证）
sqlite3 ~/freellmapi/server/data/freeapi.db \
  "SELECT value FROM settings WHERE key='unified_api_key'"

# 查看所有 settings
sqlite3 ~/freellmapi/server/data/freeapi.db \
  "SELECT key, substr(value, 1, 50) FROM settings"

# 查看所有 api_keys
sqlite3 ~/freellmapi/server/data/freeapi.db \
  "SELECT id, platform, label, enabled, status, base_url FROM api_keys"

# 查看特定 key 的模型
sqlite3 ~/freellmapi/server/data/freeapi.db \
  "SELECT id, model_id, display_name, key_id, enabled FROM models WHERE key_id=<keyId>"
```

### ⚠️ Shell 引号坑

在 Hermes 的 `terminal()` 工具中，用 f-string 传 token 容易触发 shell 引号解析错误（表现为 `unexpected EOF` 或 `syntax error near unexpected token`）。**解决方案**：用 `execute_code()` 配合 `urllib.request`，或者将 curl 写入独立 Python 脚本。

使用 `execute_code()`（推荐，最干净）：
```python
from hermes_tools import terminal
import urllib.request, json

token = terminal("cat /tmp/token.txt")['output'].strip()
data = json.dumps({...}).encode()
req = urllib.request.Request(url, data=data, headers=..., method="POST")
resp = urllib.request.urlopen(req)
```

使用独立脚本（适用于复杂 multi-step）：
```python
from hermes_tools import terminal
terminal("python3 ~/.hermes/skills/devops/freellmapi-usage-check/scripts/add-custom-provider.py")
```

或者将 curl 命令写入 /tmp/script.py 后执行。

### Key 状态说明

| 状态 | 含义 | 操作 |
|------|------|------|
| unknown | 新添加，未验证 | 触发 health check |
| healthy | 验证通过 | 可以正常使用 |
| invalid | 验证失败 | 检查 token 权限/格式 |
| rate_limited | 被限流 | 等待后重试 |

添加新 key 后状态为 `unknown`，必须触发 health check 才会变为 `healthy`。

## 自动化优化（自我修复模式）

可设置 no_agent cron 定时运行优化脚本，自动禁用表现差的上游、恢复已恢复的。

### 核心逻辑

```
for each platform in by-platform-stats(24h window):
    if requests >= MIN_OBS and success_rate < THRESHOLD:
        PATCH /api/keys/platform/{name} enabled=false  # 禁用
    if was_disabled_by_optimizer and requests >= MIN_OBS:
        if success_rate >= THRESHOLD:
            PATCH /api/keys/platform/{name} enabled=true   # 恢复（数据说话）
        else:
            keep disabled  # 仍然低
    if was_disabled_by_optimizer and requests < MIN_OBS:
        # 没数据 = 被我们禁了所以没流量 — 用健康检查判断
        POST /api/health/check/<key_id>
        if status == "healthy":
            PATCH enabled=true   # 给一次机会，让真实流量重新验证
        else:
            keep disabled
```

### ⚠️ 关键设计约束：恢复死胡同

**问题：** 禁用 → 没请求 → 没数据 → 永远达不到 MIN_OBS → 永远无法恢复

**补救：** 对已禁用且零数据的平台，必须用**健康检查（health check）**绕过 analytics 的数据依赖：

- 健康检查返回 `healthy` → 重新启用（真实流量会重新积累数据，下一轮 window 的自然判断会接手）
- 健康检查返回其他状态 → 保持禁用

健康检查只测 base URL 可达性（不保证模型能成功调用），但作为"能不能给一次机会"的信号足够。重新启用后如果还是不行，下一轮 runs 会再次禁用。

### 状态追踪

状态文件 `~/.freellmapi_optimizer_state.json` 跟踪谁是被自动禁的。格式：

```json
{"disabled_by_optimizer": ["opencode", "ollama"]}
```

只有自动优化器写入此文件。手动禁用的不在此列，不会自动恢复。

### 凭证管理

no_agent 脚本不能交互输入密码。用独立凭证文件（chmod 600），脚本启动时读取。

### Cron 配置

```bash
cronjob action=create name='FreeLLMAPI 自动优化' no_agent=true schedule='0 8,16,23 * * *' script='freellmapi_optimizer.py'
```

脚本成功无变化时 stdout 为空 → cron 静默。有变化时输出报告 → 推送频道。

### 已部署参考

完整实现位于 `~/.hermes/scripts/freellmapi_optimizer.py`，含登录 → 24h 统计 → 逐个决策 → PATCH 禁用/恢复 + 状态持久化。

## 参考文件

- `references/cloudflare-workers-ai-setup.md` — Cloudflare Workers AI 完整诊断和修复
- `references/agnes-ai-setup.md` — Agnes AI 永久免费 API 集成
- `references/operations.md` — 运维操作（登录重试、密码修改、锁处理）
- `references/analytics-interpretation.md` — 快速解读 Analytics 页面指标
- `scripts/add-custom-provider.py` — 通过 REST API 添加 custom provider
- `scripts/freellmapi_optimizer.py` — 自动优化器脚本（no_agent cron）\n\n---\n