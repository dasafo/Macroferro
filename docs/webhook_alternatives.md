# 🌐 Alternativas Gratuitas para Webhooks de Telegram

Este documento lista todas las opciones gratuitas para configurar webhooks de Telegram sin necesidad de servicios de pago.

## 🆓 **Opción 1: Ngrok Gratuito (Más Fácil)**

### ✅ **Ventajas:**
- Configuración en 30 segundos
- No requiere servidor externo
- Perfecto para desarrollo y pruebas

### ❌ **Desventajas:**
- URL cambia cada reinicio
- Límite de conexiones concurrentes
- Dependes de un servicio externo

### 🚀 **Uso:**
```bash
# Ejecutar el script automático
chmod +x scripts/setup_webhook.sh
./scripts/setup_webhook.sh
```

---

## 🏠 **Opción 2: Tu Dominio `dasafodata.com` (Recomendado)**

### ✅ **Ventajas:**
- URL fija y profesional
- Control total sobre la infraestructura
- Mejor rendimiento
- No depende de terceros

### 📋 **Configuración paso a paso:**

#### **1. Configurar DNS**
```bash
# En tu panel de DNS de dasafodata.com, crear:
Tipo: A
Nombre: bot
Valor: [IP_DE_TU_SERVIDOR]
TTL: 300

# Resultado: bot.dasafodata.com → tu servidor
```

#### **2. Configurar HTTPS con Cloudflare (Gratis)**
1. Ve a [Cloudflare](https://cloudflare.com)
2. Agrega tu dominio `dasafodata.com`
3. Cambia los nameservers en tu registrador
4. En Cloudflare > SSL/TLS > Overview > "Full (strict)"
5. ✅ Automáticamente tendrás HTTPS gratuito

#### **3. Configurar Proxy Reverso**

**Opción A: Con nginx**
```nginx
server {
    listen 443 ssl http2;
    server_name bot.dasafodata.com;
    
    # SSL configurado automáticamente por Cloudflare
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Opción B: Con Traefik (Docker)**
```yaml
# docker-compose.yml
version: '3.8'
services:
  traefik:
    image: traefik:v2.10
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./traefik.yml:/traefik.yml
      
  backend:
    # tu configuración actual...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.bot.rule=Host(`bot.dasafodata.com`)"
      - "traefik.http.routers.bot.tls.certresolver=letsencrypt"
```

---

## 🌍 **Opción 3: Servicios de Túnel Gratuitos**

### **3.1 LocalTunnel**
```bash
# Instalar
npm install -g localtunnel

# Usar
lt --port 8000 --subdomain macroferro-bot

# URL resultante: https://macroferro-bot.loca.lt
```

### **3.2 Serveo**
```bash
# SSH tunnel directo
ssh -R 80:localhost:8000 serveo.net

# Con subdominio personalizado
ssh -R macroferro:80:localhost:8000 serveo.net
```

### **3.3 PageKite**
```bash
# Instalar
pip install pagekite

# Usar (30 días gratis)
python pagekite.py 8000 macroferro.pagekite.me
```

---

## 🐳 **Opción 4: Hosting Gratuito con Docker**

### **4.1 Railway**
```bash
# Conectar repo de GitHub
# Railway detecta automáticamente Docker
# URL automática: [app-name].railway.app
```

### **4.2 Render**
```bash
# Conectar repo de GitHub
# Configurar como Web Service
# URL automática: [app-name].onrender.com
```

### **4.3 Fly.io**
```bash
# Instalar flyctl
curl -L https://fly.io/install.sh | sh

# Deploy
fly launch
fly deploy

# URL automática: [app-name].fly.dev
```

---

## 🎯 **Recomendación por Caso de Uso**

| **Caso de Uso** | **Recomendación** | **Por qué** |
|-----------------|-------------------|-------------|
| **Desarrollo/Pruebas** | Ngrok gratuito | Rapidez, simplicidad |
| **Producción** | Tu dominio + Cloudflare | Profesional, confiable |
| **Prototipo rápido** | LocalTunnel | Fácil de usar |
| **Demo público** | Railway/Render | URL bonita y permanente |

---

## 🔧 **Scripts de Configuración Rápida**

### **Para desarrollo (ngrok):**
```bash
./scripts/setup_webhook.sh
```

### **Para producción (tu dominio):**
```bash
# Editar DOMAIN en el script
vim scripts/setup_webhook_domain.sh

# Ejecutar
./scripts/setup_webhook_domain.sh
```

### **Verificar webhook activo:**
```bash
curl -X GET "http://localhost:8000/api/v1/telegram/webhook-info"
```

---

## 🚨 **Consideraciones Importantes**

### **Seguridad:**
- ✅ Siempre usar HTTPS en producción
- ✅ Validar secret token en el webhook
- ✅ Rate limiting para evitar spam

### **Rendimiento:**
- ✅ Tu dominio > servicios externos
- ✅ Cloudflare acelera la entrega global
- ✅ Monitorear latencia del webhook

### **Monitoreo:**
- ✅ Logs de webhooks recibidos
- ✅ Métricas de tiempo de respuesta
- ✅ Alertas si el webhook falla

---

## 📞 **Soporte y Debugging**

### **Verificar si el webhook funciona:**
```bash
# Ver info del webhook actual
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"

# Test manual del endpoint
curl -X POST "https://tu-domain.com/api/v1/telegram/webhook" \
  -H "Content-Type: application/json" \
  -d '{"update_id": 1, "message": {"message_id": 1, "chat": {"id": 123}, "text": "test"}}'
```

### **Logs útiles:**
```bash
# Ver logs del backend
docker compose logs -f backend

# Ver logs de ngrok
curl -s http://localhost:4040/api/requests/http
``` 