# mem0 长期记忆 Skill

## 目标
为 Hermes 提供跨会话、向量化的长期记忆，弥补系统提示 2k‑token 上限。

## API（本机 127.0.0.1:8000）
- `POST /store`   {"user_id": str, "text": str, "tags": [str]}
- `POST /search`  {"user_id": str, "query": str, "top_k": int}
- `POST /forget`  {"user_id": str, "memory_id": str}
- `GET  /list`    {"user_id": str, "limit": int}

## Python 示例（已在虚拟环境 `~/mem0_venv` 中）
```python
import requests, json
BASE = "http://127.0.0.1:8000"

def mem0_store(uid, txt, tags=None):
    r = requests.post(f"{BASE}/store", json={"user_id": uid, "text": txt, "tags": tags or []})
    return r.json()  # 包含 memory_id

def mem0_query(uid, q, k=5):
    r = requests.post(f"{BASE}/search", json={"user_id": uid, "query": q, "top_k": k})
    return r.json().get("results", [])

def mem0_forget(uid, mid):
    r = requests.post(f"{BASE}/forget", json={"user_id": uid, "memory_id": mid})
    return r.json()

def mem0_list(uid, limit=10):
    r = requests.get(f"{BASE}/list", params={"user_id": uid, "limit": limit})
    return r.json().get("results", [])
```

## 使用方式（在聊天中直接调用）
```
mem0_store("5981641465", "我今天跑了5公里，状态很好。", ["跑步","健康"])
mem0_query("5981641465", "我的跑步记录")
```

系统会把检索到的记忆自动注入到系统提示中，帮助保持对话连贯。
