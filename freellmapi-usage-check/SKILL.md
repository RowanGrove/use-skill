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
- **有数据（obs > 0）** 且成功率 < 50% 的模型 → 应手动禁用
- **有数据（obs > 0）** 且成功率 = 0% 的模型 → 应手动禁用（已确认失败）
- 延迟 > 60s 的模型 → 考虑禁用
- **无数据（obs = 0）的模型不要禁用** — 可能从未被调用过，路由策略会自动处理
  
特别注意：
- Cloudflare 模型如果有数据且 = 0% 则禁用（API 401 认证问题）
- Google models 低成功率且 obs > 0 → 禁用
- NVIDIA 超时频繁 → 禁用心跳超时的模型
- 区分「0 obs（从未调用）」和「0%（调用但全失败）」

### 4. 切换到 Models 页面并优化

```bash
browser-act --session freellmapi-optimize browser open <browser_id> http://localhost:3001/models/chat
sleep 2
browser-act --session freellmapi-optimize state
```

**先切换路由策略**：找到「Most reliable」按钮（通常是 #16），点击它。

**再手动禁用失败模型**（逐个来，每点一个等0.5秒）：

注意：99个模型分布在约 **5-6屏** scroll 范围内，需要多次 scroll down 才能看到全部。

```bash
# 读取当前可见模型 → 找到 aria-checked=true 但成功率<50%的 toggle → 点击禁用
browser-act --session freellmapi-optimize click <ref_id>

# 滚动查看下一批模型
browser-act --session freellmapi-optimize scroll down
sleep 1
browser-act --session freellmapi-optimize state
```

需要禁用的模型规则：
- **Cloudflare (CF) 模型**：API 401 认证失败，全部 0% → 全部禁用
- **Google gemini-3 系列**：function_call 参数错误，成功率 <50% → 禁用
- **NVIDIA 0% 模型**：GLM-5.1、Gemma 4 31B NV、Llama 各版本 NV（数据量小的）→ 禁用
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
