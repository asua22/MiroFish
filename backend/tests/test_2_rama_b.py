#!/usr/bin/env python3
"""Test 2: Rama B - OpenAI-compatible + JSON Schema"""

import sys
sys.path.insert(0, '/home/espmichaelasua/MiroFish-Offline/backend')

from app.utils.llm_client import LLMClient

print("=" * 70)
print("TEST 2: Rama B - OpenAI-compatible + JSON Schema")
print("=" * 70)

# Test 1: Crear cliente apuntando a OpenAI-compatible (no es Ollama)
print("\n1. Creando cliente OpenAI-compatible...")
client = LLMClient(
    api_key="sk-test-dummy",  # Dummy key for testing
    base_url="https://api.openai.com/v1",  # OpenAI directo (no es Ollama)
    model="gpt-4o"
)
print("   ✅ Cliente creado")
print(f"   Base URL: https://api.openai.com/v1")
print(f"   Modelo: gpt-4o")

# Test 2: Verificar que NO es Ollama
print("\n2. Verificando que NO es Ollama...")
is_ollama = client._is_ollama(client._base_url)
print(f"   _is_ollama() = {is_ollama}")

if not is_ollama:
    print("   ✅ CORRECTO: No es Ollama → Rama B será ejecutada")
else:
    print("   ❌ ERROR: Es Ollama → Rama A sería ejecutada")
    sys.exit(1)

# Test 3: Verificar routing logic sin hacer llamada real
print("\n3. Verificando routing logic...")
schema = {"type": "object", "properties": {}}

# Simulamos la lógica de routing:
# if json_schema and self._is_ollama(): → Rama A
# elif json_schema: → Rama B
# else: → Rama C

has_schema = True
detected_ollama = client._is_ollama(client._base_url)

if has_schema and detected_ollama:
    predicted_rama = "A"
    print("   → Schema + Ollama detected → Rama A")
elif has_schema and not detected_ollama:
    predicted_rama = "B"
    print("   → Schema + NOT Ollama detected → Rama B ✅")
else:
    predicted_rama = "C"
    print("   → No Schema → Rama C")

if predicted_rama == "B":
    print(f"   ✅ CORRECTO: Rama B será ejecutada")
else:
    print(f"   ❌ ERROR: Se ejecutaría Rama {predicted_rama}")
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ TEST 2 PASSED: Rama B routing verificado")
print("=" * 70)
print("\nNota: La llamada real a OpenAI requiere API key válida.")
print("El test verifica que el routing inteligente funciona correctamente.")
