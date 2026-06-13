# llmwebtoken 使用情况查询指南

在 FreeLLMAPI 中，llmwebtoken 并非一个独立的文件或环境变量，而是指系统中使用的统一 API 令牌及其使用情况的查询方式。

## 令牌说明

FreeLLMAPI 使用一个统一的承载令牌（Bearer Token）对外提供 OpenAI 兼容的 `/v1` 接口。此令牌在首次启动时生成并存储在加密的数据库中。

令牌格式：`freellmapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## 查询 token 使用情况

虽然没有名为 `llmwebtoken` 的特定命令或文件，但可以通过以下方式查询 token 使用情况：

### 1. Web UI 仪表板
- 访问 `http://<服务器IP>:3001`
- 登录后查看仪表板中的使用统计
- 包含总使用量、按供应商分布、趋势图等

### 2. 分析 API（需要认证）
获取仪表板访问令牌：
```bash
curl -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"your-password"}' \
  -s | jq -r '.token'
```

然后查询各种使用情况：
- 汇总使用量（24h）: `/api/analytics/summary?range=24h`
- 按模型分布: `/api/analytics/by-model?range=24h`
- 按平台分布: `/api/analytics/by-platform?range=24h`
- 时间序列: `/api/analytics/timeline?range=24h`

### 3. 直接数据库查询（高级）
使用情况存储在 `rate_limit_usage` 表中：
```bash
# 查询今日总使用量
sqlite3 /home/ubuntu/freellmapi/server/data/freeapi.db \
  "SELECT SUM(input_tokens + output_tokens) as total_tokens_today \
   FROM rate_limit_usage \
   WHERE datetime(created_at_ms/1000, 'unixepoch', '+8 hours') >= date('now', 'start of day');"

# 查询按供应商分布
sqlite3 /home/ubuntu/freellmapi/server/data/freeapi.db \
  "SELECT platform, \
          SUM(input_tokens) as prompt_tokens, \
          SUM(output_tokens) as completion_tokens, \
          SUM(input_tokens + output_tokens) as total_tokens \
   FROM rate_limit_usage \
   WHERE datetime(created_at_ms/1000, 'unixepoch', '+8 hours') >= date('now', 'start of day') \
   GROUP BY platform \
   ORDER BY total_tokens DESC;"
```

## 常见问题

**Q: 为什么找不到 llmwebtoken 文件？**
A: llmwebtoken 不是一个实际的文件名，而是用户可能误解的术语。实际的令牌存储在加密数据库中，使用情况通过上述方式查询。

**Q: 如何获取我的统一 API 令牌？**
A: 令牌在首次启动 FreeLLMAPI 时显示在日志中，可通过 `sudo journalctl -u freellmapi` 查看。如果丢失，删除 `server/data/freeapi.db` 后重启会重新生成新令牌（但会丢失所有已配置的提供商 Key）。

**Q: 令牌使用情况多久更新一次？**
A: 每个请求完成后立即记录到数据库中，查询时即可看到最新情况。