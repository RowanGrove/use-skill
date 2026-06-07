---
name: freellmapi-deployment
description: "Deploy and integrate FreeLLMAPI as a custom provider for Hermes Agent on Linux — install, build client, configure systemd, integrate with Hermes, and known pitfalls. Tested on Tencent Cloud Ubuntu (China mainland) with Mihomo proxy."
version: 2.0.0
author: Milo
platforms: [linux]
---

# FreeLLMAPI 部署接入指南（Linux 版）

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

npm workspaces 下 @types/react-dom 和 @vitejs/plugin-react 经常装不到正确位置，需要手动下载：

```bash
# 从 repo 根目录执行
mkdir -p client/node_modules/@types/react-dom
curl -sL "https://registry.npmjs.org/@types/react-dom/-/react-dom-19.2.3.tgz" | tar xz --strip-components=1 -C client/node_modules/@types/react-dom

mkdir -p client/node_modules/@vitejs/plugin-react
curl -sL "https://registry.npmjs.org/@vitejs/plugin-react/-/plugin-react-6.0.2.tgz" | tar xz --strip-components=1 -C client/node_modules/@vitejs/plugin-react

cd client && npm run build && cd ..
# 构建成功标志：dist/index.html 生成
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

## 获取 API Key

FreeLLMAPI 首次启动打印的才是 API Key，**不是 `.env` 里的 `ENCRYPTION_KEY`**：

```
Your unified API key: freellmapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- 从 `sudo journalctl -u freellmapi` 或首次启动日志里找
- 如果丢失：删除 `server/data/freeapi.db` 后重启即可重新生成新 key

## Web UI 管理面板

地址：`http://<服务器IP>:3001`

进去后添加各提供商的 API Key（Groq、OpenRouter、Google Gemini 等），FreeLLMAPI 才能路由请求。

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

## 推荐注册的提供商

| 推荐度 | 提供商 | 速度 | 注册地址 |
|--------|--------|------|----------|
| ⭐⭐⭐ | Groq | ~0.3s | https://console.groq.com/keys |
| ⭐⭐⭐ | OpenRouter | ~3s | https://openrouter.ai/keys |
| ⭐⭐ | Google Gemini | ~2s | https://aistudio.google.com/apikey |
| ⭐⭐ | Cerebras | ~0.3s | https://cloud.cerebras.ai |
| ⭐ | GitHub Models | ~2s | https://github.com/settings/tokens |
| ⭐ | Mistral | ~3s | https://console.mistral.ai/api-keys |
