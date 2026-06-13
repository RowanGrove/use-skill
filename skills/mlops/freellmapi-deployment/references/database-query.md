# FreeLLMAPI 数据库查询

FreeLLMAPI 使用 SQLite，数据库位于：
```
/home/ubuntu/freellmapi/server/data/freeapi.db
```

## 查询已配置平台

```python
import sqlite3
conn = sqlite3.connect('/home/ubuntu/freellmapi/server/data/freeapi.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT platform, enabled FROM api_keys ORDER BY platform")
for r in cur.fetchall():
    print(f"  {r['platform']:15s}  enabled={r['enabled']}")
```

## 查询各平台模型数

```python
cur.execute("SELECT platform, COUNT(*) as cnt FROM models GROUP BY platform ORDER BY cnt DESC")
for r in cur.fetchall():
    print(f"  {r['platform']:15s}  {r['cnt']} models")
```

## api_keys 表结构

| 列名 | 说明 |
|------|------|
| platform | 平台名（groq/openrouter/google 等） |
| label | 标签（用户自定义） |
| encrypted_key | 加密后的 API Key |
| enabled | 是否启用（1=启用） |
| base_url | 自定义 provider 的 URL |

## models 表结构

| 列名 | 说明 |
|------|------|
| platform | 所属平台 |
| model_id | 模型 ID（如 `meta-llama/llama-4-70b-instruct`） |
| display_name | 显示名 |
| intelligence_rank | 智能度排名 |
| speed_rank | 速度排名 |
| context_window | 上下文窗口大小 |
| rpm_limit / rpd_limit | 分钟/天请求限制 |
| tpm_limit / tpd_limit | 分钟/天 token 限制 |
| supports_vision | 是否支持视觉 |
| supports_tools | 是否支持工具调用 |
| enabled | 是否启用 |

## 通过 API 查询可用模型（需要 API Key）

```bash
curl -s http://localhost:3001/v1/models \
  -H "Authorization: Bearer freellmapi-xxxxxxxxxxxxxxxxxxxxxxxx"
```

注意：匿名访问会返回 `Invalid API key`，但路由端点仍可工作。