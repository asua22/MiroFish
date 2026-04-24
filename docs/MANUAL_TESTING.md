# MANUAL TESTING GUIDE — Ejecuta los tests tu mismo

**Guía para ejecutar cada test manualmente en tu terminal**

---

## TEST 1.1: Detección de Ollama

### Paso 1: Abre una terminal en el servidor

```bash
# Desde tu terminal conectada al servidor vía SSH:
ssh espmichaelasua@<server-ip>
cd /home/espmichaelasua/MiroFish-Offline/backend
```

### Paso 2: Activa conda y ejecuta Python

```bash
# Opción A: Con conda run (más simple)
conda run -n mirofish_env python3 << 'EOF'
import sys
sys.path.insert(0, '/home/espmichaelasua/MiroFish-Offline/backend')
from app.utils.llm_client import LLMClient

print("=" * 70)
print("TEST 1.1: Test de Detección - RAMA A")
print("=" * 70)

client = LLMClient(
    api_key="dummy",
    base_url="http://localhost:11434/v1",
    model="gemma4:e4b"
)

print("\n✅ Prueba 1: localhost:11434")
result1 = client._is_ollama("http://localhost:11434/v1")
print(f"   _is_ollama() = {result1}")

print("\n✅ Prueba 2: OpenAI")
result2 = not client._is_ollama("https://api.openai.com/v1")
print(f"   NOT _is_ollama(OpenAI) = {result2}")

print("\n✅ Prueba 3: NVIDIA")
result3 = not client._is_ollama("https://integrate.api.nvidia.com/v1")
print(f"   NOT _is_ollama(NVIDIA) = {result3}")

print("\n✅ Prueba 4: IP Tailscale")
result4 = client._is_ollama("http://100.123.212.63:11434/v1")
print(f"   _is_ollama(100.123.212.63) = {result4}")

print("\n" + "=" * 70)
if all([result1, result2, result3, result4]):
    print("✅ TEST 1.1 PASSED")
else:
    print("❌ TEST 1.1 FAILED")
print("=" * 70)
EOF
```

**Esperado:**
```
======================================================================
TEST 1.1: Test de Detección - RAMA A
======================================================================

✅ Prueba 1: localhost:11434
   _is_ollama() = True

✅ Prueba 2: OpenAI
   NOT _is_ollama(OpenAI) = True

✅ Prueba 3: NVIDIA
   NOT _is_ollama(NVIDIA) = True

✅ Prueba 4: IP Tailscale
   _is_ollama(100.123.212.63) = True

======================================================================
✅ TEST 1.1 PASSED
======================================================================
```

---

## TEST 1.2: Endpoint Nativo `/api/chat`

### Paso 1: Desde tu laptop, verifica que Ollama está corriendo

```bash
# En tu LAPTOP (donde está Ollama):
curl http://localhost:11434/api/version

# Esperado: {"version":"0.20.3"}
```

### Paso 2: Desde el servidor, llama al endpoint nativo vía Tailscale

```bash
# En el servidor:
curl -s -X POST http://100.123.212.63:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma4:e4b",
    "messages": [
      {"role": "user", "content": "Generate a person with name and age only"}
    ],
    "format": {
      "type": "object",
      "properties": {
        "full_name": {"type": "string"},
        "age": {"type": "integer"}
      },
      "required": ["full_name", "age"]
    },
    "stream": false
  }' | jq .
```

**Esperado:**
```json
{
  "model": "gemma4:e4b",
  "created_at": "2026-04-09T09:35:31...",
  "message": {
    "role": "assistant",
    "content": "{\"full_name\": \"Eleanor Vance\", \"age\": 42}"
  },
  "done": true
}
```

✅ **Verificar:** El JSON debe ser válido (no Markdown)

---

## TEST 1.3: Backend Integration - chat_json()

### Paso 1: Crea un script Python en el servidor

