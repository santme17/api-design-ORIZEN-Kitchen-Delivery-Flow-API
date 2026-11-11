# app/services/producto.py
from fastapi import HTTPException, status

from app.models.producto import Producto, ProductoCreate, ProductoUpdate
from app.repositories.producto import ProductoRepository


class ProductoService:
    """Capa 4 - Lógica de Negocio para Producto.

    Reglas:
    - Nombre único en el menú (sin importar mayúsculas) al crear y al editar (400).
    - Los productos no se borran (están en pedidos viejos): se desactivan con `activo=False`.
    - Cambiar el precio no altera pedidos existentes (regla 7, ya garantizada por ItemPedido).
    """

    def __init__(self, producto_repo: ProductoRepository) -> None:
        self.producto_repo = producto_repo

    async def get_by_id(self, producto_id: int) -> Producto:
        producto = await self.producto_repo.get_by_id(producto_id)
        if not producto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Producto no encontrado",
            )
        return producto

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        only_active: bool = False,
    ) -> list[Producto]:
        return await self.producto_repo.get_multi(
            skip=skip, limit=limit, search=search, only_active=only_active
        )

    async def create(self, producto_in: ProductoCreate) -> Producto:
        producto_in.nombre = producto_in.nombre.strip()
        await self._validar_nombre_unico(producto_in.nombre)
        return await self.producto_repo.create(producto_in)

    async def update(self, producto_id: int, producto_in: ProductoUpdate) -> Producto:
        producto = await self.get_by_id(producto_id)

        if producto_in.nombre is not None:
            producto_in.nombre = producto_in.nombre.strip()
            if producto_in.nombre.lower() != producto.nombre.lower():
                await self._validar_nombre_unico(producto_in.nombre, excluir_id=producto.id)

        return await self.producto_repo.update(producto, producto_in)

    async def delete(self, producto_id: int) -> Producto:
        """Borrado lógico: el producto deja de aparecer en el menú."""
        producto = await self.get_by_id(producto_id)
        return await self.producto_repo.update(producto, ProductoUpdate(activo=False))

    # ==========================================
    # Reglas internas
    # ==========================================

    async def _validar_nombre_unico(self, nombre: str, excluir_id: int | None = None) -> None:
        # search usa ILIKE '%nombre%'; aquí se filtra la coincidencia EXACTA
        candidatos = await self.producto_repo.get_multi(search=nombre, limit=1000)
        for p in candidatos:
            if p.nombre.strip().lower() == nombre.lower() and p.id != excluir_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe un producto llamado '{nombre}'",
                )
