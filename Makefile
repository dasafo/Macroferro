# Makefile para Macroferro
# Proyecto de gestión mayorista B2B con FastAPI

# Variables de configuración
COMPOSE_FILE := docker-compose.yml
PROJECT_NAME := macroferro
BACKEND_CONTAINER := $(PROJECT_NAME)_backend
POSTGRES_CONTAINER := $(PROJECT_NAME)_postgres
REDIS_CONTAINER := $(PROJECT_NAME)_redis
QDRANT_CONTAINER := $(PROJECT_NAME)_qdrant
PGADMIN_CONTAINER := $(PROJECT_NAME)_pgadmin

# Colores para output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color
BLUE := \033[0;34m

.PHONY: help build up down restart status logs clean test dev prod backup restore

# Comando por defecto
.DEFAULT_GOAL := help

## 🚀 Comandos principales
help: ## Mostrar esta ayuda
	@echo "$(GREEN)Makefile para Macroferro - Sistema de Gestión Mayorista B2B$(NC)"
	@echo "$(BLUE)===============================================================$(NC)"
	@echo ""
	@echo "$(YELLOW)Uso: make [comando]$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

build: ## 🔨 Construir todos los contenedores
	@echo "$(YELLOW)🔨 Construyendo contenedores...$(NC)"
	docker compose -f $(COMPOSE_FILE) build

up: ## ⬆️ Levantar todos los servicios
	@echo "$(YELLOW)⬆️ Levantando servicios...$(NC)"
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "$(GREEN)✅ Servicios levantados correctamente$(NC)"
	@echo "$(BLUE)📖 API Docs: http://localhost:8000/docs$(NC)"
	@echo "$(BLUE)🐘 PgAdmin: http://localhost:5050$(NC)"

down: ## ⬇️ Bajar todos los servicios
	@echo "$(YELLOW)⬇️ Bajando servicios...$(NC)"
	docker compose -f $(COMPOSE_FILE) down
	@echo "$(GREEN)✅ Servicios detenidos correctamente$(NC)"

restart: ## 🔄 Reiniciar todos los servicios
	@echo "$(YELLOW)🔄 Reiniciando servicios...$(NC)"
	docker compose -f $(COMPOSE_FILE) restart
	@echo "$(GREEN)✅ Servicios reiniciados correctamente$(NC)"

## 📊 Monitoreo y logs
status: ## 📊 Ver estado de contenedores
	@echo "$(YELLOW)📊 Estado de contenedores:$(NC)"
	docker compose -f $(COMPOSE_FILE) ps

logs: ## 📋 Ver logs de todos los servicios
	@echo "$(YELLOW)📋 Logs de todos los servicios:$(NC)"
	docker compose -f $(COMPOSE_FILE) logs --tail=50 -f

logs-backend: ## 📋 Ver logs del backend
	@echo "$(YELLOW)📋 Logs del backend:$(NC)"
	docker logs -f $(BACKEND_CONTAINER)

logs-db: ## 📋 Ver logs de PostgreSQL
	@echo "$(YELLOW)📋 Logs de PostgreSQL:$(NC)"
	docker logs -f $(POSTGRES_CONTAINER)

logs-redis: ## 📋 Ver logs de Redis
	@echo "$(YELLOW)📋 Logs de Redis:$(NC)"
	docker logs -f $(REDIS_CONTAINER)

logs-qdrant: ## 📋 Ver logs de Qdrant
	@echo "$(YELLOW)📋 Logs de Qdrant:$(NC)"
	docker logs -f $(QDRANT_CONTAINER)

## 🔧 Desarrollo
dev: ## 🚀 Modo desarrollo (build + up + logs)
	@echo "$(YELLOW)🚀 Iniciando modo desarrollo...$(NC)"
	make build
	make up
	@echo "$(GREEN)✅ Entorno de desarrollo listo$(NC)"
	@echo "$(BLUE)🔍 Para ver logs: make logs$(NC)"

rebuild: ## 🔨 Reconstruir y levantar servicios
	@echo "$(YELLOW)🔨 Reconstruyendo servicios...$(NC)"
	docker compose -f $(COMPOSE_FILE) up -d --build
	@echo "$(GREEN)✅ Servicios reconstruidos y levantados$(NC)"

rebuild-backend: ## 🔨 Reconstruir solo el backend
	@echo "$(YELLOW)🔨 Reconstruyendo backend...$(NC)"
	docker compose -f $(COMPOSE_FILE) up -d --build backend
	@echo "$(GREEN)✅ Backend reconstruido$(NC)"

## 🔍 Debugging y acceso
shell-backend: ## 🐚 Acceso shell al contenedor backend
	@echo "$(YELLOW)🐚 Accediendo al contenedor backend...$(NC)"
	docker exec -it $(BACKEND_CONTAINER) /bin/bash

shell-db: ## 🐚 Acceso shell a PostgreSQL
	@echo "$(YELLOW)🐚 Accediendo a PostgreSQL...$(NC)"
	docker exec -it $(POSTGRES_CONTAINER) psql -U user -d macroferro_db

shell-redis: ## 🐚 Acceso shell a Redis
	@echo "$(YELLOW)🐚 Accediendo a Redis...$(NC)"
	docker exec -it $(REDIS_CONTAINER) redis-cli

## 🧹 Limpieza
clean: ## 🧹 Limpiar contenedores, imágenes y volúmenes
	@echo "$(YELLOW)🧹 Limpiando recursos Docker...$(NC)"
	docker compose -f $(COMPOSE_FILE) down -v --remove-orphans
	docker system prune -f
	@echo "$(GREEN)✅ Limpieza completada$(NC)"

clean-all: ## 🧹 Limpieza completa (incluye imágenes)
	@echo "$(RED)⚠️ ATENCIÓN: Esto eliminará TODAS las imágenes Docker$(NC)"
	@read -p "¿Estás seguro? [y/N]: " confirm && [ "$$confirm" = "y" ]
	docker compose -f $(COMPOSE_FILE) down -v --remove-orphans
	docker system prune -a -f
	@echo "$(GREEN)✅ Limpieza completa realizada$(NC)"

## 🧪 Testing y verificación
test-api: ## 🧪 Probar endpoints básicos de la API
	@echo "$(YELLOW)🧪 Probando endpoints de la API...$(NC)"
	@echo "$(BLUE)🔍 Health check:$(NC)"
	curl -s http://localhost:8000/ | jq . || echo "API no disponible"
	@echo "\n$(BLUE)📦 Productos:$(NC)"
	curl -s http://localhost:8000/api/v1/products/?limit=3 | jq '.[:3]' || echo "Endpoint de productos no disponible"
	@echo "\n$(BLUE)📁 Categorías:$(NC)"
	curl -s http://localhost:8000/api/v1/categories/?limit=3 | jq '.[:3]' || echo "Endpoint de categorías no disponible"

check-health: ## 🏥 Verificar salud de todos los servicios
	@echo "$(YELLOW)🏥 Verificando salud de servicios...$(NC)"
	@echo "$(BLUE)Backend:$(NC)"
	@curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:8000/ || echo "❌ Backend no responde"
	@echo "$(BLUE)PgAdmin:$(NC)"
	@curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:5050/ || echo "❌ PgAdmin no responde"
	@echo "$(BLUE)Qdrant:$(NC)"
	@curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:6333/ || echo "❌ Qdrant no responde"

## 📊 Información del sistema
info: ## 📊 Mostrar información del proyecto
	@echo "$(GREEN)📊 Información del Proyecto Macroferro$(NC)"
	@echo "$(BLUE)===============================================$(NC)"
	@echo "Proyecto: $(PROJECT_NAME)"
	@echo "Compose File: $(COMPOSE_FILE)"
	@echo ""
	@echo "$(YELLOW)🔗 URLs de Servicios:$(NC)"
	@echo "  • API Backend: http://localhost:8000"
	@echo "  • API Docs: http://localhost:8000/docs"
	@echo "  • PgAdmin: http://localhost:5050"
	@echo "  • Qdrant: http://localhost:6333"
	@echo "  • Redis: localhost:6379"
	@echo ""
	@echo "$(YELLOW)📦 Contenedores:$(NC)"
	@echo "  • Backend: $(BACKEND_CONTAINER)"
	@echo "  • PostgreSQL: $(POSTGRES_CONTAINER)"
	@echo "  • Redis: $(REDIS_CONTAINER)"
	@echo "  • Qdrant: $(QDRANT_CONTAINER)"
	@echo "  • PgAdmin: $(PGADMIN_CONTAINER)"

## 🗃️ Base de datos
db-backup: ## 💾 Backup de la base de datos
	@echo "$(YELLOW)💾 Creando backup de la base de datos...$(NC)"
	@mkdir -p backups
	docker exec $(POSTGRES_CONTAINER) pg_dump -U user macroferro_db > backups/macroferro_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✅ Backup creado en backups/$(NC)"

db-restore: ## 📥 Restaurar base de datos (requiere archivo)
	@echo "$(YELLOW)📥 Restaurando base de datos...$(NC)"
	@echo "$(RED)Uso: make db-restore FILE=backups/archivo.sql$(NC)"
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED)❌ Error: Especifica el archivo con FILE=ruta/archivo.sql$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f "$(FILE)" ]; then \
		echo "$(RED)❌ Error: Archivo $(FILE) no encontrado$(NC)"; \
		exit 1; \
	fi
	docker exec -i $(POSTGRES_CONTAINER) psql -U user macroferro_db < $(FILE)
	@echo "$(GREEN)✅ Base de datos restaurada$(NC)"

