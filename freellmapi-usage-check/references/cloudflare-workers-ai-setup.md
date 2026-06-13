# FreeLLMAPI Cloudflare Workers AI 配置

## 本次实践确认

- Cloudflare API token 当前使用 `cfut_` 前缀（示例：`cfut_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`）
- Workers AI 模板自动设置永不过期（TTL 留空即可）
- 同一账户可以创建多个 Workers AI token

## 问题：401 Authentication error

Cloudflare Workers AI 调用返回 401 的**常见原因**：

### 原因一：Permission 权限不对（最常见）

API token 的 permission 必须是 **Workers AI**，不是 `Account.Access:Keys`。

Cloudflare API Tokens 页面上，如果有 token 显示 `Account.Access:Keys` 权限，说明创建时用的是「Custom token」模板而非「Workers AI」模板，或者自己选了错误的 permission 分组。Workers AI 模型调用需要的是 `Workers AI:Read` + `Workers AI:Edit` 两个权限。

**容易混淆**：`Account.Access:Keys` 这个权限名看起来像"账户访问"但不是 Workers AI；它只是允许通过 API 管理其他 API tokens，而非调用 AI 模型。

### 原因二：缺少 Account ID

FreeLLMAPI 源码 `providers/cloudflare.ts` 要求 key 格式为 `account_id:api_token`（或 FreeLLMAPI 新版拆成两个独立输入字段）。如果只填了 token 没填 Account ID，健康检查可能通过（只验证 token 是否 active），但实际调用会 401。

### 原因三：Token 格式错误

Cloudflare Workers AI 使用 Bearer token 认证，API endpoint 为：
`https://api.cloudflare.com/client/v4/accounts/{accountId}/ai/v1/chat/completions`

## 诊断步骤

### 1. 直接 curl 测试（最快定位器）

```bash
curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST \
  "https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai/v1/chat/completions" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"model":"@cf/meta/llama-3.1-8b-instruct","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
```

- HTTP 401 → token 权限不对（最常见）或格式错误
- HTTP 200 → token 是活且有效的，问题在 FreeLLMAPI 配置端

### 2. 浏览器验证 token 权限

用 browser-act 打开 Cloudflare API Tokens 页面检查：

```bash
browser-act --session check-cf browser open <browser_id> "https://dash.cloudflare.com/profile/api-tokens"
browser-act --session check-cf wait stable --timeout 15000
browser-act --session check-cf state
```

Permissions 列显示的内容决定 token 能力：
- 正确：Workers AI:Read, Workers AI:Edit — 可以调用
- 错误：Account.Access:Keys — 只能管理 API tokens，无法调用 AI

## 修复步骤

### 创建正确的 API Token（必须用 Workers AI 模板）

```bash
# 1. 打开 API Tokens 页面
browser-act --session cf-create browser open <browser_id> "https://dash.cloudflare.com/profile/api-tokens"
browser-act --session cf-create wait stable

# 2. 点击 "Create Token"
# 3. 在模板列表中找到 "Workers AI"，点击 "Use template"
#    模板自动设置 Workers AI:Read + Workers AI:Edit

# 4. Account Resources 选 "All accounts"
# 5. 点击 "Continue to summary" → "Create Token"
# 6. 复制页面显示的 token 值（只显示一次！务必立即保存）
```

| 模板名 | Permissions 列 | 是否可用 |
|--------|---------------|---------|
| Workers AI | Workers AI:Read, Workers AI:Edit | 正确 |
| Custom | Account.Access:Keys | 错误 |

### browser-act 操作细节（Cloudflare 页面 ref IDs）

Cloudflare API Tokens 页面的 **Create Token** 按钮和模板按钮在不同状态下有不同 ref ID：

**步骤详述：**

1. 打开页面 → 找到 `[18] Create Token` 按钮，点击
2. 页面显示模板列表 → 找到 `[26] Workers AI · Use template`，点击
3. 表单页面：
   - Token name 自动填入 "Workers AI"（`[17]`）
   - Permissions 自动显示 Account → Workers AI → Read (`[22]`) 和 Account → Workers AI → Edit (`[27]`)
   - Account Resources：`[31]` 下拉框当前显示 "Select..."，点击后弹出选项
   - 选择 `[32] All accounts`（或 `[33] Xiaxrannc@gmail.com's Account`）
   - TTL：start/end date 输入框标记 required=true 但模板默认留空无过期时间
   - 点击 `[40] Continue to summary`
