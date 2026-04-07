"""
LLM Client Wrapper
Unified OpenAI format API calls
Supports Ollama num_ctx parameter to prevent prompt truncation

Hot-swap support: reads LLM config from runtime_llm_config.json on every call
(with a 5-second cache) so base_url/model/api_key can change while the
simulation subprocess is still running — no restart needed.
"""
import logging
logger = logging.getLogger(__name__)

import json
import os
import re
import tempfile
import threading
import time
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config


# ---------------------------------------------------------------------------
# Module-level runtime config cache — shared by ALL LLMClient instances.
# Using a module-level cache (not per-instance) means that when one instance
# refreshes the file, all other instances in the same process benefit immediately.
# ---------------------------------------------------------------------------

# Absolute path to runtime_llm_config.json at the project root.
# __file__ is  backend/app/utils/llm_client.py  →  ../../../  is project root.
_RUNTIME_CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../../runtime_llm_config.json')
)

# How long (seconds) to keep the cached config before re-reading the file.
# 5 s is short enough to feel responsive but avoids a disk read on every token.
_CONFIG_CACHE_TTL = 30.0

# Cache state: {"data": dict|None, "ts": float}
_runtime_config_cache: Dict[str, Any] = {"data": None, "ts": 0.0}

# Lock ensures only one thread reads the file at a time; all others wait and
# then use the freshly-cached value — no duplicate disk reads under load.
_runtime_config_lock = threading.Lock()


def _get_runtime_config() -> Dict[str, str]:
    """
    Return the effective LLM config dict {"api_key", "base_url", "model"}.

    Priority order:
      1. runtime_llm_config.json  (hot-swappable, checked every 5 s)
      2. Config.LLM_*             (fallback if file is missing or malformed)

    Thread-safe: a single threading.Lock guards the cache so concurrent calls
    from the simulation's worker threads don't cause duplicate reads or a torn
    write to the cache dict.
    """
    with _runtime_config_lock:
        now = time.time()

        # Return cached value if it is still fresh
        if _runtime_config_cache["data"] is not None and (now - _runtime_config_cache["ts"]) < _CONFIG_CACHE_TTL:
            return _runtime_config_cache["data"]

        # Cache expired (or first call) — read from disk
        try:
            with open(_RUNTIME_CONFIG_PATH, 'r') as f:
                data = json.load(f)
            logger.debug(f"[LLM] Runtime config loaded from {_RUNTIME_CONFIG_PATH}")
        except FileNotFoundError:
            # File doesn't exist yet → fall back to static Config values
            logger.debug("[LLM] runtime_llm_config.json not found, using Config defaults")
            data = {
                "api_key": Config.LLM_API_KEY,
                "base_url": Config.LLM_BASE_URL,
                "model": Config.LLM_MODEL_NAME,
            }
        except json.JSONDecodeError as e:
            # File exists but is being written right now (torn write) or is corrupt.
            # Keep whatever was in cache previously; if cache is empty, fall back to Config.
            logger.warning(f"[LLM] runtime_llm_config.json parse error ({e}), keeping previous config")
            if _runtime_config_cache["data"] is not None:
                return _runtime_config_cache["data"]
            data = {
                "api_key": Config.LLM_API_KEY,
                "base_url": Config.LLM_BASE_URL,
                "model": Config.LLM_MODEL_NAME,
            }

        # .env values always override runtime_llm_config.json when defined
        if Config.LLM_API_KEY:
            data["api_key"] = Config.LLM_API_KEY
        if Config.LLM_BASE_URL:
            data["base_url"] = Config.LLM_BASE_URL
        if Config.LLM_MODEL_NAME:
            data["model"] = Config.LLM_MODEL_NAME

        _runtime_config_cache["data"] = data
        _runtime_config_cache["ts"] = now
        return data


def save_runtime_config(data: Dict[str, str]) -> None:
    """
    Write a new LLM config to runtime_llm_config.json atomically.

    "Atomic" here means: write to a temp file in the same directory, then
    os.replace() it over the real file. os.replace() is guaranteed by POSIX
    to be atomic — a reader will always see either the old file or the new
    file, never a half-written one.

    Also invalidates the in-process cache so the next _get_runtime_config()
    call returns the new values immediately (no need to wait 5 s).
    """
    dir_path = os.path.dirname(_RUNTIME_CONFIG_PATH)
    # Write to a temp file in the same directory so os.replace can use a
    # rename (same filesystem) instead of a copy — this is what makes it atomic.
    with tempfile.NamedTemporaryFile('w', delete=False, dir=dir_path, suffix='.tmp') as tf:
        json.dump(data, tf, indent=2)
        temp_name = tf.name

    os.replace(temp_name, _RUNTIME_CONFIG_PATH)

    # Invalidate in-process cache immediately — callers see new config on the next call
    with _runtime_config_lock:
        _runtime_config_cache["data"] = data
        _runtime_config_cache["ts"] = time.time()

    logger.info(f"[LLM] Runtime config updated → base_url={data.get('base_url')} model={data.get('model')}")


