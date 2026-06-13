# FreeLLM API 备份策略（实战记录）

## 环境
- 服务器：腾讯云 Ubuntu，国内网络（需 Mihomo 代理）
- 应用：FreeLLM API（localhost:3001）
- 已配置 11 个 LLM 提供商，108 个模型
- 数据库：SQLite（`/home/ubuntu/freellmapi/server/data/freeapi.db`）

## 备份清单

### ✅ 必须备份（缺一不可）
| 文件 | 路径 | 备注 |
|------|------|------|
| 数据库 | `~/freellmapi/server/data/freeapi.db` | 全部 API Keys（加密）、模型路由、用量统计 |
| 环境变量 | `~/freellmapi/.env` | ENCRYPTION_KEY，用于解密 db |
| Hermes 配置 | `~/.hermes/config.yaml` | custom_providers 定义 |

> **⚠️ `.env` 是整个备份中最关键的文件！** 数据库中的 API Keys 是用 `ENCRYPTION_KEY` 加密存储的。即使有 `freeapi.db`，没有原始的 `ENCRYPTION_KEY` 也无法解密。丢失 `.env` 等于丢失所有 API Key。

### ❌ 不需要备份
- `node_modules/`、`client/dist/`、`docker/` — 项目本身，重新 `npm install` 即可
- 系统服务文件（`/etc/systemd/system/freellmapi.service`）— 记录在 SKILL.md 中

### 额外备份：部署文档（skill）
作为部署文档的 `freellmapi-deployment` skill 本身也会同步到仓库的 `skills/` 目录下，这样在任何新机器上都能直接参照部署。

## 脚本文件位置

自动备份脚本已纳入 skill 的 `scripts/` 目录，可以直接引用：
- `~/.hermes/skills/mlops/freellmapi-deployment/scripts/freellmapi_backup.sh`
- 自动备份路径：`~/.hermes/scripts/freellmapi_backup.sh`（由 `cronjob` 工具引用）

## 安全原则

**不做任何脱敏/过滤！** 备份目的是灾难恢复，缺任何一个文件都可能导致无法还原 API Keys。API Keys 在 db 中已用 ENCRYPTION_KEY 加密存储，两层保护已经足够。

## 动态 README 生成

每次备份自动生成 `README.md`，内容包含：
- 最新备份时间戳（北京时间）
- 从 SQLite 实时查询的已配置平台列表
- 快速恢复步骤

仅当内容有变化时才覆盖文件，避免无变更的 git commit 噪声。

## SHA256 验证备份完整性

备份推送到远程后，可通过 SHA256 校验确认文件一致性：

```bash
# 克隆远程仓库到临时目录
cd /tmp && gh repo clone <user>/<repo> verify

# 逐个对比文件
sha256sum ~/freellmapi/server/data/freeapi.db
sha256sum verify/freeapi.db
# 两个输出一致则备份有效
```

## 备份工具选择

| 方式 | 优点 | 缺点 |
|------|------|------|
| 私有 GitHub 仓库 | 简单、版本控制、多地备份 | GitHub 宕机时不可用 |
| COS/S3 对象存储 | 可靠、便宜 | 需要额外配置 s3cmd |
| 本地定时 cp | 无外部依赖 | 服务器炸了备份也跟着炸 |

推荐：**GitHub 私有仓库 + 每天凌晨 cron 自动推送**。故障时只需 `git clone` 即可恢复。

## Cron 配置要点

使用 Hermes 内置 cron 的 `no_agent=true` 模式（watchdog 模式）：
- 脚本成功 → stdout 为空 → 不发送消息（不打扰用户）
- 脚本失败 → stdout 非空 → 自动推送错误日志到 Telegram
- 无需 LLM 参与，零 token 消耗

**重要：脚本必须放在 `~/.hermes/scripts/` 下**，cron 引用时只用文件名，不用绝对路径。

配置命令：
```
cronjob(action='create', name='FreeLLM API 自动备份', no_agent=true,
        schedule='0 1 * * *', script='freellmapi_backup.sh')
```

## 恢复流程

```bash
# 1. 拉取备份
git clone https://github.com/<user>/freellmapi-backup.git

# 3. 恢复文件
cp freeapi.db         ~/freellmapi/server/data/freeapi.db
cp .env               ~/freellmapi/.env
cp hermes_config.yaml ~/.hermes/config.yaml
cp -r skills/freellmapi-deployment ~/.hermes/skills/mlops/

# 3. 重启服务
sudo systemctl restart freellmapi
hermes gateway restart

# 4. 验证
curl http://localhost:3001/v1/models -H "Authorization: Bearer <key>"
# 应该返回所有已配置的模型列表
```
