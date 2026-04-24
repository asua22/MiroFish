"""
LLM Client Wrapper
Unified OpenAI format API calls
Supports Ollama num_ctx parameter to prevent prompt truncation
"""
import logging
logger = logging.getLogger(__name__)

import json
import os
import re
import time
from typing import Optional, Dict, Any, List
from openai import OpenAI
import requests

from ..config import Config


class LLMClient:
    """
    LLM Client. Reads config from .env (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME).
    To change the model, update .env and restart the backend.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 600.0
    ):
        self._api_key = api_key or Config.LLM_API_KEY
        self._base_url = base_url or Config.LLM_BASE_URL
        self._model = model or Config.LLM_MODEL_NAME
        self._timeout = timeout

        if not self._api_key:
            raise ValueError("LLM_API_KEY not configured")

        self.client = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=timeout,
        )

        # Ollama context window size — prevents prompt truncation.
        # Read from env OLLAMA_NUM_CTX, default 8192 (Ollama default is only 2048).
        self._num_ctx = int(os.environ.get('OLLAMA_NUM_CTX', '8192'))

    def _is_ollama(self, base_url: str) -> bool:
        """
        Detect if base_url points to an Ollama instance.

        Checks if URL contains port 11434 (default Ollama port).
        This detection is used to route requests to the appropriate
        constrained decoding implementation (native /api/chat vs response_format).

        Args:
            base_url (str): API base URL to check

        Returns:
            bool: True if Ollama detected, False otherwise

        Examples:
            >>> client._is_ollama("http://localhost:11434/v1")
            True
            >>> client._is_ollama("https://api.openai.com/v1")
            False
        """
        return '11434' in (base_url or '')

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
        kwargs = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        # For Ollama: pass num_ctx via extra_body to prevent prompt truncation
        if self._is_ollama(self._base_url) and self._num_ctx:
            kwargs["extra_body"] = {
                "options": {"num_ctx": self._num_ctx}
            }

        start = time.time()
        logger.info(f"[LLM] >>> llamando modelo={self._model} | mensajes={len(messages)} | max_tokens={max_tokens}")

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
        max_tokens: int = 4096,
        json_schema: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Send chat request and return JSON with intelligent routing for structured outputs.

        Intelligently routes to appropriate constrained decoding implementation based on
        LLM provider and schema availability:

        - **Rama A (Ollama + Schema):** Native /api/chat with GBNF grammar constrained decoding.
          Guarantees valid JSON at token generation level. Highest reliability for Ollama.

        - **Rama B (OpenAI-compatible + Schema):** response_format json_schema with strict mode.
          Uses OpenAI structured outputs API. Works with OpenAI, Anthropic, and compatible services.

        - **Rama C (No Schema):** json_object mode fallback. Backward compatible, works with
          any model but only hints at JSON format (not guaranteed).

        Args:
            messages (list): Chat messages in OpenAI format
                [{"role": "user", "content": "..."}, ...]
            temperature (float): Sampling temperature (0.0-1.0). Default 0.3 for JSON generation.
            max_tokens (int): Maximum tokens to generate. Default 4096.
            json_schema (dict, optional): JSON Schema for structured output enforcement.
                If provided, routes to Rama A (Ollama) or B (OpenAI-compatible).
                If not provided, uses Rama C fallback.

        Returns:
            dict: Parsed JSON object following the provided schema (if applicable)

        Raises:
            ConnectionError: If unable to reach Ollama endpoint
            TimeoutError: If request times out
            ValueError: If response is not valid JSON
            RuntimeError: If unexpected error occurs during API call

        Examples:
            # With schema (Rama A/B) - Guaranteed JSON validity
            schema = {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"}
                },
                "required": ["name", "age"]
            }
            result = client.chat_json(
                messages=[{"role": "user", "content": "Generate a person"}],
                json_schema=schema
            )

            # Without schema (Rama C) - Backward compatible
            result = client.chat_json(
                messages=[{"role": "user", "content": "Generate JSON"}]
            )
        """
        # Rama A: Ollama Local + Schema (constrained decoding via native endpoint)
        if json_schema and self._is_ollama(self._base_url):
            try:
                return self._chat_json_native_ollama(messages, json_schema, temperature, max_tokens)
            except (ValueError, RuntimeError) as e:
                # Rama A fallback: Si GBNF falla, usar Rama C con json_object mode
                logger.warning(f"[LLM] Rama A falló, fallback a Rama C (json_object): {str(e)[:100]}")
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
                    # Intenta extraer JSON de respuesta que contiene markdown
                    json_match = re.search(r'\{[\s\S]*\}', cleaned_response)
                    if json_match:
                        try:
                            return json.loads(json_match.group())
                        except json.JSONDecodeError:
                            pass
                    raise ValueError(f"Invalid JSON format from LLM: {cleaned_response[:200]}")

        # Rama B: OpenAI-compatible + Schema (structured outputs via response_format)
        elif json_schema:
            return self._chat_json_openai_structured(messages, json_schema, temperature, max_tokens)

        # Rama C: Sin Schema (actual behavior - json_object mode)
        else:
            logger.info(f"[LLM] >>> Rama C (json_object mode)")
            start = time.time()

            response = self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )

            elapsed = time.time() - start
            logger.info(f"[LLM] <<< Rama C en {elapsed:.1f}s")

            # Clean markdown code block markers
            cleaned_response = response.strip()
            cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
            cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
            cleaned_response = cleaned_response.strip()

            try:
                return json.loads(cleaned_response)
            except json.JSONDecodeError:
                # Intenta extraer JSON de respuesta que contiene markdown
                json_match = re.search(r'\{[\s\S]*\}', cleaned_response)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass
                raise ValueError(f"Invalid JSON format from LLM: {cleaned_response[:200]}")

    def _chat_json_native_ollama(
        self,
        messages: List[Dict[str, str]],
        json_schema: Dict[str, Any],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """
        Rama A: Ollama native constrained decoding with GBNF grammar.

        Uses Ollama's native /api/chat endpoint with format parameter to enforce
        JSON schema at token generation level (constrained decoding). This guarantees
        that the output will always be valid JSON matching the provided schema.

        The schema is automatically converted to GBNF (GGML BNF) grammar by Ollama
        for token-level constraint enforcement. This approach is significantly more
        reliable than post-processing for structured outputs.

        Args:
            messages (list): Chat messages in OpenAI format
            json_schema (dict): JSON Schema for GBNF conversion. Should have:
                - "type": "object"
                - "properties": {field_name: field_schema, ...}
                - "required": [required_field_names, ...]
            temperature (float): Sampling temperature (0.0-1.0)
            max_tokens (int): Maximum tokens to generate

        Returns:
            dict: Parsed JSON response following the provided schema.
                Always valid JSON if schema enforcement succeeded.

        Raises:
            ConnectionError: If unable to reach Ollama endpoint
            TimeoutError: If request takes longer than configured timeout
            ValueError: If response cannot be parsed as valid JSON
            RuntimeError: If unexpected error occurs during API call

        Implementation Notes:
            - Uses requests.post() directly (bypasses OpenAI SDK)
            - Removes /v1 from base_url to access native Ollama endpoint
            - Includes num_ctx in options to prevent prompt truncation
            - Cleans markdown code blocks from response before JSON parsing
        """
        # Validate num_ctx is integer
        num_ctx = self._num_ctx
        if not isinstance(num_ctx, int) or num_ctx <= 0:
            logger.warning(f"[LLM] Invalid num_ctx ({num_ctx}), falling back to default 8192")
            num_ctx = 8192

        payload = {
            "model": self._model,
            "messages": messages,
            "format": json_schema,
            "options": {
                "num_ctx": num_ctx,
                "temperature": temperature,
                "top_k": 40,
                "top_p": 0.9,
                "num_predict": max_tokens
            },
            "stream": False
        }

        start = time.time()
        logger.info(f"[LLM] >>> llamando Ollama nativo | modelo={self._model} | schema={bool(json_schema)} | num_ctx={num_ctx}")

        try:
            # Remove /v1 from base_url to get native Ollama endpoint
            native_url = self._base_url.replace("/v1", "") + "/api/chat"
            response = requests.post(
                native_url,
                json=payload,
                timeout=self._timeout
            )
            response.raise_for_status()

            elapsed = time.time() - start
            logger.info(f"[LLM] <<< Ollama nativo en {elapsed:.1f}s")

            data = response.json()
            content = data.get("message", {}).get("content", "")

            # Clean markdown code block markers
            cleaned_response = content.strip()
            cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
            cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
            cleaned_response = cleaned_response.strip()

            try:
                return json.loads(cleaned_response)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON from Ollama native: {cleaned_response}")

        except requests.exceptions.ConnectionError as e:
            logger.error(f"[LLM] ConnectionError a Ollama: {e}")
            raise ConnectionError(f"No se pudo conectar con Ollama: {e}")
        except requests.exceptions.Timeout as e:
            logger.error(f"[LLM] Timeout Ollama: {e}")
            raise TimeoutError(f"Timeout al conectar con Ollama: {e}")
        except Exception as e:
            logger.error(f"[LLM] Error inesperado en Ollama nativo: {e}")
            raise RuntimeError(f"Error inesperado con Ollama: {e}")

    def _chat_json_openai_structured(
        self,
        messages: List[Dict[str, str]],
        json_schema: Dict[str, Any],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """
        Rama B: OpenAI-compatible JSON schema enforcement with response_format.

        Uses OpenAI's response_format parameter with type 'json_schema' and strict mode
        to guarantee JSON output matching the provided schema. This API is available
        from OpenAI, Anthropic Claude API, and other compatible providers.

        When strict mode is enabled, the model is constrained to only output values
        that strictly adhere to the provided schema (not just valid JSON).

        Args:
            messages (list): Chat messages in OpenAI format
            json_schema (dict): JSON Schema for enforcement. Should be a complete
                OpenAI-compatible schema with:
                - "type": "object"
                - "properties": {field_name: field_schema, ...}
                - "required": [required_field_names, ...]
            temperature (float): Sampling temperature (0.0-1.0)
            max_tokens (int): Maximum tokens to generate

        Returns:
            dict: Parsed JSON response strictly conforming to the provided schema.
                Always valid JSON when strict mode is enforced.

        Raises:
            ValueError: If response cannot be parsed as valid JSON
            RuntimeError: If API returns an error or connection fails

        Implementation Notes:
            - Uses OpenAI client with response_format parameter
            - Sets strict: True for strict schema enforcement
            - Works with OpenAI API and compatible services
            - Cleans markdown code blocks from response before JSON parsing
        """
        logger.info(f"[LLM] >>> Rama B (OpenAI structured) | modelo={self._model} | schema=True")
        start = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "schema": json_schema,
                        "strict": True
                    }
                },
                temperature=temperature,
                max_tokens=max_tokens
            )

            elapsed = time.time() - start
            logger.info(f"[LLM] <<< Rama B en {elapsed:.1f}s")

            content = response.choices[0].message.content

            # Clean markdown code block markers
            cleaned_response = content.strip()
            cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
            cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
            cleaned_response = cleaned_response.strip()

            try:
                return json.loads(cleaned_response)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON from OpenAI-compatible API: {cleaned_response}")

        except Exception as e:
            logger.error(f"[LLM] Error en OpenAI structured outputs: {e}")
            raise RuntimeError(f"Error con API OpenAI-compatible: {e}")
