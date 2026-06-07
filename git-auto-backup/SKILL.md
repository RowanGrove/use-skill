---
name: git-auto-backup
description: After creating/updating persistent files, auto-add, sanitize secrets, commit, and push to the use-skill repo.
---

# Git Auto-Backup

每次创建或更新持久化文件后，自动备份到 ~/use-skill/ (RowanGrove/use-skill)。

## 步骤

1. `cd ~/use-skill && git add <file-path>`
2. 提交前 grep diff 中的敏感内容：
   - `sk-`（API keys）
   - `github_pat_`
   - `freellmapi-[a-f0-9]`（FreeLLM API tokens）
   - 密码明文
   - token/secret 字样的值
3. 将真实密钥替换为占位符后再 commit
4. `git commit -m "<描述>" && git push`

## 仓库配置

- 路径：`~/use-skill`
- 远程：`RowanGrove/use-skill`，分支 main
- 认证：HTTPS credential store (~/.git-credentials)
- 代理：`http://127.0.0.1:7890` for github.com

## 安全规则

**绝对不要**将真实 API keys、token、密码、订阅 URL 提交到仓库。
