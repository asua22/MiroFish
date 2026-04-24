# Fase 3: Documentation & Cleanup

**Objetivo:** Limpiar el código, actualizar documentación y verificar logs antes de hacer merge a main.

**Duración estimada:** 30 minutos

**Status:** Por hacer

---

## 📋 Checklist de Fase 3

### 1. Actualizar Docstrings en Métodos

**Archivo:** `backend/app/utils/llm_client.py`

#### 1.1 chat_json() - Agregar documentación del nuevo parámetro

**Ubicación:** Líneas 104-150 (método principal)

**Qué hacer:**
- Actualizar el docstring para incluir el parámetro `json_schema`
- Documentar qué hace cada rama (A, B, C)
- Agregar ejemplos de uso

**Estructura esperada:**
```python
def chat_json(self, messages, json_schema=None, temperature=0.7, max_tokens=2048):
    """
    Make a chat completion request expecting JSON output.
    
    Args:
        messages (list): Chat messages
        json_schema (dict, optional): JSON Schema for structured output. If provided:
            - Ollama providers use Rama A (native /api/chat with GBNF grammar)
            - OpenAI-compatible use Rama B (response_format json_schema)
            - If not provided, uses Rama C (json_object mode fallback)
        temperature (float): Sampling temperature
        max_tokens (int): Maximum tokens to generate
    
    Returns:
        dict: Parsed JSON response
    
    Raises:
        ConnectionError: If unable to connect to LLM provider
        JSONDecodeError: If response is not valid JSON
    
    Examples:
        # With schema (Rama A/B)
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        result = client.chat_json(messages, json_schema=schema)
        
        # Without schema (Rama C - backward compatible)
        result = client.chat_json(messages)
    """
```

#### 1.2 _chat_json_native_ollama() - Agregar documentación

**Ubicación:** Líneas 152-223

**Qué hacer:**
- Documentar qué es Rama A
- Explicar GBNF grammar
- Documentar parámetros y errores manejados

**Estructura esperada:**
```python
def _chat_json_native_ollama(self, messages, json_schema, temperature, max_tokens):
    """
    Rama A: Ollama native constrained decoding with GBNF grammar.
    
    Uses /api/chat endpoint with format parameter to enforce JSON schema
    at token generation level (constrained decoding).
    
    Args:
        messages (list): Chat messages
        json_schema (dict): JSON Schema for GBNF conversion
        temperature (float): Sampling temperature
        max_tokens (int): Maximum tokens to generate
    
    Returns:
        dict: Parsed JSON response following the schema
    
    Raises:
        ConnectionError: If unable to reach Ollama endpoint
        TimeoutError: If request times out
        JSONDecodeError: If response is not valid JSON
        KeyError: If response missing required fields
    """
```

#### 1.3 _chat_json_openai_structured() - Agregar documentación

**Ubicación:** Líneas 224-265

**Qué hacer:**
- Documentar qué es Rama B
- Explicar response_format json_schema
- Documentar strict mode

**Estructura esperada:**
```python
def _chat_json_openai_structured(self, messages, json_schema, temperature, max_tokens):
    """
    Rama B: OpenAI-compatible JSON schema enforcement.
    
    Uses response_format with type 'json_schema' and strict mode
    for guaranteed JSON schema compliance (available in OpenAI API and compatible services).
    
    Args:
        messages (list): Chat messages
        json_schema (dict): JSON Schema for enforcement
        temperature (float): Sampling temperature
        max_tokens (int): Maximum tokens to generate
    
    Returns:
        dict: Parsed JSON response following the schema
    
    Raises:
        Exception: If API returns error
    """
```

#### 1.4 _is_ollama() - Agregar documentación

**Ubicación:** Líneas 51-52

**Qué hacer:**
- Documentar método de detección

**Estructura esperada:**
```python
def _is_ollama(self, base_url):
    """
    Detect if base_url points to an Ollama instance.
    
    Checks if URL contains port 11434 (default Ollama port).
    
    Args:
        base_url (str): API base URL
    
    Returns:
        bool: True if Ollama detected, False otherwise
    """
```

---

### 2. Remover Comentarios de Debug Temporales

**Archivo:** `backend/app/utils/llm_client.py`

**Qué hacer:**
Buscar y remover comentarios que digan:
- "# DEBUG:" 
- "# TODO:"
- "# FIXME:"
- Commented-out code lines (print statements, etc.)
- Comments explaining obvious code

**Dónde buscar:**
- Método `_chat_json_native_ollama()` (líneas 152-223)
- Método `_chat_json_openai_structured()` (líneas 224-265)
- Sección de imports (líneas 1-20)

**Mantener estos comentarios:**
- Comments explaining routing logic (why Rama A/B/C)
- Comments about error handling strategies
- Comments about GBNF grammar or JSON schema concepts

