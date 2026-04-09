# MiroFish Backend

REST API backend for MiroFish knowledge graph generation system.

## Features

- **Multiple LLM Providers**: Ollama, OpenAI, and OpenAI-compatible APIs
- **Structured Output (JSON Schema)**: Intelligent routing for guaranteed JSON output
- **Context Window Management**: Automatic handling of large documents
- **Graph Generation**: Create knowledge graphs from documents with entity and relationship extraction

## Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```bash
# LLM Configuration
LLM_API_KEY=your-api-key
LLM_BASE_URL=http://localhost:11434/v1  # Ollama example
LLM_MODEL_NAME=gemma:7b

# Ollama-specific (optional)
OLLAMA_NUM_CTX=8192  # Context window size (default: 8192)

# Backend
DEBUG=False
PORT=5000
```

## Structured Output (JSON Schema)

The backend supports JSON schema enforcement with intelligent routing between three implementation branches:

### How It Works

The `LLMClient.chat_json()` method automatically selects the best constrained decoding strategy:

#### Rama A: Ollama Native Constrained Decoding
- **When:** Provider is Ollama + JSON Schema is provided
- **How:** Uses `/api/chat` endpoint with GBNF grammar
- **Guarantee:** JSON output is constrained at token generation level
- **Best for:** Local Ollama instances requiring maximum reliability

#### Rama B: OpenAI-compatible JSON Schema
- **When:** Provider is not Ollama + JSON Schema is provided
- **How:** Uses `response_format` with `type: "json_schema"` and `strict: true`
- **Guarantee:** Output strictly conforms to schema
- **Best for:** OpenAI, Anthropic Claude API, and compatible services

#### Rama C: JSON Object Mode Fallback
- **When:** No JSON Schema is provided
- **How:** Uses `response_format: {"type": "json_object"}`
- **Guarantee:** Output is valid JSON (format not schema-constrained)
- **Best for:** Backward compatibility with existing code

### Usage Examples

#### With JSON Schema (Rama A/B - Constrained)

```python
from app.utils.llm_client import LLMClient

client = LLMClient()

# Define your schema
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "email": {"type": "string", "format": "email"}
    },
    "required": ["name", "age"]
}

# Call with schema - automatically routes to Rama A or B
result = client.chat_json(
    messages=[
        {"role": "user", "content": "Extract person info: John Smith, 30 years old, john@example.com"}
    ],
    json_schema=schema,
    temperature=0.3,
    max_tokens=256
)

print(result)
# Output: {"name": "John Smith", "age": 30, "email": "john@example.com"}
```

#### Without Schema (Rama C - Backward Compatible)

```python
# Existing code without schema continues to work
result = client.chat_json(
    messages=[
        {"role": "user", "content": "Generate a JSON object with person data"}
    ],
    temperature=0.3,
    max_tokens=256
)
# Returns valid JSON but not schema-constrained
```

#### Ontology Generation with Structured Output

```python
from app.services.ontology_generator import OntologyGenerator

generator = OntologyGenerator(llm_client=client)

result = generator.generate(
    document_texts=["Your document text here..."],
    simulation_requirement="Identify all entities and relationships"
)

# Returns structured ontology with guaranteed schema compliance
```

## API Endpoints

### POST /api/graph/ontology/generate

Generates knowledge graph ontology from provided documents.

**Request:**
```json
{
    "document_texts": ["Document 1 text", "Document 2 text"],
    "simulation_requirement": "What entities and relationships to extract?"
}
```

**Response:**
```json
{
    "entity_types": [
        {
            "name": "Person",
            "description": "A human entity",
            "properties": ["name", "age"]
        }
    ],
    "edge_types": [
        {
            "name": "works_for",
            "source": "Person",
            "target": "Organization"
        }
    ],
    "analysis_summary": "Summary of the analysis..."
}
```

## LLMClient Parameters

### chat_json()

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `messages` | list | Required | Chat messages in OpenAI format |
| `json_schema` | dict | None | JSON Schema for structured output enforcement |
| `temperature` | float | 0.3 | Sampling temperature (0.0-1.0) |
| `max_tokens` | int | 4096 | Maximum tokens to generate |

### Routing Logic

```python
if json_schema and is_ollama():
    # Rama A: Native Ollama constrained decoding
    return _chat_json_native_ollama(...)
elif json_schema:
    # Rama B: OpenAI-compatible structured outputs
    return _chat_json_openai_structured(...)
else:
    # Rama C: JSON object mode fallback
    return chat(response_format={"type": "json_object"})
```

## Context Window Management

For Ollama instances, the client automatically manages context window size:

- Default context: 8192 tokens (configurable via `OLLAMA_NUM_CTX`)
- Large documents are automatically truncated to `MAX_TEXT_LENGTH_FOR_LLM` (50,000 chars)
- Prevents prompt truncation errors

## Development

### Running Tests

```bash
# Run specific test
python backend/test_1_rama_a.py

# Run all tests
for test in backend/test_*.py; do
    python "$test"
done
```

### Test Coverage

- **Test 1:** Rama A (Ollama native) ✓
- **Test 2:** Rama B (OpenAI-compatible) ✓
- **Test 3:** Rama C (Backward compatibility) ✓
- **Test 4:** Error handling and defensive measures ✓
- **Test 5:** Large context handling (>13k tokens) ✓
- **Test 6:** Logging verification ✓
- **Test 7:** Frontend integration ✓

## Architecture

### Project Structure

```
backend/
├── app/
│   ├── utils/
│   │   ├── llm_client.py          # LLM client with routing logic
│   │   └── ...
│   ├── services/
│   │   ├── ontology_generator.py  # Ontology generation service
│   │   └── ...
│   ├── routes/
│   │   └── ...
│   └── config.py
├── tests/
│   ├── test_1_rama_a.py           # Rama A tests
│   ├── test_2_rama_b.py           # Rama B tests
│   └── ...
└── README.md                       # This file
```

### Key Components

- **LLMClient**: Unified interface for all LLM providers with intelligent routing
- **OntologyGenerator**: Service for generating knowledge graphs from documents
- **Config**: Configuration management from environment variables

## Troubleshooting

### ConnectionError to Ollama

```
Error: No se pudo conectar con Ollama: Connection refused
```

**Solution:** Ensure Ollama is running on the configured `LLM_BASE_URL`

```bash
# Start Ollama (local)
ollama serve

# Or verify remote connection
curl http://100.123.212.63:11434/api/tags
```

### Invalid JSON Response

```
Error: Invalid JSON format from LLM
```

**Solution:** 
- If using Rama A/B: Verify schema is valid JSON Schema
- If using Rama C: Ensure model supports JSON mode
- Check model's JSON generation capability

### Timeout Errors

**Solution:** Increase timeout or `max_tokens`:

```python
client = LLMClient(timeout=900.0)  # 15 minutes
result = client.chat_json(..., max_tokens=2048)
```

## Performance Notes

- **Rama A (Ollama native):** Fastest, most reliable for local Ollama
- **Rama B (OpenAI-compatible):** Slower API call but works remotely
- **Rama C (Fallback):** Backward compatible but least reliable for JSON

Choose Rama A when possible for best performance and reliability.

## Related Documentation

- [Structured Output Fix](../STRUCTURED_OUTPUT_FIX.md) - Implementation details
- [Manual Testing Guide](./MANUAL_TESTING.md) - How to run tests manually
- [Fase 3 Cleanup](./fase3.md) - Documentation and cleanup procedures
