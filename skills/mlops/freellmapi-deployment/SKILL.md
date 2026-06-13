---
name: freellmapi-deployment
description: "Deploy and integrate FreeLLMAPI as a custom provider for Hermes Agent on Linux — install, build client, configure systemd, integrate with Hermes, and known pitfalls. Tested on Tencent Cloud Ubuntu (China mainland) with Mihomo proxy."
version: 2.1.0
author: Milo
platforms: [linux]
---

# FreeLLMAPI 部署接入指南（Linux 版）

> **部署文档仓库**: `https://github.com/RowanGrove/freellmapi-backup.git`
> 包含手写 README（新装部署 + 恢复二合一）、部署清单、提供商注册指南。
> 新主机部署时优先参考该仓库的 `README.md` 和 `docs/` 目录。

## 快速入口

| 文档 | 用途 |
|------|------|
| `references/new-host-deployment-checklist.md` | 新主机 Hermes 逐步执行清单 |
| `README.md`（备份仓库） | 完整部署指南 + 提供商注册 + 踩坑 |
| `docs/provider-setup.md`（备份仓库） | 各提供商注册地址 & Key 格式 |

## 架构

```
Hermes Agent
  ↓ HTTP (custom provider, /v1/chat/completions)
FreeLLMAPI (localhost:3001)
  ↓ HTTP(s) 直连 或 走代理
各 LLM 提供商 API (Groq, OpenRouter, Google Gemini...)
```

## 部署步骤

### 1. 克隆 & 安装依赖

```bash
cd ~
git clone https://github.com/tashfeenahmed/freellmapi.git
cd freellmapi
npm install
```

### 2. 构建前端（Web UI 管理面板需要）

npm workspaces 下 @types/react-dom 和 @vitejs/plugin-react 经常装不到正确位置，可以一键运行构建脚本：

```bash
# 从项目根目录执行
bash scripts/build-client.sh
```

或者手动操作：

