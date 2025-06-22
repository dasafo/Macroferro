# backend/app/crud/product_crud.py

"""
Operaciones CRUD para el modelo Product.

Este módulo implementa las operaciones de Create, Read, Update, Delete para productos,
siendo el corazón del sistema de catálogo. Maneja relaciones complejas con categorías,
imágenes, stock e ítems de factura.

Funcionalidades principales:
- Consultas optimizadas con eager loading para evitar N+1 queries
- Filtrado avanzado por múltiples criterios (precio, marca, categoría, nombre)
- Gestión de asociaciones many-to-many con imágenes
- Manejo de especificaciones técnicas en formato JSON
- Validaciones de integridad referencial

Estrategias de optimización implementadas:
- selectinload() para cargar relaciones de manera eficiente
- Filtros combinables para búsquedas flexibles
- Paginación para manejo de catálogos grandes
- Lazy loading controlado según el contexto de uso
"""

from sqlalchemy.orm import Session, joinedload, subqueryload,selectinload
from typing import List, Optional, Dict, Any

from app.db.models.product_model import Product, ProductImage, Image
from app.schemas import product as product_schema # Schemas Pydantic para productos

# ========================================
# OPERACIONES DE LECTURA (READ)
# ========================================

def get_product_by_sku(db: Session, sku: str) -> Optional[Product]:
    """
    Obtiene un producto por su SKU, con relaciones precargadas.
    
    Esta función implementa eager loading para categoría e imágenes,
    evitando consultas N+1 cuando se accede a estas relaciones.
    Es la función más utilizada para mostrar detalles de producto.
    
    Args:
        db: Sesión de SQLAlchemy
        sku: Código único del producto (clave primaria)
        
    Returns:
        Objeto Product con relaciones cargadas, o None si no existe
        
    Estrategia de carga:
        - selectinload(category): Carga la categoría en una sola query adicional
        - selectinload(images_association).selectinload(image): Carga todas las imágenes
          del producto de manera eficiente usando la tabla de asociación
          
    Uso típico:
        product = get_product_by_sku(db, "DRILL001")
        if product:
            print(f"Producto: {product.name}")
            print(f"Categoría: {product.category.name if product.category else 'Sin categoría'}")
            print(f"Imágenes: {len(product.images_association)}")
    """
    return (
        db.query(Product)
        .options(
            selectinload(Product.category),  # Carga eficiente de la categoría
            selectinload(Product.images_association).selectinload(ProductImage.image)  # Carga eficiente de imágenes
        )
        .filter(Product.sku == sku)
        .first()
    )


def get_products(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    category_id: Optional[int] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    name_like: Optional[str] = None
) -> List[Product]:
    """
    Obtiene una lista filtrada y paginada de productos.
    
    Esta función implementa un sistema de filtrado flexible que permite
    combinar múltiples criterios de búsqueda. Incluye eager loading para
    optimizar el acceso a relaciones en las respuestas de la API.
    
    Args:
        db: Sesión de SQLAlchemy
        skip: Número de registros a omitir (para paginación)
        limit: Número máximo de registros a devolver
        category_id: Filtrar por categoría específica (opcional)
        brand: Filtrar por marca (búsqueda parcial, insensible a mayúsculas)
        min_price: Precio mínimo (inclusivo)
        max_price: Precio máximo (inclusivo)
        name_like: Búsqueda parcial en el nombre del producto
        
    Returns:
        Lista de productos que cumplen los criterios, con relaciones cargadas
        
    Estrategias de filtrado:
        - ilike(): Búsqueda insensible a mayúsculas/minúsculas
        - Filtros combinables: Solo se aplican si se proporcionan
        - Rangos de precio: Permiten filtrado por rango mín/máx independientes
        
    Consideraciones de rendimiento:
        - Los filtros por precio usan índices numéricos (eficientes)
        - category_id usa foreign key (muy eficiente)
        - name_like y brand pueden beneficiarse de índices de texto
        - Para catálogos grandes (>10K productos), considerar:
          * Índices compuestos (category_id, price)
          * Full-text search para name_like
          * Caché para combinaciones de filtros frecuentes
          
    Ejemplo de uso:
        # Taladros eléctricos entre $50 y $200
        products = get_products(
            db, 
            category_id=5, 
            name_like="taladro", 
            min_price=50.0, 
            max_price=200.0,
            skip=0, 
            limit=20
        )
    """
    query = db.query(Product).options(
        selectinload(Product.category),  # Precarga categoría
        selectinload(Product.images_association).selectinload(ProductImage.image)  # Precarga imágenes
    )

    # Aplicar filtros solo si se proporcionan (filtros opcionales y combinables)
    if category_id is not None:
        query = query.filter(Product.category_id == category_id)
    if brand:
        query = query.filter(Product.brand.ilike(f"%{brand}%"))  # Búsqueda insensible a mayúsculas/minúsculas
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if name_like:
        query = query.filter(Product.name.ilike(f"%{name_like}%"))
        
    return query.offset(skip).limit(limit).all()