# ---------------------------------------------------------------------------
# LLMClient
# ---------------------------------------------------------------------------

class LLMClient:
    """
    LLM Client with hot-swap support.

    On every chat() call the client resolves the effective (api_key, base_url,
    model) from runtime_llm_config.json (cached 5 s).  If base_url or api_key
    changed since the last call, the internal OpenAI client is transparently
    recreated — the caller never needs to do anything.

    Explicit constructor arguments (api_key, base_url, model) act as hard
    overrides and always take priority over the runtime file.  This preserves
    backward-compatibility for callers that pass their own credentials.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 600.0
    ):
        # Store explicit overrides — None means "use runtime config / Config fallback"
        self._override_api_key = api_key
        self._override_base_url = base_url
        self._override_model = model
        self._timeout = timeout

        # Resolve config once at construction to validate and build initial client
        cfg = self._resolve_config()

        if not cfg["api_key"]:
            raise ValueError("LLM_API_KEY not configured")

        # Track what the current OpenAI client was created with so _ensure_client()
        # knows when it needs to recreate it.
        self._active_api_key = cfg["api_key"]
        self._active_base_url = cfg["base_url"]

        self.client = OpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            timeout=timeout,
        )

        # Ollama context window size — prevents prompt truncation.
        # Read from env OLLAMA_NUM_CTX, default 8192 (Ollama default is only 2048).
        self._num_ctx = int(os.environ.get('OLLAMA_NUM_CTX', '8192'))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_config(self) -> Dict[str, str]:
        """
        Merge explicit constructor overrides with the current runtime config.

        Priority: explicit arg > runtime_llm_config.json > Config static defaults.
        Returns a dict with keys: api_key, base_url, model.
        """
        rt = _get_runtime_config()
        return {
            "api_key":  self._override_api_key  or rt.get("api_key")  or Config.LLM_API_KEY,
            "base_url": self._override_base_url or rt.get("base_url") or Config.LLM_BASE_URL,
            "model":    self._override_model    or rt.get("model")    or Config.LLM_MODEL_NAME,
        }

    def _ensure_client(self, api_key: str, base_url: str) -> None:
        """
        Recreate the internal OpenAI client if base_url or api_key changed.

        The OpenAI SDK fixes base_url at construction time, so a new instance
        is required whenever the endpoint changes.  The comparison is a cheap
        string equality check that runs on every chat() call.
        """
        if self._active_base_url != base_url or self._active_api_key != api_key:
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=self._timeout,
            )
            self._active_base_url = base_url
            self._active_api_key = api_key
            logger.info(f"[LLM] OpenAI client recreated → base_url={base_url}")

    def _is_ollama(self, base_url: str) -> bool:
        """Return True if base_url points to an Ollama server (port 11434)."""
        return '11434' in (base_url or '')

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Send chat request

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Max token count
            response_format: Response format (e.g., JSON mode)

        Returns:
            Model response text
        """
        # Resolve fresh config on every call (file re-read at most every 5 s)
        cfg = self._resolve_config()

        # Transparently swap the OpenAI client if the endpoint or key changed
        self._ensure_client(cfg["api_key"], cfg["base_url"])

        kwargs = {
            "model": cfg["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        # For Ollama: pass num_ctx via extra_body to prevent prompt truncation
        if self._is_ollama(cfg["base_url"]) and self._num_ctx:
            kwargs["extra_body"] = {
                "options": {"num_ctx": self._num_ctx}
            }

        start = time.time()
        logger.info(f"[LLM] >>> llamando modelo={cfg['model']} | mensajes={len(messages)} | max_tokens={max_tokens}")

        response = self.client.chat.completions.create(**kwargs)

        elapsed = time.time() - start
        usage = response.usage
        logger.info(f"[LLM] <<< respuesta en {elapsed:.1f}s | prompt={usage.prompt_tokens} completion={usage.completion_tokens} total={usage.total_tokens} tokens")

        content = response.choices[0].message.content
        # Some models (like MiniMax M2.5) include <think>thinking content in response, need to remove
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send chat request and return JSON

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Max token count

        Returns:
            Parsed JSON object
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # Clean markdown code block markers
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON format from LLM: {cleaned_response}")
