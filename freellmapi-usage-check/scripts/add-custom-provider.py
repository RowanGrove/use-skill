def add_custom_provider(base_url, model, api_key, password, label="Custom"):
    """添加 custom OpenAI-compatible provider 到 FreeLLMAPI

    用法:
        result = add_custom_provider(
            "https://apihub.agnes-ai.com/v1",
            "agnes-2.0-flash",
            "sk-xxx",
            "<dashboard密码>",
            "Agnes AI"
        )
        # → {"success": true, "keyId": 24, "modelDbId": 1214, ...}

    注意: model 名必须与上游 API 完全一致（大小写敏感）
    """
    import urllib.request, json

    # 获取 dashboard session token
    req = urllib.request.Request(
        "http://localhost:3001/api/auth/login",
        data=json.dumps({"email": "your@email.com", "password": password}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    token = json.loads(resp.read())["token"]

    # 注册自定义 provider
    data = json.dumps({
        "baseUrl": base_url,
        "model": model,
        "displayName": model,
        "apiKey": api_key,
        "label": label,
    }).encode()

    req = urllib.request.Request(
        "http://localhost:3001/api/keys/custom",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())
