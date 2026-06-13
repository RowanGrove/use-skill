# FreeLLMAPI Dashboard Auth

## Login Credentials

- Email: your@email.com
- Password: stored in memory (set via `/api/auth/setup` after deleting old user)

## Password Rules

- Minimum 8 characters
- No built-in "change password" endpoint
- To reset: delete user from SQLite, then call `/api/auth/setup`:
  ```sql
  sqlite3 ~/freellmapi/server/data/freeapi.db "DELETE FROM sessions; DELETE FROM users;"
  curl -X POST http://localhost:3001/api/auth/setup \
    -H "Content-Type: application/json" \
    -d '{"email":"your@email.com","password":"<new_pw>"}'
  ```

## Brute-Force Lockout

- 5 failed attempts → 15 minute lockout (per email)
- Lockout is **in-memory** (not persisted to DB)
- To clear: restart the service
  ```bash
  sudo systemctl restart freellmapi.service
  ```

## Session Management

- Sessions last 30 days
- browser-act cookies stored in stealth browser 100287258835473970
- After password reset: must log in via browser to refresh cookie
