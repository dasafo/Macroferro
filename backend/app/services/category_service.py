# backend/app/services/category_service.py

"""
Capa de servicios para operaciones de negocio relacionadas con categorías.

Esta capa implementa el patrón Service Layer, proporcionando una abstracción
entre los endpoints de la API y las operaciones CRUD de base de datos. Su
responsabilidad principal es manejar la lógica de negocio compleja, validaciones
y orquestación de múltiples operaciones CRUD.

Responsabilidades de la capa de servicio:
- Validaciones de negocio complejas (duplicados, integridad referencial)
- Orquestación de múltiples operaciones CRUD
- Manejo de reglas de negocio específicas del dominio
- Transformaciones de datos entre diferentes representaciones
- Logging y auditoría de operaciones críticas
- Manejo centralizado de excepciones de negocio

Patrón de diseño implementado:
- Service Layer: Encapsula lógica de negocio
- Dependency Injection: Recibe Session de SQLAlchemy como parámetro
- Single Responsibility: Cada método tiene una responsabilidad específica
- Composición: Utiliza operaciones CRUD como building blocks

Diferencias con la capa CRUD:
- CRUD: Operaciones atómicas de base de datos
- Service: Lógica de negocio y validaciones complejas
"""

from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.models.category_model import Category
from app.crud import category_crud
from app.schemas import category as category_schema
# Podríamos definir excepciones personalizadas aquí o en un módulo `exceptions.py`
# from app.core.exceptions import NotFoundError, DuplicateError

