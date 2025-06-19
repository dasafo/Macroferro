# backend/app/crud/category_crud.py

"""
Operaciones CRUD para el modelo Category.

Este módulo implementa las operaciones de Create, Read, Update, Delete para categorías,
proporcionando una capa de abstracción entre los endpoints de la API y la base de datos.

Funcionalidades principales:
- Consultas básicas por ID y nombre
- Manejo de jerarquías (categorías padre/hijo)
- Validación de duplicados
- Operaciones de paginación
- Gestión de relaciones y constraints

Patrones implementados:
- Repository pattern: Abstrae las consultas de SQLAlchemy
- Lazy loading opcional: Para optimizar consultas según el contexto
- Validación de integridad: Previene duplicados y conflictos
"""

from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.db import models # Importamos los modelos SQLAlchemy
from app.schemas import category as category_schema # Importamos los schemas Pydantic para categorías

# ========================================
# OPERACIONES DE LECTURA (READ)
# ========================================

def get_category(db: Session, category_id: int) -> Optional[models.Category]:
    """
    Obtiene una categoría por su ID.
    
    Esta función realiza una consulta simple por clave primaria,
    que es la operación más eficiente en la base de datos.
    
    Args:
        db: Sesión de SQLAlchemy
        category_id: ID único de la categoría
        
    Returns:
        Objeto Category si existe, None si no se encuentra
        
    Uso típico:
        category = get_category(db, 1)
        if category:
            print(f"Categoría encontrada: {category.name}")
    """
    return db.query(models.Category).filter(models.Category.category_id == category_id).first()


def get_category_by_name_and_parent(db: Session, name: str, parent_id: Optional[int]) -> Optional[models.Category]:
    """
    Obtiene una categoría por su nombre y parent_id.
    
    Esta función es crucial para validar duplicados antes de crear
    o actualizar categorías. Implementa la regla de negocio que permite
    nombres duplicados siempre que estén en diferentes niveles jerárquicos.
    
    Args:
        db: Sesión de SQLAlchemy
        name: Nombre de la categoría a buscar
        parent_id: ID de la categoría padre (None para categorías raíz)
        
    Returns:
        Objeto Category si existe una categoría con ese nombre y padre, None en caso contrario
        
    Ejemplos de uso:
        # Verificar si "Herramientas" ya existe como categoría raíz
        existing = get_category_by_name_and_parent(db, "Herramientas", None)
        
        # Verificar si "Eléctricas" ya existe bajo la categoría padre ID 1
        existing = get_category_by_name_and_parent(db, "Eléctricas", 1)
    """
    query = db.query(models.Category).filter(models.Category.name == name)
    
    # Manejo especial para categorías raíz (parent_id = None)
    if parent_id is None:
        query = query.filter(models.Category.parent_id.is_(None))
    else:
        query = query.filter(models.Category.parent_id == parent_id)
    return query.first()


def get_categories(db: Session, skip: int = 0, limit: int = 100) -> List[models.Category]:
    """
    Obtiene una lista paginada de todas las categorías.
    
    Implementa paginación para manejar eficientemente grandes volúmenes
    de categorías. Es especialmente útil para interfaces de administración
    y listados completos del catálogo.
    
    Args:
        db: Sesión de SQLAlchemy
        skip: Número de registros a omitir (para paginación)
        limit: Número máximo de registros a devolver
        
    Returns:
        Lista de objetos Category
        
    Consideraciones de rendimiento:
        - Para catálogos grandes (>1000 categorías), considerar índices en name
        - El orden por defecto es por ID, considerar ordenar por name si es necesario
        - Para UI, combinar con get_total_categories() para mostrar paginación completa
    """
    return db.query(models.Category).offset(skip).limit(limit).all()


