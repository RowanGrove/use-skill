# FreeLLMAPI Provider 健康检查与启停

## 场景

上游 LLM 提供商故障恢复后，需要批量检查哪些 provider 又通了，把他们重新启用。

## 流程

### 1. 登录面板拿 token

```python
import json, urllib.request
BASE = "http://<panel-ip>:3001"
data = json.dumps({"email": "...", "password": "..."}).encode()
req = urllib.request.Request(f"{BASE}/api/auth/login", data=data,
    headers={"Content-Type":"application/json"})
token = json.loads(urllib.request.urlopen(req).read())["token"]
```

### 2. 查看所有 provider 状态

```python
req = urllib.request.Request(f"{BASE}/api/keys",
    headers={"Authorization": f"Bearer {token}"})
keys = json.loads(urllib.request.urlopen(req).read())
for k in keys:
    print(k.get('platform'), k.get('enabled'), k.get('obs', 0), k.get('label',''))
```

### 3. 检查单个 provider 是否健康

```python
req = urllib.request.Request(f"{BASE}/api/health/check/{id}",
    method="POST",
    headers={"Authorization": f"Bearer {token}"})
resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
print(resp.get('status'))  # 'healthy' 或错误信息
```

支持 POST `/api/health/check-all` 一次性全部检查，返回每个 provider 的状态字典。

### 4. 启用 / 禁用

```python
payload = json.dumps({"enabled": True}).encode()
req = urllib.request.Request(
    f"{BASE}/api/keys/platform/{platform_name}",
    data=payload, method="PATCH",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
urllib.request.urlopen(req)
```

`platform_name` 取小写单词：`groq`、`opencode`、`nvidia`、`cloudflare`、`google`、`cerebras`、`sambanova` 等。

### 5. 更新 custom provider 的 API key

注意：`PATCH /api/keys/:id` **只接受 `enabled` 和 `label` 字段**，不能直接更新 apiKey。

要更新 custom provider 的 key，必须先 DELETE 再 POST：

```python
# 删除旧 key
req_del = urllib.request.Request(f"{BASE}/api/keys/{id}",
    method="DELETE",
    headers={"Authorization": f"Bearer {token}"})
urllib.request.urlopen(req_del)

# 创建新 key（displayName 控制面板显示名，不是 label）
payload = json.dumps({
    "baseUrl": "https://provider-url/v1",
    "model": "auto",
    "displayName": "显示名称",
    "apiKey": "sk-new-key-here"
}).encode()
req_new = urllib.request.Request(f"{BASE}/api/keys/custom",
    data=payload, method="POST",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
result = json.loads(urllib.request.urlopen(req_new).read())
```

**注意**：`POST /api/keys/custom` 的参数字段是 `displayName`（面板显示名），不是 `label`。如果漏掉或传错，面板会显示默认名 "Custom"。

### 6. 验证

```python
req = urllib.request.Request(f"{BASE}/api/keys",
    headers={"Authorization": f"Bearer {token}"})
keys = json.loads(urllib.request.urlopen(req).read())
enabled = [k for k in keys if k.get('enabled')]
disabled = [k for k in keys if not k.get('enabled')]
print(f"启用: {len(enabled)}, 禁用: {len(disabled)}")
```

### 7. 在面板外直接测试 key 合法性

在把 key 写入面板之前，先直接 curl 提供商的 API 确认 key 有效：

```bash
curl -s -X POST https://provider-url/v1/chat/completions \
  -H "Authorization: Bearer <key>" \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```

如果返回 `{"error":...}` 说明 key 本身就有问题，不用写入面板了。

## 典型场景：批量重开

当某个区域网络恢复，之前因超时/墙禁掉的上游 provider 全部变 healthy 时：

1. POST `/api/health/check/:id` 逐个验证（或一次 `/api/health/check-all`）
2. 对 status==healthy 的，PATCH `/api/keys/platform/:platform` `{"enabled":true}`
3. 最后 GET `/api/keys` 确认状态

## 典型场景：重新注册后更新 custom provider key

1. 从 provider 后台复制新 key
2. 直接 curl 测试 key 合法性（见上方第 7 步）
3. 如果有效：DELETE 旧的 custom key → POST `/api/keys/custom` 带新 key
4. POST `/api/health/check/:id` 验证新的 key 状态为 healthy
