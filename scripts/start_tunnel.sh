#!/bin/bash

echo "🚀 Iniciando túnel de Cloudflare para Macroferro Bot..."

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuración
TUNNEL_NAME="macroferro-bot"
DOMAIN="bot.dasafodata.com"
LOCAL_URL="http://localhost:8000"
WEBHOOK_ENDPOINT="/api/v1/telegram/webhook"
HEALTH_ENDPOINT="/api/v1/telegram/health"

echo -e "${BLUE}📋 Configuración:${NC}"
echo -e "  Túnel: ${TUNNEL_NAME}"
echo -e "  Dominio: ${DOMAIN}"
echo -e "  Backend: ${LOCAL_URL}"
echo ""

# 1. Verificar que el backend esté corriendo
echo -e "${BLUE}🔍 Verificando backend...${NC}"
if curl -s -f ${LOCAL_URL}${HEALTH_ENDPOINT} > /dev/null; then
    echo -e "${GREEN}✅ Backend está corriendo${NC}"
else
    echo -e "${RED}❌ Backend no está corriendo. Iniciando...${NC}"
    docker compose up -d
    sleep 10
    
    if curl -s -f ${LOCAL_URL}${HEALTH_ENDPOINT} > /dev/null; then
        echo -e "${GREEN}✅ Backend iniciado correctamente${NC}"
    else
        echo -e "${RED}❌ Error: No se pudo iniciar el backend${NC}"
        exit 1
    fi
fi

# 2. Obtener token del túnel
echo -e "${BLUE}🔑 Obteniendo token del túnel...${NC}"
TOKEN=$(cloudflared tunnel token ${TUNNEL_NAME})
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Token obtenido${NC}"
else
    echo -e "${RED}❌ Error obteniendo token${NC}"
    exit 1
fi

# 3. Matar procesos anteriores de cloudflared
echo -e "${BLUE}🛑 Limpiando procesos anteriores...${NC}"
pkill -f cloudflared 2>/dev/null || true

# 4. Iniciar túnel
echo -e "${BLUE}🌐 Iniciando túnel...${NC}"
cloudflared tunnel run --token ${TOKEN} --loglevel info &
TUNNEL_PID=$!

# Esperar a que el túnel se conecte
echo -e "${BLUE}⏳ Esperando conexión del túnel...${NC}"
sleep 15

# 5. Verificar que el túnel esté funcionando
echo -e "${BLUE}🧪 Probando conexión...${NC}"
for i in {1..10}; do
    if curl -s -f --max-time 10 https://${DOMAIN}${HEALTH_ENDPOINT} > /dev/null; then
        echo -e "${GREEN}✅ Túnel funcionando correctamente${NC}"
        TUNNEL_WORKING=true
        break
    else
        echo -e "  Intento ${i}/10 fallido, esperando..."
        sleep 5
    fi
done

if [ "${TUNNEL_WORKING}" != "true" ]; then
    echo -e "${RED}❌ Error: Túnel no está funcionando después de 10 intentos${NC}"
    kill ${TUNNEL_PID} 2>/dev/null || true
    exit 1
fi

# 6. Configurar webhook de Telegram
echo -e "${BLUE}📨 Configurando webhook de Telegram...${NC}"
WEBHOOK_URL="https://${DOMAIN}${WEBHOOK_ENDPOINT}"
RESPONSE=$(curl -s -X POST ${LOCAL_URL}/api/v1/telegram/set-webhook \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"${WEBHOOK_URL}\"}")

if echo "${RESPONSE}" | grep -q "error" || echo "${RESPONSE}" | grep -q "detail"; then
    echo -e "${RED}❌ Error configurando webhook:${NC}"
    echo "${RESPONSE}"
else
    echo -e "${GREEN}✅ Webhook configurado correctamente${NC}"
    echo -e "  URL: ${WEBHOOK_URL}"
fi

# 7. Mostrar información final
echo ""
echo -e "${GREEN}🎉 ¡Túnel configurado exitosamente!${NC}"
echo ""
echo -e "${BLUE}📊 Información del túnel:${NC}"
echo -e "  🌐 URL pública: https://${DOMAIN}"
echo -e "  🏥 Health check: https://${DOMAIN}${HEALTH_ENDPOINT}"
echo -e "  📨 Webhook: https://${DOMAIN}${WEBHOOK_ENDPOINT}"
echo -e "  🔧 PID del túnel: ${TUNNEL_PID}"
echo ""
echo -e "${BLUE}💡 Para detener el túnel:${NC}"
echo -e "  kill ${TUNNEL_PID}"
echo ""
echo -e "${BLUE}📱 Tu bot de Telegram ya está listo para recibir mensajes${NC}"
echo ""

# Mantener el script corriendo para mostrar logs
echo -e "${BLUE}📋 Presiona Ctrl+C para detener el túnel${NC}"
wait ${TUNNEL_PID} 