```bash
# En el servidor:
cat > /tmp/test_1_3.py << 'EOF'
import sys
sys.path.insert(0, '/home/espmichaelasua/MiroFish-Offline/backend')

from app.utils.llm_client import LLMClient

print("=" * 70)
print("TEST 1.3: Rama A en Backend - chat_json() con schema")
print("=" * 70)

# Crear cliente apuntando a Ollama vía Tailscale
client = LLMClient(
    api_key="ollama",
    base_url="http://100.123.212.63:11434/v1",
    model="gemma4:e4b"
)

print("\n✅ Cliente creado (Ollama vía Tailscale)")

# Definir schema
json_schema = {
    "type": "object",
    "properties": {
        "full_name": {"type": "string"},
        "age": {"type": "integer"},
        "city": {"type": "string"}
    },
    "required": ["full_name", "age", "city"]
}

# Preparar mensajes
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Generate a person with name, age, and city"}
]

# Llamar chat_json() con schema (activará Rama A)
print("\n✅ Llamando chat_json() con schema...")
result = client.chat_json(
    messages=messages,
    temperature=0.3,
    max_tokens=256,
    json_schema=json_schema
)

print(f"\n✅ Resultado: {result}")

# Validar
if all(k in result for k in ["full_name", "age", "city"]):
    print("\n✅ TEST 1.3 PASSED")
else:
    print("\n❌ TEST 1.3 FAILED")

print("=" * 70)
EOF
```

### Paso 2: Ejecuta el script

```bash
# En el servidor:
conda run -n mirofish_env python3 /tmp/test_1_3.py
```

**Esperado:**
```
======================================================================
TEST 1.3: Rama A en Backend - chat_json() con schema
======================================================================

✅ Cliente creado (Ollama vía Tailscale)

✅ Llamando chat_json() con schema...

✅ Resultado: {'full_name': 'Eleanor Vance', 'age': 34, 'city': 'Seattle'}

✅ TEST 1.3 PASSED
======================================================================
```

---

## TEST 1.4: Logs

### Paso 1: Levanta el backend con DEBUG

```bash
# En el servidor:
cd /home/espmichaelasua/MiroFish-Offline
FLASK_DEBUG=1 npm run dev
```

Verás en los logs:
```
[backend] * Debug mode: on
[backend] * Running on http://127.0.0.1:5001
```

### Paso 2: En otra terminal, ejecuta Test 1.3

```bash
# En otra terminal del servidor:
conda run -n mirofish_env python3 /tmp/test_1_3.py
```

### Paso 3: Observa los logs en la terminal de npm run dev

Busca líneas como:
```
[LLM] >>> llamando Ollama nativo | modelo=gemma4:e4b | schema=True | num_ctx=8192
[LLM] <<< Ollama nativo en X.Xs
```

✅ **Verificación:** Los logs muestran "Ollama nativo" = Rama A ejecutada

---

## RESUMEN DE COMANDOS

| Test | Comando Principal |
|---|---|
| **1.1** | `conda run -n mirofish_env python3 << 'EOF' ... EOF` |
| **1.2** | `curl -s -X POST http://100.123.212.63:11434/api/chat ...` |
| **1.3** | `conda run -n mirofish_env python3 /tmp/test_1_3.py` |
| **1.4** | `FLASK_DEBUG=1 npm run dev` + observar logs |

---

## FLUJO MANUAL PASO A PASO

```bash
# Terminal 1: Backend con logs
cd /home/espmichaelasua/MiroFish-Offline
FLASK_DEBUG=1 npm run dev

# Terminal 2: Tests
cd /home/espmichaelasua/MiroFish-Offline/backend

# Test 1.1
conda run -n mirofish_env python3 << 'EOF'
# ... código de Test 1.1 ...
EOF

# Test 1.2 (desde Terminal 1, otra ventana)
curl -s -X POST http://100.123.212.63:11434/api/chat ...

# Test 1.3
cat > /tmp/test_1_3.py << 'EOF'
# ... código de Test 1.3 ...
EOF
conda run -n mirofish_env python3 /tmp/test_1_3.py

# Test 1.4: Observa logs en Terminal 1
```

---

## NOTAS

- Los comandos están diseñados para copiar y pegar directamente
- Cada `<< 'EOF' ... EOF` es un bloque de código Python inline
- Si prefieres, puedes crear archivos `.py` en lugar de heredocs
- Los logs aparecen en la terminal donde ejecutaste `npm run dev`

**¡Ahora puedes ejecutar los tests manualmente! 🚀**
