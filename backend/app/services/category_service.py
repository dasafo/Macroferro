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
            Lista paginada de categoría
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