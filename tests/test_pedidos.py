# tests/test_pedidos.py
from tests.conftest import API


def _datos_base(client, admin):
    producto = client.post(f"{API}/products/", headers=admin, json={"nombre": "Wok", "precio": "25000"}).json()
    cliente = client.post(f"{API}/customers/", headers=admin, json={"nombre": "Ana", "telefono": "300"}).json()
    repartidor = client.post(
        f"{API}/couriers/", headers=admin, json={"nombre": "Luis", "telefono": "311", "vehiculo": "Moto"}
    ).json()
    return producto, cliente, repartidor


def test_flujo_completo_de_un_pedido(client, admin, crear_usuario):
    cajero = crear_usuario("CAJERO", "caja@test.com")
    cocina = crear_usuario("COCINA", "cocina@test.com")
    producto, cliente, repartidor = _datos_base(client, admin)

    # El cajero crea el pedido: el servidor calcula el total
    r = client.post(
        f"{API}/orders/",
        headers=cajero,
        json={
            "cliente_id": cliente["id"],
            "tipo_pedido": "DOMICILIO",
            "direccion_entrega": "Calle 10",
            "items": [{"producto_id": producto["id"], "cantidad": 2}],
        },
    )
    assert r.status_code == 201, r.text
    pedido = r.json()
    assert pedido["total"] == "50000.00"
    assert pedido["estado_actual"] == "EN_COLA"

    # Asignar repartidor lo deja OCUPADO
    assert client.patch(
        f"{API}/orders/{pedido['id']}/courier", headers=cajero, json={"repartidor_id": repartidor["id"]}
    ).status_code == 200

    # Cocina avanza el estado; un salto inválido da 409
    url_estados = f"{API}/orders/{pedido['id']}/statuses"
    assert client.post(url_estados, headers=cocina, json={"estado": "EN_PREPARACION"}).status_code == 201
    assert client.post(url_estados, headers=cocina, json={"estado": "ENTREGADO"}).status_code == 409

    # El detalle trae ítems, historial y cronómetros en una sola petición
    detalle = client.get(f"{API}/orders/{pedido['id']}", headers=cajero).json()
    assert len(detalle["items"]) == 1
    assert [e["estado"] for e in detalle["estados"]] == ["EN_COLA", "EN_PREPARACION"]

    # Cancelar libera al repartidor
    assert client.post(
        f"{API}/orders/{pedido['id']}/cancel", headers=cajero, json={"observacion": "prueba"}
    ).status_code == 200
    rep = client.get(f"{API}/couriers/{repartidor['id']}", headers=admin).json()
    assert rep["estado_disponibilidad"] == "DISPONIBLE"


def test_pedido_inexistente_responde_404(client, admin):
    assert client.get(f"{API}/orders/999", headers=admin).status_code == 404