def get_products_by_skus(db: Session, skus: List[str]) -> List[Product]:
    """
    Obtiene una lista de productos a partir de una lista de SKUs.

    Esta función es muy eficiente para recuperar múltiples productos
    cuando ya se conocen sus identificadores (por ejemplo, después de
    una búsqueda en un sistema externo como Qdrant).

    Utiliza una consulta `WHERE sku IN (...)` y precarga las relaciones
    para evitar el problema N+1.

    Args:
        db: Sesión de SQLAlchemy
        skus: Lista de SKUs a recuperar.

    Returns:
        Lista de objetos Product correspondientes a los SKUs encontrados.
        La lista puede no estar en el mismo orden que la lista de entrada.
    """
    if not skus:
        return []
    
    return (
        db.query(Product)
        .options(
            selectinload(Product.category),
            selectinload(Product.images_association).selectinload(ProductImage.image)
        )
        .filter(Product.sku.in_(skus))
        .all()
    )


# ========================================
# OPERACIONES DE ESCRITURA (CREATE, UPDATE, DELETE)
# ========================================

def create_product(
    db: Session, 
    product: product_schema.ProductCreate, 
    image_urls: Optional[List[str]] = None
) -> Product:
    """
    Crea un nuevo producto en la base de datos, con la opción de asociar imágenes.
    
    Esta función maneja la creación de productos con validación previa
    de los datos a través de esquemas Pydantic. El campo spec_json
    ya viene parseado como dict gracias al validador del schema.
    
    Args:
        db: Sesión de SQLAlchemy
        product: Esquema Pydantic con los datos validados del producto
        image_urls: Lista de URLs de imágenes asociadas al producto
        
    Returns:
        Objeto Product recién creado y persistido
        
    Validaciones previas recomendadas:
        1. Verificar que el SKU no exista (debe ser único)
        2. Validar que category_id existe si se proporciona
        3. Verificar formato de precio (debe ser positivo)
        4. Validar estructura de spec_json si tiene requerimientos específicos
        
    Notas sobre tipos de datos:
        - price: Se convierte automáticamente de float (Pydantic) a Numeric (SQLAlchemy)
        - spec_json: PostgreSQL JSONB maneja automáticamente la serialización
        - SKU: Actúa como clave primaria, debe ser único y no nulo
        
    Ejemplo:
        new_product = ProductCreate(
            sku="DRILL002",
            name="Taladro Industrial",
            price=150.99,
            brand="PowerTools",
            category_id=5,
            spec_json={"potencia": "1200W", "rpm": "3500"}
        )
        created = create_product(db, new_product)
    """
    # spec_json ya debería ser un dict gracias al validador de Pydantic
    db_product = Product(
        sku=product.sku,
        name=product.name,
        description=product.description,
        price=product.price,
        brand=product.brand,
        category_id=product.category_id,
        spec_json=product.spec_json  # PostgreSQL JSONB maneja la serialización automáticamente
    )
    db.add(db_product)
    
    # Procesar y asociar imágenes si se proporcionan
    if image_urls:
        for url in image_urls:
            # Simplificado: Asume que las imágenes ya existen o se crean aquí.
            # En un sistema real, aquí iría la lógica para get_or_create_image.
            image = db.query(Image).filter(Image.url == url).first()
            if not image:
                image = Image(url=url, alt_text=f"Imagen de {product.name}")
                db.add(image)
                db.flush() # Para obtener el image_id

            # Crear la asociación
            association = ProductImage(product_sku=product.sku, image_id=image.image_id)
            db.add(association)

    db.commit()
    db.refresh(db_product)
    return db_product


