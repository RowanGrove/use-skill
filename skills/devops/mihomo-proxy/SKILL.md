---
name: mihomo-proxy
description: "Complete Mihomo (Clash Meta) proxy setup for China mainland servers — install via mirror, subscription config, rule-based split routing (Chinese traffic DIRECT, foreign via proxy), node health watchdog, systemd services, schedule refresh, and Hermes gateway proxy integration."
domain: devops
triggers:
  - "install clash"
  - "setup proxy"
  - "configure mihomo"
  - "clash meta subscription"
  - "proxy behind GFW"
  - "代理配置"
  - "订阅链接"
  - "gateway proxy"
  - "telegram proxy"
  - "forward proxy for services"
  - "系统服务走代理"
requires:
  - curl
  - systemd (for auto-start)
  - python3
references:
  - templates/config.yaml  # Full Mihomo config template with rules
  - templates/hermes-gateway.service  # Hermes Gateway systemd unit with proxy
  - scripts/refresh-subscription.sh  # Subscription refresh script
  - scripts/node-watchdog.sh  # Node health watchdog script
---

# Mihomo (Clash Meta) Proxy Setup — 中国大陆服务器完整方案

## 架构

```
系统服务/应用
  ↓ HTTP_PROXY=http://127.0.0.1:7890
Mihomo — 端口 7890
  ↓ 管理 API: 127.0.0.1:9090
分流规则:
  - 国内流量 → DIRECT（直连）
  - 国外/被墙 → 代理节点（vless+reality）
  - AI/模型 API → 代理
  - 所有节点挂了 → 自动切 DIRECT（看门狗）
```

## 1. 安装 Mihomo（国内镜像）

```bash
# 获取最新版本号
LATEST=$(curl -s "https://ghproxy.net/https://api.github.com/repos/MetaCubeX/mihomo/releases/latest" | grep tag_name | cut -d'"' -f4)

# 下载（走 ghproxy 镜像）
curl -sL "https://ghproxy.net/https://github.com/MetaCubeX/mihomo/releases/download/${LATEST}/mihomo-linux-amd64-${LATEST}.gz" -o mihomo.gz

# 验证是否真的是 gzip
file mihomo.gz | grep -q "gzip compressed data" || { echo "ghproxy returned HTML!"; head -3 mihomo.gz; exit 1; }

gunzip -f mihomo.gz && chmod +x mihomo && sudo mv mihomo /usr/local/bin/mihomo
mihomo -v
# 预期: Mihomo Meta v1.19.27 linux amd64
```

## 2. 配置目录

```bash
mkdir -p ~/.config/mihomo/ruleset
```

## 3. 核心配置要点

关键参数说明（详见 `templates/config.yaml`）：

| 参数 | 值 | 说明 |
|------|-----|------|
| `mixed-port` | 7890 | HTTP/SOCKS5 混合代理端口 |
| `allow-lan` | false | **必须 false**，只监听本地 |
| `bind-address` | 127.0.0.1 | 只绑本地回环 |
| `mode` | rule | **必须 rule**！不能用 global，否则 SSH 都会走代理 |
| `external-controller` | 127.0.0.1:9090 | RESTful API，看门狗用 |
| `geodata-mode` | true | 使用 GeoIP/GeoSite 数据库做分流 |

### 分流规则逻辑

规则从上到下匹配，命中即停：

```
1. 私有网络 → DIRECT         (127.0.0.0/8, 10.0.0.0/8, 192.168.x.x)
2. STUN 端口 → REJECT        (防 WebRTC 泄漏真实 IP)
3. 广告追踪 → REJECT         (category-ads-all + 腾讯系)
4. AI/境外API → 节点选择      (RULE-SET overseas-ai + google/telegram/github)
5. 国内网站 → DIRECT         (GEOSITE:cn, GEOSITE:geolocation-cn)
6. 国内 IP → DIRECT          (GEOIP:CN)
7. 国外未匹配 → 节点选择      (GEOSITE:geolocation-!cn)
8. 兜底 → 节点选择            (MATCH)
```

### 地理数据库

Mihomo 需要 geoip.dat、geosite.dat、country.mmdb 来做 GEOSITE/GEOIP 匹配，jsdelivr CDN 在国内可访问：

```yaml
geox-url:
  geoip: 'https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/geoip.dat'
  geosite: 'https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/geosite.dat'
  mmdb: 'https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/country.mmdb'
geo-auto-update: true
geo-update-interval: 24
```