def get_root_categories(db: Session, skip: int = 0, limit: int = 100) -> List[models.Category]:
    """
    Obtiene todas las categorías raíz (nivel superior de la jerarquía).
    
    Las categorías raíz son aquellas que no tienen parent_id, formando
    el primer nivel de la jerarquía del catálogo. Son especialmente útiles
    para construir menús de navegación y vistas jerárquicas.
    
    Args:
        db: Sesión de SQLAlchemy
        skip: Número de registros a omitir (para paginación)
        limit: Número máximo de registros a devolver
        
    Returns:
        Lista de categorías raíz ordenadas por ID
        
    Casos de uso típicos:
        - Construcción de menús principales de navegación
        - Páginas de categorías principales en e-commerce
        - Estructuras de árbol en interfaces de administración
        
    Ejemplo:
        root_cats = get_root_categories(db)
        for cat in root_cats:
            print(f"Categoría principal: {cat.name}")
    """
    return db.query(models.Category).filter(models.Category.parent_id.is_(None)).offset(skip).limit(limit).all()


def get_child_categories(db: Session, parent_id: int, skip: int = 0, limit: int = 100) -> List[models.Category]:
    """
    Obtiene las subcategorías directas de una categoría padre.
    
    Esta función permite navegar un nivel hacia abajo en la jerarquía,
    obteniendo solo los hijos directos (no nietos). Es fundamental para
    construir navegación incremental y evitar cargar toda la jerarquía.
    
    Args:
        db: Sesión de SQLAlchemy
        parent_id: ID de la categoría padre
        skip: Número de registros a omitir (para paginación)
        limit: Número máximo de registros a devolver
        
    Returns:
        Lista de categorías hijas directas
        
    Casos de uso:
        - Navegación drill-down en catálogos
        - Construcción de menús desplegables
        - Lazy loading de subcategorías en interfaces
        
    Extensión futura:
        Para obtener toda la descendencia (hijos, nietos, etc.):
        - Usar consultas recursivas (CTE)
        - Implementar con múltiples queries
        - Considerar desnormalización para jerarquías muy profundas
    """
    return db.query(models.Category).filter(models.Category.parent_id == parent_id).offset(skip).limit(limit).all()


# ========================================
# OPERACIONES DE ESCRITURA (CREATE, UPDATE, DELETE)
# ========================================

def create_category(db: Session, category: category_schema.CategoryCreate) -> models.Category:
    """
    Crea una nueva categoría en la base de datos.
    
    Esta función maneja la creación de categorías con IDs predefinidos
    (provenientes del CSV de datos iniciales) en lugar de usar auto-incremento.
    Es importante validar duplicados antes de llamar esta función.
    
    Args:
        db: Sesión de SQLAlchemy
        category: Esquema Pydantic con los datos de la nueva categoría
        
    Returns:
        Objeto Category recién creado y persistido
        
    Flujo recomendado:
        1. Validar que no exista duplicado con get_category_by_name_and_parent()
        2. Validar que el parent_id existe (si se proporciona)
        3. Crear la categoría con esta función
        4. Manejar errores de integridad si ocurren
        
    Ejemplo:
        # Validación previa
        existing = get_category_by_name_and_parent(db, "Nueva Categoría", None)
        if existing:
            raise ValueError("La categoría ya existe")
            
        # Creación
        new_category = CategoryCreate(category_id=10, name="Nueva Categoría", parent_id=None)
        created = create_category(db, new_category)
    """
    db_category = models.Category(
        category_id=category.category_id,  # ID específico del CSV
        name=category.name, 
        parent_id=category.parent_id
    )
    db.add(db_category)
    db.commit()  # Persiste en la base de datos
    db.refresh(db_category)  # Recarga el objeto con datos actualizados de la BD
    return db_category


