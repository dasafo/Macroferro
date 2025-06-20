#!/bin/bash

echo "🤖 Auto-iniciador del túnel Cloudflare"

# Configuración
TUNNEL_NAME="macroferro-bot"
DOMAIN="bot.dasafodata.com"
LOCAL_URL="http://localhost:8000"
HEALTH_ENDPOINT="/api/v1/telegram/health"
CHECK_INTERVAL=10  # segundos

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "[$(date '+%H:%M:%S')] $1"
}

# Función para verificar si el backend está corriendo
check_backend() {
    curl -s -f --max-time 5 ${LOCAL_URL}${HEALTH_ENDPOINT} > /dev/null 2>&1
    return $?
}

# Función para verificar si el túnel está corriendo
check_tunnel() {
    curl -s -f --max-time 10 https://${DOMAIN}${HEALTH_ENDPOINT} > /dev/null 2>&1
    return $?
}

# Función para iniciar el túnel
start_tunnel() {
    log "${BLUE}🌐 Iniciando túnel...${NC}"
    
    # Obtener token
    TOKEN=$(cloudflared tunnel token ${TUNNEL_NAME} 2>/dev/null)
    if [ $? -ne 0 ]; then
        log "${RED}❌ Error obteniendo token del túnel${NC}"
        return 1
    fi
    
    # Matar procesos anteriores
    pkill -f cloudflared 2>/dev/null || true
    sleep 2
    
    # Iniciar túnel en segundo plano
    nohup cloudflared tunnel run --token ${TOKEN} --loglevel warn > /dev/null 2>&1 &
    TUNNEL_PID=$!
    
    # Esperar un poco para que se conecte
    sleep 15
    
    # Verificar que funcione
    if check_tunnel; then
        log "${GREEN}✅ Túnel iniciado correctamente (PID: ${TUNNEL_PID})${NC}"
        echo ${TUNNEL_PID} > /tmp/cloudflared.pid
        return 0
    else
        log "${RED}❌ Túnel no pudo conectarse${NC}"
        kill ${TUNNEL_PID} 2>/dev/null || true
        return 1
    fi
}

# Función principal de monitoreo
monitor() {
    log "${BLUE}👀 Iniciando monitoreo automático...${NC}"
    log "${YELLOW}💡 Presiona Ctrl+C para detener${NC}"
    
    while true; do
        # Verificar backend
        if ! check_backend; then
            log "${YELLOW}⏳ Esperando que el backend esté listo...${NC}"
            sleep ${CHECK_INTERVAL}
            continue
        fi
        
        # Backend está corriendo, verificar túnel
        if ! check_tunnel; then
            log "${YELLOW}🔧 Backend listo, túnel no conectado. Iniciando túnel...${NC}"
            if start_tunnel; then
                log "${GREEN}🎉 ¡Bot completamente operativo!${NC}"
                log "${BLUE}📱 URL: https://${DOMAIN}${NC}"
            else
                log "${RED}❌ Error iniciando túnel, reintentando en ${CHECK_INTERVAL}s...${NC}"
            fi
        else
            # Todo está funcionando
            log "${GREEN}✅ Backend y túnel funcionando correctamente${NC}"
        fi
        
        sleep ${CHECK_INTERVAL}
    done
}

# Función de cleanup al salir
cleanup() {
    log "${YELLOW}🛑 Deteniendo monitoreo...${NC}"
    if [ -f /tmp/cloudflared.pid ]; then
        TUNNEL_PID=$(cat /tmp/cloudflared.pid)
        if kill -0 ${TUNNEL_PID} 2>/dev/null; then
            log "${BLUE}🔌 Deteniendo túnel (PID: ${TUNNEL_PID})...${NC}"
            kill ${TUNNEL_PID}
        fi
        rm -f /tmp/cloudflared.pid
    fi
    log "${GREEN}👋 ¡Hasta luego!${NC}"
    exit 0
}

# Configurar trap para cleanup
trap cleanup SIGINT SIGTERM

# Ejecutar según parámetro
case "${1:-monitor}" in
    "start")
        log "${BLUE}🚀 Iniciando túnel manualmente...${NC}"
        if check_backend; then
            start_tunnel
        else
            log "${RED}❌ Backend no está corriendo${NC}"
            exit 1
        fi
        ;;
    "monitor")
        monitor
        ;;
    "stop")
        if [ -f /tmp/cloudflared.pid ]; then
            TUNNEL_PID=$(cat /tmp/cloudflared.pid)
            if kill -0 ${TUNNEL_PID} 2>/dev/null; then
                log "${BLUE}🔌 Deteniendo túnel...${NC}"
                kill ${TUNNEL_PID}
                rm -f /tmp/cloudflared.pid
                log "${GREEN}✅ Túnel detenido${NC}"
            else
                log "${YELLOW}⚠️  Túnel no estaba corriendo${NC}"
            fi
        else
            log "${YELLOW}⚠️  No se encontró PID del túnel${NC}"
        fi
        ;;
    *)
        echo "Uso: $0 [start|monitor|stop]"
        echo "  start   - Iniciar túnel una vez"
        echo "  monitor - Monitorear y auto-iniciar (por defecto)"
        echo "  stop    - Detener túnel"
        exit 1
        ;;
esac 