"""
LLM Config API
Read-only endpoint to inspect the active LLM configuration from .env.
To change the config, update .env and restart the backend.
"""
from flask import jsonify

from . import config_bp
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.config')


@config_bp.route('/llm', methods=['GET'])
def get_llm_config():
    """
    GET /api/config/llm
    Returns the currently active LLM configuration from .env.
    The api_key field is masked to avoid leaking credentials.
    """
    api_key = Config.LLM_API_KEY or ""
    return jsonify({
        "api_key":  api_key[:6] + "***" if api_key else "",
        "base_url": Config.LLM_BASE_URL or "",
        "model":    Config.LLM_MODEL_NAME or "",
    })
