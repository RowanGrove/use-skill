# FreeLLMAPI 模型优化实测记录

测试日期：2026-06-08

## 路由策略

切换为「Most reliable」（默认是 Custom: reliability 35%, speed 10%, intelligence 55%）

## 禁用模型清单

### Cloudflare (CF) — API 401 认证失败，全部 0%
| 模型 | 请求 | 额度/月 |
|------|------|---------|
| Kimi K2.6 (CF) | 8 | 19.7M |
| GPT-OSS 120B (CF) | 4 | ~45M |
| GLM-4.7 Flash (CF) | 2 | ~45M |
| Llama 4 Scout (CF) | 1 | ~45M |
| Llama 3.3 70B fp8-fast (CF) | 1 | ~45M |
| Qwen3 30B-A3B fp8 (CF) | 1 | ~45M |
| DeepSeek R1 Distill Qwen 32B (CF) | 1 | ~5M |
| Gemma 4 26B-A4B it (CF) | — | ~20M |
| Nemotron 3 120B (CF) | — | ~10M |
| Granite 4.0 H Micro (CF) | — | ~10M |

### Google Gemini — function_call 参数错误
| 模型 | 请求 | 成功率 | 额度/月 |
|------|------|--------|---------|
| Gemini 3.5 Flash | 20 | 40% | 3.0M |
| Gemini 3 Flash Preview | 18 | 22.2% | 3.0M |
| Gemini 3.1 Flash-Lite Preview | 5 | 40% | 3.0M |

### NVIDIA — 超时/中断，0% 成功率
| 模型 | 请求 | 额度/月 |
|------|------|---------|
| GLM-5.1 (NV, slow cold-start) | 7 | 3.0M |
| Llama 3.3 70B (NV) | 2 | 3.0M |
| Qwen3-Coder 480B (NV) | 2 | 3.0M |
| Gemma 4 31B (NV) | 1 | 3.0M |
| Llama 3.1 70B (NV) | 1 | 3.0M |
| Llama 4 Maverick (NV) | 1 | 3.0M |
| Mistral Large 3 675B (NV) | 1 | 3.0M |

### 其他 0%
| 模型 | 额度/月 |
|------|---------|
| GPT-OSS 120B (Cerebras) | 29.6M |
| Llama 4 Scout (Groq) | ~30M |
| GPT-OSS 120B (Groq) | ~6M |

## 额度影响

禁用总量约 **330M** / 总预算 1.6B = 约 **20%**（大部分来自 Cloudflare 的高额度但零成功率的模型）

## 当前活跃 Top 模型

| 排名 | 模型 | 请求 | 成功率 | 延迟 |
|------|------|------|--------|------|
| 1 | Owl Alpha (OR-house) | 9 | 100% | 18.4s |
| 2 | Cogito 2.1 671B (Ollama) | 13 | 84.6% | 20.7s |
| 3 | DeepSeek V4 Flash Free (OpenCode) | 200 | 91% | 7.8s |
| 4 | Kimi K2.6 (HF) | 4 | 75% | 14.6s |
| 5 | DeepSeek V4 Flash (NV) | 32 | 65.6% | 37.7s |
