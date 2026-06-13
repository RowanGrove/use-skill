# Agnes AI - 永久免费 AI API 集成

## 基本信息

- **官网**: https://agnes-ai.com
- **API Endpoint**: `https://apihub.agnes-ai.com/v1`（OpenAI 兼容）
- **Auth**: `Authorization: Bearer <api_key>`
- **Platform Dashboard**: https://platform.agnes-ai.com
- **注册**: 官网 → Login → API Platform → Sign Up → Email + 验证码 + 密码

## 免费模型

| 模型ID（小写，API用） | 类型 | 说明 |
|---|---|---|
| agnes-2.0-flash | 文本 (多模态Agent) | ✅ 已确认可用 |
| agnes-1.5-flash | 文本 | 免费 |
| agnes-image-2.0-flash | 图像生成/编辑 | 待测 |
| agnes-video-v2.0 | 视频 (含音频) | 待测 |

## ⚠️ 关键陷阱：模型名大小写敏感

**Agnes API 严格要求模型名全小写**。大写/PascalCase (`Agnes-2.0-Flash`) 会返回 `model_not_found` 错误（channel not available）。

- ✅ 正确: `agnes-2.0-flash`
- ❌ 错误: `Agnes-2.0-Flash` → `No available channel for model Agnes-2.0-Flash`

注册到 FreeLLMAPI 时，`model` 字段必须用小写名。`displayName` 可以用美观的大写名。

## 集成到 FreeLLMAPI

### 🔑 先验证 key，再添加

**先直接调 Agnes API**（绕过 FreeLLMAPI，隔离问题）：

```python
import urllib.request, json
url = "https://apihub.agnes-ai.com/v1/chat/completions"
payload = json.dumps({"model": "agnes-2.0-flash", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}).encode()
req = urllib.request.Request(url, data=payload, headers={"Authorization": "Bearer sk-<key>", "Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=15)
    print("✅ 直连通")
except urllib.error.HTTPError as e:
    print(f"❌ {e.code}: {e.read().decode()[:200]}")
    # 问题在 Agnes 端，不是 FreeLLMAPI
```

直连通才添加到 FreeLLMAPI。不通则问题在 Agnes 端，排查账户/IP/激活状态。

作为 custom OpenAI-compatible provider 添加。**用 REST API 方式，不要走 browser**（更可靠）：

```python
import urllib.request, json

# 1. 先获取 dashboard session token
req = urllib.request.Request(
    "http://localhost:3001/api/auth/login",
    data=json.dumps({"email": "your@email.com", "password": "<密码>"}).encode(),
    headers={"Content-Type": "application/json"},
)
resp = urllib.request.urlopen(req)
token = json.loads(resp.read())["token"]

# 2. 添加自定义 provider（每个模型单独注册）
# 注意：model 必须用小写名！
data = json.dumps({
    "baseUrl": "https://apihub.agnes-ai.com/v1",
    "model": "agnes-2.0-flash",         # 小写！大写会 404
    "displayName": "Agnes-2.0-Flash",    # displayName 随意
    "apiKey": "sk-<完整key>",
    "label": "Agnes AI"
}).encode()

req = urllib.request.Request(
    "http://localhost:3001/api/keys/custom",
    data=data,
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    method="POST"
)
resp = urllib.request.urlopen(req)
result = json.loads(resp.read())
# → {"success": true, "keyId": 24, "modelDbId": 1214, ...}
```

多个模型共享同一个 base URL + API key，只需重复 POST 不同 model 名。FreeLLMAPI 会自动绑定到同一个 key（keyId 相同）。

## 验证调用

直接调 Agnes API：
```bash
curl -s https://apihub.agnes-ai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-<key>" \
  -d '{"model":"agnes-2.0-flash","messages":[{"role":"user","content":"hello"}],"max_tokens":20}'
```

通过 FreeLLMAPI（用 unified API key）：
```bash
curl -s http://localhost:3001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <unified_key>" \
  -d '{"model":"agnes-2.0-flash","messages":[{"role":"user","content":"hello"}],"max_tokens":20}'
```

## 注意事项

- 宣布永久免费（2026年6月1日起），但不确定长期稳定性
- 母公司为 Sapiens AI（自称全球Top 10 AI lab）
- Agnes-2.0-Flash 定位为 Agent 任务模型
- 支持图片生成、视频+音频生成的多模态能力
- 注册需要邮箱验证码，需要用户配合提供

## 🔴 常见故障：所有 key 返回"无效的令牌"

### 现象
从 platform.agnes-ai.com 控制台生成的 sk- 格式 API key，全部返回 401：
```json
{"error":{"code":"","message":"无效的令牌 (request id: ...)","type":"AgnesAI_error"}}
```

多把 key 逐一测试，包括刚生成的新 key，都是同样的错误。

### 已排除的原因
| 可能性 | 结论 |
|---|---|
| Endpoint 错误 | ❌ 已确认 `https://apihub.agnes-ai.com/v1` 正确（文档验证） |
| Auth 格式错误 | ❌ `Authorization: Bearer <key>` 正确 |
| 模型名不对 | ❌ 所有 model 名都试过，认证层就拒绝了（没到模型层） |
| Base URL 不一致 | ❌ `api.agnes-ai.com` 404，其他变体 403/404 |
| Key 格式不匹配 | ❌ 文档中 key 就是 `sk-` 开头 |
| 单把 key 过期 | ❌ 连续生成 4+ 把新 key，全部无效 |

### 根因推测
认证在服务端就被拒绝了，说明是**账户层面的问题**，不是 key 本身：

1. **邮箱未验证** — 注册后需要点验证链接才能激活账户
2. **账户未激活/审核中** — 免费平台可能有人工审核流程
3. **IP 限制** — 账户后台可能设了 IP 白名单
4. **账户余额/配额** — 可能需要先充值或申请免费额度

### 处理建议
- 登入 `platform.agnes-ai.com` → 检查账户状态（已验证/待激活）
- 查看 API Keys 页面 → key 的状态列（active/pending/disabled）
- 检查 Profile/Account 设置 → 邮箱验证状态
- 发邮件到 `support@agnes-ai.com` 询问
- 如果之前能用但最近不行 → 可能是服务端的 token 系统变更
