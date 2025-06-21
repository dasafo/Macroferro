# backend/app/api/v1/endpoints/products.py

"""
Endpoints de la API REST para operaciones con productos.

Esta capa implementa los controladores REST para el recurso Product,
manejando operaciones complejas que involucran productos, categorías,
imágenes y especificaciones técnicas. Actúa como interfaz entre las
peticiones HTTP y la capa de servicios.

Responsabilidades específicas para productos:
- Manejo de SKU como identificador único inmutable
- Validación y serialización de especificaciones JSON
- Coordinación con categorías para integridad referencial
- Gestión de relaciones many-to-many con imágenes
- Aplicación de filtros complejos para búsqueda de productos
- Manejo de operaciones que afectan inventario y facturación

Características distintivas del dominio de productos:
- SKU como identificador de negocio (no autogenerado)
- Especificaciones técnicas flexibles en formato JSON
- Relaciones opcionales con categorías
- Asociaciones múltiples con imágenes
- Integración con sistemas de inventario y facturación
- Búsqueda y filtrado avanzado para catálogos grandes

Arquitectura implementada:
- RESTful Resource Controller: Endpoints estándar con SKU como identificador
- Complex Query Support: Múltiples filtros y parámetros de búsqueda
- Business Logic Delegation: Delega validaciones complejas a ProductService
- Error Translation: Convierte errores de dominio a códigos HTTP apropiados
- Response Enhancement: Enriquece respuestas con relaciones cargadas
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api import deps  # Inyección de dependencias para sesión de BD
from app.schemas import product as product_schema  # Esquemas Pydantic para productos
from app.services.product_service import product_service  # Capa de servicios con lógica de negocio de productos
# from app.core.exceptions import NotFoundError, DuplicateError, InvalidOperationError  # Excepciones futuras

# Configuración del router para endpoints de productos
# El prefijo /products será agregado por el router principal
router = APIRouter()

# ========================================
# ENDPOINTS DE ESCRITURA (CREATE, UPDATE, DELETE)
# ========================================

@router.post("/", response_model=product_schema.ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    *,
    db: Session = Depends(deps.get_db),  # Inyección de sesión de BD
    product_in: product_schema.ProductCreate,  # Validación automática de entrada
    # image_urls: Optional[List[HttpUrl]] = Body(None, embed=True)  # Futuro: URLs de imágenes
) -> product_schema.ProductResponse:
    """
    Crea un nuevo producto en el catálogo.
    
    Este endpoint maneja la creación completa de productos, incluyendo
    validación de SKU único, verificación de categoría asociada, y
    preparación para asociación de imágenes.
    
    **Validaciones aplicadas:**
    - SKU debe ser único en todo el sistema
    - Categoría debe existir si se especifica category_id
    - Especificaciones JSON deben tener formato válido
    - Campos obligatorios según esquema ProductCreate
    - Validaciones de negocio específicas del dominio
    
    **Códigos de estado:**
    - 201: Producto creado exitosamente
    - 409: Conflicto (SKU duplicado)
    - 404: Categoría asociada no encontrada
    - 422: Datos de entrada inválidos (validación Pydantic)
    - 500: Error interno (problema de consistencia de datos)
    
    **Proceso de creación:**
    1. Validación previa de SKU único
    2. Delegación a capa de servicios para creación
    3. Recarga del producto con relaciones para respuesta completa
    4. Preparación para asociación de imágenes (implementación futura)
    
    **Consideraciones especiales:**
    - SKU es proporcionado por el cliente (no autogenerado)
    - Diseñado para carga inicial desde CSV
    - Especificaciones JSON permiten flexibilidad en atributos técnicos
    - Relación con categoría es opcional (productos pueden no estar categorizados)
    
    **Extensiones futuras:**
    - Asociación automática de imágenes desde URLs
    - Validación avanzada de especificaciones según categoría
    - Integración con sistema de inventario inicial
    - Notificaciones automáticas de nuevos productos
    
    Args:
        db: Sesión de SQLAlchemy para operaciones de BD
        product_in: Datos del producto validados por Pydantic
        
    Returns:
        ProductResponse: Producto creado con relaciones cargadas
        
    Raises:
        HTTPException: 409 si SKU ya existe
        HTTPException: 404 si categoría no existe
        HTTPException: 422 si datos son inválidos
        HTTPException: 500 si hay error de consistencia
    """
    # VALIDACIÓN PREVIA: Verificar unicidad del SKU
    # Esta validación temprana evita errores 500 y proporciona mensajes claros
    existing_product = product_service.get_product_by_sku_details(db, sku=product_in.sku)
    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with SKU {product_in.sku} already exists."
        )
    
    # DELEGACIÓN A SERVICIO: Crear producto con validaciones de negocio
    product = product_service.create_new_product(db=db, product_in=product_in)
    
    # ENRIQUECIMIENTO DE RESPUESTA: Recargar con relaciones para respuesta completa
    # El CRUD básico no carga relaciones por defecto, pero la API debe devolverlas
    created_product_details = product_service.get_product_by_sku_details(db, sku=product.sku)
    if not created_product_details:
        # Este caso indica un problema serio de consistencia de datos
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Error creating product details"
        )
    
    # MANEJO DE ERRORES FUTURO (cuando se implementen excepciones personalizadas):
    # try:
    #     product = product_service.create_new_product(db=db, product_in=product_in)
    #     created_product_details = product_service.get_product_by_sku_details(db, sku=product.sku)
    # except DuplicateError as e:
    #     raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    # except NotFoundError as e:  # Categoría no encontrada
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    # except ValidationError as e:  # Especificaciones JSON inválidas
    #     raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    
    return created_product_details


@router.put("/{sku}", response_model=product_schema.ProductResponse)
async def update_product(
    *,
    db: Session = Depends(deps.get_db),
    sku: str,  # Path parameter: SKU del producto (identificador inmutable)
    product_in: product_schema.ProductUpdate,  # Body: campos a actualizar (opcionales)
) -> product_schema.ProductResponse:
    """
    Actualiza un producto existente con validaciones de negocio complejas.
    
    Este endpoint maneja actualizaciones parciales de productos, aplicando
    validaciones específicas según el tipo de cambio y considerando el
    impacto en otros sistemas (inventario, facturación, órdenes pendientes).
    
    **Operaciones soportadas:**
    - Cambio de información básica (nombre, descripción, marca)
    - Actualización de precios (con validaciones de negocio)
    - Reasignación de categoría
    - Modificación de especificaciones técnicas (JSON completo)
    - Actualización parcial (solo campos especificados)
    
    **Validaciones aplicadas:**
    - Producto debe existir (verificación por SKU)
    - Nueva categoría debe existir si se especifica
    - Especificaciones JSON deben tener formato válido
    - Validaciones de negocio para cambios críticos (precio, categoría)
    
    **Consideraciones especiales:**
    - SKU es inmutable (identificador de negocio)
    - Cambios de precio pueden requerir aprobación
    - Cambios de categoría afectan clasificación y navegación
    - Especificaciones JSON se reemplazan completamente
    
    **Códigos de estado:**
    - 200: Actualización exitosa
    - 404: Producto no encontrado
    - 404: Nueva categoría no encontrada
    - 409: Conflicto (restricciones de negocio)
    - 422: Datos de entrada inválidos
    - 500: Error de consistencia de datos
    
    **Validaciones de negocio futuras:**
    - Audit trail de cambios críticos
    - Aprobación requerida para cambios de precio significativos
    - Verificación de impacto en órdenes pendientes
    - Validación de permisos según tipo de cambio
    
    Args:
        db: Sesión de SQLAlchemy
        sku: SKU del producto a actualizar (inmutable)
        product_in: Campos a actualizar (esquema con campos opcionales)
        
    Returns:
        ProductResponse: Producto actualizado con relaciones cargadas
        
    Raises:
        HTTPException: 404 si el producto o nueva categoría no existen
        HTTPException: 409 si hay conflictos de validación
        HTTPException: 422 si los datos son inválidos
        HTTPException: 500 si hay error de consistencia
    """
    # DELEGACIÓN A SERVICIO: Actualizar con validaciones de negocio
    updated_product = product_service.update_existing_product(db=db, sku=sku, product_in=product_in)
    if not updated_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found for update")
    
    # ENRIQUECIMIENTO DE RESPUESTA: Recargar con relaciones actualizadas
    # Asegurar que la respuesta incluya todas las relaciones actualizadas
    product_details = product_service.get_product_by_sku_details(db, sku=updated_product.sku)
    if not product_details:
        # Este caso indica problema de consistencia después de la actualización
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Error fetching updated product details"
        )
    
    # MANEJO DE ERRORES FUTURO:
    # try:
    #     updated_product = product_service.update_existing_product(db=db, sku=sku, product_in=product_in)
    #     if not updated_product:
    #         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found for update")
    #     product_details = product_service.get_product_by_sku_details(db, sku=updated_product.sku)
    # except NotFoundError as e:  # Producto o categoría no encontrada
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    # except ValidationError as e:  # Especificaciones o datos inválidos
    #     raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    # except BusinessRuleError as e:  # Violación de reglas de negocio
    #     raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    
    return product_details


@router.delete("/{sku}", response_model=product_schema.ProductResponse)
async def delete_product(
    *,
    db: Session = Depends(deps.get_db),
    sku: str,  # Path parameter: SKU del producto a eliminar
) -> product_schema.ProductResponse:
    """
    Elimina un producto del sistema con validaciones críticas de integridad.
    
    **ADVERTENCIA: Operación crítica con restricciones de integridad**
    
    La eliminación de productos está sujeta a estrictas validaciones de
    integridad debido a su impacto en otros sistemas del negocio.
    
    **Restricciones de integridad (FK constraints):**
    - invoice_items: RESTRICT - Impide eliminación si está en facturas
    - product_images: CASCADE - Elimina asociaciones con imágenes automáticamente
    - stock: CASCADE - Elimina registros de inventario relacionados
    
    **Códigos de estado:**
    - 200: Eliminación exitosa, devuelve producto eliminado
    - 404: Producto no encontrado
    - 409: No se puede eliminar (restricciones de integridad o negocio)
    
    **Validaciones de integridad:**
    - Verificar ausencia en facturas existentes (crítico para auditoría contable)
    - Evaluar impacto en inventario actual
    - Considerar referencias en órdenes pendientes
    - Verificar dependencias en sistemas externos
    
    **Efectos colaterales automáticos:**
    - Eliminación de asociaciones producto-imagen (CASCADE)
    - Eliminación de registros de stock (CASCADE)
    - Preservación de histórico de facturas (RESTRICT)
    
    **Alternativas recomendadas:**
    - Descatalogar: Marcar como inactivo en lugar de eliminar
    - Archivar: Mover a tabla de productos históricos
    - Soft delete: Marcar como eliminado pero preservar datos
    
    **Procedimiento de eliminación:**
    1. Verificar existencia del producto
    2. Validar restricciones de integridad
    3. Evaluar impacto en sistemas relacionados
    4. Ejecutar eliminación con manejo de errores
    5. Manejar violaciones de FK constraints
    
    Args:
        db: Sesión de SQLAlchemy
        sku: SKU del producto a eliminar
        
    Returns:
        ProductResponse: Datos del producto eliminado (para confirmación)
        
    Raises:
        HTTPException: 404 si el producto no existe
        HTTPException: 409 si no se puede eliminar por restricciones
        
    Note:
        Si el producto está referenciado en facturas, la BD impedirá
        la eliminación y se debe capturar la excepción de integridad.
    """
    # DELEGACIÓN A SERVICIO: Eliminar con validaciones críticas
    deleted_product = product_service.delete_existing_product(db=db, sku=sku)
    if not deleted_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Product not found for deletion or cannot be deleted (e.g., in an invoice)."
        )
    
    # MANEJO DE ERRORES FUTURO (cuando se implementen excepciones específicas):
    # try:
    #     deleted_product = product_service.delete_existing_product(db=db, sku=sku)
    #     if not deleted_product:
    #         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found for deletion")
    # except InvalidOperationError as e:  # No se puede borrar por estar en facturas
    #     raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    # except NotFoundError as e:  # Producto no encontrado
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    # except IntegrityError as e:  # Violación de constraints de BD
    #     raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete: product has dependencies")
    
    return deleted_product

# ========================================
# ENDPOINTS DE LECTURA (READ, LIST con filtros avanzados)
# ========================================

@router.get("/{sku}", response_model=product_schema.ProductResponse)
async def read_product(
    *,
    db: Session = Depends(deps.get_db),
    sku: str,  # Path parameter: SKU único del producto
) -> product_schema.ProductResponse:
    """
    Obtiene los detalles completos de un producto por su SKU.
    
    Este endpoint devuelve información completa del producto, incluyendo
    todas sus relaciones (categoría, imágenes) cargadas de manera eficiente
    para evitar consultas N+1.
    
    **Información incluida:**
    - Datos básicos del producto (SKU, nombre, descripción, precio, marca)
    - Categoría asociada (si existe)
    - Imágenes asociadas con URLs completas
    - Especificaciones técnicas (JSON)
    - Metadatos de creación/actualización
    
    **Optimizaciones aplicadas:**
    - Eager loading de categoría e imágenes (evita N+1 queries)
    - Carga eficiente de relaciones many-to-many
    - Consulta única optimizada por índice en SKU
    
    **Códigos de estado:**
    - 200: Producto encontrado y devuelto con todas sus relaciones
    - 404: Producto no encontrado
    - 422: SKU inválido (formato incorrecto)
    
    **Extensiones futuras:**
    - Incluir información de stock disponible
    - Agregar precios especiales según contexto del usuario
    - Incluir productos relacionados o recomendaciones
    - Métricas de popularidad y valoraciones
    - Verificar permisos de visualización
    
    Args:
        db: Sesión de SQLAlchemy
        sku: SKU único del producto
        
    Returns:
        ProductResponse: Producto con todas sus relaciones cargadas
        
    Raises:
        HTTPException: 404 si el producto no existe
    """
    product = product_service.get_product_by_sku_details(db=db, sku=sku)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    return product


@router.get("/", response_model=List[product_schema.ProductResponse])
async def read_products(
    db: Session = Depends(deps.get_db),
    skip: int = 0,  # Query param: offset para paginación
    limit: int = Query(default=100, ge=1, le=200),  # Query param: límite con validación
    category_id: Optional[int] = None,  # Query param: filtro por categoría
    brand: Optional[str] = None,  # Query param: filtro por marca
    min_price: Optional[float] = Query(default=None, ge=0),  # Query param: precio mínimo
    max_price: Optional[float] = Query(default=None, ge=0),  # Query param: precio máximo
    name: Optional[str] = None  # Query param: búsqueda por nombre
) -> List[product_schema.ProductResponse]:
    """
    Obtiene una lista filtrada y paginada de productos.
    
    Este endpoint proporciona capacidades avanzadas de búsqueda y filtrado
    para catálogos grandes, aplicando múltiples criterios de manera eficiente
    y devolviendo resultados paginados con todas las relaciones cargadas.
    
    **Opciones de filtrado disponibles:**
    
    1. **Por categoría** (`category_id`):
       - Filtra productos de una categoría específica
       - Útil para navegación jerárquica del catálogo
       - No incluye subcategorías (filtro directo)
    
    2. **Por marca** (`brand`):
       - Búsqueda parcial case-insensitive en campo marca
       - Permite encontrar marcas sin conocer el nombre exacto
       - Utiliza ILIKE para búsqueda flexible
    
    3. **Por rango de precios** (`min_price`, `max_price`):
       - Filtros inclusivos para rangos de precio
       - Validación automática de valores no negativos
       - Intercambio automático si max < min para facilidad de uso
    
    4. **Por nombre** (`name`):
       - Búsqueda parcial case-insensitive en nombre del producto
       - Útil para búsquedas de texto libre
       - Implementación preparada para full-text search futuro
    
    **Paginación:**
    - `skip`: Número de registros a omitir (default: 0)
    - `limit`: Máximo de registros por página (default: 100, max: 200)
    - Validación automática de límites para prevenir sobrecarga
    
    **Optimizaciones implementadas:**
    - Eager loading de categorías e imágenes para todos los productos
    - Índices utilizados eficientemente en filtros
    - Límites de paginación para proteger performance
    - Consultas optimizadas según combinación de filtros
    
    **Códigos de estado:**
    - 200: Lista devuelta exitosamente (puede estar vacía)
    - 422: Parámetros de consulta inválidos (validación Query)
    
    **Casos de uso típicos:**
    - `/products/` → Lista completa paginada
    - `/products/?category_id=5` → Productos de categoría específica
    - `/products/?brand=Samsung&min_price=100` → Productos Samsung > $100
    - `/products/?name=laptop&skip=20&limit=10` → Búsqueda paginada de laptops
    - `/products/?category_id=1&min_price=50&max_price=500` → Filtros combinados
    
    **Extensiones futuras:**
    - Ordenamiento avanzado (popularidad, precio, fecha)
    - Filtros adicionales (etiquetas, atributos dinámicos)
    - Búsqueda full-text en especificaciones
    - Agregaciones (conteos por categoría, rangos de precio)
    - Faceted search con filtros dinámicos
    
    Args:
        db: Sesión de SQLAlchemy
        skip: Offset para paginación
        limit: Límite de registros (validado entre 1-200)
        category_id: ID de categoría para filtrar (opcional)
        brand: Marca para búsqueda parcial (opcional)
        min_price: Precio mínimo inclusivo (opcional, >= 0)
        max_price: Precio máximo inclusivo (opcional, >= 0)
        name: Nombre para búsqueda parcial (opcional)
        
    Returns:
        List[ProductResponse]: Lista filtrada de productos con relaciones
        
    Note:
        Todos los filtros son opcionales y se pueden combinar.
        Los resultados están limitados por paginación para performance.
    """
    # DELEGACIÓN A SERVICIO: Búsqueda con filtros complejos
    # El servicio maneja la lógica de combinación de filtros y optimizaciones
    products = product_service.get_all_products_with_details(
        db=db, skip=skip, limit=limit, category_id=category_id, brand=brand,
        min_price=min_price, max_price=max_price, name_like=name  # name_like en el servicio
    )
    return products

@router.post("/search", response_model=product_schema.ProductSearchResponse)
async def search_products(
    query: product_schema.ProductSearchQuery,
    db: Session = Depends(deps.get_db)
) -> product_schema.ProductSearchResponse:
    """
    Realiza una búsqueda de productos basada en una consulta de texto.
    
    Devuelve los resultados separados en:
    - `main_results`: Los 3 productos más relevantes.
    - `related_results`: Los siguientes 2 productos como sugerencias.
    """
    if not query.query_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La consulta de búsqueda no puede estar vacía.")

    # El servicio ahora devuelve un diccionario con 'main_results' y 'related_results'
    search_results = await product_service.search_products(
        db=db,
        query_text=query.query_text,
        top_k=query.top_k # El servicio internamente tomará los que necesite
    )

    if not search_results["main_results"] and not search_results["related_results"]:
        # Devolver una respuesta vacía pero bien formada si no hay resultados
        return product_schema.ProductSearchResponse(main_results=[], related_results=[])

    return search_results

# ========================================
# CONFIGURACIÓN Y METADATOS
# ========================================

# Tags para documentación OpenAPI/Swagger
# Se configurarán en el router principal junto con el prefijo /products

# Extensiones futuras para este módulo:
# 
# @router.post("/{sku}/images", response_model=product_schema.ProductResponse)
# def add_product_image(sku: str, image_url: HttpUrl, db: Session = Depends(deps.get_db)):
#     """Asocia una imagen existente al producto."""
#     pass
#
# @router.delete("/{sku}/images/{image_id}", response_model=product_schema.ProductResponse)
# def remove_product_image(sku: str, image_id: int, db: Session = Depends(deps.get_db)):
#     """Desasocia una imagen del producto."""
#     pass
#
# @router.get("/{sku}/stock", response_model=StockResponse)
# def get_product_stock(sku: str, db: Session = Depends(deps.get_db)):
#     """Obtiene información de stock disponible del producto."""
#     pass
#
# @router.get("/search", response_model=List[product_schema.ProductResponse])
# def search_products(q: str, db: Session = Depends(deps.get_db)):
#     """Búsqueda full-text en productos."""
#     pass
#
# @router.get("/popular", response_model=List[product_schema.ProductResponse])
# def get_popular_products(limit: int = 10, db: Session = Depends(deps.get_db)):
#     """Obtiene productos más populares/vendidos."""
#     pass