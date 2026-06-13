#!/bin/bash
# FreeLLM API 配置备份脚本
# 自动备份数据库和配置文件到 GitHub 私有仓库
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

# 1-3. 备份核心文件（不做任何过滤！）
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

# 4. 备份部署文档（freellmapi-deployment skill）
SKILL_SRC="/home/ubuntu/.hermes/skills/mlops/freellmapi-deployment"
SKILL_DST="$REPO_DIR/skills/freellmapi-deployment"
if [ -d "$SKILL_SRC" ]; then
  mkdir -p "$REPO_DIR/skills"
  # 清理旧版本再复制，避免残留文件
  rm -rf "$SKILL_DST"
  cp -r "$SKILL_SRC" "$SKILL_DST"
  log "✅ 部署文档已备份 (skills/freellmapi-deployment)"
fi

# 5. 生成 backup-status.md（含当前平台列表 + 时间戳）
# 不覆盖 hand-crafted README.md — 手动维护的部署指南更完整
status_tmp=$(mktemp)
platform_list=$(sqlite3 "/home/ubuntu/freellmapi/server/data/freeapi.db" \
    "SELECT platform FROM api_keys WHERE enabled=1 ORDER BY platform;" 2>/dev/null \
    | sed 's/^/- /')

cat > "$status_tmp" << REOF
# 备份状态

> 自动生成 | 最后更新: $(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M:%S') 北京时间

## 当前已配置平台

${platform_list:-（暂无）}

---

*自动生成于 $(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M')*
REOF

# 仅内容变化时覆盖
if [ -f "$REPO_DIR/backup-status.md" ]; then
  if ! diff -q "$status_tmp" "$REPO_DIR/backup-status.md" > /dev/null 2>&1; then
    cp "$status_tmp" "$REPO_DIR/backup-status.md"
    log "✅ backup-status.md 已更新"
  else
    log "ℹ️ backup-status.md 无变更，跳过"
  fi
else
  cp "$status_tmp" "$REPO_DIR/backup-status.md"
  log "✅ backup-status.md 已创建"
fi
rm -f "$status_tmp"

# 6-7. Git 提交 & 推送
cd "$REPO_DIR"
if [ ! -d ".git" ]; then
  git init && git remote add origin "$GITHUB_REPO"
  git config user.name "RowanGrove"
  git config user.email "your@email.com"
  git branch -M main
  log "🆕 Git 仓库初始化完成"
fi

if ! git diff --quiet HEAD -- 2>/dev/null; then
  git add .
  git commit -m "📦 自动备份: $(date '+%Y-%m-%d %H:%M:%S')"
  log "✅ 备份已提交到 Git"

  log "☁️ 正在推送到 GitHub..."
  if git push -u origin main 2>&1; then
    log "✅ 备份已推送到 GitHub: https://github.com/RowanGrove/freellmapi-backup"
  else
    log "❌ 推送失败！请检查 GitHub token 权限"
    cat "$LOG_FILE" >&2
    exit 1
  fi
else
  log "ℹ️ 没有新的更改需要推送"
fi

log "========== 备份完成 =========="
