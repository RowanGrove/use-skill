# FreeLLMAPI Analytics 页面解读指南

## 关键指标区域
- **请求数、成功率、输入/输出 token、平均延迟、预估节省**：页面顶部的主要统计。
- **Requests by provider**：显示各提供商的请求数量（顺序与下面的数字行对应）。
- **Avg latency by provider**：显示各提供商的平均延迟（毫秒）。
- **Per-model breakdown**：详细表格，列出每个模型的请求数、成功率、延迟、token 使用等。
- **Errors by provider**：各提供商的错误计数。
- **Recent errors**：最近的错误列表，包含提供商、错误消息和时间。

## 快速洞察
- 要获取提供商级别的精确数字，可使用 `browser-act --session <name> state` 获取交互元素，或直接观察页面文本。
- 提供商名称和数字通常紧凑显示，如：
  ```
  opencodeopenrouterollamacloudflarezhipusambanovagroqkilo
  085170255340
  ```
  第一行是提供商名连写，第二行是对应的数字（请求数或延迟）。
- 错误计数同样格式。

## 注意事项
- 页面可能因更新而调整选择器，但上述文本区域通常保持稳定。
- 若需要自动化提取具体数字，考虑使用正则表达式解析获取的 markdown 文本。