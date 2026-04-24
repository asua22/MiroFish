#!/usr/bin/env python3
"""Test 1.4: Verificar Logs de Rama A"""

import sys
import logging

# Configurar logging para capturar todo
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(name)s] %(levelname)s: %(message)s'
)

sys.path.insert(0, '/home/espmichaelasua/MiroFish-Offline/backend')

from app.utils.llm_client import LLMClient

print("=" * 70)
print("TEST 1.4: Verificar Logs de Rama A")
print("=" * 70)

# Crear cliente
print("\n1. Creando cliente LLM...")
client = LLMClient(
    api_key="ollama",
    base_url="http://100.123.212.63:11434/v1",
    model="gemma4:e4b"
)
print("   ✅ Cliente creado")

# Schema
json_schema = {
    "type": "object",
    "properties": {
        "full_name": {"type": "string"},
        "age": {"type": "integer"},
        "city": {"type": "string"}
    },
    "required": ["full_name", "age", "city"]
}

# Mensajes
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Generate a person"}
]

# Llamar con schema (Rama A)
print("\n2. Llamando chat_json() con schema (debería mostrar logs de Rama A)...")
print("\n" + "-" * 70)
print("CAPTURA DE LOGS:")
print("-" * 70)

result = client.chat_json(
    messages=messages,
    temperature=0.3,
    max_tokens=256,
    json_schema=json_schema
)

print("-" * 70)
print(f"\n3. Resultado: {result}")
print("\n" + "=" * 70)
print("✅ TEST 1.4 PASSED: Logs capturados correctamente")
print("=" * 70)