def update_product(db: Session, sku: str, product_update: product_schema.ProductUpdate) -> Optional[Product]:
    """
    Actualiza un producto existente.
    
    Implementa actualización parcial usando exclude_unset=True,
    permitiendo que los clientes envíen solo los campos que desean modificar.
    El SKU no se puede cambiar ya que actúa como identificador.
    
    Args:
        db: Sesión de SQLAlchemy
        sku: SKU del producto a actualizar (identificador inmutable)
        product_update: Esquema Pydantic con los campos a actualizar
        
    Returns:
        Objeto Product actualizado, o None si no existe
        
    Consideraciones especiales:
        - Cambiar category_id afecta la clasificación del producto
        - Actualizar price puede afectar órdenes de compra pendientes
        - Modificar spec_json reemplaza completamente las especificaciones
        - Los cambios en name/description pueden afectar SEO y búsquedas
        
    Validaciones recomendadas:
        - Verificar que el nuevo category_id existe
        - Validar que el nuevo precio es positivo
        - Comprobar permisos de modificación
        - Considerar logging de cambios para auditoría
        
    Manejo de spec_json:
        - La actualización reemplaza completamente el JSON
        - Para actualizaciones parciales de especificaciones, implementar
          lógica específica que merge los objetos JSON
        
    Ejemplo:
        update_data = ProductUpdate(price=89.99, spec_json={"potencia": "900W"})
        updated = update_product(db, "DRILL001", update_data)
        if updated:
            print(f"Producto actualizado: {updated.name} - ${updated.price}")
    """
    db_product = get_product_by_sku(db, sku)
    if not db_product:
        return None

    # Obtener los datos del schema Pydantic como un diccionario
    update_data = product_update.model_dump(exclude_unset=True)

    # Actualizar los campos del objeto SQLAlchemy
    for key, value in update_data.items():
        setattr(db_product, key, value)

    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    return db_product


def delete_product(db: Session, sku: str) -> Optional[Product]:
    """
    Elimina un producto de la base de datos.
    
    Esta operación debe manejarse cuidadosamente debido a las relaciones
    con otros modelos. El comportamiento está definido por las foreign key
    constraints configuradas en los modelos.
    
    Args:
        db: Sesión de SQLAlchemy
        sku: SKU del producto a eliminar
        
    Returns:
        Objeto Product eliminado, o None si no existía
        
    Efectos colaterales (según constraints FK):
        - product_images: ON DELETE CASCADE - Se eliminan automáticamente
        - stock: ON DELETE CASCADE - Se eliminan automáticamente  
        - invoice_items: ON DELETE RESTRICT - Previene eliminación si está en facturas
        
    Consideraciones de negocio:
        - ¿Permitir eliminar productos con stock?
        - ¿Permitir eliminar productos que han sido vendidos?
        - ¿Soft delete vs hard delete para preservar historial?
        - ¿Requerir confirmación para productos con alto valor?
        
    Manejo de errores:
        - IntegrityError si el producto está en facturas existentes
        - La aplicación debe capturar y manejar estos errores apropiadamente
        - Considerar mostrar mensajes específicos al usuario
        
    Validaciones recomendadas:
        1. Verificar que no está en facttura pendientes/procesando
        2. Verificar nivel de stock actual
        3. Comprobar permisos de eliminación
        4. Registrar la eliminación para auditoría
        
    Ejemplo con manejo de errores:
        try:
            deleted = delete_product(db, "DRILL001")
            if deleted:
                print(f"Producto {deleted.sku} eliminado correctamente")
        except IntegrityError:
            print("No se puede eliminar: producto presente en facturas")
    """
    db_product = get_product_by_sku(db, sku)
    if db_product:
        db.delete(db_product)
        db.commit()
    return db_product


# ========================================
# GESTIÓN DE ASOCIACIONES PRODUCTO-IMAGEN
# ========================================