### AI 服务自定义分流

配置中引用了 `rule-providers: overseas-ai` 从 GitHub 拉取 AI 服务列表：

```yaml
rule-providers:
  overseas-ai:
    type: http
    behavior: classical
    # 注意: raw.githubusercontent.com 在国内也被墙
    # Mihomo 自己是代理，没法走自己下载规则
    # 方案 A：用 jsdelivr CDN 镜像（国内可访问）
    url: 'https://cdn.jsdelivr.net/gh/viewer12/OverseasAI.list@main/rule/Clash/OverseasAI/OverseasAI.list'
    # 方案 B：如果用 raw.githubusercontent.com 需要先在本地准备好规则文件
    # url: 'https://raw.githubusercontent.com/viewer12/OverseasAI.list/main/rule/Clash/OverseasAI/OverseasAI.list'
    path: ./ruleset/overseas-ai.list
    interval: 86400
    format: text
```

## 4. 节点订阅配置

节点从机场订阅获取。**订阅 URL 是敏感信息，不要公开保存。**

### 订阅刷新脚本

`scripts/refresh-subscription.sh`：

```bash
#!/bin/bash
curl -sL -H "User-Agent: clash.meta" \
  "YOUR_SUBSCRIPTION_URL" \
  -o /tmp/subscription-new.yaml

# 验证是否为合法配置
if grep -q "^mixed-port:" /tmp/subscription-new.yaml 2>/dev/null; then
  cp /tmp/subscription-new.yaml ~/.config/mihomo/config.new.yaml
  # 强制覆盖安全设置
  sed -i 's/^allow-lan:.*/allow-lan: false/' ~/.config/mihomo/config.new.yaml
  sed -i "s/^bind-address:.*/bind-address: '127.0.0.1'/" ~/.config/mihomo/config.new.yaml
  sed -i 's/^mode:.*/mode: rule/' ~/.config/mihomo/config.new.yaml
  mv ~/.config/mihomo/config.new.yaml ~/.config/mihomo/config.yaml
  sudo systemctl restart mihomo
  echo "订阅已刷新，Mihomo 已重启"
else
  echo "无效订阅响应，跳过更新"
  head -5 /tmp/subscription-new.yaml
fi
```

### 定时刷新（每天 6:00）

```bash
crontab -e
# 添加：
0 6 * * * /bin/bash /home/ubuntu/.config/mihomo/refresh-subscription.sh >> /home/ubuntu/.config/mihomo/refresh.log 2>&1
```

## 5. Systemd 服务

### Mihomo 主服务

`/etc/systemd/system/mihomo.service`：

```ini
[Unit]
Description=Mihomo (Clash Meta) Proxy Service
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/.config/mihomo
ExecStart=/usr/local/bin/mihomo -d /home/ubuntu/.config/mihomo
Restart=on-failure
RestartSec=10
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mihomo
```

### 节点看门狗服务

看门狗每 5 秒检查当前节点延迟，节点挂了自动切到最快的可用节点，全挂则切 DIRECT。

`/etc/systemd/system/mihomo-watchdog.service`：

```ini
[Unit]
Description=Mihomo Node Health Watchdog
After=mihomo.service
Requires=mihomo.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
ExecStart=/home/ubuntu/.config/mihomo/node-watchdog.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mihomo-watchdog

# 查看看门狗日志
tail -f /tmp/watchdog.log
```

看门狗行为：

| 状态 | 行为 |
|------|------|
| 当前节点正常 (< 5s) | 等 5 秒再检查 |
| 当前节点超时/失败 | 扫描所有节点，选最快的 |
| 所有节点不可达 | 立即切换到 DIRECT |
| DIRECT 模式（全挂） | 每 15 秒检测是否有节点恢复 |
| 有节点恢复 | 自动切回代理 |

## 6. 验证代理

```bash
# 国内（应直连快）
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" -x http://127.0.0.1:7890 https://www.baidu.com

# 国外（应走代理）
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" -x http://127.0.0.1:7890 https://www.google.com -m 15

# Telegram API
curl -x http://127.0.0.1:7890 -s --connect-timeout 5 https://api.telegram.org

# 看当前节点
curl -sf http://127.0.0.1:9090/proxies/节点选择 | python3 -c "import json,sys;d=json.load(sys.stdin);print('当前:', d.get('now',''))"
```

## 7. 给其他服务加代理

### systemd 服务加代理

