# 🚀 Guía Rápida - Estructura Reorganizada

## Estructura Resumida

```
backend/
  ├── app/              ← Código fuente (no modificar estructura)
  ├── scripts/          ← Scripts ejecutables
  ├── tests/            ← Tests (nuevos tests aquí)
  ├── data/             ← ⭐ TODOS LOS DATOS VAN AQUÍ
  │   ├── logs/         ← Logs de ejecución (auto-creado)
  │   └── uploads/      ← Datos de usuarios
  │       ├── projects/
  │       ├── reports/
  │       └── simulations/
  ├── pyproject.toml    ← Dependencias Python
  └── run.py            ← Entry point
```

## Dónde Van los Diferentes Archivos

| Tipo de archivo | Ubicación | Nota |
|-----------------|-----------|------|
| Código Python | `backend/app/` | ✅ Ya está organizado por módulos |
| Scripts executable | `backend/scripts/` | Para scripts independientes |
| Tests | `backend/tests/` | Mueve nuevos tests aquí |
| **Logs** | `backend/data/logs/` | Auto-creado, no tocar |
| **Uploads de usuarios** | `backend/data/uploads/` | Auto-creado, no tocar |

## Cambios Importantes

### ❌ ANTIGUO (no usar):
```
backend/uploads/
backend/logs/
```

### ✅ NUEVO (usar esto):
```
backend/data/uploads/
backend/data/logs/
```

## Cómo Agregar Nuevas Cosas

### 1. Nuevo módulo Python
```bash
cd backend/app/services/
# o api/, models/, storage/, utils/ según corresponda
touch my_module.py
```

### 2. Nuevo script
```bash
cd backend/scripts/
touch my_script.py
chmod +x my_script.py
```

### 3. Nuevo test
```bash
cd backend/tests/
touch test_my_feature.py
```

### 4. Referencia a datos en código

**En un archivo dentro de `backend/app/`:**
```python
import os
from ..config import Config

# Para uploads
upload_path = os.path.join(Config.UPLOAD_FOLDER, 'mis_datos.json')

# Para logs
from ..utils.logger import get_logger
logger = get_logger('mi_modulo')
logger.info("mensaje")  # Se guarda automáticamente en backend/data/logs/
```

## Comandos Comunes

```bash
# Verificar la reorganización
bash verify_reorganization.sh

# Ejecutar tests
cd backend && python -m pytest tests/

# Ejecutar aplicación
npm run dev

# Con Docker
docker-compose up

# Limpiar caché Python
find backend -type d -name __pycache__ -exec rm -rf {} +
find backend -type f -name "*.pyc" -delete
```

## Rutas Relativas (para Developers)

Si trabajas dentro de `backend/app/services/` y necesitas acceder a:

- **backend/data/uploads/**: `../../data/uploads/`
- **backend/data/logs/**: `../../data/logs/`
- **backend/scripts/**: `../../scripts/`

```python
import os
current_file = __file__  # backend/app/services/my_module.py
uploads_dir = os.path.join(os.path.dirname(current_file), '../../data/uploads')
```

## .gitignore

El archivo `.gitignore` está configurado para ignorar:
- `backend/data/` - No se commitean datos de usuarios
- `.env` - Variables de entorno sensibles
- `node_modules/` y `__pycache__/` - Directorios generados

## ¿Qué NO Cambió?

✅ Los scripts siguen en `backend/scripts/`  
✅ El código sigue en `backend/app/`  
✅ Los comandos npm siguen igual: `npm run dev`  
✅ La lógica de la aplicación sigue igual  
✅ Docker sigue funcionando igual  
✅ Las APIs siguen siendo iguales  

**Solo cambiaron las rutas internas de los directorios de datos.**

## En Caso de Error

Si algo no funciona después de la reorganización:

1. Ejecuta el script de verificación:
   ```bash
   bash verify_reorganization.sh
   ```

2. Verifica que `backend/data/` existe:
   ```bash
   ls -la backend/data/
   ```

3. Lee el archivo `REORGANIZATION_SUMMARY.md` para más detalles

---

**¡Listo para trabajar! 🚀**
