#!/bin/bash
# Script para añadir DATABASE_URL al .env

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}📝 Añadiendo DATABASE_URL al archivo .env${NC}"
echo ""

# Pedir contraseña
read -sp "Ingresa tu contraseña de Supabase: " PASSWORD
echo ""

# Construir la URL
DATABASE_URL="postgresql://postgres:${PASSWORD}@db.tqqvgaiueheiqtqmbpjh.supabase.co:5432/postgres"

# Verificar si ya existe DATABASE_URL en .env
if grep -q "^DATABASE_URL=" .env 2>/dev/null; then
    echo -e "${YELLOW}⚠️  DATABASE_URL ya existe en .env${NC}"
    read -p "¿Quieres reemplazarlo? (s/n): " REPLACE
    if [[ $REPLACE == "s" || $REPLACE == "S" ]]; then
        # Reemplazar la línea existente
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s|^DATABASE_URL=.*|DATABASE_URL=${DATABASE_URL}|" .env
        else
            # Linux
            sed -i "s|^DATABASE_URL=.*|DATABASE_URL=${DATABASE_URL}|" .env
        fi
        echo -e "${GREEN}✅ DATABASE_URL actualizado en .env${NC}"
    else
        echo "❌ Operación cancelada"
        exit 0
    fi
else
    # Añadir al final del archivo
    echo "" >> .env
    echo "# PostgreSQL connection for LangGraph persistent memory" >> .env
    echo "DATABASE_URL=${DATABASE_URL}" >> .env
    echo -e "${GREEN}✅ DATABASE_URL añadido a .env${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Configuración completa!${NC}"
echo ""
echo "Próximos pasos:"
echo "1. Reinicia el backend:"
echo "   pkill -f 'python.*app.py'"
echo "   python3 app.py"
echo ""
echo "2. Verifica que veas este mensaje:"
echo "   ✅ Using PostgreSQL checkpointer for persistent memory"
echo ""

