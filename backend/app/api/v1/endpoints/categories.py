# backend/app/api/v1/endpoints/categories.py

"""
Endpoints de la API REST para operaciones con categorías.

Esta capa implementa los controladores REST para el recurso Category,
actuando como interfaz entre las peticiones HTTP y la capa de servicios.
Maneja la serialización/deserialización de datos, códigos de estado HTTP,
y la traducción de excepciones de negocio a respuestas HTTP apropiadas.

Responsabilidades de esta capa:
- Definición de endpoints REST con sus rutas y métodos HTTP
- Validación de entrada usando esquemas Pydantic
- Manejo de inyección de dependencias (database session)
- Traducción de errores de negocio a códigos HTTP apropiados
- Documentación automática de la API con OpenAPI/Swagger
- Aplicación de políticas de autorización (futuro)

Arquitectura utilizada:
- Controller Layer: Maneja peticiones HTTP y respuestas
- Dependency Injection: Inyección de sesión de BD via FastAPI
- Schema-driven: Validación automática con Pydantic
- Service Layer Integration: Delega lógica de negocio a CategoryService
- Error Handling: Traducción consistente de errores a HTTP

Patrones implementados:
- REST Resource: Operaciones CRUD estándar
- Dependency Injection: get_db() inyecta sesión de SQLAlchemy
- DTO Pattern: Esquemas Pydantic como Data Transfer Objects
- Exception Translation: Conversión de errores de negocio a HTTP
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api import deps # Importamos get_db desde deps.py para inyección de dependencias
from app.schemas import category as category_schema # Schemas Pydantic para validación y serialización
from app.services.category_service import category_service # Capa de servicios con lógica de negocio
# from app.core.exceptions import NotFoundError, DuplicateError # Para manejo de errores personalizado futuro

# Configuración del router para agrupar endpoints relacionados con categorías
# Prefix será agregado por el router principal (ej: /api/v1/categories)
router = APIRouter()

# ========================================
# ENDPOINTS DE ESCRITURA (CREATE, UPDATE, DELETE)
# ========================================

@router.post("/", response_model=category_schema.CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    *,
    db: Session = Depends(deps.get_db),  # Inyección de dependencia: sesión de BD
    category_in: category_schema.CategoryCreate  # Validación automática con Pydantic
) -> category_schema.CategoryResponse:
    """
    Crea una nueva categoría en el sistema.
    
    Este endpoint permite la creación de categorías tanto raíz como subcategorías,
    con validaciones automáticas de integridad referencial y prevención de duplicados.
    
    **Validaciones aplicadas:**
    - Category ID debe ser único (validación de BD)
    - Nombre único por nivel jerárquico (constraint UNIQUE en BD)
    - Parent ID debe existir si se especifica (validación de servicio)
    - Datos requeridos según esquema CategoryCreate
    
    **Códigos de estado:**
    - 201: Categoría creada exitosamente
    - 409: Conflicto (ID duplicado o nombre duplicado en mismo nivel)
    - 404: Categoría padre no encontrada (si parent_id especificado)
    - 422: Datos de entrada inválidos (validación Pydantic)
    
    **Consideraciones especiales:**
    - Diseñado para carga inicial desde CSV con IDs predefinidos
    - En producción, los IDs serían típicamente autogenerados
    - Validación de duplicados relaxed para facilitar carga masiva
    
    **Manejo de errores futuro:**
    Cuando se implemente el sistema de excepciones personalizadas:
    - DuplicateError → 409 Conflict
    - NotFoundError (padre) → 404 Not Found
    - ValidationError → 422 Unprocessable Entity
    
    Args:
        db: Sesión de SQLAlchemy inyectada automáticamente
        category_in: Datos de la categoría validados por Pydantic
        
    Returns:
        CategoryResponse: Categoría creada con todos sus campos
        
    Raises:
        HTTPException: 409 si la categoría ya existe
        HTTPException: 422 si los datos son inválidos
    """
    # VALIDACIÓN PREVIA: Verificar que el ID no esté en uso
    # Esta validación previene errores 500 de la BD y proporciona mensajes más claros
    existing_category_by_id = category_service.get_category_by_id(db, category_id=category_in.category_id)
    if existing_category_by_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with ID {category_in.category_id} already exists."
        )
    
    # DELEGACIÓN A SERVICIO: La lógica de negocio se maneja en la capa de servicios
    # El servicio maneja validaciones adicionales como existencia del padre y duplicados por nombre
    category = category_service.create_new_category(db=db, category_in=category_in)
    
    # MANEJO DE ERRORES FUTURO (cuando se implementen excepciones personalizadas):
    # try:
    #     category = category_service.create_new_category(db=db, category_in=category_in)
    # except DuplicateError as e:
    #     raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    # except NotFoundError as e: # Si el padre no se encuentra
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
    return category


@router.put("/{category_id}", response_model=category_schema.CategoryResponse)
async def update_category(
    *,
    db: Session = Depends(deps.get_db),
    category_id: int,  # Path parameter: ID de la categoría a actualizar
    category_in: category_schema.CategoryUpdate,  # Body: campos a actualizar (opcionales)
) -> category_schema.CategoryResponse:
    """
    Actualiza una categoría existente.
    
    Permite actualización parcial de categorías, incluyendo cambio de nombre,
    descripción y reubicación en la jerarquía (cambio de padre).
    
    **Operaciones soportadas:**
    - Cambio de nombre (con validación de duplicados)
    - Actualización de descripción
    - Cambio de categoría padre (reubicación en jerarquía)
    - Actualización parcial (solo campos especificados)
    
    **Validaciones aplicadas:**
    - Categoría objetivo debe existir
    - Nuevo nombre no debe duplicarse en el mismo nivel
    - Nueva categoría padre debe existir (si se especifica)
    - Prevención de ciclos en jerarquía (validación futura)
    
    **Códigos de estado:**
    - 200: Actualización exitosa
    - 404: Categoría no encontrada para actualizar
    - 409: Conflicto (nombre duplicado o ciclo en jerarquía)
    - 422: Datos de entrada inválidos
    
    **Consideraciones de negocio:**
    - Cambiar parent_id puede afectar productos asociados
    - Cambio de nombre puede afectar URLs y navegación
    - Las validaciones consideran el estado actual + cambios propuestos
    
    Args:
        db: Sesión de SQLAlchemy
        category_id: ID de la categoría a actualizar
        category_in: Campos a actualizar (esquema con campos opcionales)
        
    Returns:
        CategoryResponse: Categoría actualizada
        
    Raises:
        HTTPException: 404 si la categoría no existe
        HTTPException: 409 si hay conflictos de validación
    """
    category = category_service.update_existing_category(db=db, category_id=category_id, category_in=category_in)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found for update")
    
    # MANEJO DE ERRORES FUTURO:
    # El servicio podría lanzar DuplicateError o NotFoundError (para el nuevo padre)
    # try:
    #     category = category_service.update_existing_category(db=db, category_id=category_id, category_in=category_in)
    #     if not category:
    #         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found for update")
    # except DuplicateError as e:
    #     raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    # except NotFoundError as e:  # Para nuevo padre inválido
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
    return category


@router.delete("/{category_id}", response_model=category_schema.CategoryResponse)
async def delete_category(
    *,
    db: Session = Depends(deps.get_db),
    category_id: int,  # Path parameter: ID de la categoría a eliminar
) -> category_schema.CategoryResponse:
    """
    Elimina una categoría del sistema.
    
    **ADVERTENCIA: Operación crítica con efectos colaterales**
    
    La eliminación de una categoría tiene impactos importantes en el sistema:
    - Productos asociados quedan sin categoría (category_id = NULL)
    - Subcategorías se convierten en categorías raíz (parent_id = NULL)
    - Se pierden relaciones jerárquicas establecidas
    
    **Efectos colaterales (manejados por FK constraints):**
    - products.category_id → NULL (ON DELETE SET NULL)
    - categories.parent_id → NULL (ON DELETE SET NULL)
    
    **Códigos de estado:**
    - 200: Eliminación exitosa, devuelve la categoría eliminada
    - 404: Categoría no encontrada
    - 409: No se puede eliminar (restricciones de negocio futuras)
    
    **Validaciones futuras recomendadas:**
    - Verificar impacto en productos asociados
    - Evaluar subcategorías que se volverían huérfanas
    - Requerir confirmación explícita para categorías con contenido
    - Considerar soft delete en lugar de eliminación física
    
    **Alternativas de implementación futuras:**
    - Soft delete: Marcar como inactiva en lugar de eliminar
    - Reasignación: Mover productos y subcategorías antes de eliminar
    - Confirmación: Requerir parámetro de confirmación explícita
    
    Args:
        db: Sesión de SQLAlchemy
        category_id: ID de la categoría a eliminar
        
    Returns:
        CategoryResponse: Datos de la categoría eliminada (para confirmación)
        
    Raises:
        HTTPException: 404 si la categoría no existe
        
    Note:
        En un sistema de producción, se recomendaría requerir confirmación
        explícita y mostrar el impacto antes de permitir la eliminación.
    """
    deleted_category = category_service.delete_existing_category(db=db, category_id=category_id)
    if not deleted_category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found for deletion")
    return deleted_category

# ========================================
# ENDPOINTS DE LECTURA (READ, LIST)
# ========================================

@router.get("/{category_id}", response_model=category_schema.CategoryResponse)
async def read_category(
    *,
    db: Session = Depends(deps.get_db),
    category_id: int,  # Path parameter: ID de la categoría a obtener
) -> category_schema.CategoryResponse:
    """
    Obtiene los detalles de una categoría específica por su ID.
    
    Endpoint para recuperar información completa de una categoría individual,
    incluyendo sus metadatos y posición en la jerarquía.
    
    **Información devuelta:**
    - Datos básicos (ID, nombre, descripción)
    - Relación jerárquica (parent_id)
    - Metadatos de creación/actualización (si están disponibles)
    
    **Códigos de estado:**
    - 200: Categoría encontrada y devuelta
    - 404: Categoría no encontrada
    - 422: ID inválido (no numérico)
    
    **Extensiones futuras:**
    - Incluir conteo de productos asociados
    - Agregar información de subcategorías
    - Incluir metadatos de uso y estadísticas
    - Verificar permisos de lectura por usuario
    
    Args:
        db: Sesión de SQLAlchemy
        category_id: ID único de la categoría
        
    Returns:
        CategoryResponse: Datos completos de la categoría
        
    Raises:
        HTTPException: 404 si la categoría no existe
    """
    category = category_service.get_category_by_id(db=db, category_id=category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


@router.get("/", response_model=List[category_schema.CategoryResponse])
async def read_categories(
    db: Session = Depends(deps.get_db),
    skip: int = 0,  # Query parameter: offset para paginación
    limit: int = 100,  # Query parameter: límite de registros
    parent_id: Optional[int] = None,  # Query parameter: filtro por categoría padre
    main_categories_only: bool = False  # Query parameter: solo categorías raíz
) -> List[category_schema.CategoryResponse]:
    """
    Obtiene una lista de categorías con filtros y paginación.

    Permite filtrar por categorías principales o subcategorías de un padre.
    
    **Casos de uso:**
    - `GET /`: Lista todas las categorías paginadas.
    - `GET /?main_categories_only=true`: Lista solo categorías raíz.
    - `GET /?parent_id=1`: Lista las subcategorías de la categoría con ID 1.
    
    **Validaciones:**
    - `parent_id` y `main_categories_only` son mutuamente excluyentes.
    - El endpoint asegura que solo se aplique un filtro a la vez.
    
    Args:
        db: Sesión de SQLAlchemy inyectada
        skip: Offset para paginación
        limit: Límite de resultados
        parent_id: ID de la categoría padre para filtrar subcategorías
        main_categories_only: Flag para obtener solo categorías raíz
        
    Returns:
        Lista de categorías según los filtros aplicados.
        
    Raises:
        HTTPException 400: Si se usan `parent_id` y `main_categories_only` juntos.
    """
    # Validación para asegurar que los filtros no se contradigan
    if main_categories_only and parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot use 'parent_id' and 'main_categories_only' filters simultaneously."
        )

    # Delegación a la capa de servicio según el filtro aplicado
    if main_categories_only:
        # Llama al servicio para obtener solo las categorías principales
        categories = category_service.get_main_categories(db=db, skip=skip, limit=limit)
    elif parent_id is not None:
        # Llama al servicio para obtener subcategorías de un padre específico
        categories = category_service.get_subcategories(db=db, parent_id=parent_id, skip=skip, limit=limit)
    else:
        # Por defecto, obtiene todas las categorías paginadas
        categories = category_service.get_all_categories(db=db, skip=skip, limit=limit)
    
    if not categories:
        # Opcional: devolver 404 si la consulta no devuelve resultados
        # raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No categories found matching criteria")
        pass # Devolver lista vacía es una respuesta válida (200 OK)
        
    return categories

# ========================================
# CONFIGURACIÓN Y METADATOS
# ========================================

# Tags para la documentación de OpenAPI/Swagger
# Se configurarán en el router principal junto con el prefijo

# Extensiones futuras para este módulo:
# 
# @router.get("/{category_id}/products", response_model=List[ProductResponse])
# def get_category_products(category_id: int, db: Session = Depends(deps.get_db)):
#     """Obtiene todos los productos de una categoría específica."""
#     pass
#
# @router.get("/{category_id}/subcategories", response_model=List[CategoryResponse])
# def get_category_hierarchy(category_id: int, db: Session = Depends(deps.get_db)):
#     """Obtiene la jerarquía completa desde una categoría."""
#     pass
#
# @router.get("/{category_id}/path", response_model=List[CategoryResponse])
# def get_category_path(category_id: int, db: Session = Depends(deps.get_db)):
#     """Obtiene la ruta desde la raíz hasta la categoría especificada."""
#     pass