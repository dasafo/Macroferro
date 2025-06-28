# backend/app/services/category_service.py
"""
Servicio para operaciones de negocio relacionadas con categorías.

Este servicio se encarga de gestionar la lógica de negocio para el manejo de categorías,
incluyendo validaciones complejas, verificación de integridad referencial
y orquestación de operaciones que involucran múltiples entidades.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.models.category_model import Category
from app.crud import category_crud
from app.schemas import category_schema
from fastapi import HTTPException
from starlette import status

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

    async def get_category_by_id(self, db: AsyncSession, category_id: int) -> Optional[Category]:
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
        return await category_crud.get_category(db, category_id=category_id)

    async def get_all_categories(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Category]:
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
        if limit > 1000: # Prevenir consultas excesivamente grandes
            limit = 1000
        return await category_crud.get_categories(db, skip=skip, limit=limit)

    async def get_main_categories(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Category]:
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
        return await category_crud.get_root_categories(db)
    
    async def get_subcategories(self, db: AsyncSession, parent_id: int, skip: int = 0, limit: int = 100) -> List[Category]:
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
        return await category_crud.get_subcategories(db, parent_id=parent_id)

    # ========================================
    # OPERACIONES DE ESCRITURA CON LÓGICA DE NEGOCIO
    # ========================================

    async def create_new_category(self, db: AsyncSession, category_in: category_schema.CategoryCreate) -> Category:
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
        existing_by_id = await category_crud.get_category(db, category_id=category_in.category_id)
        if existing_by_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category with ID {category_in.category_id} already exists."
            )

        existing_by_name = await category_crud.get_category_by_name_and_parent(
            db, name=category_in.name, parent_id=category_in.parent_id
        )
        if existing_by_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category '{category_in.name}' already exists under the specified parent."
            )

        if category_in.parent_id is not None:
            parent = await category_crud.get_category(db, category_id=category_in.parent_id)
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent category with id {category_in.parent_id} not found."
                )
        
        return await category_crud.create_category(db=db, category=category_in)

    async def update_existing_category(self, db: AsyncSession, category_id: int, category_in: category_schema.CategoryUpdate) -> Category:
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
        db_category = await self.get_category_by_id(db, category_id)
        if not db_category:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Category with ID {category_id} not found.")

        update_data = category_in.model_dump(exclude_unset=True)

        if 'name' in update_data or 'parent_id' in update_data:
            name = update_data.get('name', db_category.name)
            parent_id = update_data.get('parent_id', db_category.parent_id)
            
            existing = await category_crud.get_category_by_name_and_parent(db, name=name, parent_id=parent_id)
            if existing and existing.category_id != category_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A category named '{name}' already exists under the target parent."
                )

        if 'parent_id' in update_data:
            new_parent_id = update_data['parent_id']
            if new_parent_id is not None:
                if new_parent_id == category_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A category cannot be its own parent.")
                
                children_ids = await category_crud.get_category_and_all_children_ids(db, category_id=category_id)
                if new_parent_id in children_ids:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot move a category under one of its own descendants.")

        return await category_crud.update_category(db, category_id, category_in)

    async def delete_existing_category(self, db: AsyncSession, category_id: int) -> Category:
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
        category = await self.get_category_by_id(db, category_id)
        if not category:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Category with id {category_id} not found.")

        if category.products:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete category with associated products. Reassign products first."
            )
        
        return await category_crud.delete_category(db, category_id=category_id)

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