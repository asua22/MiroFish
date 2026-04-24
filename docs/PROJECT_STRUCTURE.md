# MiroFish-Offline — Estructura del Proyecto

## 📁 Directorios principales

### `/backend`
Backend en Python (Flask). Gestiona toda la lógica de simulación, construcción de grafos y procesamiento.

#### `/backend/app`
Código principal de la aplicación:

- **`__init__.py`** — Inicializa la aplicación Flask y configura extensiones
- **`config.py`** — Configuración global (variables de entorno, ajustes)
- **`run.py`** — Punto de entrada del servidor Flask

#### `/backend/app/models`
Modelos de datos:

- **`task.py`** — Modelo Task (tareas de simulación, reportes)
- **`project.py`** — Modelo Project (proyectos/simulaciones)

#### `/backend/app/services`
Servicios con la lógica de negocio:

- **`graph_builder.py`** — Extrae entidades y relaciones del documento, construye el grafo de conocimiento
- **`simulation_config_generator.py`** — Genera configuración de simulación (cantidad de agentes, parámetros)
- **`simulation_manager.py`** — Orquesta el flujo completo de simulación
- **`simulation_runner.py`** — Ejecuta los pasos de la simulación
- **`simulation_ipc.py`** — Inter-Process Communication (IPC) para comunicación entre procesos
- **`entity_reader.py`** — Lee y procesa entidades del grafo
- **`graph_memory_updater.py`** — Actualiza memoria compartida en el grafo durante la simulación
- **`graph_tools.py`** — Herramientas para interactuar con el grafo (búsqueda, actualizaciones)
- **`ontology_generator.py`** — Genera ontología (estructura de conocimiento)
- **`oasis_profile_generator.py`** — Genera perfiles de agentes (personalidades, sesgos)
- **`report_agent.py`** — Agente especial que analiza la simulación y genera reportes
- **`text_processor.py`** — Procesa y limpia texto de entrada

#### `/backend/app/storage`
Capa de almacenamiento (Neo4j):

- **`graph_storage.py`** — Interface abstracta para almacenamiento de grafos
- **`neo4j_storage.py`** — Implementación con Neo4j Community
- **`neo4j_schema.py`** — Define esquema de la BD (nodos, relaciones)
- **`ner_extractor.py`** — Extrae entidades nombradas (NER) usando Ollama
- **`embedding_service.py`** — Genera embeddings de texto con nomic-embed-text
- **`search_service.py`** — Búsqueda híbrida (vectorial + BM25)

#### `/backend/app/utils`
Utilidades:

- **`llm_client.py`** — Cliente para conectar con Ollama/LLM
- **`file_parser.py`** — Parser de documentos (PDF, TXT, etc.)
- **`logger.py`** — Sistema de logging
- **`retry.py`** — Reintentos con backoff exponencial

#### `/backend/scripts`
Scripts auxiliares:

- **`run_parallel_simulation.py`** — Ejecuta simulaciones en paralelo
- **`run_reddit_simulation.py`** — Simulación con perfil Reddit
- **`run_twitter_simulation.py`** — Simulación con perfil Twitter
- **`action_logger.py`** — Logging de acciones de agentes
- **`test_profile_format.py`** — Valida formato de perfiles

#### `/backend/requirements.txt`
Dependencias Python (Flask, Neo4j driver, Ollama, etc.)

#### `/backend/test_*.py`
Archivos de prueba/testing del backend

---

### `/frontend`
Frontend en Vue/JavaScript. Interfaz web para crear simulaciones, ver resultados, interactuar con agentes.

#### `/frontend/src`
Código fuente:

- **`main.js`** — Punto de entrada de Vue
- Otros componentes `.vue` (vistas, componentes)

#### `/frontend/public`
Archivos estáticos (favicon, imágenes, etc.)

#### `/frontend/package.json`
Dependencias Node.js (Vue, Vite, Axios, etc.)

#### `/frontend/vite.config.js`
Configuración de Vite (bundler)

---

### `/docs`
Documentación:

- **`progress.md`** — Registro de progreso del proyecto
- **`manual_tailscale.md`** — Guía de configuración con Tailscale

### `/static`
Archivos estáticos públicos:

- **`/image`** — Banners, screenshots, imágenes del proyecto

---

## 🐳 Archivos de configuración

- **`Dockerfile`** — Imagen Docker para toda la app
- **`docker-compose.yml`** — Orquestación: Neo4j, Ollama, app
- **`.env.example`** — Template de variables de entorno
- **`package.json`** (raíz) — Scripts npm globales

---

## 📄 Documentación del proyecto

- **`README.md`** — Introducción, quick start, arquitectura general
- **`ROADMAP.md`** — Funcionalidades planeadas
- **`MANUAL_TESTING.md`** — Guía de testing manual
- **`TEST_PROGRESS.md`** — Estado de las pruebas
- **`TESTS_COMPLETED_SUMMARY.md`** — Resumen de tests completados
- **`STRUCTURED_OUTPUT_FIX.md`** — Detalles de correcciones
- **`implement.md`** — Notas de implementación
- **`test.md`** — Información de testing
- **`fase3.md`** — Notas de fase 3

---

## 🔄 Flujo de datos

```
Usuario sube documento
    ↓
graph_builder.py → extrae entidades → Neo4j
    ↓
simulation_config_generator.py → genera parámetros
    ↓
oasis_profile_generator.py → crea perfiles de agentes
    ↓
simulation_runner.py → ejecuta simulación
    ↓
graph_memory_updater.py → actualiza estados en Neo4j
    ↓
report_agent.py → analiza y genera reporte
    ↓
Frontend → muestra resultados
```

---

## 🎯 Puntos de entrada

- **Backend**: `backend/run.py` — inicia servidor Flask en puerto 5000
- **Frontend**: `frontend/src/main.js` — inicia app Vue
- **Docker**: `docker-compose up -d` — levanta todo

---

## 🔧 Dependencias clave

### Backend (Python)
- **Flask** — framework web
- **Neo4j** — base de datos de grafos
- **Ollama** — LLM local
- **CAMEL-AI** — framework de agentes
- **Pydantic** — validación de datos

### Frontend (Node.js)
- **Vue 3** — framework UI
- **Vite** — bundler
- **Axios** — cliente HTTP
- **Tailwind/Bootstrap** — estilos

### Servicios externos
- **Neo4j 5.15** — BD grafo
- **Ollama** — LLM + embeddings (qwen2.5, nomic-embed-text)

