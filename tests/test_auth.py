# tests/test_auth.py
from tests.conftest import ADMIN_EMAIL, API


def test_sin_token_responde_401(client):
    assert client.get(f"{API}/customers/").status_code == 401


def test_login_con_clave_mala_responde_401(client):
    r = client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "mala"})
    assert r.status_code == 401


def test_me_devuelve_al_dueno_del_token_sin_password(client, admin):
    r = client.get(f"{API}/auth/me", headers=admin)
    assert r.status_code == 200
    assert r.json()["email"] == ADMIN_EMAIL
    assert "password_hash" not in r.json()


def test_cajero_no_puede_crear_productos(client, crear_usuario):
    cajero = crear_usuario("CAJERO", "caja@test.com")
    r = client.post(f"{API}/products/", headers=cajero, json={"nombre": "Wok", "precio": "25000"})
    assert r.status_code == 403


def test_limit_mayor_a_100_responde_422(client, admin):
    assert client.get(f"{API}/products/?limit=1000", headers=admin).status_code == 422


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"
    assert r.json()["database"] == "ok"