在 `[Service]` 段加：

```ini
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
```

在 `[Unit]` 段加依赖确保 Mihomo 先启动：

```ini
After=mihomo.service
Wants=mihomo.service
```

### Hermes Gateway 示例（user service）

`templates/hermes-gateway.service`（放在 `~/.config/systemd/user/`）：

```ini
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
```

重启命令（注意用 `sudo -u` + `XDG_RUNTIME_DIR` 因为 SSH 没有 dbus session）：

```bash
sudo -u ubuntu XDG_RUNTIME_DIR=/run/user/1000 systemctl --user daemon-reload
sudo -u ubuntu XDG_RUNTIME_DIR=/run/user/1000 systemctl --user restart hermes-gateway
```

验证代理是否注入到进程：

```bash
cat /proc/<PID>/environ | tr '\0' '\n' | grep -i proxy
# 预期输出:
# HTTP_PROXY=http://127.0.0.1:7890
# HTTPS_PROXY=http://127.0.0.1:7890
```

### 其他常见场景

| 场景 | 方法 | 示例 |
|------|------|------|
| 单条命令 | 前缀 env vars | `HTTP_PROXY=http://127.0.0.1:7890 curl https://example.com` |
| 当前 shell | export | `export HTTP_PROXY=http://127.0.0.1:7890` |
| apt | 配置文件 | `echo 'Acquire::http::Proxy "http://127.0.0.1:7890";' | sudo tee /etc/apt/apt.conf.d/90proxy` |
| git | 配置 per-repo | `git config --global http.proxy http://127.0.0.1:7890` |

## 8. 日常维护

```bash
# 状态
sudo systemctl status mihomo
sudo systemctl status mihomo-watchdog

# 实时日志
sudo journalctl -u mihomo -f
tail -f /tmp/watchdog.log

# 手动切换节点
curl -X PUT http://127.0.0.1:9090/proxies/节点选择 \
  -H "Content-Type: application/json" \
  -d '{"name":"🇸🇬Singapore 01"}'

# 强制直连
curl -X PUT http://127.0.0.1:9090/proxies/节点选择 \
  -H "Content-Type: application/json" \
  -d '{"name":"DIRECT"}'

# 测所有节点延迟
curl -s http://127.0.0.1:9090/proxies | python3 -c "
import json,sys,urllib.parse
d=json.load(sys.stdin)
nodes=[k for k in d['proxies'] if d['proxies'][k].get('type') not in ('Direct','Reject','Selector','URLTest')]
import subprocess,time
for n in nodes:
    e=urllib.parse.quote(n)
    r=subprocess.run(['curl','-sf',f'http://127.0.0.1:9090/proxies/{e}/delay?timeout=2000&url=http://cp.cloudflare.com/generate_204'],capture_output=True,text=True)
    if r.returncode==0: d2=json.loads(r.stdout); print(f'{n}: {d2.get(\"delay\",\"?\")}ms')
    else: print(f'{n}: timeout')
    time.sleep(0.1)
"
```

## 踩坑记录

| # | 坑 | 原因 | 解决 |
|---|-----|------|------|
| 1 | ghproxy 返回 HTML 页面 | 镜像有时返回错误页面而非文件 | 用 `file` 验证是否为 gzip |
| 2 | `systemctl --user` 报 "No medium found" | SSH 没有 dbus session | `sudo -u ubuntu XDG_RUNTIME_DIR=/run/user/1000 systemctl --user ...` |
| 3 | 加了代理环境变量但进程没生效 | systemd daemon-reload 没跑 | reload → restart，然后用 `cat /proc/PID/environ` 验证 |
| 4 | 订阅更新后 allow-lan 变 true | 订阅端配置可能覆盖安全设置 | refresh 脚本里用 sed 强制覆盖 |
| 5 | 节点全红网络断 | 看门狗没运行 | `sudo systemctl enable --now mihomo-watchdog` |
| 6 | EADDRINUSE 7890 | 旧进程残留 | `fuser -k 7890/tcp` 再重启 |
| 7 | Telegram API 连不上 | 网关没走代理 | systemd 加 `HTTP_PROXY`，重启验证 |
| 8 | rule-provider 下载失败（overseas-ai 列表） | raw.githubusercontent.com 在国内被墙，Mihomo 没法走自己下载规则 | 换成 jsdelivr CDN 镜像 `cdn.jsdelivr.net/gh/...@main/...` |