## 🚀 Entornos
prod: ## 🚀 Levantar en modo producción
	@echo "$(YELLOW)🚀 Levantando en modo producción...$(NC)"
	docker compose -f $(COMPOSE_FILE) up -d --build
	@echo "$(GREEN)✅ Entorno de producción levantado$(NC)"

## 📈 Monitoreo avanzado
watch-logs: ## 👀 Monitorear logs en tiempo real (filtrado)
	@echo "$(YELLOW)👀 Monitoreando logs (Ctrl+C para salir)...$(NC)"
	docker compose -f $(COMPOSE_FILE) logs -f | grep -E "(ERROR|WARNING|INFO|Started|Stopped)"

stats: ## 📈 Estadísticas de contenedores
	@echo "$(YELLOW)📈 Estadísticas de contenedores:$(NC)"
	docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

## 🔧 Utilidades
update: ## 🔄 Actualizar imágenes base
	@echo "$(YELLOW)🔄 Actualizando imágenes base...$(NC)"
	docker compose -f $(COMPOSE_FILE) pull
	@echo "$(GREEN)✅ Imágenes actualizadas$(NC)"

ports: ## 🌐 Mostrar puertos utilizados
	@echo "$(YELLOW)🌐 Puertos utilizados por el proyecto:$(NC)"
	@echo "  • 8000 - FastAPI Backend"
	@echo "  • 5432 - PostgreSQL"
	@echo "  • 5050 - PgAdmin"
	@echo "  • 6379 - Redis"
	@echo "  • 6333 - Qdrant"