```bash
mkdir -p client/node_modules/@types/react-dom
curl -sL "https://registry.npmjs.org/@types/react-dom/-/react-dom-19.2.3.tgz" | tar xz --strip-components=1 -C client/node_modules/@types/react-dom

mkdir -p client/node_modules/@vitejs/plugin-react
curl -sL "https://registry.npmjs.org/@vitejs/plugin-react/-/plugin-react-6.0.2.tgz" | tar xz --strip-components=1 -C client/node_modules/@vitejs/plugin-react

cd client && npm run build && cd ..
```
```

### 3. 配置 .env

```bash
ENCRYPTION_KEY=$(node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")
cat > .env << EOF
ENCRYPTION_KEY=$ENCRYPTION_KEY
PORT=3001
EOF
```

### 4. Systemd 服务（开机自启 + 挂后自动重启）

**国内服务器需要加代理**，`After=mihomo.service` 确保代理先启动：

```bash
sudo tee /etc/systemd/system/freellmapi.service > /dev/null << 'EOF'
[Unit]
Description=FreeLLMAPI
After=network.target mihomo.service
Wants=mihomo.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/freellmapi/server
ExecStart=/usr/bin/npx tsx src/index.ts
Environment=PORT=3001
Environment=HTTP_PROXY=http://127.0.0.1:7890
Environment=HTTPS_PROXY=http://127.0.0.1:7890
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now freellmapi
```

海外服务器去掉 `HTTP_PROXY`/`HTTPS_PROXY` 和 `After=mihomo.service` 行。

验证启动：

```bash
sudo journalctl -u freellmapi --no-pager | tail -10
# 应该看到: Server running on http://[::]:3001
```

### 5. Hermes 集成

config.yaml 是受保护文件，必须用 `hermes config set` 逐条写入：

```bash
hermes config set providers.freellmapi.name "FreeLLM API"
hermes config set providers.freellmapi.base_url "http://127.0.0.1:3001/v1"
hermes config set providers.freellmapi.api_key "freellmapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
hermes config set providers.freellmapi.model "auto"
hermes config set providers.freellmapi.discover_models true
```

注意：
- `custom_providers` 也可设但没必要：`hermes config set custom_providers ""`（或干脆不管）
- Web UI 里显示自定义 provider 需要加 `custom_providers` 数组，但 CLI 不需要

验证配置：

```bash
grep -A6 'freellmapi' ~/.hermes/config.yaml
```

### 6. 重启 Hermes 网关

```bash
hermes gateway restart
```

### 7. 切换模型

```bash
hermes model           # 交互式选 custom:freellmapi -> 选具体模型
# 或在会话中用 /model 切换
```

## ⚠️ 安全警示：密钥保密

- **`freellmapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`** 只是占位符
- 真实的 API Key 在首次启动日志里，**绝对不要提交到任何仓库**
- 复制 key 时只复制到配置文件中，用完即清空
- 如果 key 泄露，立即删除 `server/data/freeapi.db` 重启重置
- 配置 Hermes 时：`export KEY=实际key && hermes config set providers.freellmapi.api_key "$KEY" && unset KEY`

## 获取 API Key

```
Your unified API key: freellmapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- 从 `sudo journalctl -u freellmapi` 或首次启动日志里找
- 如果丢失：删除 `server/data/freeapi.db` 后重启即可重新生成新 key

## Web UI 管理面板

地址：`http://<服务器IP>:3001`

进去后添加各提供商的 API Key（Groq、OpenRouter、Google Gemini 等），FreeLLMAPI 才能路由请求。

### 各提供商 Key 格式

| 提供商 | Key 格式 | 说明 |
|--------|----------|------|
| Groq | `gsk_xxx...` | 直接填 API Key |
| OpenRouter | `sk-or-xxx...` | 直接填 API Key |
| Google Gemini | `AIza...` | 直接填 API Key |
| **Cloudflare** | **`account_id:api_token`** | **必须用冒号拼接 Account ID 和 Token！**  |
| NVIDIA | `nvapi-xxx...` | 直接填 API Key |
| OpenCode | `oc_xxx...` | 直接填 API Key |

## Hermes Studio 集成（让模型出现在 Studio 下拉框）

除了 `hermes config set` 配 `providers.freellmapi` 外，还需要在 `~/.hermes/config.yaml` 里配 `custom_providers` **YAML 数组格式**，Hermes Studio 才识别：

```yaml
custom_providers:
  - name: "FreeLLM API"
    base_url: "http://127.0.0.1:3001/v1"
    api_key: "freellmapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    model: "auto"
    discover_models: true
```

注意：
- `hermes config set custom_providers "..."` 会存成**纯字符串**，Studio 不认
- 必须用 `sed` 直接写 YAML 数组格式到 `~/.hermes/config.yaml`
- 改完后还需要更新 Hermes Studio 的 provider 缓存：`~/.hermes-web-ui/cache/provider-model-catalog.json`
- 最后重启网关让 Studio 重新加载

## 国内服务器 Groq/Cloudflare 代理修复

国内服务器上，Node.js 原生 `fetch()` **不认 `HTTP_PROXY` 环境变量**，导致健康检查请求被墙拦截。

**症状：** Groq Key 状态永远显示 invalid，即使 key 本身是好的。

**修复方法：**
1. 在 `freellmapi/server/` 下装 `undici` 包
2. 创建代理预加载脚本 `proxy-preload.cjs`（用 undici 的 `ProxyAgent` 设置全局代理）
3. systemd 服务加 `NODE_OPTIONS="--require /path/to/proxy-preload.cjs"`
4. 重启服务

详见同目录下的 `proxy-preload.cjs` 文件。修改 systemd 服务：

```ini
[Service]
Environment="NODE_PATH=/home/ubuntu/freellmapi/node_modules"
Environment="NODE_OPTIONS=--require /home/ubuntu/freellmapi/server/proxy-preload.cjs"
```

## 数据备份与灾难恢复

> 备份脚本已更新：**手动编写的 README.md 不会被覆盖**（备份脚本改为生成 `backup-status.md`）。
> 路径: `~/.hermes/skills/mlops/freellmapi-deployment/scripts/freellmapi_backup.sh`

> 如果 `~/.hermes/scripts/freellmapi_backup.sh` 是旧版，手动复制：
> ```bash
> cp ~/.hermes/skills/mlops/freellmapi-deployment/scripts/freellmapi_backup.sh ~/.hermes/scripts/
> ```

配置好所有提供商的 API Key 并添加了 100+ 个模型后，一旦服务器故障会非常痛苦。建议对 FreeLLM API 的关键数据进行**每日自动备份到私有 Git 仓库**。

### 需要备份的文件（缺一不可）

| 文件 | 内容 | 重要性 |
|------|------|--------|
| `server/data/freeapi.db` | 所有 API Keys（加密存储）、模型目录、请求统计 | ⭐⭐⭐⭐⭐ |
| `.env` | 加密密钥（用于解密 db 中的 API Keys） | ⭐⭐⭐⭐⭐ |
| `~/.hermes/config.yaml` | Hermes 的 custom_providers 配置 | ⭐⭐⭐ |

> **⚠️ 重要原则：备份文件不可做任何过滤/脱敏！**
> API Keys 在 db 中已加密存储，`.env` 中的加密密钥是恢复所必需的。如果脱敏掉这些信息，备份就失去了意义——服务器炸了之后无法恢复。

#### 备份脚本

```bash
#!/bin/bash
# FreeLLM API 配置备份脚本 — 注意：不会覆盖手写 README.md（改生成 backup-status.md）
set -e

REPO_DIR="$HOME/freellmapi_backup"
LOG_DIR="$HOME/.freellmapi_backup"
LOG_FILE="$LOG_DIR/backup.log"
GITHUB_REPO="https://github.com/RowanGrove/freellmapi-backup.git"

mkdir -p "$LOG_DIR"
exec > "$LOG_FILE" 2>&1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "========== FreeLLM API 备份开始 =========="
mkdir -p "$REPO_DIR"

# 1-3. 核心文件（不做任何过滤！）
for f in "freeapi.db" ".env" "hermes_config.yaml"; do
  src=""
  case "$f" in
    freeapi.db) src="/home/ubuntu/freellmapi/server/data/freeapi.db" ;;
    .env)       src="/home/ubuntu/freellmapi/.env" ;;
    hermes_config.yaml) src="$HOME/.hermes/config.yaml" ;;
  esac
  if [ -f "$src" ]; then
    cp "$src" "$REPO_DIR/$f"
    log "✅ $f 备份完成"
  else
    log "❌ $f 不存在！"
    cat "$LOG_FILE" >&2
    exit 1
  fi
done

# 4. 备份部署文档（skill）
SKILL_SRC="/home/ubuntu/.hermes/skills/mlops/freellmapi-deployment"
SKILL_DST="$REPO_DIR/skills/freellmapi-deployment"
if [ -d "$SKILL_SRC" ]; then
  mkdir -p "$REPO_DIR/skills"
  rm -rf "$SKILL_DST"
  cp -r "$SKILL_SRC" "$SKILL_DST"
  log "✅ 部署文档已备份"
fi

# 5. 生成 backup-status.md（不覆盖手写 README.md）
status_tmp=$(mktemp)
platform_list=$(sqlite3 "/home/ubuntu/freellmapi/server/data/freeapi.db" \
    "SELECT platform FROM api_keys WHERE enabled=1 ORDER BY platform;" 2>/dev/null \
    | sed 's/^/- /')
cat > "$status_tmp" << REOF
# 备份状态
> 自动生成 | 最后更新: $(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M:%S') 北京时间

## 当前已配置平台

${platform_list:-（暂无）}

*自动生成于 $(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M')*
REOF
if [ -f "$REPO_DIR/backup-status.md" ]; then
  if ! diff -q "$status_tmp" "$REPO_DIR/backup-status.md" > /dev/null 2>&1; then
    cp "$status_tmp" "$REPO_DIR/backup-status.md"
    log "✅ backup-status.md 已更新"
  else
    log "ℹ️ 无变更"
  fi
else
  cp "$status_tmp" "$REPO_DIR/backup-status.md"
  log "✅ backup-status.md 已创建"
fi
rm -f "$status_tmp"

# 6-7. Git
cd "$REPO_DIR"
if [ ! -d ".git" ]; then
  git init && git remote add origin "$GITHUB_REPO"
  git config user.name "RowanGrove"
  git config user.email "your@email.com"
  git branch -M main
fi
if ! git diff --quiet HEAD -- 2>/dev/null; then
  git add .
  git commit -m "📦 自动备份: $(date '+%Y-%m-%d %H:%M:%S')"
  git push -u origin main && log "✅ 推送成功" || { log "❌ 推送失败"; cat "$LOG_FILE" >&2; exit 1; }
else
  log "ℹ️ 无新变更"
fi

log "========== 备份完成 =========="
```

### Hermes cron 配置（watchdog 模式）

使用 `no_agent=true` 的脚本 cron，实现 **成功静默、失败通知** 的模式：

```
cronjob(action='create', name='FreeLLM API 自动备份', no_agent=true,
        schedule='0 1 * * *', script='freellmapi_backup.sh')
```

调度原理：
- `no_agent=true`：跳过 LLM，直接运行脚本，不消耗 token
- `schedule='0 1 * * *'`：每天北京时间凌晨 1 点
- 脚本成功时 stdout 为空 → 不发送任何消息（不打扰用户）
- 脚本失败时 stdout 非空 → 自动推送错误日志到 Telegram

### 恢复步骤

```bash
# 拉取备份
git clone https://github.com/RowanGrove/freellmapi-backup.git

# 放回对应位置
cp freeapi.db         ~/freellmapi/server/data/
cp .env               ~/freellmapi/
cp hermes_config.yaml ~/.hermes/

# 重启服务
sudo systemctl restart freellmapi
hermes gateway restart
```

> **注意**：`.env` 中的 `ENCRYPTION_KEY` 必须与备份当时的一致，否则无法解密 `freeapi.db` 中的 API Keys。因此 `.env` 是整个备份中最重要的文件，丢失它等于丢失所有 API Key。

## 查询 token 使用情况

FreeLLMAPI 中 token 使用情况的查询方式（当用户问"llmwebtoken 使用情况"时，实际指的是这个），详见 `references/llmwebtoken-usage.md`。

访问路径：`/api/analytics/summary?range=24h`（需 Dashboard 登录认证，非统一 API Key）。

## 新主机部署（快速开局）

如果要在新服务器上部署 FreeLLMAPI，按以下顺序参考：

1. **`references/new-host-deployment-checklist.md`** — Hermes 可直接逐条执行的部署清单
2. **备份仓库 `https://github.com/RowanGrove/freellmapi-backup.git`** — 手写 README 含完整的部署 + 恢复指南
3. **备份仓库 `docs/provider-setup.md`** — 各提供商注册地址、Key 格式、注意事项

新主机部署完后，复制本 skill 的备份脚本到 `~/.hermes/scripts/` 并设置 cron。

## 踩坑记录

| # | 坑 | 原因 | 解决 |
|---|-----|------|------|
| 1 | tsc 编译失败 | npm workspaces 下 types 没装到对应位置 | 跳过编译，直接 `npx tsx src/index.ts` 启动 |
| 2 | npm build 不跑 | npm workspaces 降级问题 | 从根目录 `npm install`，不要改 lockfile |
| 3 | 端口被 Hermes 抢占 | Hermes 可能在环境里设了 `PORT=8748` | 启动时显式 `PORT=3001` |
| 4 | Web UI 报 ENOENT client/dist/index.html | 前端没构建 | 手动下载 @types/react-dom、@vitejs/plugin-react 后 `npm run build` |
| 5 | config.yaml 写不进去 | Hermes 保护了该文件 | 只能用 `hermes config set section.key value` |
| 6 | hermes config set custom_providers 存成字符串 | CLI 把值当纯字符串 | 删掉该 key，用 `providers` 字典就够 |
| 7 | FreeLLMAPI 能启动但路由报 "All models exhausted" | 没配任何提供商的 API Key | 去 Web UI 添加 Key（Groq、OpenRouter 等） |
| 8 | EADDRINUSE port 3001 | 旧进程残留 | `fuser -k 3001/tcp` 或 `sudo systemctl restart freellmapi` |
| 9 | 国内服务器连不上境外 API | Telegram/OpenRouter 等被墙 | systemd 服务加 `HTTP_PROXY=http://127.0.0.1:7890`，依赖 `mihomo.service` |
| 10 | Groq Key 总是显示 invalid | Node.js `fetch()` 不认 `HTTP_PROXY`，健康检查没走代理被墙 | 装 `undici` + 写 `proxy-preload.cjs` + systemd 加 `NODE_OPTIONS="--require .../proxy-preload.cjs"` |
| 11 | Hermes Studio 下拉没有 FreeLLM API | `custom_providers` 没配成 YAML 数组 | 用 `sed` 写入 YAML 数组格式，重启网关 |
| 12 | Cloudflare Workers AI 始终 401 | 原因是 **权限模板选错**，不是格式问题。旧 token 可能是 Custom Token 模板创建的，权限是 `Account.Access:Keys`（只能管理 API tokens），缺少 Workers AI 权限。即使格式正确 (`account_id:token`) 也会 401。| 必须用 **Workers AI 模板** 创建 token，模板自动给 `Workers AI:Read` + `Workers AI:Edit` 权限。Custom Token 模板无论怎么选 permission 分组都不对。详见 `skill_view(name='freellmapi-usage-check', file_path='references/cloudflare-workers-ai-setup.md')` |
| 13 | Embedding 请求报 "no usable keys" | FreeLLM API 默认不支持 embedding 模型 | 如需 embedding（如 mem0），改用本地嵌入器（fastembed/huggingface）。详见 `references/local-embedding-setup.md` — 含完整代码、factory 注入、配置示例 |
| 14 | Hermes 报 400 model_not_found | 顶层 model 字段指定了当前 provider 目录里没有的模型名。两套配置容易混：default→deepseek 直连（model: deepseek-v4-flash），michael→freellmapi（model: auto）。如果 provider=freellmapi 但 model=deepseek-v4-flash，FreeLLM API 路由找不到该模型名就会报 400。 | 确认当前 profile 的 provider 用的是哪个：provider=deepseek 就配 deepseek 的模型名，provider=freellmapi 就设 model: auto 让路由自己选。用 `hermes config set model auto` 改。两个 profile 分别检查。 |

## 推荐注册的提供商（按优先级）

### 简单快速配置平台（无需额外代理或特殊设置）
- **Kilo Gateway** – 无需 API Key，只要打开开关即可使用。适合国内网络，免费且不限速。
- **Pollinations** – 同样匿名，无需密钥，适合图像生成等非敏感场景。
- **LLM7** – 匿名使用，默认每小时 100 次请求，直接在 UI 勾选即可。
- **OpenCode Zen** – 免费注册后获得一次性 key，使用步骤与其他平台相同。

这些平台在 FreeLLM API 中已经默认列出，只要在 **Keys** 页面点击 **Add key** 并留空（或粘贴免费 key）即可完成配置，无需额外的网络代理或环境变量。

### ⭐⭐⭐ 必配（额度大方、速度快）

| 提供商 | 速度 | 注册地址 | 免费额度 |
|--------|------|----------|----------|
| Groq | ~0.3s | https://console.groq.com/keys | 很充足 |
| Cerebras | ~0.3s | https://cloud.cerebras.ai | 很充足（邮箱即可注册）|
| OpenRouter | ~3s | https://openrouter.ai/keys | 有限但模型多 |
| Cohere | ~2s | https://dashboard.cohere.com/api-keys | 有免费层，Command R 系列强 |

### ⭐⭐ 值得配（额度一般或有条件）

| 提供商 | 速度 | 注册地址 | 免费额度 |
|--------|------|----------|----------|
| Google Gemini | ~2s | https://aistudio.google.com/apikey | 有免费层 |
| NVIDIA NIM | ~3s | https://developer.nvidia.com/build | 有免费积分 |
| HuggingFace Router | ~5s | https://huggingface.co/settings/tokens | $0.10/月路由额度 |
| Ollama Cloud | 5-90s | https://ollama.com/pricing | 免费（但慢，有会话时长限制）|
| Kilo Gateway | ~3s | https://api.kilo.ai | 完全匿名 200 req/hr，无需 API key |
| Pollinations | ~3s | https://pollinations.ai | 免费匿名，但数据可能用于训练 |
| LLM7 | ~3s | https://api.llm7.io | 匿名 100 req/hr |

### ⭐ 谨慎配

| 提供商 | 速度 | 注册地址 | 说明 |
|--------|------|----------|------|
| GitHub Models | ~2s | https://github.com/settings/tokens | 有限免费，需要 GitHub 账号 + `models` scope 的 PAT |
| Mistral | ~3s | https://console.mistral.ai/api-keys | 免费额度较少 |
| SambaNova | ~5s | https://console.sambanova.ai | 有免费积分 |
| OpenCode Zen | ~3s | https://opencode.ai/auth | 限时免费，需注册 |
| Cloudflare Workers AI | 快 | https://dash.cloudflare.com | 需要 Account ID:Token 格式 |
| Zhipu (智谱) | ~3s | https://bigmodel.cn | 国内可直接访问 |

## 程序化配置 API Keys（无浏览器方案）

### 背景
FreeLLM API 的 Web UI 需要每次登录账号密码（Hermes 的浏览器 session 会话不持久，每次对话都重置）。为避免重复登录，可直接调用 FreeLLM API 的内部 `/api/keys` 接口来配置 Key。

### 前置步骤：获取 Dashboard Token

FreeLLM API 使用邮箱+密码的 session 认证来保护 `/api/keys` 等管理接口。

1. **直接 curl 登录**（先注册账号）：

```bash
curl -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"your-password"}' \
  -s | jq .
```

返回示例：
```json
{
  "token": "72cf061be1ef95c7c12d0965a8ea3da377542c4d8fec49c70eae5060a6d415fd",
  "email": "your@email.com"
}
```

**保存 token**（有效期 30 天）：`DASHBOARD_TOKEN="72cf061be1ef95c7c12d0965a8ea3da377542c4d8fec49c70eae5060a6d415fd"`

2. **初始 setup（仅首次运行时）**：

```bash
curl -X POST http://localhost:3001/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"your-password"}' \
  -s | jq .
```

### 配置 GitHub Models（平台 Keys）

支持的平台列表见 `freellmapi/server/src/routes/keys.ts` 的 `PLATFORMS`：

```
'google', 'groq', 'cerebras', 'sambanova', 'nvidia', 'mistral',
'openrouter', 'github', 'cohere', 'cloudflare', 'zhipu', 'ollama',
'kilo', 'pollinations', 'llm7', 'huggingface', 'opencode', 'custom'
```

**一键添加 GitHub Models**（需要带 `models` scope 的 GitHub PAT）：

```bash
curl -X POST http://localhost:3001/api/keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DASHBOARD_TOKEN" \
  -d '{
    "platform": "github",
    "key": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "label": "GitHub Models (个人用)"
  }' \
  -s | jq .
```

返回示例（HTTP 201）：
```json
{
  "id": 3,
  "platform": "github",
  "label": "GitHub Models (个人用)",
  "maskedKey": "ghp_...xxxx",
  "status": "unknown",
  "enabled": true
}
```

**查看所有已配置 Keys**：

```bash
curl http://localhost:3001/api/keys \
  -H "Authorization: Bearer $DASHBOARD_TOKEN" \
  -s | jq '.[] | {id, platform, label, maskedKey, status, enabled}'
```

### 配置自定义 OpenAI 兼容提供商 (Custom)

用于接入本地 ollama、vLLM、LM Studio 等服务：

```bash
curl -X POST http://localhost:3001/api/keys/custom \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DASHBOARD_TOKEN" \
  -d '{
    "baseUrl": "http://127.0.0.1:11434/v1",
    "model": "llama3:8b",
    "displayName": "Llama3 8B (本地)",
    "apiKey": "no-key",
    "label": "Ollama 本地"
  }' \
  -s | jq .
```

注意：`/api/keys/custom` 对每个 `baseUrl` 会自动创建或更新 `platform='custom'` 的 Key，并自动注册模型到数据库，同时加入 fallback chain。

### 删除 Key

```bash
curl -X DELETE http://localhost:3001/api/keys/3 \
  -H "Authorization: Bearer $DASHBOARD_TOKEN" \
  -s | jq .
```

### 健康检查

批量验证上游 provider 是否可达：

```bash
# 检查单个 provider（id 在 /api/keys 列表里）
curl -s -X POST http://localhost:3001/api/health/check/5 \
  -H "Authorization: Bearer $DASHBOARD_TOKEN" | jq .

# 检查全部
curl -s -X POST http://localhost:3001/api/health/check-all \
  -H "Authorization: Bearer $DASHBOARD_TOKEN" | jq '.result'
```

返回 `status: "healthy"` 表示该 provider 当前可达。批量检查 + 重启用工作流详见 `references/provider-health-check.md`。

### 切换启用状态

```bash
# 禁用某个平台的所有 Keys
curl -X PATCH http://localhost:3001/api/keys/platform/groq \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DASHBOARD_TOKEN" \
  -d '{"enabled": false}' \
  -s | jq .

# 更新某个 Key 的 label
curl -X PATCH http://localhost:3001/api/keys/3 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DASHBOARD_TOKEN" \
  -d '{"label": "新的标签名"}' \
  -s | jq .
```

### Session过期处理

Token 有效期 30 天。过期后重新登录获取新 token：

```bash
curl -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"your-password"}' \
  -s | jq -r '.token'
```

### pitfall

**高处断点危害大：任务中途切换会导致上下文丢失**。本技能的配置流程涉及多个步骤（选平台、注册账号、取 Key、curl 配置）。在对话中切换去执行不相关的代码（如 Unison 脚本），然后再返回时需要重读文档、重新收集凭证。**最佳实践**：一个任务（如配置 GitHub Models）在拿到所有凭证后一次性做到底，不要中途分心。

## Dashboard 密码丢失恢复

如果忘了 Dashboard 登录密码，**不需要删除整个 freeapi.db**（那样会丢掉所有已配置的 API Key）。

只需清空 users 和 sessions 表，然后重新 setup：

```bash
cd ~/freellmapi/server/data
sqlite3 freeapi.db "DELETE FROM sessions; DELETE FROM users;"

# 重新创建账号（密码至少8位）
curl -s -X POST http://localhost:3001/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"新的密码"}'
```

> 此操作不影响任何已配置的 API Key 和模型路由。

恢复后建议用 browser-act 持久化登录 session，避免每次对话重新登录。已有 browser ID `100287258835473970` 已登录 FreeLLMAPI，可直接复用。