class CategoryService:
    """
    Servicio para operaciones de negocio relacionadas con categorías.
    
    Esta clase encapsula toda la lógica de negocio para el manejo de categorías,
    incluyendo validaciones complejas, verificación de integridad referencial
    y orquestación de operaciones que involucran múltiples entidades.
    
    Características:
    - Validación de duplicados en jerarquías
    - Verificación de integridad referencial padre-hijo
    - Manejo de reglas de negocio específicas del dominio
    - Preparado para manejo de excepciones personalizadas
    """

    # ========================================
    # OPERACIONES DE CONSULTA
    # ========================================

    def get_category_by_id(self, db: Session, category_id: int) -> Optional[Category]:
        """
        Obtiene una categoría por su ID con validaciones de negocio.
        
        Esta función actúa como proxy hacia la capa CRUD, pero permite
        agregar lógica de negocio adicional como logging, caché, o
        verificaciones de permisos según sea necesario.
        
        Args:
            db: Sesión de SQLAlchemy
            category_id: ID único de la categoría
            
        Returns:
            Objeto Category si existe, None si no se encuentra
            
        Extensiones futuras:
            - Verificación de permisos de lectura
            - Logging de accesos a categorías específicas
            - Caché de categorías frecuentemente accedidas
            - Métricas de uso para análisis
            
        Manejo de errores futuro:
            En lugar de devolver None, se podría lanzar NotFoundError
            para un manejo de errores más explícito en la API.
        """
        category = category_crud.get_category(db, category_id=category_id)
        
        # Extensión futura para manejo de errores explícito:
        # if not category:
        #     raise NotFoundError(f"Category with id {category_id} not found")
        
        return category

    def get_all_categories(self, db: Session, skip: int = 0, limit: int = 100) -> List[Category]:
        """
        Obtiene todas las categorías con paginación y validaciones de negocio.
        
        Proporciona una interfaz controlada para acceder a la lista completa
        de categorías, con posibilidad de agregar filtros de negocio,
        ordenamientos específicos o validaciones de permisos.
        
        Args:
            db: Sesión de SQLAlchemy
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver
            
        Returns:
            Lista paginada de categorías
            
        Validaciones de negocio futuras:
            - Límites máximos de paginación por rol de usuario
            - Filtrado automático según permisos del usuario
            - Ordenamiento específico según preferencias de negocio
            - Exclusión de categorías marcadas como inactivas
        """
        # Validación de límites de paginación (regla de negocio)
        max_limit = 1000  # Evitar consultas demasiado grandes
        if limit > max_limit:
            limit = max_limit
            
        return category_crud.get_categories(db, skip=skip, limit=limit)

    def get_main_categories(self, db: Session, skip: int = 0, limit: int = 100) -> List[Category]:
        """
        Obtiene las categorías principales (nivel raíz) para navegación.
        
        Esta función es especialmente importante para la construcción de
        menús de navegación y estructuras jerárquicas en la interfaz de usuario.
        Puede incluir lógica de ordenamiento específica para la presentación.
        
        Args:
            db: Sesión de SQLAlchemy
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver
            
        Returns:
            Lista de categorías raíz (sin parent_id)
            
        Reglas de negocio aplicadas:
            - Solo categorías activas (extensión futura)
            - Ordenamiento por prioridad de negocio (extensión futura)
            - Filtrado por visibilidad según contexto (extensión futura)
            
        Casos de uso:
            - Construcción de menús principales de navegación
            - Páginas de inicio con categorías destacadas
            - APIs para aplicaciones móviles que necesitan estructura jerárquica
        """
        return category_crud.get_root_categories(db, skip=skip, limit=limit)
    
    def get_subcategories(self, db: Session, parent_id: int, skip: int = 0, limit: int = 100) -> List[Category]:
        """
        Obtiene las subcategorías de una categoría padre específica.
        
        Implementa navegación jerárquica controlada, permitiendo la exploración
        incremental de la estructura de categorías. Incluye validaciones
        implícitas de existencia del padre.
        
        Args:
            db: Sesión de SQLAlchemy
            parent_id: ID de la categoría padre
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver
            
        Returns:
            Lista de categorías hijas directas
            
        Validaciones consideradas (comentadas para Fase 1):
            - Verificación de existencia de la categoría padre
            - Evitar consultas innecesarias cuando el padre no existe
            - Logging de navegación jerárquica para análisis
            
        Optimización actual:
            Se evita la verificación explícita del padre para reducir consultas,
            ya que si no existe, simplemente devolverá una lista vacía.
        """
        # Validación opcional de existencia del padre (comentada para evitar consulta extra):
        # parent_category = self.get_category_by_id(db, parent_id)
        # if not parent_category:
        #     raise NotFoundError(f"Parent category with id {parent_id} not found")
        
        return category_crud.get_child_categories(db, parent_id=parent_id, skip=skip, limit=limit)

    # ========================================
    # OPERACIONES DE ESCRITURA CON LÓGICA DE NEGOCIO
    # ========================================

    def create_new_category(self, db: Session, category_in: category_schema.CategoryCreate) -> Category:
        """
        Crea una nueva categoría con validaciones completas de negocio.
        
        Esta función implementa todas las reglas de negocio para la creación
        de categorías, incluyendo validación de duplicados y verificación
        de integridad referencial con categorías padre.
        
        Args:
            db: Sesión de SQLAlchemy
            category_in: Esquema Pydantic con datos de la nueva categoría
            
        Returns:
            Objeto Category recién creado
            
        Validaciones de negocio implementadas:
            1. Verificación de duplicados (nombre + parent_id)
            2. Validación de existencia de categoría padre
            3. Verificación de integridad de la jerarquía
            
        Consideraciones especiales para carga CSV:
            Las validaciones están comentadas para permitir la carga inicial
            desde archivos CSV, donde se asume que los datos son consistentes
            y están en el orden correcto de dependencias.
            
        Reglas de negocio:
            - No se permiten categorías duplicadas bajo el mismo padre
            - Las categorías padre deben existir antes de crear hijas
            - Los nombres de categorías son únicos dentro de su nivel jerárquico
        """
        # VALIDACIÓN 1: Verificar duplicados por nombre y padre
        existing_category = category_crud.get_category_by_name_and_parent(
            db, name=category_in.name, parent_id=category_in.parent_id
        )
        if existing_category:
            # Para producción, debería lanzarse una excepción:
            # raise DuplicateError(f"Category '{category_in.name}' already exists under the specified parent.")
            
            # Para carga CSV (Fase 1), se permite continuar
            # El constraint UNIQUE de la BD manejará la duplicación si ocurre
            pass

        # VALIDACIÓN 2: Verificar existencia de categoría padre
        if category_in.parent_id is not None:
            parent = category_crud.get_category(db, category_id=category_in.parent_id)
            if not parent:
                # Para producción:
                # raise NotFoundError(f"Parent category with id {category_in.parent_id} not found.")
                
                # Para carga CSV, se asume orden correcto de inserción
                pass
        
        return category_crud.create_category(db=db, category=category_in)

    def update_existing_category(self, db: Session, category_id: int, category_in: category_schema.CategoryUpdate) -> Optional[Category]:
        """
        Actualiza una categoría existente con validaciones complejas de negocio.
        
        Esta función maneja actualizaciones que pueden afectar la integridad
        de la jerarquía de categorías, incluyendo cambios de nombre que podrían
        causar duplicados y cambios de padre que podrían crear ciclos.
        
        Args:
            db: Sesión de SQLAlchemy
            category_id: ID de la categoría a actualizar
            category_in: Esquema Pydantic con campos a actualizar
            
        Returns:
            Objeto Category actualizado, o None si no existe
            
        Validaciones de negocio complejas:
            1. Verificación de existencia de la categoría objetivo
            2. Validación de duplicados considerando el estado actual
            3. Verificación de existencia del nuevo padre
            4. Prevención de ciclos en la jerarquía (extensión futura)
            
        Lógica de validación de duplicados:
            - Solo valida si se cambia nombre o parent_id
            - Excluye la categoría actual de la verificación de duplicados
            - Construye el estado final para validación (merge de actual + cambios)
            
        Consideraciones de integridad:
            - Cambiar parent_id puede afectar productos asociados
            - Cambiar nombre puede afectar URLs y navegación
            - Se requiere validación de ciclos para jerarquías complejas
        """
        # VALIDACIÓN 1: Verificar existencia de la categoría
        db_category = self.get_category_by_id(db, category_id)
        if not db_category:
            return None
            # En producción, podría ser mejor lanzar NotFoundError aquí

        # Preparar datos de actualización (solo campos proporcionados)
        update_data = category_in.model_dump(exclude_unset=True)

        # VALIDACIÓN 2: Evitar duplicados si se cambia el nombre
        if 'name' in update_data:
            parent_id = update_data.get('parent_id', db_category.parent_id)
            existing = category_crud.get_category_by_name_and_parent(
                db, name=update_data['name'], parent_id=parent_id
            )
            if existing and existing.category_id != category_id:
                # raise DuplicateError(f"Category name '{update_data['name']}' already exists under the target parent.")
                return None # Simplificado para Fase 1

        # VALIDACIÓN 3: Evitar ciclos en la jerarquía
        if 'parent_id' in update_data:
            new_parent_id = update_data['parent_id']
            if new_parent_id is not None:
                # No se puede ser padre de sí mismo
                if new_parent_id == category_id:
                    # raise ValidationError("A category cannot be its own parent.")
                    return None
                
                # Verificar que el nuevo padre no sea un descendiente de esta categoría
                descendant = self.get_category_by_id(db, new_parent_id)
                while descendant and descendant.parent_id is not None:
                    if descendant.parent_id == category_id:
                        # raise ValidationError("Cannot move a category under one of its descendants.")
                        return None
                    descendant = self.get_category_by_id(db, descendant.parent_id)

        return category_crud.update_category(db, category_id, category_in)

    def delete_existing_category(self, db: Session, category_id: int) -> Optional[Category]:
        """
        Elimina una categoría con validaciones de integridad de negocio.
        
        Esta operación es crítica porque puede afectar la integridad del catálogo
        al dejar productos sin categoría y convertir subcategorías en categorías raíz.
        Implementa validaciones de negocio para evaluar el impacto antes de eliminar.
        
        Args:
            db: Sesión de SQLAlchemy
            category_id: ID de la categoría a eliminar
            
        Returns:
            Objeto Category eliminado, o None si no existía
            
        Efectos colaterales (manejados por FK constraints):
            - Productos: category_id se establece a NULL (quedan sin categoría)
            - Subcategorías: parent_id se establece a NULL (se vuelven raíz)
            
        Validaciones de negocio recomendadas (futuras):
            1. Verificar impacto en productos asociados
            2. Evaluar si hay subcategorías que se volverían huérfanas
            3. Requerir confirmación explícita para categorías con contenido
            4. Considerar reasignación automática a categoría padre
            
        Consideraciones de auditoría:
            - Logging de eliminaciones para trazabilidad
            - Registro de productos afectados
            - Notificación a administradores de cambios críticos
            
        Alternativas de implementación:
            - Soft delete: Marcar como inactiva en lugar de eliminar
            - Reasignación: Mover productos y subcategorías antes de eliminar
            - Cascada controlada: Eliminar subcategorías vacías también
        """
        # VALIDACIÓN 1: Verificar que la categoría exista
        category = self.get_category_by_id(db, category_id)
        if not category:
            return None
            # raise NotFoundError(f"Category with id {category_id} not found.")

        # VALIDACIÓN 2 (Crítica): Verificar si la categoría tiene productos asociados
        # La FK en 'products' tiene ON DELETE SET NULL, lo que significa que
        # si eliminamos una categoría, los productos asociados pasarán a tener
        # category_id = NULL. Esto podría ser indeseado.
        
        # Opción A (más segura): Prevenir eliminación si hay productos
        if category.products:
            # raise IntegrityError("Cannot delete category with associated products. Reassign products first.")
            # Para Fase 1, se permite la eliminación y los productos quedan sin categoría.
            pass

        # Opción B (alternativa): Reasignar productos a categoría padre o a una "Sin Categoría"
        # if category.products and category.parent:
        #     for product in category.products:
        #         product.category_id = category.parent_id
        #     db.commit()

        # VALIDACIÓN 3 (Opcional): Manejar subcategorías
        # El constraint de FK maneja esto (ON DELETE SET NULL), así que
        # las subcategorías pasarán a ser categorías raíz.
        # Se podría implementar lógica para moverlas al padre de la categoría eliminada.
        
        return category_crud.delete_category(db, category_id=category_id)

# ========================================
# INSTANCIA SINGLETON DEL SERVICIO
# ========================================

# Instancia única del servicio para uso en endpoints
# Patrón Singleton para evitar recrear instancias innecesariamente
category_service = CategoryService()

# ========================================
# EXTENSIONES FUTURAS
# ========================================

# Métodos que se podrían agregar en futuras versiones:
#
# def get_category_hierarchy_path(self, db: Session, category_id: int) -> List[models.Category]:
#     """Obtiene la ruta completa desde la raíz hasta la categoría especificada."""
#     pass
#
# def validate_category_hierarchy_integrity(self, db: Session) -> List[str]:
#     """Valida la integridad de toda la jerarquía de categorías."""
#     pass
#
# def move_category_to_parent(self, db: Session, category_id: int, new_parent_id: Optional[int]) -> models.Category:
#     """Mueve una categoría y todas sus subcategorías a un nuevo padre."""
#     pass
#
# def get_category_usage_statistics(self, db: Session, category_id: int) -> Dict[str, Any]:
#     """Obtiene estadísticas de uso de una categoría (productos, subcategorías, etc.)."""
#     pass