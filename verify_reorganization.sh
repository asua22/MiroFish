#!/bin/bash

echo "🔍 Verificando reorganización del proyecto..."
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

errors=0

# Check directory structure
echo "📂 Verificando estructura de directorios..."
dirs=(
    "backend/app"
    "backend/scripts"
    "backend/data"
    "backend/data/logs"
    "backend/data/uploads"
    "backend/data/uploads/projects"
    "backend/data/uploads/reports"
    "backend/data/uploads/simulations"
    "backend/tests"
    "frontend"
)

for dir in "${dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "  ${GREEN}✓${NC} $dir"
    else
        echo -e "  ${RED}✗${NC} $dir"
        ((errors++))
    fi
done

echo ""
echo "🔍 Verificando que NO existan directorios antiguos..."
old_dirs=(
    "backend/uploads"
    "backend/logs"
)

for dir in "${old_dirs[@]}"; do
    if [ ! -d "$dir" ]; then
        echo -e "  ${GREEN}✓${NC} $dir eliminado correctamente"
    else
        echo -e "  ${RED}✗${NC} $dir aún existe (debería estar eliminado)"
        ((errors++))
    fi
done

echo ""
echo "🔍 Verificando archivos de configuración..."
config_files=(
    "backend/app/config.py"
    "backend/app/utils/logger.py"
    "backend/app/api/simulation.py"
    "backend/app/services/simulation_manager.py"
    "docker-compose.yml"
    ".gitignore"
)

for file in "${config_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file no encontrado"
        ((errors++))
    fi
done

echo ""
echo "🔍 Verificando que las rutas están correctamente actualizadas..."

# Check for incorrect paths
incorrect_paths=$(grep -r "backend/uploads\|backend/logs" --include="*.py" backend/app --exclude-dir="__pycache__" 2>/dev/null || true)

if [ -z "$incorrect_paths" ]; then
    echo -e "  ${GREEN}✓${NC} No hay referencias a backend/uploads o backend/logs en código"
else
    echo -e "  ${RED}✗${NC} Se encontraron referencias antiguas:"
    echo "$incorrect_paths" | sed 's/^/    /'
    ((errors++))
fi

# Check for new paths
data_paths=$(grep -r "backend/data/uploads\|backend/data/logs" --include="*.py" backend/app --exclude-dir="__pycache__" | wc -l)

if [ "$data_paths" -gt 0 ]; then
    echo -e "  ${GREEN}✓${NC} Se encontraron $data_paths referencias a backend/data/ (correcto)"
else
    echo -e "  ${YELLOW}⚠${NC} No se encontraron referencias a backend/data/"
fi

echo ""
echo "📊 Resumen:"
if [ $errors -eq 0 ]; then
    echo -e "${GREEN}✓ Reorganización verificada correctamente${NC}"
    exit 0
else
    echo -e "${RED}✗ Se encontraron $errors errores${NC}"
    exit 1
fi