def add_image_to_product(db: Session, sku: str, image_id: int) -> Optional[ProductImage]:
    """
    Asocia una imagen existente a un producto.
    
    Esta función maneja la relación many-to-many entre productos e imágenes
    a través de la tabla de asociación ProductImage. Permite asociar la misma
    imagen a múltiples productos y múltiples imágenes al mismo producto.
    
    Args:
        db: Sesión de SQLAlchemy
        sku: SKU del producto
        image_id: ID de la imagen a asociar
        
    Returns:
        Objeto ProductImage (asociación), o None si el producto o imagen no existen
        
    Validaciones realizadas:
        - Verifica que el producto existe
        - Verifica que la imagen existe
        - Previene asociaciones duplicadas
        
    Casos de uso:
        - Agregar imágenes adicionales a productos existentes
        - Reutilizar imágenes entre productos similares
        - Gestión dinámica de galería de imágenes
        
    Consideraciones:
        - La misma imagen puede asociarse a múltiples productos
        - No hay límite de imágenes por producto (considerar en UI)
        - Las asociaciones duplicadas se ignoran silenciosamente
        
    Ejemplo:
        # Asociar imagen de "vista frontal" al taladro
        association = add_image_to_product(db, "DRILL001", 123)
        if association:
            print("Imagen asociada correctamente")
    """
    # Verificar que el producto y la imagen existan
    product = db.query(Product).filter(Product.sku == sku).first()
    image = db.query(Image).filter(Image.image_id == image_id).first()

    if not (product and image):
        return None

    # Verificar si la asociación ya existe
    existing_association = db.query(ProductImage).filter_by(product_sku=sku, image_id=image_id).first()
    if existing_association:
        return existing_association

    # Crear la nueva asociación
    db_association = ProductImage(product_sku=sku, image_id=image_id)
    db.add(db_association)
    db.commit()
    db.refresh(db_association)
    return db_association


def remove_image_from_product(db: Session, sku: str, image_id: int) -> bool:
    """
    Desasocia una imagen de un producto.
    
    Elimina la relación entre un producto y una imagen específica sin
    afectar la imagen original ni el producto. Solo elimina la asociación
    en la tabla ProductImage.
    
    Args:
        db: Sesión de SQLAlchemy
        sku: SKU del producto
        image_id: ID de la imagen a desasociar
        
    Returns:
        True si la asociación fue eliminada, False si no existía
        
    Comportamiento:
        - No elimina la imagen original (puede estar asociada a otros productos)
        - No afecta el producto
        - Es una operación idempotente (safe para llamar múltiples veces)
        
    Casos de uso:
        - Remover imágenes obsoletas de productos
        - Gestión de galería de imágenes
        - Corrección de asociaciones incorrectas
        
    Ejemplo:
        # Remover imagen específica del producto
        removed = remove_image_from_product(db, "DRILL001", 123)
        if removed:
            print("Imagen removida de la galería del producto")
        else:
            print("La imagen no estaba asociada al producto")
    """
    db_association = db.query(ProductImage).filter_by(product_sku=sku, image_id=image_id).first()
    
    if db_association:
        db.delete(db_association)
        db.commit()
        return True
    
    return False


def get_product_images(db: Session, sku: str) -> List[Image]:
    """
    Obtiene todas las imágenes asociadas a un producto.
    """
    product = get_product_by_sku(db, sku)
    if not product:
        return []
    
    return [assoc.image for assoc in product.images_association]


# ========================================
# FUNCIONES AUXILIARES Y FUTURAS EXTENSIONES
# ========================================

# Funciones utilitarias que se podrían añadir en el futuro:

# def get_products_by_category_hierarchy(db: Session, category_id: int, include_subcategories: bool = True) -> List[Product]:
#     """Obtiene productos de una categoría y opcionalmente sus subcategorías."""
#     pass

# def search_products_full_text(db: Session, search_term: str, limit: int = 50) -> List[Product]:
#     """Búsqueda full-text en nombre, descripción y especificaciones."""
#     pass

# def get_products_low_stock(db: Session, threshold: int = 10) -> List[Product]:
#     """Obtiene productos con stock bajo el umbral especificado."""
#     pass

# def get_product_stock_summary(db: Session, sku: str) -> Dict[str, Any]:
#     """Obtiene resumen de stock por almacén para un producto."""
#     pass

# def bulk_update_prices(db: Session, price_updates: List[Dict[str, Any]]) -> int:
#     """Actualización masiva de precios para múltiples productos."""
#     pass