4. 摘要页面：显示 `Workers AI:Read, Workers AI:Edit` + `All accounts`
   - 点击 `[18] Create Token`
5. 成功页面：
   - Token 值显示在 `[16]` 区域（文本内容）
   - 格式：`cfut_<64位hex>`
   - ⚠️ **只显示一次**，关闭页面后无法再查看
   - 有 `[17] Test this token` 按钮可测试
6. 点击 `[19] View all API tokens` 回到列表

**注意事项：**
- Cloudflare SPA 的 ref ID 可能因会话不同而变化，以上数字是本次实践的参考
- 关键定位方式：找包含文本 "Workers AI" 和 "Use template" 的按钮
- Create Token 按钮在列表页和模板页各有一个，需区分上下文

### 更新 FreeLLMAPI

```bash
# 1. 打开 http://localhost:3001/keys
# 2. Remove 旧的 Cloudflare key（如果有）
# 3. 选择 Platform = "Cloudflare Workers AI"
# 4. 填写 Account ID + API token，点击 Add key
# 5. 等待状态显示 "healthy"
```

### 通过 FreeLLMAPI Dashboard API 管理 key

如果浏览器操作不行，也可通过 REST API 管理 keys。需要先获取 dashboard session token：

```bash
# 1. 登录获取 token
LOGIN_RESP=$(curl -s -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"<密码>"}')
TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
```

Token 是 64 位 hex 字符串，通过 `x-dashboard-token` 或 `Authorization: Bearer` 头发送。

```bash
# 2. 列出所有 keys（找到 cloudflare key 的 id）
curl -s http://localhost:3001/api/keys \
  -H "x-dashboard-token: $TOKEN" | python3 -m json.tool

# 3. 删除旧 key
curl -s -X DELETE "http://localhost:3001/api/keys/<id>" \
  -H "x-dashboard-token: $TOKEN"

# 4. 添加新 key
curl -s -X POST http://localhost:3001/api/keys \
  -H "x-dashboard-token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"platform":"cloudflare","key":"<ACCOUNT_ID>:<TOKEN>","label":"Workers AI"}'

# 5. 禁用旧 key（替代删除）
curl -s -X PATCH "http://localhost:3001/api/keys/<id>" \
  -H "x-dashboard-token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled":false}'
```

**注意事项：**
- Shell 中传递 token 时注意引号问题，推荐用 Python subprocess 避免转义
- Token 有效期有限（SESSION_TTL_MS），长时间操作需重新登录
- `x-dashboard-token` 和 `Authorization: Bearer` 都可接受
- POST/PATCH/DELETE 都可能返回 401 如果 token 过期
- **在 Hermes 的 terminal() 工具中使用 f-string 传 token 时容易触发 shell 引号解析错误**（表现为 `unexpected EOF while looking for matching` 或 `syntax error near unexpected token`）。解决方案：将 curl 命令写入独立 Python 脚本文件，用 `subprocess.run()` 执行，避免 shell 引号嵌套：`write_file(path='/tmp/script.py', content='...subprocess.run(...)'`，然后 `terminal("python3 /tmp/script.py")`。

### 健康检查（触发 key 状态更新）

添加新 key 后状态为 `unknown`，需要通过 health check endpoint 触发验证变为 `healthy`：

```bash
# 用 dashboard token 触发
curl -s -X POST "http://localhost:3001/api/health/check/23" \
  -H "x-dashboard-token: $DASHBOARD_TOKEN"
# → {"keyId":23,"status":"healthy"}
```

或者一次检查所有 keys：
```bash
curl -s -X POST "http://localhost:3001/api/health/check-all" \
  -H "x-dashboard-token: $DASHBOARD_TOKEN"
# → {"success":true}
```

### 验证

```bash
# 通过 FreeLLMAPI 代理调用
curl -X POST http://localhost:3001/v1/chat/completions \
  -H "Authorization: Bearer freellmapi-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"@cf/meta/llama-3.1-8b-instruct","messages":[{"role":"user","content":"hi"}]}'
```

## 注意事项

- 健康检查通过不代表能调用：`/user/tokens/verify` 只验证 token 是否存在/active，不检查 Workers AI 权限
- Permission 是 ROOT CAUSE：大部分 401 的根源是 token 权限不对
- 模板必须选 Workers AI，不要自己勾 Account 下的 Access:Keys
- Account ID 找法：Cloudflare Dashboard URL 的第一段 path 就是
- curl 401 + 浏览器 Permissions 列显示 Account.Access:Keys = 确认是权限问题
