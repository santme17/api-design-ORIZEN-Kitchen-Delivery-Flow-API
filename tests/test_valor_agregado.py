# tests/test_valor_agregado.py
import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.tiempo import hoy_local
from tests.conftest import API


def _crear_pedido(client, headers, cantidad=2):
    producto = client.post(f"{API}/products/", headers=headers, json={"nombre": f"Wok {cantidad}", "precio": "25000"}).json()
    cliente = client.post(f"{API}/customers/", headers=headers, json={"nombre": "Ana", "telefono": "300"}).json()
    r = client.post(
        f"{API}/orders/",
        headers=headers,
        json={"cliente_id": cliente["id"], "tipo_pedido": "RECOGER", "items": [{"producto_id": producto["id"], "cantidad": cantidad}]},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_pantalla_de_cocina_recibe_el_pedido_nuevo(client, admin):
    token = admin["Authorization"].removeprefix("Bearer ")
    with client.websocket_connect(f"{API}/ws/kitchen?token={token}") as ws:
        pedido = _crear_pedido(client, admin)
        mensaje = ws.receive_json()
    assert mensaje["evento"] == "pedido_creado"
    assert mensaje["datos"]["id"] == pedido["id"]


def test_websocket_rechaza_token_invalido(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"{API}/ws/kitchen?token=basura") as ws:
            ws.receive_json()


def test_resumen_del_dia_excluye_cancelados(client, admin):
    _crear_pedido(client, admin, cantidad=2)  # 50.000
    cancelado = _crear_pedido(client, admin, cantidad=1)  # 25.000, se cancela
    client.post(f"{API}/orders/{cancelado['id']}/cancel", headers=admin, json={})

    r = client.get(f"{API}/reports/daily-summary", headers=admin)
    assert r.status_code == 200, r.text
    resumen = r.json()
    assert resumen["total_pedidos"] == 2
    assert resumen["ventas"] == "50000.00"
    assert resumen["pedidos_por_estado"]["CANCELADO"] == 1


def test_reportes_solo_admin(client, crear_usuario):
    cajero = crear_usuario("CAJERO", "caja@test.com")
    assert client.get(f"{API}/reports/daily-summary", headers=cajero).status_code == 403


def test_filtro_de_pedidos_por_dia_local(client, admin):
    _crear_pedido(client, admin)
    hoy = hoy_local().isoformat()
    assert len(client.get(f"{API}/orders/?fecha={hoy}", headers=admin).json()) == 1
    assert client.get(f"{API}/orders/?fecha=2020-01-01", headers=admin).json() == []


def test_tiempos_y_productos_mas_vendidos(client, admin):
    pedido = _crear_pedido(client, admin, cantidad=3)
    crono = client.post(f"{API}/orders/{pedido['id']}/process-timers", headers=admin, json={"nombre_proceso": "PREPARACION"}).json()
    client.patch(f"{API}/process-timers/{crono['id']}/stop", headers=admin)

    tiempos = client.get(f"{API}/reports/process-times", headers=admin).json()
    assert tiempos[0]["nombre_proceso"] == "PREPARACION"
    assert tiempos[0]["cantidad"] == 1

    top = client.get(f"{API}/reports/top-products", headers=admin).json()
    assert top[0]["unidades"] == 3
    assert top[0]["ingresos"] == "75000.00"
