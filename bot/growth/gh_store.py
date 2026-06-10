"""
Backup del estado en GitHub (Contents API).
Render free tiene disco efimero: cada deploy/reinicio borra el archivo local.
Este modulo guarda state/growth_state.json en el propio repo para recuperarlo.

Env vars:
  GITHUB_STATE_TOKEN — fine-grained PAT con permiso Contents (read/write) sobre el repo.
  GITHUB_STATE_REPO  — opcional, default "claudemdai-cell/EliotteAlartBot".
"""

import os
import json
import base64
import requests

REPO = os.getenv("GITHUB_STATE_REPO", "claudemdai-cell/EliotteAlartBot")
PATH = "state/growth_state.json"
API = f"https://api.github.com/repos/{REPO}/contents/{PATH}"

# SHA del archivo en GitHub (necesario para actualizarlo); se cachea entre llamadas
_sha_cache: dict = {"sha": None}


def _headers() -> dict | None:
    token = os.getenv("GITHUB_STATE_TOKEN")
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def enabled() -> bool:
    return bool(os.getenv("GITHUB_STATE_TOKEN"))


def download() -> dict | None:
    """Descarga el estado desde GitHub. None si no existe o falla."""
    headers = _headers()
    if not headers:
        return None
    try:
        r = requests.get(API, headers=headers, timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        _sha_cache["sha"] = data.get("sha")
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content)
    except Exception as e:
        print(f"[GH_STORE] Error descargando estado: {e}")
        return None


def upload(state: dict) -> bool:
    """Sube el estado a GitHub. Maneja el SHA para actualizaciones."""
    headers = _headers()
    if not headers:
        return False
    try:
        content = base64.b64encode(
            json.dumps(state, indent=2, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        payload = {
            "message": "backup: growth state",
            "content": content,
        }
        if _sha_cache["sha"]:
            payload["sha"] = _sha_cache["sha"]

        r = requests.put(API, headers=headers, json=payload, timeout=15)
        if r.status_code == 409 or (r.status_code == 422 and "sha" in r.text):
            # SHA desactualizado: refrescar y reintentar una vez
            g = requests.get(API, headers=headers, timeout=15)
            if g.status_code == 200:
                payload["sha"] = g.json().get("sha")
                r = requests.put(API, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        _sha_cache["sha"] = r.json().get("content", {}).get("sha")
        return True
    except Exception as e:
        print(f"[GH_STORE] Error subiendo estado: {e}")
        return False
