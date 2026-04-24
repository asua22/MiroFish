# Plan: Integración de Datos Reales + Dinámica de Mercado Predictiva en MiroFish

## 📋 Visión General

Integrar **SCRAPEGRAPH-AI** y **CRAWL4AI** en MiroFish-Offline para:
1. Extraer perfiles reales de Twitter/X y noticias financieras
2. Convertir datos en JSON estructurado (personalidades de agentes)
3. Inyectar esos perfiles como agentes con "memoria" real en MiroFish
4. Simular **dinámica de mercado predictiva** con análisis de sentimiento

**Caso de Uso**: Alimentar MiroFish con perfiles reales de traders/inversionistas de Twitter + noticias de mercado → observar cómo se propaga el sentimiento → predecir reacciones del mercado.

---

## 🏗️ Arquitectura Actual de MiroFish

```
MiroFish-Offline
├── backend/
│   ├── app/
│   │   ├── services/
│   │   │   ├── oasis_profile_generator.py    ← Genera personas (LLM-based)
│   │   │   ├── simulation_runner.py           ← Ejecuta simulación
│   │   │   ├── graph_builder.py               ← Construye grafo en Neo4j
│   │   │   └── report_agent.py                ← Analiza resultados
│   │   ├── api/
│   │   │   ├── simulation.py                  ← API para simular
│   │   │   ├── graph.py                       ← API para grafo
│   │   │   └── report.py                      ← API para reportes
│   │   └── storage/
│   │       └── neo4j_storage.py               ← Interfaz BD
│   └── run.py                                  ← Punto entrada
└── frontend/
    └── UI para uploads + ejecución simulación
```

**Punto de inyección actual**: `oasis_profile_generator.py` genera agentes desde ontología del documento
→ **NUEVO**: Inyectar agentes desde datos reales (Twitter, noticias)

---

## 🎯 Fases de Implementación

### **FASE 1: Módulo Data Ingestion (datos → JSON)**
**Objetivo**: Extraer datos reales y convertir a perfiles JSON compatibles con MiroFish

#### 1.1 Script: `twitter_data_fetcher.py`
- **Input**: Lista de handles de Twitter / hashtags de mercado
- **Tools**: SCRAPEGRAPH-AI (o API de Twitter si tienes acceso)
- **Output**: JSON con estructura:
```json
{
  "username": "trader_juan",
  "source": "twitter",
  "bio": "Trader independiente, 5 años exp",
  "follower_count": 12500,
  "recent_posts": [
    {"text": "...", "likes": 100, "date": "2026-04-23"},
    ...
  ],
  "sentiment_history": "mostly_bullish",
  "expertise": ["crypto", "stocks"],
  "risk_profile": "high_risk"
}
```

**Ubicación**: `backend/scripts/data_ingestion/twitter_data_fetcher.py`

#### 1.2 Script: `news_crawler.py`
- **Input**: Fuentes de noticias financieras (Bloomberg, Reuters, etc.)
- **Tools**: CRAWL4AI para extraer contenido desde URLs
- **Output**: JSON con estructura:
```json
{
  "title": "Fed decides not to raise rates",
  "source": "Bloomberg",
  "date": "2026-04-24",
  "sentiment": "neutral",
  "entities": ["Fed", "Interest Rates", "USD"],
  "summary": "...",
  "impact_sectors": ["Banking", "Tech"]
}
```

**Ubicación**: `backend/scripts/data_ingestion/news_crawler.py`

#### 1.3 Script: `profile_converter.py`
- **Input**: Datos de Twitter + contexto de noticias
- **Proceso**: 
  - Generar "personalidad" del agente basada en datos reales (LLM: "Este usuario es un trader bullish con perfil X")
  - Crear historial de "memoria" del agente (posts previos, sentimientos)
  - Asignar "sesgo de opinión" (bullish/bearish) basado en tweets reales
- **Output**: Perfil compatible con `oasis_profile_generator.py`

**Ubicación**: `backend/scripts/data_ingestion/profile_converter.py`

