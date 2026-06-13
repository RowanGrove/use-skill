#!/usr/bin/env python3
"""
FreeLLMAPI Auto-Optimizer v2 — 模型级优化
检查每个模型的错误分布，只禁失败的模型，保留能用的。
每日 8/16/23 点跑，24h 滚动窗口。

逻辑：
  1. 获取错误分布 — 哪些 (platform, model_id) 在过去 24h 报过错
  2. 遍历所有平台的每个模型：
     - 有错误 → 直接 sqlite 禁用该模型
     - 没错误 → 直接 sqlite 启用该模型（给机会，或是原本就好的）
  3. 每个平台检查：至少一个模型启用 → 确保平台 Key 启用；零模型启用 → 确保平台 Key 禁用
  4. 带防抖：同一模型被反复禁用会延长冷却期
"""
import urllib.request, json, os, sys, subprocess, time, traceback

BASE = os.environ.get("FREEML_BASE", "http://127.0.0.1:3001")
CRED_FILE = os.path.expanduser("~/.freellmapi_cred.json")
STATE_FILE = os.path.expanduser("~/.freellmapi_optimizer_state.json")
DB_PATH = os.path.expanduser("~/freellmapi/server/data/freeapi.db")
RANGE = "24h"

# 防抖：同一模型/平台反复禁用时指数增加冷却
COOLDOWN_BASE = 86400       # 1 天（秒）
COOLDOWN_MAX = 604800       # 7 天（秒）
ERROR_PER_MODEL = 1          # 模型只要有 1 次报错就禁用
ERROR_THRESHOLD_PLATFORM = 5 # 平台级别至少 5 次报错才禁整个平台

def log(msg):
    print(msg, flush=True)

def db_update(sql):
    """Run SQL on FreeLLMAPI database."""
    subprocess.run(["sqlite3", DB_PATH, sql], capture_output=True, check=True)

