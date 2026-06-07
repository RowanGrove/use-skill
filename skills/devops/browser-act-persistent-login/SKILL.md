---
name: browser-act-persistent-login
description: |
  使用 browser-act 的 stealth browser 实现多站点自动登录和 cookie 持久化。
  每个站点可以配置独立的账号密码，一次自动登录后永久复用。
  不再需要手动登录或重复输入密码。
category: devops
---

# browser-act 持久化登录

## 原理

`browser-act` 的 **stealth browser** 自带持久化 profile。只要创建一个 browser，
所有通过 `--session <name> browser open <browser_id>` 打开的窗口都自动
共享该 browser 的 **cookie、localStorage、sessionStorage**。

## 快速开始

### 1️⃣ 创建 stealth browser（只需一次）

```bash
browser-act browser create \
  --name "<site-name>" \
  --type stealth \
  --desc "自动登录 <site-url>，持久化 cookie"
```

记录返回的 `<browser_id>`。

### 2️⃣ 自动登录（填写表单 + 提交）

```bash
# 打开 browser 进入登录页
browser-act --session login-s1 browser open <browser_id> "https://<site>/login"

# 查看页面状态，找到登录表单元素索引
browser-act --session login-s1 state
# 输出示例：
#   [3] <input id=auth-email ...>
#   [5] <input id=auth-password ...>
#   [6] <button type=submit> Sign in

# 填写用户名/密码
browser-act --session login-s1 input <email_index> "user@example.com"
browser-act --session login-s1 input <pwd_index> "your_password"

# 点击登录按钮
browser-act --session login-s1 click <submit_button_index>

# 等待页面稳定
browser-act --session login-s1 wait stable --timeout 30000

# 验证登录成功（查看是否出现 Sign out、用户名等）
browser-act --session login-s1 state

# 关闭本次 session（cookie 已自动保存到 browser 的 profile 中）
browser-act session close login-s1
```

### 3️⃣ 后续复用登录状态

**任意 session 名、任意时间**，只要使用同一个 browser ID：

```bash
browser-act --session my-new-task browser open <browser_id> "https://<site>/dashboard"
```

✅ **无需再次登录**，cookie 自动带上。

### 4️⃣ 查看已存在的 browser

```bash
browser-act browser list
```

### 5️⃣ 失效处理（需要重新登录时）

```bash
browser-act browser delete <browser_id>
# 重新执行步骤 1 和 2
```

## 多站点管理

每增加一个站点：

| 步骤 | 操作 |
|------|------|
| 1 | `browser-act browser create --name "<site-name>" --type stealth` |
| 2 | 将其 browser ID 记录下来 |
| 3 | 按上述步骤 2 完成一次自动登录即可 |
| 4 | 后续所有操作指定该 browser ID 即可复用 |

> **安全提示**：密码不应明文写入 SKILL.md。可保存在 `~/.browser-act-secrets/<site>.env`
> （已在 .gitignore 中排除），脚本运行前读取环境变量注入。

## 注意事项

- Stealth browser 需要 browser-act API key（运行 `browser-act auth login` 获取）
- 登录表单的选择器（`input`、`button` 索引）需要根据 `state` 输出确认
- 如果网站有 CAPTCHA 或 2FA，需要人工配合一次（使用 `--headed` 模式）
- 本地服务（如 localhost）不需要代理；外部网站可能需要通过 Mihomo 代理访问
