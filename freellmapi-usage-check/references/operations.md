# FreeLLMAPI 运维操作手册

## Dashboard 登录

### 浏览器登录
```bash
browser-act --session <name> browser open <browser_id> http://localhost:3001
sleep 2
browser-act --session <name> state
# → 找到 email [3], password [5], sign in [6]
browser-act --session <name> input 3 "your@email.com"
browser-act --session <name> input 5 "<password>"
browser-act --session <name> click 6
```

### click 后页面无响应（Snapshot element is missing）
SPA 重新渲染导致 ref ID 失效。直接再点一次：
```bash
browser-act --session <name> click 6
sleep 2
# 检查是否已登录到 dashboard
browser-act --session <name> state
# 出现 Sign out 按钮即为成功
```

## 密码修改

FreeLLMAPI 没有改密码 API，只能删除用户后重新 setup：

```bash
# 1. 删除旧用户
sqlite3 ~/freellmapi/server/data/freeapi.db \
  "DELETE FROM sessions; DELETE FROM users;"

# 2. 创建新用户（密码 ≥ 8 位）
curl -s -X POST http://localhost:3001/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"<新密码>"}'

# 3. 浏览器重新登录持久化 cookie
browser-act --session <name> browser open <browser_id> http://localhost:3001
# ... 输入新密码登录 ...
```

## 登录锁处理

连续5次密码错误会触发 15 分钟锁（`Too many failed attempts. Try again later.`）。

锁计数器在内存中（Map），重启服务即清空：

```bash
sudo systemctl restart freellmapi.service
sleep 3
# 确认服务恢复
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001
```

## Cloudflare 模型全部 0%

报 `Cloudflare API error 401: Authentication error`，不是额度问题。

key 虽然配了且显示 healthy，但实际 API 不认。可能原因：
- API token 缺少 **Workers AI** 权限
- 需要 Account ID + API Token 组合

解决方案：去 Cloudflare dashboard 检查 API token 权限，重新配 key。

## 模型禁用原则

| 条件 | 操作 |
|------|------|
| obs > 0 且 success = 0% | 禁用（已确认失败） |
| obs > 0 且 success < 50% | 禁用 |
| obs = 0（从未调用） | 不动，让 Most reliable 自动处理 |
