#!/usr/bin/env python3
"""
FreeLLMAPI Auto-Optimizer — Hermes cron script
Checks analytics, disables providers <30% success, re-enables recovered ones.
Runs 3x daily, uses 24h rolling window.

Logic:
  - Has data (>=MIN_OBS) + success < THRESHOLD  → disable
  - Disabled by us + has data + success >= THRESHOLD → re-enable
  - Disabled by us + NO data (because we disabled it) → run health check
    - Healthy → re-enable (give it a chance with real traffic)
    - Unhealthy → keep disabled
"""
import urllib.request, json, os, sys, traceback

BASE = os.environ.get("FREEML_BASE", "http://127.0.0.1:3001")
CRED_FILE = os.path.expanduser("~/.freellmapi_cred.json")
STATE_FILE = os.path.expanduser("~/.freellmapi_optimizer_state.json")
THRESHOLD = 30       # success rate %
MIN_OBS = 5           # min requests to make a decision
RANGE = "24h"

def log(msg):
    print(msg, flush=True)

def main():
    # 0. Credentials
    if not os.path.exists(CRED_FILE):
        log(f"[ERROR] Credentials file {CRED_FILE} not found")
        sys.exit(1)
    try:
        creds = json.load(open(CRED_FILE))
        email, password = creds["email"], creds["password"]
    except Exception as e:
        log(f"[ERROR] Failed to read credentials: {e}")
        sys.exit(1)

    # 1. Load state
    state = {"disabled_by_optimizer": []}
    if os.path.exists(STATE_FILE):
        try:
            state = json.load(open(STATE_FILE))
        except Exception:
            log("[WARN] State file corrupt, resetting")

    # 2. Login
    try:
        data = json.dumps({"email": email, "password": password}).encode()
        req = urllib.request.Request(f"{BASE}/api/auth/login", data=data,
            headers={"Content-Type": "application/json"})
        token = json.loads(urllib.request.urlopen(req, timeout=15).read())["token"]
    except Exception as e:
        log(f"[ERROR] Login failed: {e}")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Analytics by platform
    try:
        req = urllib.request.Request(
            f"{BASE}/api/analytics/by-platform?range={RANGE}", headers=headers)
        platforms = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        log(f"[ERROR] Analytics fetch failed: {e}")
        sys.exit(1)

    # 4. Keys list (maps platform name → key info, including key_id)
    try:
        req = urllib.request.Request(f"{BASE}/api/keys", headers=headers)
        keys = json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as e:
        log(f"[ERROR] Keys fetch failed: {e}")
        sys.exit(1)

    key_map = {k["platform"]: k for k in keys}
    analytics_map = {p["platform"]: p for p in platforms}

    changes = {"disabled": [], "reenabled": [], "health_reenabled": [],
               "health_kept_disabled": [], "other": []}

    all_disabled_by_optimizer = list(state["disabled_by_optimizer"])

    for platform_name in all_disabled_by_optimizer:
        if platform_name not in key_map:
            changes["other"].append(f"{platform_name} (no longer in keys, removing from tracker)")
            state["disabled_by_optimizer"].remove(platform_name)
            continue
        key = key_map[platform_name]
        if key.get("enabled", True):
            state["disabled_by_optimizer"].remove(platform_name)
            changes["other"].append(f"{platform_name} (manually re-enabled, tracker cleared)")
            continue

        pdata = analytics_map.get(platform_name, {})
        req_count = pdata.get("requests", 0)
        success_rate = pdata.get("successRate", 0)

        if req_count >= MIN_OBS:
            if success_rate >= THRESHOLD:
                try:
                    patch = json.dumps({"enabled": True}).encode()
                    req = urllib.request.Request(
                        f"{BASE}/api/keys/platform/{platform_name}",
                        data=patch, method="PATCH",
                        headers=headers | {"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=10)
                    changes["reenabled"].append(
                        f"{platform_name} ({success_rate}% on {req_count} req)")
                    state["disabled_by_optimizer"].remove(platform_name)
                except Exception as e:
                    log(f"[ERROR] Re-enable {platform_name} failed: {e}")
            else:
                changes["other"].append(
                    f"{platform_name} (still {success_rate}% on {req_count} req, keeping disabled)")
        else:
            key_id = key.get("id")
            if key_id is None:
                changes["other"].append(f"{platform_name} (no key_id, can't health-check)")
                continue
            try:
                req = urllib.request.Request(
                    f"{BASE}/api/health/check/{key_id}",
                    method="POST", headers=headers)
                health = json.loads(urllib.request.urlopen(req, timeout=30).read())
                status = health.get("status", "unknown")
                if status == "healthy":
                    patch = json.dumps({"enabled": True}).encode()
                    req = urllib.request.Request(
                        f"{BASE}/api/keys/platform/{platform_name}",
                        data=patch, method="PATCH",
                        headers=headers | {"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=10)
                    changes["health_reenabled"].append(
                        f"{platform_name} (health=healthy, giving another chance)")
                    state["disabled_by_optimizer"].remove(platform_name)
                else:
                    changes["health_kept_disabled"].append(
                        f"{platform_name} (health={status}, keeping disabled)")
            except Exception as e:
                log(f"[ERROR] Health check {platform_name} failed: {e}")
                changes["health_kept_disabled"].append(
                    f"{platform_name} (health check error, keeping disabled)")

    # Check all platforms for NEW platforms to disable
    for p in platforms:
        platform_name = p["platform"]
        req_count = p["requests"]
        success_rate = p["successRate"]

        if platform_name not in key_map:
            continue
        if platform_name in state["disabled_by_optimizer"]:
            continue
        if not key_map[platform_name].get("enabled", True):
            continue

        if req_count >= MIN_OBS and success_rate < THRESHOLD:
            try:
                patch = json.dumps({"enabled": False}).encode()
                req = urllib.request.Request(
                    f"{BASE}/api/keys/platform/{platform_name}",
                    data=patch, method="PATCH",
                    headers=headers | {"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=10)
                changes["disabled"].append(
                    f"{platform_name} ({success_rate}% on {req_count} req)")
                state["disabled_by_optimizer"].append(platform_name)
            except Exception as e:
                log(f"[ERROR] Disable {platform_name} failed: {e}")

    json.dump(state, open(STATE_FILE, "w"))

    log(f"FreeLLMAPI 优化报告 [{RANGE} 窗口]")
    log(f"检查了 {len(platforms)} 个平台, {len(state['disabled_by_optimizer'])} 个正被禁用")

    if changes["disabled"]:
        log(f"新禁用（成功率 <{THRESHOLD}%, 请求 >= {MIN_OBS}）:")
        for c in changes["disabled"]:
            log(f"  - {c}")

    if changes["reenabled"]:
        log(f"已恢复（数据表明已恢复）:")
        for c in changes["reenabled"]:
            log(f"  - {c}")

    if changes["health_reenabled"]:
        log(f"健康检查通过，恢复启用:")
        for c in changes["health_reenabled"]:
            log(f"  - {c}")

    if changes["health_kept_disabled"]:
        log(f"健康检查未通过，保持禁用:")
        for c in changes["health_kept_disabled"]:
            log(f"  - {c}")

    if changes["other"]:
        log(f"其他:")
        for c in changes["other"]:
            log(f"  - {c}")

    if not any(changes.values()):
        log("本轮无变化")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"[FATAL] {e}")
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)
