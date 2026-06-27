"""
Persistencia del estado Elliott en GitHub — mismo patrón que growth/gh_store.py.
Guarda: proyecciones diarias, historial de precisión.
"""

import os, json, base64, requests

REPO = os.getenv("GITHUB_STATE_REPO", "claudemdai-cell/EliotteAlartBot")
PATH = "state/elliott_state.json"
API  = f"https://api.github.com/repos/{REPO}/contents/{PATH}"
_sha: dict = {"v": None}


def _headers() -> dict | None:
    token = os.getenv("GITHUB_STATE_TOKEN")
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def load() -> dict:
    h = _headers()
    if not h:
        return {}
    try:
        r = requests.get(API, headers=h, timeout=15)
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        d = r.json()
        _sha["v"] = d.get("sha")
        return json.loads(base64.b64decode(d["content"]).decode("utf-8"))
    except Exception as e:
        print(f"[ESTORE] load: {e}")
        return {}


def save(state: dict) -> bool:
    h = _headers()
    if not h:
        return False
    try:
        content = base64.b64encode(
            json.dumps(state, indent=2, ensure_ascii=False).encode()
        ).decode()
        payload = {"message": "backup: elliott state", "content": content}
        if _sha["v"]:
            payload["sha"] = _sha["v"]
        r = requests.put(API, headers=h, json=payload, timeout=15)
        if r.status_code in (409, 422):
            g = requests.get(API, headers=h, timeout=15)
            if g.status_code == 200:
                payload["sha"] = g.json().get("sha")
                r = requests.put(API, headers=h, json=payload, timeout=15)
        r.raise_for_status()
        _sha["v"] = r.json().get("content", {}).get("sha")
        return True
    except Exception as e:
        print(f"[ESTORE] save: {e}")
        return False
