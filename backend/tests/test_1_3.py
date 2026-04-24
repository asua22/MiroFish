#!/usr/bin/env python3
"""Test 1.3: Rama A en Backend - chat_json() con schema"""

import sys
sys.path.insert(0, '/home/espmichaelasua/MiroFish-Offline/backend')

from app.utils.llm_client import LLMClient

print("=" * 70)
print("TEST 1.3: Rama A en Backend - chat_json() con schema")
print("=" * 70)

# Test 1: Crear cliente
print("\n1. Creando cliente LLM (Ollama vía Tailscale)...")
client = LLMClient(
    api_key="ollama",
    base_url="http://100.123.212.63:11434/v1",
    model="gemma4:e4b"
)
print("   ✅ Cliente creado")
print(f"   Base URL: http://100.123.212.63:11434/v1")
print(f"   Modelo: gemma4:e4b")

# Test 2: Verificar que es Ollama
print("\n2. Verificando detección de Ollama...")
is_ollama = client._is_ollama(client._base_url)
if is_ollama:
    print(f"   ✅ CORRECTO: _is_ollama() = {is_ollama}")
else:
    print(f"   ❌ ERROR: _is_ollama() = {is_ollama}")
    sys.exit(1)

# Test 3: Preparar schema
print("\n3. Preparando schema JSON...")
json_schema = {
    "type": "object",
    "properties": {
        "full_name": {"type": "string"},
        "age": {"type": "integer"},
        "city": {"type": "string"}
    },
    "required": ["full_name", "age", "city"]
}
print("   ✅ Schema preparado (full_name, age, city)")

# Test 4: Preparar mensajes
print("\n4. Preparando mensajes...")
messages = [
    {"role": "system", "content": "You are a helpful assistant. Output valid JSON only."},
    {"role": "user", "content": "Generate a person with name, age, and city"}
]
print("   ✅ Mensajes preparados (system + user)")

# Test 5: Llamar chat_json() con schema (Rama A)
print("\n5. Llamando chat_json() con schema (debe usar Rama A)...")
try:
    result = client.chat_json(
        messages=messages,
        temperature=0.3,
        max_tokens=256,
        json_schema=json_schema
    )
    print("   ✅ chat_json() ejecutado exitosamente")
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Verificar respuesta
print("\n6. Verificando respuesta...")
print(f"   Tipo: {type(result).__name__}")
print(f"   Contenido: {result}")

# Test 7: Validar schema
print("\n7. Validando que respuesta cumple schema...")
required_fields = ["full_name", "age", "city"]
all_present = all(field in result for field in required_fields)

if all_present:
    print(f"   ✅ CORRECTO: Todos los campos requeridos están presentes")
    print(f"      - full_name: {result.get('full_name')}")
    print(f"      - age: {result.get('age')}")
    print(f"      - city: {result.get('city')}")
else:
    print(f"   ❌ ERROR: Faltan campos en la respuesta")
    print(f"      Presentes: {list(result.keys())}")
    print(f"      Requeridos: {required_fields}")
    sys.exit(1)

# Test 8: Verificar tipos
print("\n8. Verificando tipos de datos...")
errors = []
if not isinstance(result.get('full_name'), str):
    errors.append(f"full_name no es string: {type(result.get('full_name'))}")
if not isinstance(result.get('age'), int):
    errors.append(f"age no es int: {type(result.get('age'))}")
if not isinstance(result.get('city'), str):
    errors.append(f"city no es string: {type(result.get('city'))}")

if errors:
    print(f"   ❌ ERROR: Tipos de datos incorrectos:")
    for error in errors:
        print(f"      - {error}")
    sys.exit(1)
else:
    print(f"   ✅ CORRECTO: Todos los tipos de datos son correctos")

print("\n" + "=" * 70)
print("✅ TEST 1.3 PASSED: Rama A en Backend funciona correctamente")
print("=" * 70)