---

### **FASE 2: Inyector de Perfiles (JSON → Agentes en MiroFish)**
**Objetivo**: Modificar MiroFish para aceptar perfiles reales en lugar de solo generar desde ontología

#### 2.1 Módulo: `real_profile_injector.py`
- **Input**: JSON de perfiles reales (de FASE 1)
- **Proceso**:
  - Cargar perfiles JSON
  - Inyectar en `oasis_profile_generator.py` como "seed agents"
  - Mantener datos históricos en Neo4j (memoria del agente)
- **Output**: Agentes en MiroFish con memoria real

**Ubicación**: `backend/app/services/real_profile_injector.py`

#### 2.2 API Extension: `profiles.py`
- **Endpoint 1**: `POST /api/profiles/import` 
  - Recibe JSON de perfiles reales
  - Los guarda en BD (table `real_profiles`)
  
- **Endpoint 2**: `GET /api/profiles/list`
  - Devuelve perfiles disponibles
  
- **Endpoint 3**: `POST /api/profiles/use-for-simulation`
  - Marca perfil para usar en próxima simulación

**Ubicación**: `backend/app/api/profiles.py`

---

### **FASE 3: Motor de Simulación de Mercado**
**Objetivo**: Especializar la simulación para dinámica de mercado + sentimiento

#### 3.1 Módulo: `market_dynamics_simulator.py`
- **Extiende**: `simulation_runner.py`
- **Cambios**:
  - Agentes tienen "posiciones" (long/short)
  - Reacciones afectan "precio simulado" del activo
  - Sentimiento agregado = volatilidad del mercado
  - Noticias disparan "eventos de mercado" en tiempo real

**Ubicación**: `backend/app/services/market_dynamics_simulator.py`

#### 3.2 Módulo: `sentiment_analyzer.py`
- **Input**: Posts/reacciones de agentes durante simulación
- **Proceso**:
  - Analizar sentimiento en tiempo real
  - Agregar por sector/activo
  - Detectar cambios de opinión ("flip" de bullish a bearish)
- **Output**: Métrica de sentimiento para reportes

**Ubicación**: `backend/app/services/sentiment_analyzer.py`

#### 3.3 API Extension: Endpoints de mercado
- `POST /api/market/simulate-market-prediction`
  - Input: Lista de tickers/assets + perfiles reales
  - Output: Simulación de dinámica de precios + sentimiento

**Ubicación**: Extender `backend/app/api/simulation.py`

---

### **FASE 4: Frontend + Reportes**
**Objetivo**: UI para cargar perfiles + visualizar predicciones

#### 4.1 Vista: Market Prediction Dashboard
- Upload de archivo JSON (perfiles)
- Selector de activos/tickers
- Botón "Run Market Prediction"
- Gráficos en tiempo real:
  - Evolución del sentimiento
  - "Precio simulado" vs sentimiento
  - Timeline de posts de agentes

**Ubicación**: `frontend/src/views/MarketPrediction.vue`

#### 4.2 Reporte: Market Analysis Report
- Análisis de sentimiento por perfil
- Predicción de "volatilidad esperada"
- Recomendación: bullish/bearish/neutral
- Casos de "flip" de opinión (agentes que cambiaron)

**Ubicación**: Extender `backend/app/services/report_agent.py`

---

## 📊 Orden de Implementación (Recomendado)

### **Orden de Prioridades**:

1. **[PRIMERO]** FASE 1.1 - Script de Twitter (`twitter_data_fetcher.py`)
   - **Herramienta**: ScrapeGraphAI (SmartScraperGraph) + Ollama local
   - Define estructura JSON de perfiles
   - Prueba con 5-10 handles reales
   - Prompt: "Extrae bio, posts recientes, follower count, sentimiento general bullish/bearish"
   - ⏱️ ~2-3 horas

2. **[SEGUNDO]** FASE 1.3 - Convertidor de perfiles (`profile_converter.py`)
   - Convierte tweets → "personalidad" de agente
   - Integra con LLM local (Ollama qwen2.5)
   - LLM genera: personality traits, opinion bias, expertise
   - ⏱️ ~2-3 horas

