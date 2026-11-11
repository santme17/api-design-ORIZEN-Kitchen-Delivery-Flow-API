# app/services/cliente.py
from fastapi import HTTPException, status

from app.models.cliente import Cliente, ClienteCreate, ClienteUpdate
from app.repositories.cliente import ClienteRepository


class ClienteService:
    """Capa 4 - Lógica de Negocio para Cliente.

    Reglas:
    - El cliente debe existir para consultarlo o editarlo (404).
    - Los clientes no se borran: tienen pedidos asociados que deben conservarse.
    """

    def __init__(self, cliente_repo: ClienteRepository) -> None:
        self.cliente_repo = cliente_repo

    async def get_by_id(self, cliente_id: int) -> Cliente:
        cliente = await self.cliente_repo.get_by_id(cliente_id)
        if not cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado",
            )
        return cliente

    async def list_all(
        self, skip: int = 0, limit: int = 100, search: str | None = None
    ) -> list[Cliente]:
        return await self.cliente_repo.get_multi(skip=skip, limit=limit, search=search)

    async def create(self, cliente_in: ClienteCreate) -> Cliente:
        return await self.cliente_repo.create(cliente_in)

    async def update(self, cliente_id: int, cliente_in: ClienteUpdate) -> Cliente:
        cliente = await self.get_by_id(cliente_id)

        # nombre y teléfono son obligatorios: no se pueden "borrar" enviando null
        datos = cliente_in.model_dump(exclude_unset=True)
        for campo in ("nombre", "telefono"):
            if campo in datos and not datos[campo]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El campo '{campo}' no puede quedar vacío",
                )

        return await self.cliente_repo.update(cliente, cliente_in)