def update_category(db: Session, category_id: int, category_update: category_schema.CategoryUpdate) -> Optional[models.Category]:
    """
    Actualiza una categoría existente.
    
    Implementa actualización parcial usando el patrón "exclude_unset",
    que solo actualiza los campos que fueron proporcionados en la petición.
    Esto permite actualizaciones PATCH eficientes.
    
    Args:
        db: Sesión de SQLAlchemy
        category_id: ID de la categoría a actualizar
        category_update: Esquema Pydantic con los campos a actualizar
        
    Returns:
        Objeto Category actualizado, o None si no existe
        
    Validaciones recomendadas antes de actualizar:
        - Verificar que el nuevo nombre no cause duplicados
        - Validar que el nuevo parent_id no cree ciclos
        - Comprobar permisos de modificación
        
    Consideraciones especiales:
        - Cambiar parent_id puede afectar la jerarquía completa
        - Renombrar puede afectar URLs y navegación
        - Considerar logging de cambios para auditoría
        
    Ejemplo:
        update_data = CategoryUpdate(name="Nuevo Nombre")
        updated = update_category(db, 1, update_data)
        if updated:
            print(f"Categoría actualizada: {updated.name}")
    """
    db_category = get_category(db, category_id=category_id)
    if not db_category:
        return None
    
    # Solo actualiza campos que fueron proporcionados (exclude_unset=True)
    update_data = category_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)
    
    db.add(db_category)  # Marca el objeto como modificado
    db.commit()  # Persiste los cambios
    db.refresh(db_category)  # Recarga datos actualizados
    return db_category


def delete_category(db: Session, category_id: int) -> Optional[models.Category]:
    """
    Elimina una categoría de la base de datos.
    
    Esta operación debe manejarse con cuidado debido a las relaciones
    con productos y subcategorías. El comportamiento está definido por
    las foreign keys con ON DELETE SET NULL.
    
    Args:
        db: Sesión de SQLAlchemy
        category_id: ID de la categoría a eliminar
        
    Returns:
        Objeto Category eliminado, o None si no existía
        
    Efectos colaterales (manejados automáticamente por FK constraints):
        - Productos asociados: category_id se establece a NULL
        - Subcategorías: parent_id se establece a NULL (se vuelven raíz)
        
    Consideraciones de negocio:
        - ¿Permitir eliminar categorías con productos?
        - ¿Reasignar productos a categoría padre antes de eliminar?
        - ¿Requerir confirmación explícita para categorías no vacías?
        - ¿Soft delete vs hard delete para auditoría?
        
    Validaciones recomendadas:
        1. Verificar si tiene productos asociados
        2. Verificar si tiene subcategorías
        3. Requerir confirmación del usuario
        4. Considerar logging de la eliminación
        
    Ejemplo de uso con validaciones:
        category = get_category(db, category_id)
        if category:
            # Verificar productos asociados
            product_count = db.query(models.Product).filter_by(category_id=category_id).count()
            if product_count > 0:
                print(f"Advertencia: {product_count} productos perderán su categoría")
            
            deleted = delete_category(db, category_id)
    """
    db_category = get_category(db, category_id=category_id)
    if not db_category:
        return None
        
    # Las foreign key constraints manejarán automáticamente:
    # - productos.category_id -> NULL (ON DELETE SET NULL)
    # - categorias.parent_id -> NULL (ON DELETE SET NULL)
    # 
    # Si se necesita un comportamiento diferente, implementar aquí:
    # - Reasignar productos a categoría padre
    # - Promover subcategorías al nivel del padre
    # - Prevenir eliminación si hay dependencias

    db.delete(db_category)
    db.commit()
    return db_category

# ========================================
# FUNCIONES AUXILIARES Y FUTURAS EXTENSIONES
# ========================================

# Función utilitaria que se podría añadir en el futuro:
# def get_category_hierarchy(db: Session, category_id: int) -> List[models.Category]:
#     """Obtiene la ruta completa desde la raíz hasta la categoría especificada."""
#     pass

# def get_category_tree(db: Session, parent_id: Optional[int] = None) -> Dict[str, Any]:
#     """Obtiene un árbol completo de categorías en formato JSON."""
#     pass

# def count_products_in_category(db: Session, category_id: int, include_subcategories: bool = False) -> int:
#     """Cuenta productos en una categoría, opcionalmente incluyendo subcategorías."""
#     pass