3. **[TERCERO]** FASE 2.1 - Inyector de perfiles (`real_profile_injector.py`)
   - Integra con `oasis_profile_generator.py`
   - Prueba end-to-end: Twitter JSON → Agentes en MiroFish
   - ⏱️ ~3-4 horas

4. **[CUARTO]** FASE 3.1 - Motor de mercado (`market_dynamics_simulator.py`)
   - Extiende simulación con lógica de precios
   - ⏱️ ~4-5 horas

5. **[QUINTO]** FASE 1.2 - Crawler de noticias (opcional, mejora)
   - **Herramienta**: Crawl4AI (AsyncWebCrawler)
   - Crawlea Bloomberg, Reuters, noticias financieras
   - Inyecta noticias como "eventos" en simulación
   - ⏱️ ~2-3 horas

6. **[SEXTO]** FASE 4 - Frontend + UI (pulido)
   - Dashboard de mercado
   - ⏱️ ~3-4 horas

---

## 🔧 Decisiones Técnicas

### **¿Dónde obtenemos datos de Twitter?**
- **Opción A**: SCRAPEGRAPH-AI + Ollama (sin API official) ✅ RECOMENDADO
  - Pros: Sin dependencias externas, LLM local (Ollama qwen2.5), flexible
  - Contras: Más lento, puede detectarse como bot
  - Código base:
    ```python
    from scrapegraphai.graphs import SmartScraperGraph
    
    graph_config = {
        "llm": {"model": "ollama/qwen2.5:32b", "format": "json"},
        "verbose": True,
        "headless": True,
    }
    
    scraper = SmartScraperGraph(
        prompt="Extract bio, recent posts (last 10), follower count, sentiment (bullish/neutral/bearish)",
        source="https://twitter.com/username",
        config=graph_config
    )
    result = scraper.run()  # Returns JSON
    ```

- **Opción B**: API oficial de Twitter/X (requiere key)
  - Pros: Fiable, rápido, oficial
  - Contras: Necesita credenciales, limits de rate

- **Nuestra estrategia**: SCRAPEGRAPH-AI local (opción A), fallback a API si es necesario

### **¿Cómo se "personifican" los agentes?**
1. Extraer tweets reales del usuario
2. LLM lee tweets → genera "perfil" (personalidad, sesgo, expertise)
3. LLM genera "memoria" inicial (resumen de posts previos)
4. Agente usa esa memoria en simulación (responde según su historia real)

### **¿Cómo afecta el sentimiento al precio?**
- Agregamos sentimiento de todos los agentes
- Fórmula simple: `precio_simulado = precio_base * (1 + (sentimiento_promedio * volatility_factor))`
- Ejemplo: Sentimiento -0.5 (bearish) → precio baja 50% (según factor)

---

## 📁 Estructura de Directorios a Crear

```
backend/
├── scripts/
│   └── data_ingestion/
│       ├── __init__.py
│       ├── twitter_data_fetcher.py        # FASE 1.1
│       ├── news_crawler.py                # FASE 1.2
│       ├── profile_converter.py           # FASE 1.3
│       └── sample_profiles.json           # Ejemplos de test
├── app/
│   ├── services/
│   │   ├── real_profile_injector.py       # FASE 2.1
│   │   ├── market_dynamics_simulator.py   # FASE 3.1
│   │   └── sentiment_analyzer.py          # FASE 3.2
│   └── api/
│       ├── profiles.py                     # FASE 2.2
│       └── market_endpoints.py             # FASE 3.3
└── tests/
    └── test_market_prediction.py           # Tests del flujo
```

---

## ✅ Definición de "Hecho"

Cada fase se considera **completa** cuando:

### FASE 1: Twitter data + conversion
- [ ] `twitter_data_fetcher.py` extrae 10 perfiles de Twitter reales
- [ ] `profile_converter.py` convierte a JSON compatible
- [ ] Ejemplo JSON está en `sample_profiles.json`