---

### 3. Verificar Logs

**Archivos afectados:**
- `backend/app/utils/llm_client.py`

**Qué hacer:**

#### 3.1 Logs en _chat_json_native_ollama()

**Línea aproximada:** 160-170

**Verificar:**
- `self._logger.info(">>> Llamando Ollama nativo...")` - ✅ Apropiado
- `self._logger.info(f"<<< Ollama nativo en {elapsed:.2f}s")` - ✅ Apropiado
- Sin logs de DEBUG excesivos (payload completo, etc.) - ✅ Verificar

**Si encuentra logs verbose:**
- Cambiar `logger.debug()` a comentarios en el código
- O remover logs que muestren respuesta completa

#### 3.2 Logs en _chat_json_openai_structured()

**Línea aproximada:** 230-240

**Verificar:**
- Logs de inicio/fin de llamada
- Sin mostrar API keys o sensitive data
- Sin logs de respuesta completa

#### 3.3 Logs en chat_json()

**Línea aproximada:** 104-150

**Verificar:**
- Log de qué rama se ejecuta: "Rama A", "Rama B", "Rama C" - ✅ Útil
- Sin logs excesivos de parámetros

---

### 4. Actualizar README

**Archivo:** `backend/README.md`

**Qué hacer:**

#### 4.1 Agregar sección "Structured Output (JSON Schema)"

**Ubicación:** Al final del README o en sección de "Features"

**Contenido esperado:**
```markdown
## Structured Output (JSON Schema)

El cliente LLM soporta JSON schema enforcement con routing inteligente:

### Ramas de Procesamiento

1. **Rama A (Ollama):** Constrained decoding con GBNF grammar
   - Usar cuando: Provider es Ollama y se proporciona `json_schema`
   - Ventaja: Garantiza validez JSON a nivel de tokens

2. **Rama B (OpenAI-compatible):** response_format json_schema
   - Usar cuando: Provider es OpenAI-compatible y se proporciona `json_schema`
   - Ventaja: JSON schema enforcement estricto

3. **Rama C (Fallback):** json_object mode
   - Usar cuando: No se proporciona `json_schema`
   - Ventaja: Backward compatible, funciona con cualquier modelo

### Uso

```python
from app.utils.llm_client import LLMClient

client = LLMClient(api_key="...", base_url="...", model="...")

# Con schema (Rama A o B)
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

# Sin schema (Rama C)
result = client.chat_json(
    messages=[{"role": "user", "content": "Generate JSON"}]
)
```

### Configuración

```bash
# .env
LLM_API_KEY=your-api-key
LLM_BASE_URL=http://localhost:11434/v1  # Ollama, Rama A
# O
LLM_BASE_URL=https://api.openai.com/v1  # OpenAI, Rama B
LLM_MODEL=gemma:7b
```
```

#### 4.2 Actualizar tabla de parámetros de chat_json()

**Si existe tabla de métodos, agregar:**
| Parámetro | Tipo | Descripción | Requerido |
|-----------|------|-------------|-----------|
| messages | list | Chat messages | Sí |
| json_schema | dict | JSON Schema para structured output | No |
| temperature | float | Sampling temperature (0-1) | No |
| max_tokens | int | Max tokens to generate | No |

---

## 🔍 Orden de Ejecución Recomendado

1. **Primero:** Actualizar docstrings (será fácil de revisar)
2. **Segundo:** Remover comentarios de debug (buscar/reemplazar)
3. **Tercero:** Verificar logs (leer y probablemente limpiar)
4. **Cuarto:** Actualizar README (documentación final)

---

## ✅ Verificación Final

Antes de hacer commit:

```bash
# 1. Verificar que no hay comentarios de debug
grep -n "# DEBUG\|# TODO\|# FIXME" backend/app/utils/llm_client.py

# 2. Verificar sintaxis Python
python -m py_compile backend/app/utils/llm_client.py

# 3. Ejecutar tests nuevamente para asegurar nada se rompió
# (Tests ya creados en previous fase)

# 4. Verificar docstrings con help()
python -c "from app.utils.llm_client import LLMClient; help(LLMClient.chat_json)"
```

---

## 📝 Notas Importantes

- No cambiar lógica de código, solo documentación y limpieza
- Los tests ya confirman que todo funciona
- Los docstrings deben ser claros pero concisos
- Los logs deben ser útiles para debugging sin ser verbosos
- README debe ser accesible para nuevos desarrolladores

---

## 🎯 Resultado Esperado

Después de Fase 3:
- ✅ Código bien documentado y autoexplicativo
- ✅ Sin comentarios temporales o debug
- ✅ Logs apropiados (útiles sin ser verbosos)
- ✅ README actualizado con nuevas funcionalidades
- ✅ Listo para hacer merge a main branch
