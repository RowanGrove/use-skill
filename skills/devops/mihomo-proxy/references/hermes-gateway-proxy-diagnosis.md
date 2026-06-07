# Hermes Gateway Proxy Diagnosis

## Symptom
Telegram platform fails to connect on a server in China:
```
WARNING gateway.platforms.telegram: [Telegram] Connect attempt 1/8 failed: Timed out — retrying in 1s
ERROR gateway.run: ✗ telegram error: telegram connect timed out after 30s
```

## Diagnosis Checklist

1. **Is Mihomo running?**
   ```bash
   sudo systemctl status mihomo
   curl -s --connect-timeout 3 -x http://127.0.0.1:7890 https://api.telegram.org/bot<TOKEN>/getMe
   ```
   If Mihomo is down: `sudo systemctl start mihomo`

2. **Does the gateway process have proxy env vars?**
   ```bash
   cat /proc/<GATEWAY_PID>/environ | tr '\0' '\n' | grep -i proxy
   ```
   Expected: `HTTP_PROXY=http://127.0.0.1:7890` and `HTTPS_PROXY=http://127.0.0.1:7890`

3. **Is the systemd unit file correct?**
   Check `~/.config/systemd/user/hermes-gateway.service`:
   ```ini
   Environment="HTTP_PROXY=http://127.0.0.1:7890"
   Environment="HTTPS_PROXY=http://127.0.0.1:7890"
   ```

4. **Verify proxy connectivity** (independent of gateway):
   ```bash
   export HTTP_PROXY=http://127.0.0.1:7890
   curl -s "https://api.telegram.org/bot<TOKEN>/getMe"
   ```
   Expected: `{"ok":true,"result":{"id":...,"is_bot":true,...}}`

## Gateway Logs

Key log locations:
- `~/.hermes/logs/gateway.log` — main gateway runtime log
- `journalctl --user -u hermes-gateway.service` — systemd journal (user service)
- `sudo journalctl -u hermes-gateway.service` — only if it's a system service

## Known Good Config

Line to add in `~/.config/systemd/user/hermes-gateway.service` after `Environment="HERMES_HOME=..."`:

```
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
```

Then restart:
```bash
sudo -u ubuntu XDG_RUNTIME_DIR=/run/user/1000 systemctl --user daemon-reload
sudo -u ubuntu XDG_RUNTIME_DIR=/run/user/1000 systemctl --user restart hermes-gateway
```

## Proxy Auto-Detection

Hermes Gateway 0.6.x+ auto-detects `HTTP_PROXY` from the environment and passes it explicitly to the Telegram HTTPXRequest adapter. Success is logged as:
```
[Telegram] Proxy detected; passing explicitly to HTTPXRequest: http://127.0.0.1:7890
[Telegram] Connected to Telegram (polling mode)
✓ telegram connected
```
