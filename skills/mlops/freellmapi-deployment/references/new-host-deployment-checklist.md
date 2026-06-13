# FreeLLM API 部署清单

> 供新主机的 Hermes Agent 按步骤执行。每条完成后打 ✓。

---

## 阶段一：安装 FreeLLMAPI

- [ ] `cd ~ && git clone https://github.com/tashfeenahmed/freellmapi.git`
- [ ] `cd freellmapi && npm install`
- [ ] `bash scripts/build-client.sh`
  - 如失败，手动装 `@types/react-dom` 和 `@vitejs/plugin-react`
- [ ] 生成 `.env`：
  ```bash
  ENCRYPTION_KEY=$(node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")
  cat > .env << EOF
  ENCRYPTION_KEY=$ENCRYPTION_KEY
  PORT=3001
  EOF
  ```
- [ ] 配置 Systemd 服务（海外 or 国内，选一个）
- [ ] `sudo systemctl daemon-reload && sudo systemctl enable --now freellmapi`
- [ ] 验证：`sudo journalctl -u freellmapi --no-pager | tail -10` → 看到 `Server running on http://[::]:3001`
- [ ] 记下 API Key：`sudo journalctl -u freellmapi --no-pager | grep "unified API key"`

## 阶段二：配置 Hermes

- [ ] 配 provider：
  ```bash
  export FREELM_KEY="从日志里拿到的 key"
  hermes config set providers.freellmapi.name "FreeLLM API"
  hermes config set providers.freellmapi.base_url "http://127.0.0.1:3001/v1"
  hermes config set providers.freellmapi.api_key "$FREELM_KEY"
  hermes config set providers.freellmapi.model "auto"
  hermes config set providers.freellmapi.discover_models true
  unset FREELM_KEY
  ```
- [ ] 验证：`grep -A6 'freellmapi' ~/.hermes/config.yaml`
- [ ] 重启网关：`hermes gateway restart`
- [ ] 切模型：`/model` → 选 `custom:FreeLLM API`

## 阶段三：Dashboard 账号

- [ ] `curl -X POST http://localhost:3001/api/auth/setup -H "Content-Type: application/json" -d '{"email":"你的邮箱","password":"你的密码（8位以上）"}'`

## 阶段四：配置提供商

- [ ] **匿名即用**（Add Key 留空）：Kilo Gateway、Pollinations、LLM7
- [ ] **必配**（需 Key）：Groq、Cerebras、OpenRouter、Cohere
- [ ] **推荐配**：Google Gemini、NVIDIA、GitHub Models、HuggingFace 等

## 阶段五：验证

- [ ] `curl http://localhost:3001/v1/models` 返回模型列表
- [ ] 在 Hermes 中发一条消息确认服务正常工作

## 国内服务器额外步骤

- [ ] Systemd 服务加 `HTTP_PROXY=http://127.0.0.1:7890` + `HTTPS_PROXY=http://127.0.0.1:7890`
- [ ] 装 undici + proxy-preload（修复 Node.js fetch 不认 HTTP_PROXY 的问题）
- [ ] `After=mihomo.service` + `Wants=mihomo.service` 确保代理先启动
