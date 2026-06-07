# Subscription Config Reference

This file documents the specific subscription config structure from the Hokkaido Toyoni provider used in the original setup session.

## Provider Info

- **Domain**: conf1.hokkaido-toyoni.com
- **Path pattern**: `/oosaka/<hash>`
- **Required User-Agent**: `clash.meta` (returns full Clash YAML config)
- **Alt User-Agent**: `v2rayNG` (returns base64-encoded vmess:// links)

## Config Structure (Clash Meta format)

The subscription returns a complete Clash YAML with these sections:

### Ports & Mode
```yaml
mixed-port: 7890
allow-lan: true           # MUST change to false on server
bind-address: '*'         # MUST change to '127.0.0.1'
mode: rule                # Keep as rule - NOT global
```

### Proxy Nodes (VLESS Reality)
All nodes use VLESS + XTLS Reality (Vision flow) with x25519 public key encryption:
- Type: `vless`
- Flow: `xtls-rprx-vision`
- Encryption: `none`
- TLS: `true`
- Client fingerprint: `chrome`
- Network: `tcp`

Available node groups from the original subscription:
- United States (4 nodes)
- Malaysia (2 nodes)
- Singapore (4 nodes)
- Japan (4 nodes)
- Korea (2 nodes)
- Netherlands (2 nodes)
- United Kingdom (4 nodes)
- Hong Kong (6 nodes, some marked [Home])
- Taiwan (4 nodes, some marked [Home])
- Germany (2 nodes)

### Proxy Groups
```yaml
# Manual selection group
- name: 节点选择
  type: select
  proxies: [自动选择, ...all nodes...]

# Auto latency test group
- name: 自动选择
  type: url-test
  url: 'http://cp.cloudflare.com/generate_204'
  interval: 300
  tolerance: 50
  exclude-filter: '\\[Home\\]'
```

### Routing Rules (split-tunneling)
Critical rules that ensure safe split routing:
1. Private IPs → DIRECT (always)
2. REJECT rules for STUN/TURN (port 3478-5350, 19302-19309)
3. REJECT rules for ads/tracking
4. `RULE-SET,overseas-ai,节点选择` — AI services through proxy
5. `GEOSITE,google,节点选择` + `GEOSITE,telegram,节点选择` + `GEOSITE,github,节点选择` — blocked services
6. `GEOSITE,cn,DIRECT` + `GEOSITE,geolocation-cn,DIRECT` — Chinese traffic DIRECT
7. `GEOIP,CN,DIRECT` — Chinese IPs DIRECT
8. `MATCH,节点选择` — everything else through proxy

### DNS Configuration
```yaml
dns:
  enable: true
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  default-nameserver: [223.5.5.5, 119.29.29.29]  # Chinese DNS
  nameserver: ['https://dns.cloudflare.com/dns-query', 'https://dns.google/dns-query']
  proxy-server-nameserver: ['https://dns.alidns.com/dns-query']
  nameserver-policy:
    'geosite:cn,geolocation-cn': ['https://doh.pub/dns-query', 'https://dns.alidns.com/dns-query']
```

### Rule Provider
```yaml
rule-providers:
  overseas-ai:
    type: http
    behavior: classical
    url: 'https://raw.githubusercontent.com/viewer12/OverseasAI.list/main/rule/Clash/OverseasAI/OverseasAI.list'
```

## Safe Config Overrides

When using a fresh subscription download, ALWAYS override:

```yaml
allow-lan: false           # ← critical: don't expose to LAN
bind-address: '127.0.0.1' # ← critical: localhost only
mode: rule                 # ← critical: not global
```

## Update Pattern

Subscription nodes change over time. The daily refresh script:
1. Downloads fresh config via `curl -H "User-Agent: clash.meta"`
2. Validates by checking for `mixed-port:` 
3. Applies safe overrides (sed for allow-lan, bind-address, mode)
4. Replaces config and restarts mihomo