## 📚 Documentación
docs: ## 📚 Abrir documentación de la API
	@echo "$(YELLOW)📚 Abriendo documentación de la API...$(NC)"
	@command -v xdg-open >/dev/null 2>&1 && xdg-open http://localhost:8000/docs || \
	command -v open >/dev/null 2>&1 && open http://localhost:8000/docs || \
	echo "$(BLUE)📖 Visita: http://localhost:8000/docs$(NC)"

## 🎯 Comandos rápidos
quick-start: ## ⚡ Inicio rápido (clean + build + up)
	@echo "$(YELLOW)⚡ Inicio rápido del proyecto...$(NC)"
	make clean
	make build
	make up
	@echo "$(GREEN)✅ Proyecto iniciado correctamente$(NC)"
	@echo "$(BLUE)🔍 Verifica el estado con: make status$(NC)"

stop-all: ## ⏹️ Parar todos los contenedores de Docker
	@echo "$(YELLOW)⏹️ Parando todos los contenedores de Docker...$(NC)"
	docker stop $$(docker ps -q) 2>/dev/null || echo "No hay contenedores ejecutándose"
	@echo "$(GREEN)✅ Todos los contenedores detenidos$(NC)"

## 🤖 Inteligencia Artificial
update-catalog: ## 🔄 Actualizar el catálogo de productos con IA (descripciones y embeddings)
	@echo "$(YELLOW)🤖 Actualizando catálogo de productos con IA...$(NC)"
	@echo "$(BLUE)🔍 Ejecutando script de indexación...$(NC)"
	docker exec $(BACKEND_CONTAINER) python scripts/index_qdrant_data.py
	@echo "$(GREEN)✅ Catálogo actualizado correctamente$(NC)"

search-test: ## 🧪 Probar la búsqueda semántica con una consulta
	@echo "$(YELLOW)🧪 Probando búsqueda semántica...$(NC)"
	@if [ -z "$(query)" ]; then \
		echo "$(RED)❌ Error: Debes proporcionar una consulta. Uso: make search-test query=\"tu búsqueda\"$(NC)"; \
		exit 1; \
	fi
	docker exec $(BACKEND_CONTAINER) python scripts/test_semantic_search.py "$(query)" 