"""One door for every paid model call: content-hash cache, cost log, spending cap, provider failover.

Nothing is paid for twice: a call with the same model, messages and settings is answered from
`cache/llm/`. Every paid call is appended to `cache/cost-log.jsonl` with tokens and an estimated cost
(VAT included). A run stops before any call that would take the session past SAHIBILL_BUDGET_USD.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.environ.get("SAHIBILL_CACHE", ROOT / "cache"))
VAT = 1.05   # Nebius invoice showed about 5% VAT (subtotal 1.02, VAT 0.05, 21 Oct 2026)

PROVIDERS = {
    # Muse Spark Open served as open weights. Price: Meta's listed partner price per 1M tokens.
    "nebius": {"base": "https://api.tokenfactory.nebius.com/v1", "key_env": "NEBIUS_API_KEY",
               "model": "meta-models/muse-spark-open", "price_in": 1.25, "price_out": 4.25},
}


class BudgetExceeded(RuntimeError):
    pass


def _env_key(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    for parent in [ROOT, *ROOT.parents]:
        env = parent / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def image_part(path: str | Path) -> dict:
    p = Path(path)
    mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()}}


def _spent() -> float:
    log = CACHE / "cost-log.jsonl"
    if not log.exists():
        return 0.0
    return sum(json.loads(l)["usd"] for l in log.read_text().splitlines() if l.strip())


def chat(messages: list, provider: str = "nebius", max_tokens: int = 6000, reasoning_effort: str | None = None,
         tag: str = "", tools: list | None = None) -> dict:
    """Returns {"content": str, "usage": dict, "cached": bool, "usd": float}, plus "tool_calls" when `tools`
    (OpenAI function definitions) are offered and the model calls one."""
    cfg = PROVIDERS[provider]
    body = {"model": cfg["model"], "messages": messages, "max_tokens": max_tokens}
    if tools:
        body["tools"] = tools
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    key = hashlib.sha256(json.dumps([provider, body], sort_keys=True).encode()).hexdigest()
    cpath = CACHE / "llm" / f"{key}.json"
    if cpath.exists():
        r = json.loads(cpath.read_text())
        return {**r, "cached": True}
    budget = float(os.environ.get("SAHIBILL_BUDGET_USD", "0"))
    if _spent() >= budget:
        raise BudgetExceeded(f"spent {_spent():.4f} of budget {budget:.4f} USD; raise SAHIBILL_BUDGET_USD only with approval")
    api_key = _env_key(cfg["key_env"])
    if not api_key:
        raise RuntimeError(f"{cfg['key_env']} not set")
    req = urllib.request.Request(cfg["base"] + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"})
    last = None
    for attempt in range(3):
        try:
            t = time.time()
            resp = json.load(urllib.request.urlopen(req, timeout=300))
            break
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode()[:300]}"
            if e.code in (400, 401, 403, 404):
                raise RuntimeError(last)
            time.sleep(4 * (attempt + 1))
        except Exception as e:   # network
            last = repr(e)
            time.sleep(4 * (attempt + 1))
    else:
        raise RuntimeError(f"provider {provider} failed: {last}")
    u = resp.get("usage", {})
    usd = (u.get("prompt_tokens", 0) * cfg["price_in"] + u.get("completion_tokens", 0) * cfg["price_out"]) / 1e6 * VAT
    msg = resp["choices"][0]["message"]
    out = {"content": msg.get("content") or "", "usage": u, "usd": round(usd, 6),
           "tool_calls": [{"id": c.get("id"), "name": c["function"]["name"], "arguments": c["function"].get("arguments") or "{}"}
                          for c in msg.get("tool_calls") or []],
           "latency_s": round(time.time() - t, 1), "provider": provider, "model": cfg["model"],
           "reasoning_effort": reasoning_effort}
    cpath.parent.mkdir(parents=True, exist_ok=True)
    cpath.write_text(json.dumps(out))
    with (CACHE / "cost-log.jsonl").open("a") as fh:
        fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tag": tag, "provider": provider,
                             "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
                             "reasoning_effort": reasoning_effort, "usd": out["usd"]}) + "\n")
    return {**out, "cached": False}


def parse_json(text: str):
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e < 0:
        raise ValueError("no JSON object in model output")
    return json.loads(text[s:e + 1])