### FASE 2: Inyección en MiroFish
- [ ] `real_profile_injector.py` inyecta perfiles en `oasis_profile_generator.py`
- [ ] `/api/profiles/import` funciona end-to-end
- [ ] Agentes generados tienen datos reales (verificable en Neo4j)

### FASE 3: Motor de mercado
- [ ] Simulación genera "precio simulado" basado en sentimiento
- [ ] Reportes muestran "predicción de sentimiento"
- [ ] Visualización en tiempo real funciona

---

## 💡 Ejemplos de Código (Referencia Rápida)

### **1. Extraer perfil de Twitter con ScrapeGraphAI**

```python
# backend/scripts/data_ingestion/twitter_data_fetcher.py
import json
from scrapegraphai.graphs import SmartScraperGraph

def fetch_twitter_profile(handle: str) -> dict:
    graph_config = {
        "llm": {
            "model": "ollama/qwen2.5:32b",
            "format": "json",
        },
        "verbose": False,
        "headless": True,
    }
    
    scraper = SmartScraperGraph(
        prompt="""Extract the following from the Twitter profile in JSON format:
        - username
        - display_name
        - bio
        - follower_count
        - following_count
        - last_5_posts: [{text, date, likes, retweets}]
        - overall_sentiment: (bullish/neutral/bearish based on recent posts)
        - expertise_topics: [list of topics]
        """,
        source=f"https://twitter.com/{handle}",
        config=graph_config
    )
    
    return scraper.run()

# Uso
profile = fetch_twitter_profile("bitcoinmaxi")
print(json.dumps(profile, indent=2))
```

### **2. Crawlear noticias con Crawl4AI**

```python
# backend/scripts/data_ingestion/news_crawler.py
import asyncio
from crawl4ai import AsyncWebCrawler

async def crawl_financial_news(url: str) -> str:
    async with AsyncWebCrawler(headless=True) as crawler:
        result = await crawler.arun(
            url=url,
            cache_mode="bypass"  # Siempre fresco
        )
        return result.markdown

# Uso
news = asyncio.run(crawl_financial_news("https://www.bloomberg.com/markets"))
print(news[:500])
```

### **3. Convertir Twitter → Personalidad de Agente**

```python
# backend/scripts/data_ingestion/profile_converter.py
from anthropic import Anthropic

def twitter_to_agent_personality(twitter_profile: dict) -> dict:
    client = Anthropic()
    
    prompt = f"""Analiza este perfil de Twitter real y genera una "personalidad" de agente para simulación:

Twitter Profile:
{json.dumps(twitter_profile, indent=2)}

Genera un JSON con:
1. personality_traits: descripción de carácter (bullish, cautious, reckless, etc)
2. opinion_bias: -1 (muy bearish) a +1 (muy bullish) basado en tweets
3. expertise_level: 0-100 en finanzas
4. risk_profile: 'conservative', 'moderate', 'aggressive'
5. memory_summary: resumen de opiniones históricas del usuario
6. decision_speed: cómo de rápido reacciona (0-100, donde 100 es muy rápido)
7. influence_score: qué tan influyente es entre otros traders (0-100)

Responde SOLO en JSON válido, sin explicaciones."""

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return json.loads(message.content[0].text)

# Uso
agent_personality = twitter_to_agent_personality(profile)
print(json.dumps(agent_personality, indent=2))
```

---

## 🚀 Próximos Pasos Inmediatos

**Si estás de acuerdo con este plan:**

1. ¿Tienes acceso a API oficial de Twitter/X o prefieres SCRAPEGRAPH-AI?
2. ¿Hay activos/tickers específicos que quieras simular? (ej: Bitcoin, Tesla, S&P 500)
3. ¿Quieres empezar con fase 1 (extracción de datos) o prefieres un MVP más rápido?

---

**Tiempo total estimado**: 15-20 horas para MVP completo  
**Complejidad**: Media (extender módulos existentes, no construir desde cero)