def main():
    # 0. Credentials
    if not os.path.exists(CRED_FILE):
        log("[ERROR] Credentials file not found")
        sys.exit(1)
    try:
        creds = json.load(open(CRED_FILE))
        email, password = creds["email"], creds["password"]
    except Exception as e:
        log(f"[ERROR] Failed to read credentials: {e}")
        sys.exit(1)

    # 1. Load state (handle old format migration)
    state = {"models_disabled": {}, "platforms_fixed": []}
    if os.path.exists(STATE_FILE):
        try:
            state = json.load(open(STATE_FILE))
            # Migrate from old format (platform-level) to new (model-level)
            if "disabled_by_optimizer" in state and not state.get("models_disabled"):
                log(f"[MIGRATE] Old state found with {len(state['disabled_by_optimizer'])} platforms, resetting to model-level")
                state["models_disabled"] = {}
                state["platforms_fixed"] = []
        except Exception:
            log("[WARN] State file corrupt, resetting")

    now = int(time.time())

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

    # 3. Error distribution (24h)
    try:
        req = urllib.request.Request(
            f"{BASE}/api/analytics/error-distribution?range={RANGE}", headers=headers)
        err_data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        log(f"[ERROR] Error distribution fetch failed: {e}")
        sys.exit(1)

    # Build: set of (platform, model_id) with errors, count per (platform, model_id)
    error_models = {}  # (platform, model_id) -> total_errors
    error_platforms = {}  # platform -> total_errors
    for e in err_data.get("detailed", []):
        key = (e["platform"], e["model_id"])
        error_models[key] = error_models.get(key, 0) + e["count"]
        error_platforms[e["platform"]] = error_platforms.get(e["platform"], 0) + e["count"]

    log(f"报错涉及 {len(set(p for p,_ in error_models))} 个平台, {len(error_models)} 个模型")

    # 4. All models
    try:
        req = urllib.request.Request(f"{BASE}/api/models", headers=headers)
        all_models = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        log(f"[ERROR] Models fetch failed: {e}")
        sys.exit(1)

    # Group by platform
    platform_models = {}
    for m in all_models:
        p = m["platform"]
        platform_models.setdefault(p, []).append(m)

    # 5. Keys list
    try:
        req = urllib.request.Request(f"{BASE}/api/keys", headers=headers)
        keys = json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as e:
        log(f"[ERROR] Keys fetch failed: {e}")
        sys.exit(1)

    key_map = {k["platform"]: k for k in keys}

    # 6. Process each platform's models
    changes = {"model_disabled": [], "model_reenabled": [],
               "platform_enabled": [], "platform_disabled": [],
               "cooldown_skip": []}

    models_disabled_new = {}  # will replace state["models_disabled"]

    for platform in sorted(platform_models.keys()):
        if platform not in key_map:
            continue

        models = platform_models[platform]
        if not models:
            continue

        platform_total_errors = error_platforms.get(platform, 0)
        working = 0
        broken = 0
        cooldown_skipped = 0

        for m in models:
            mid = m["id"]
            model_id = m["modelId"]
            currently_enabled = m["enabled"]
            err_count = error_models.get((platform, model_id), 0)
            state_key = f"{platform}/{model_id}"

            if err_count >= ERROR_PER_MODEL:
                # Model has errors → disable
                if currently_enabled:
                    try:
                        db_update(f"UPDATE models SET enabled=0 WHERE id={mid}")
                        changes["model_disabled"].append(f"{platform}/{model_id} ({err_count} errors)")
                    except Exception as e:
                        log(f"[ERROR] DB disable {platform}/{model_id}: {e}")

                # Update cooldown: when this model was last disabled
                prev = state["models_disabled"].get(state_key, {})
                prev_count = prev.get("count", 0)
                models_disabled_new[state_key] = {
                    "disabled_at": now,
                    "count": prev_count + 1,
                    "reenable_after": now + min(COOLDOWN_BASE * (prev_count + 1), COOLDOWN_MAX)
                }
                broken += 1

            else:
                # No errors → should be enabled
                # But check cooldown if it was previously disabled by us
                prev = state["models_disabled"].get(state_key, {})
                if prev and not currently_enabled:
                    # Was disabled by us — check cooldown
                    if now < prev.get("reenable_after", 0):
                        cooldown_skipped += 1
                        changes["cooldown_skip"].append(
                            f"{platform}/{model_id} (冷却中, 还剩 {(prev['reenable_after'] - now)//3600}h)")
                        continue  # Keep disabled during cooldown

                # No cooldown or cooldown expired → enable
                if not currently_enabled:
                    try:
                        db_update(f"UPDATE models SET enabled=1 WHERE id={mid}")
                        changes["model_reenabled"].append(f"{platform}/{model_id}")
                    except Exception as e:
                        log(f"[ERROR] DB enable {platform}/{model_id}: {e}")

                working += 1

        # Now decide platform key status
        if working > 0:
            if not key_map[platform].get("enabled", True):
                try:
                    patch = json.dumps({"enabled": True}).encode()
                    req = urllib.request.Request(
                        f"{BASE}/api/keys/platform/{platform}",
                        data=patch, method="PATCH",
                        headers=headers | {"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=10)
                    changes["platform_enabled"].append(
                        f"{platform} ({working} working of {len(models)} models)")
                except Exception as e:
                    log(f"[ERROR] Enable platform {platform}: {e}")
        else:
            # Zero working models — disable the platform
            # But only if it has enough total errors to not be a fluke
            if platform_total_errors >= ERROR_THRESHOLD_PLATFORM:
                if key_map[platform].get("enabled", True):
                    try:
                        patch = json.dumps({"enabled": False}).encode()
                        req = urllib.request.Request(
                            f"{BASE}/api/keys/platform/{platform}",
                            data=patch, method="PATCH",
                            headers=headers | {"Content-Type": "application/json"})
                        urllib.request.urlopen(req, timeout=10)
                        changes["platform_disabled"].append(
                            f"{platform} (0 working models, {platform_total_errors} total errors)")
                    except Exception as e:
                        log(f"[ERROR] Disable platform {platform}: {e}")
            else:
                log(f"[SKIP] {platform}: 0 working but only {platform_total_errors} total errors, keeping as-is")

        if cooldown_skipped > 0:
            log(f"  {platform}: {cooldown_skipped} model(s) in cooldown, skipped")

    # Save state (merge: keep models that weren't in this run + new ones)
    # Actually replace entirely: models_disabled_new only has models we just disabled
    # We also need to carry forward models from previous state that are still disabled in DB
    # But the simplest is: models_disabled_new has current state of all disabled-by-us models
    # And we keep entries for models not seen in this run but still in DB disabled state
    for state_key, prev_data in state["models_disabled"].items():
        if state_key not in models_disabled_new:
            # Check if this model is still disabled in DB
            parts = state_key.split("/", 1)
            if len(parts) == 2:
                p, mid_name = parts
                # Check current DB state
                try:
                    result = subprocess.run(
                        ["sqlite3", DB_PATH,
                         f"SELECT enabled FROM models WHERE platform='{p}' AND model_id='{mid_name}'"],
                        capture_output=True, text=True, timeout=5)
                    db_enabled = result.stdout.strip()
                    if db_enabled == "0":
                        # Still disabled in DB — carry forward the state
                        models_disabled_new[state_key] = prev_data
                except Exception:
                    pass

    state["models_disabled"] = models_disabled_new
    json.dump(state, open(STATE_FILE, "w"))

    # Restart FreeLLMAPI if any model changes were made — NO!
    # DB 修改即时生效，重启反而会被 FreeLLMAPI 的启动同步覆盖。
    # 脚本改完就走，下个请求路由器就会跳过 enabled=0 的模型。
    if changes["model_disabled"] or changes["model_reenabled"]:
        log(f"\n模型有变更，DB 已更新（不重启，即时生效）")

    # Report
    log(f"\n📊 FreeLLMAPI 优化报告 v2 [模型级, {RANGE}]")

    if changes["model_disabled"]:
        log(f"\n🚫 禁用失败模型 ({len(changes['model_disabled'])}):")
        for c in changes["model_disabled"]:
            log(f"  • {c}")

    if changes["model_reenabled"]:
        log(f"\n✅ 恢复模型 ({len(changes['model_reenabled'])}):")
        for c in changes["model_reenabled"]:
            log(f"  • {c}")

    if changes["platform_enabled"]:
        log(f"\n🔛 启用平台:")
        for c in changes["platform_enabled"]:
            log(f"  • {c}")

    if changes["platform_disabled"]:
        log(f"\n🔴 禁用平台（无可用模型）:")
        for c in changes["platform_disabled"]:
            log(f"  • {c}")

    if changes["cooldown_skip"]:
        log(f"\n⏳ 冷却中（暂不恢复）:")
        for c in changes["cooldown_skip"][:10]:
            log(f"  • {c}")
        if len(changes["cooldown_skip"]) > 10:
            log(f"  ... 还有 {len(changes['cooldown_skip'])-10} 个")

    # Stats
    total_disabled = len(state["models_disabled"])
    log(f"\n━━━━━━━━━━━━━━━━━━━━")
    log(f"当前管理 {total_disabled} 个禁用模型")
    if not any(changes.values()):
        log(f"本轮无变化，所有平台状态正常")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"[FATAL] {e}")
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)
