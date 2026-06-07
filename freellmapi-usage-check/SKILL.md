---
name: freellmapi-usage-check
description: 登录 FreeLLMAPI dashboard，查看用量详情（请求数/token/延迟/节省），分析各模型成功率，智能优化路由，总结后回复。
---

# FreeLLMAPI 用量检查 + 智能优化

每次用户问 FreeLLMAPI 用量/额度/性能时执行此 skill。

## 步骤

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
- 成功率 < 50% 的模型 → 应禁用
- 延迟 > 60s 的模型 → 考虑禁用
- Cloudflare 全部 0% → 应全部禁用
- Google models 低成功率 → 应禁用
- NVIDIA 超时频繁 → 考虑禁用心跳超时的模型

### 4. 切换到 Models 页面并优化

```bash
browser-act --session freellmapi-optimize browser open <browser_id> http://localhost:3001/models/chat
```

优化操作：
1. **切换路由策略**：点击「Most reliable」按钮
2. **手动禁用失败模型**：找到成功率 < 50% 的模型 toggle 开关，逐个点击禁用
3. **保存**：点击 Save changes 按钮

### 5. 关闭 session

```bash
browser-act session close freellmapi-usage
browser-act session close freellmapi-optimize
```

### 6. 回复用户

用中文回复，包含：
- 当前用量概览（总量、token、节省金额）
- 优化操作总结（切换了什么策略、禁用了哪些模型、释放了多少额度）
- 优化后预期效果

不需要冗余解释，直接给出数据 + 操作结果。
