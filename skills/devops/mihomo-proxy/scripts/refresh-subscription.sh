#!/bin/bash
# =====================================================
# Mihomo 订阅刷新脚本
# 从机场订阅下载最新节点配置
# 强制覆盖安全设置，然后重启 Mihomo
# =====================================================

# !! 替换为你的实际订阅 URL !!
SUBSCRIPTION_URL="https://your-subscription-url"

curl -sL -H "User-Agent: clash.meta" \
  "$SUBSCRIPTION_URL" \
  -o /tmp/subscription-new.yaml

# 验证是否为合法配置（不是报错页面）
if grep -q "^mixed-port:" /tmp/subscription-new.yaml 2>/dev/null; then
  cp /tmp/subscription-new.yaml ~/.config/mihomo/config.new.yaml

  # 强制覆盖安全设置（订阅端可能下发不安全配置）
  sed -i 's/^allow-lan:.*/allow-lan: false/' ~/.config/mihomo/config.new.yaml
  sed -i "s/^bind-address:.*/bind-address: '127.0.0.1'/" ~/.config/mihomo/config.new.yaml
  sed -i 's/^mode:.*/mode: rule/' ~/.config/mihomo/config.new.yaml

  mv ~/.config/mihomo/config.new.yaml ~/.config/mihomo/config.yaml

  # 重启 Mihomo
  sudo systemctl restart mihomo
  echo "$(date): 订阅已刷新，Mihomo 已重启"
else
  echo "$(date): 无效订阅响应，跳过更新"
  head -5 /tmp/subscription-new.yaml
fi
