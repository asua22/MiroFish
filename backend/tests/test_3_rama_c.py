#!/usr/bin/env python3
"""Test 3: Rama C - Sin Schema (Backward Compatibility)"""

import sys
sys.path.insert(0, '/home/espmichaelasua/MiroFish-Offline/backend')

from app.utils.llm_client import LLMClient

print("=" * 70)
print("TEST 3: Rama C - Sin Schema (Backward Compatibility)")
print("=" * 70)

# Test 1: Crear cliente
print("\n1. Creando cliente...")
client = LLMClient(
    api_key="ollama",
    base_url="http://100.123.212.63:11434/v1",
    model="gemma4:e4b"
)
print("   ✅ Cliente creado")

# Test 2: Llamar chat_json() SIN schema (Rama C)
print("\n2. Llamando chat_json() SIN schema...")
messages = [
    {"role": "user", "content": "Generate a simple JSON with name and age"}
]

try:
    # Llamar SIN json_schema → Rama C
    result = client.chat_json(
        messages=messages,
        temperature=0.3,
        max_tokens=256
        # ← NO json_schema aquí
    )
    print("   ✅ chat_json() ejecutado")
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    sys.exit(1)

# Test 3: Verificar respuesta
print("\n3. Verificando respuesta...")
print(f"   Tipo: {type(result).__name__}")
print(f"   Contenido: {result}")

# Test 4: Validar que es JSON válido
if isinstance(result, dict):
    print("   ✅ CORRECTO: Respuesta es diccionario (JSON válido)")
else:
    print(f"   ❌ ERROR: Respuesta no es diccionario: {type(result)}")
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ TEST 3 PASSED: Rama C funciona correctamente")
print("=" * 70)
print("\nRama C usa json_object mode (sin schema enforcement)")
print("Sigue siendo válida para llamadas sin schema (backward compatible)")
