"""
LLM Config API
Exposes endpoints to read and hot-swap the runtime LLM configuration
(api_key, base_url, model) without restarting the backend or losing
simulation state in Neo4j.
"""
import os
from flask import request, jsonify

from . import config_bp
from ..utils.llm_client import _get_runtime_config, save_runtime_config
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.config')


@config_bp.route('/llm', methods=['GET'])
def get_llm_config():
    """
    GET /api/config/llm

    Returns the currently active LLM configuration — whatever is in
    runtime_llm_config.json (or the Config defaults if the file is absent).

    The api_key field is masked in the response to avoid leaking credentials
    in browser network tabs / logs.
    """
    cfg = _get_runtime_config()
    return jsonify({
        # Mask the key: show only the first 6 chars followed by ***
        "api_key":  cfg.get("api_key", "")[:6] + "***" if cfg.get("api_key") else "",
        "base_url": cfg.get("base_url", ""),
        "model":    cfg.get("model", ""),
    })


@config_bp.route('/llm', methods=['POST'])
def update_llm_config():
    """
    POST /api/config/llm

    Body (JSON) — all fields optional, only provided fields are updated:
      {
        "api_key":  "ollama",
        "base_url": "http://100.123.212.63:11434/v1",
        "model":    "qwen2.5:7b"
      }

    What happens after a successful call:
      1. runtime_llm_config.json is rewritten atomically (os.replace).
      2. The in-process cache is invalidated immediately.
      3. os.environ is updated for the backend process (helps libraries that
         read OPENAI_API_KEY / OPENAI_API_BASE_URL at call-time rather than
         import-time, e.g. some CAMEL-AI code paths).
      4. The next LLMClient.chat() call — even in a running simulation
         subprocess — will pick up the new values automatically.

    Note: CAMEL-AI agents that already imported their config at subprocess
    start will NOT be affected by the os.environ update (they captured the
    values at import time).  Only LLMClient (our wrapper) is fully hot-swapped.
    """
    body = request.get_json(silent=True) or {}

    # Reject completely empty payloads early
    if not any(k in body for k in ("api_key", "base_url", "model")):
        return jsonify({"error": "Provide at least one of: api_key, base_url, model"}), 400

    # Start from the current config so partial updates are non-destructive
    current = _get_runtime_config()
    new_cfg = {
        "api_key":  body.get("api_key",  current.get("api_key",  "")),
        "base_url": body.get("base_url", current.get("base_url", "")),
        "model":    body.get("model",    current.get("model",    "")),
    }

    # Persist to disk (atomic write) and invalidate the in-process cache
    save_runtime_config(new_cfg)

    # Also push into os.environ so libraries that read env vars at call-time
    # (not at import-time) pick up the change in this process.
    os.environ["LLM_API_KEY"]   = new_cfg["api_key"]
    os.environ["LLM_BASE_URL"]  = new_cfg["base_url"]
    os.environ["LLM_MODEL_NAME"] = new_cfg["model"]
    # CAMEL-AI / OASIS reads these specific env var names
    os.environ["OPENAI_API_KEY"]      = new_cfg["api_key"]
    os.environ["OPENAI_API_BASE_URL"] = new_cfg["base_url"]

    logger.info(f"[Config] LLM config updated via API → base_url={new_cfg['base_url']} model={new_cfg['model']}")

    return jsonify({
        "status": "ok",
        "message": "LLM config updated. Next LLMClient call will use the new values.",
        "config": {
            # Mask the key in the response
            "api_key":  new_cfg["api_key"][:6] + "***" if new_cfg["api_key"] else "",
            "base_url": new_cfg["base_url"],
            "model":    new_cfg["model"],
        }
    })
