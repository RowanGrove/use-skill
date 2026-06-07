#!/bin/bash
# =====================================================
# Mihomo 节点健康检查看门狗 v2
# 每5秒扫描一次当前节点延迟
# 当前节点挂了 -> 扫描所有节点找最快可用的
# 所有节点全挂 -> 切换到 DIRECT（直连）
# DIRECT 模式下每15秒检查是否有节点恢复
# =====================================================

API_BASE="http://127.0.0.1:9090"
PROXY_GROUP="节点选择"
LATENCY_TIMEOUT=3000   # 测试延迟超时(ms)
LATENCY_THRESHOLD=5000 # 超过此值的视为挂掉
CHECK_INTERVAL=5       # 每5秒检查一次
TEST_URL="http://cp.cloudflare.com/generate_204"

log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a /tmp/watchdog.log
}

urlencode() {
    python3 -c "import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1]))" "$1"
}

FORCE_DIRECT=false
IDLE_SKIP=0

log "🚀 节点看门狗启动，每${CHECK_INTERVAL}秒检查一次"

while true; do
    # 获取当前选中的节点
    GROUP_INFO=$(curl -sf "${API_BASE}/proxies/${PROXY_GROUP}" 2>/dev/null)
    if [ $? -ne 0 ] || [ -z "$GROUP_INFO" ]; then
        sleep 5
        continue
    fi

    NOW_NODE=$(echo "$GROUP_INFO" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d.get('now',''))
" 2>/dev/null)

    # ========================
    # 模式 A: 当前就是 DIRECT
    # ========================
    if [ "$NOW_NODE" = "DIRECT" ]; then
        IDLE_SKIP=$((IDLE_SKIP + 1))
        if [ $IDLE_SKIP -lt 3 ]; then
            sleep $CHECK_INTERVAL
            continue
        fi
        IDLE_SKIP=0

        # 检查是否有活着的节点
        NODE_LIST=$(echo "$GROUP_INFO" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for item in d.get('all',[]):
    if item not in ('DIRECT','REJECT','COMPATIBLE','自动选择'):
        print(item)
" 2>/dev/null)

        if [ -z "$NODE_LIST" ]; then
            sleep $CHECK_INTERVAL
            continue
        fi

        # 批量测试延迟
        FOUND_GOOD=false
        while IFS= read -r node; do
            [ -z "$node" ] && continue
            encoded=$(urlencode "$node")
            delay_result=$(curl -sf "${API_BASE}/proxies/${encoded}/delay?timeout=2000&url=${TEST_URL}" 2>/dev/null)
            if [ $? -eq 0 ]; then
                delay=$(echo "$delay_result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('delay',9999))")
                if [ "$delay" != "9999" ] && [ "$delay" -lt "$LATENCY_THRESHOLD" ]; then
                    log "✅ 节点 [${node}] 已恢复(${delay}ms)，切换回代理"
                    curl -sf -X PUT "${API_BASE}/proxies/${PROXY_GROUP}" \
                        -H "Content-Type: application/json" \
                        -d "{\"name\":\"${node}\"}" > /dev/null 2>&1
                    FOUND_GOOD=true
                    FORCE_DIRECT=false
                    break
                fi
            fi
        done <<< "$NODE_LIST"

        if [ "$FOUND_GOOD" = false ]; then
            log "⏳ 所有节点仍不可达，保持直连"
        fi
        sleep $CHECK_INTERVAL
        continue
    fi

    # ========================
    # 模式 B: 正常代理模式
    # ========================
    IDLE_SKIP=0

    # 如果当前是自动选择组，测试自动选择下的实际代理
    if [ "$NOW_NODE" = "自动选择" ]; then
        AUTO_INFO=$(curl -sf "${API_BASE}/proxies/自动选择" 2>/dev/null)
        if [ $? -eq 0 ]; then
            AUTO_NOW=$(echo "$AUTO_INFO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('now',''))")
            if [ -n "$AUTO_NOW" ] && [ "$AUTO_NOW" != "自动选择" ]; then
                NOW_NODE="$AUTO_NOW"
            fi
        fi
    fi

    # 测试当前节点
    encoded=$(urlencode "$NOW_NODE")
    delay_result=$(curl -sf "${API_BASE}/proxies/${encoded}/delay?timeout=${LATENCY_TIMEOUT}&url=${TEST_URL}" 2>/dev/null)
    current_ok=false

    if [ $? -eq 0 ]; then
        current_delay=$(echo "$delay_result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('delay',9999))")
        if [ -n "$current_delay" ] && [ "$current_delay" != "9999" ] && [ "$current_delay" -lt "$LATENCY_THRESHOLD" ]; then
            current_ok=true
        fi
    fi

    if [ "$current_ok" = true ]; then
        sleep $CHECK_INTERVAL
        continue
    fi

    # ========================
    # 当前节点挂了，扫描全部节点
    # ========================
    log "⚠️ 当前节点 [${NOW_NODE}] 延迟异常，扫描全部节点..."

    NODE_LIST=$(echo "$GROUP_INFO" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for item in d.get('all',[]):
    if item not in ('DIRECT','REJECT','COMPATIBLE','自动选择'):
        print(item)
" 2>/dev/null)

    BEST_NODE=""
    BEST_DELAY=99999
    ANY_ALIVE=false

    while IFS= read -r node; do
        [ -z "$node" ] && continue
        encoded=$(urlencode "$node")
        delay_result=$(curl -sf --max-time 4 "${API_BASE}/proxies/${encoded}/delay?timeout=${LATENCY_TIMEOUT}&url=${TEST_URL}" 2>/dev/null)
        if [ $? -eq 0 ]; then
            delay=$(echo "$delay_result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('delay',9999))" 2>/dev/null)
            if [ -n "$delay" ] && [ "$delay" != "9999" ] && [ "$delay" -lt "$LATENCY_THRESHOLD" ]; then
                ANY_ALIVE=true
                if [ "$delay" -lt "$BEST_DELAY" ]; then
                    BEST_DELAY=$delay
                    BEST_NODE="$node"
                fi
            fi
        fi
    done <<< "$NODE_LIST"

    if [ "$ANY_ALIVE" = true ] && [ -n "$BEST_NODE" ]; then
        log "🔄 切换到最快节点 [${BEST_NODE}] (${BEST_DELAY}ms)"
        curl -sf -X PUT "${API_BASE}/proxies/${PROXY_GROUP}" \
            -H "Content-Type: application/json" \
            -d "{\"name\":\"${BEST_NODE}\"}" > /dev/null 2>&1
        FORCE_DIRECT=false
    else
        log "🚫 所有节点不可达！切换到直连(DIRECT)"
        curl -sf -X PUT "${API_BASE}/proxies/${PROXY_GROUP}" \
            -H "Content-Type: application/json" \
            -d '{"name":"DIRECT"}' > /dev/null 2>&1
        FORCE_DIRECT=true
    fi

    sleep $CHECK_INTERVAL
done
