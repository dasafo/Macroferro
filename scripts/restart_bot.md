# 🔄 Sistema de Auto-Inicio del Bot de Telegram

## 🎯 **Nuevo Enfoque: Completamente Automático**

### **✅ Situación Ideal (Recomendada):**
```bash
# Iniciar el auto-monitor en segundo plano
nohup ./scripts/auto_start_tunnel.sh monitor > tunnel.log 2>&1 &

# Iniciar el backend
docker compose up -d
```

**¡El túnel se iniciará automáticamente cuando el backend esté listo!**

---

## 🛠️ **Opciones del Auto-Monitor:**

### **Monitoreo Automático (en primer plano):**
```bash
./scripts/auto_start_tunnel.sh monitor
```
- 🔍 Detecta cuando el backend está listo
- 🌐 Inicia el túnel automáticamente
- ✅ Mantiene todo funcionando
- 📊 Muestra logs en tiempo real

### **Monitoreo en Segundo Plano:**
```bash
nohup ./scripts/auto_start_tunnel.sh monitor > tunnel.log 2>&1 &
```
- 🤖 Funciona completamente automático
- 📝 Logs guardados en `tunnel.log`
- 🔄 Se reinicia automáticamente si falla

### **Inicio Manual (solo una vez):**
```bash
./scripts/auto_start_tunnel.sh start
```

### **Detener Túnel:**
```bash
./scripts/auto_start_tunnel.sh stop
```

---

## 🚨 **Si algo no funciona:**

### **Opción de Emergencia - Script Completo:**
```bash
./scripts/start_tunnel.sh
```

### **Verificación Manual:**
```bash
# 1. Backend
curl -s http://localhost:8000/api/v1/telegram/health

# 2. Túnel
curl -s https://bot.dasafodata.com/api/v1/telegram/health

# 3. Ver logs del auto-monitor
tail -f tunnel.log
```

---

## ⚡ **Flujo de Trabajo Recomendado:**

```bash
# 1. Iniciar auto-monitor (una sola vez)
nohup ./scripts/auto_start_tunnel.sh monitor > tunnel.log 2>&1 &

# 2. Desde ahora, solo necesitas:
docker compose up -d
docker compose down

# El túnel se maneja automáticamente ✨
```

## 🔑 **Puntos Clave:**
- ✅ **Webhook**: Permanentemente configurado
- 🤖 **Auto-Monitor**: Detecta y conecta automáticamente  
- 🔄 **Reinicio**: Solo `docker compose up -d`
- 🛠️ **Emergencia**: `./scripts/start_tunnel.sh` 