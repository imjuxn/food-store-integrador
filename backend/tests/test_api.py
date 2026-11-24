import os
import unittest
from pathlib import Path

Path('.tmp').mkdir(exist_ok=True)
os.environ["DATABASE_URL"] = os.environ.get("FOODSTORE_TEST_DATABASE_URL", "sqlite:///./.tmp/test_foodstore.db")
os.environ["SECRET_KEY"] = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEF"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.core.database import engine
from app.db.seed import seed
from app.main import app

API = "/api/v1"


class FoodStoreAPITest(unittest.TestCase):
    def setUp(self):
        SQLModel.metadata.drop_all(engine)
        seed()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def login_admin(self):
        respuesta = self.client.post(
            f"{API}/auth/token", data={"username": "admin", "password": "Admin1234!"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("access_token", respuesta.json())
        self.assertIn("access_token", self.client.cookies)

    def registrar_cliente(self, username="cliente", email="cliente@correo.com"):
        respuesta = self.client.post(
            f"{API}/auth/register",
            json={
                "username": username,
                "full_name": "Cliente de prueba",
                "email": email,
                "password": "Clave1234!",
            },
        )
        self.assertEqual(respuesta.status_code, 201)
        return respuesta.json()

    def login_cliente(self, username="cliente"):
        respuesta = self.client.post(
            f"{API}/auth/token", data={"username": username, "password": "Clave1234!"}
        )
        self.assertEqual(respuesta.status_code, 200)

    def primer_producto(self):
        return self.client.get(f"{API}/productos").json()["items"][0]

    def test_seed_idempotente_y_documentacion(self):
        seed()
        self.assertEqual(len(self.client.get(f"{API}/categorias").json()), 3)
        self.assertEqual(self.client.get(f"{API}/productos").json()["total"], 8)
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertEqual(self.client.get("/redoc").status_code, 200)

    def test_registro_login_cookie_y_roles(self):
        self.assertEqual(self.client.get(f"{API}/auth/me").status_code, 401)
        usuario = self.registrar_cliente()
        self.assertEqual(usuario["role"], "user")
        self.assertNotIn("hashed_password", usuario)
        self.assertEqual(
            self.client.post(
                f"{API}/auth/register",
                json={"username": "CLIENTE", "full_name": "Otro", "email": "otro@correo.com", "password": "Clave1234!"},
            ).status_code,
            409,
        )
        self.login_cliente()
        self.assertEqual(self.client.get(f"{API}/auth/me").status_code, 200)
        self.assertEqual(self.client.get(f"{API}/admin/usuarios").status_code, 403)
        self.assertEqual(self.client.post(f"{API}/auth/logout").status_code, 200)
        self.assertEqual(self.client.get(f"{API}/auth/me").status_code, 401)

    def test_catalogo_crud_y_baja_logica(self):
        self.assertEqual(self.client.post(f"{API}/categorias", json={"nombre": "Helados"}).status_code, 401)
        self.login_admin()
        categoria = self.client.post(f"{API}/categorias", json={"nombre": "Helados", "descripcion": "Fríos"})
        self.assertEqual(categoria.status_code, 201)
        categoria_id = categoria.json()["id"]
        self.assertEqual(self.client.post(f"{API}/categorias", json={"nombre": "HELADOS"}).status_code, 409)
        producto = self.client.post(
            f"{API}/productos",
            json={"categoria_id": categoria_id, "nombre": "Helado de chocolate", "precio_base": 4000, "stock": 5},
        )
        self.assertEqual(producto.status_code, 201)
        producto_id = producto.json()["id"]
        self.assertEqual(producto.json()["categoria"]["nombre"], "Helados")
        self.assertEqual(self.client.put(f"{API}/productos/{producto_id}", json={"precio_base": 4500}).json()["nombre"], "Helado de chocolate")
        self.assertEqual(self.client.patch(f"{API}/productos/{producto_id}/stock", json={"stock": 7, "disponible": False}).json()["stock"], 7)
        self.assertEqual(self.client.get(f"{API}/productos?search=chocolate").json()["total"], 1)
        self.assertEqual(self.client.delete(f"{API}/categorias/{categoria_id}").status_code, 204)
        self.assertEqual(self.client.get(f"{API}/productos/{producto_id}").status_code, 200)
        self.assertEqual(self.client.delete(f"{API}/productos/{producto_id}").status_code, 204)
        self.assertEqual(self.client.get(f"{API}/productos/{producto_id}").status_code, 404)
        self.assertEqual(self.client.delete(f"{API}/productos/{producto_id}").status_code, 404)

    def test_pedido_y_cancelacion_restituyen_stock(self):
        self.registrar_cliente()
        self.login_cliente()
        producto = self.primer_producto()
        pedido = self.client.post(
            f"{API}/pedidos",
            json={
                "items": [{"producto_id": producto["id"], "cantidad": 2}],
                "forma_pago": "EFECTIVO",
                "direccion_entrega": "Calle Falsa 123",
            },
        )
        self.assertEqual(pedido.status_code, 201)
        self.assertEqual(pedido.json()["estado"], "PENDIENTE")
        self.assertEqual(pedido.json()["items"][0]["nombre_producto"], producto["nombre"])
        self.assertEqual(pedido.json()["total"], producto["precio_base"] * 2)
        self.assertEqual(self.client.get(f"{API}/productos/{producto['id']}").json()["stock"], producto["stock"] - 2)
        pedido_id = pedido.json()["id"]
        cancelado = self.client.patch(f"{API}/pedidos/{pedido_id}/cancelar")
        self.assertEqual(cancelado.status_code, 200)
        self.assertEqual(cancelado.json()["estado"], "CANCELADO")
        self.assertEqual(self.client.get(f"{API}/productos/{producto['id']}").json()["stock"], producto["stock"])
        self.assertEqual(self.client.patch(f"{API}/pedidos/{pedido_id}/cancelar").status_code, 400)

    def test_rollback_si_falla_un_item(self):
        self.registrar_cliente()
        self.login_cliente()
        productos = self.client.get(f"{API}/productos").json()["items"]
        primero, segundo = productos[:2]
        pedido = self.client.post(
            f"{API}/pedidos",
            json={
                "items": [
                    {"producto_id": primero["id"], "cantidad": 1},
                    {"producto_id": segundo["id"], "cantidad": segundo["stock"] + 1},
                ],
                "forma_pago": "TRANSFERENCIA",
                "direccion_entrega": "Calle Falsa 123",
            },
        )
        self.assertEqual(pedido.status_code, 400)
        self.assertEqual(self.client.get(f"{API}/productos/{primero['id']}").json()["stock"], primero["stock"])
        self.assertEqual(self.client.get(f"{API}/pedidos").json()["total"], 0)

    def test_pedido_ajeno_y_snapshot_historico(self):
        self.registrar_cliente()
        self.login_cliente()
        producto = self.primer_producto()
        pedido = self.client.post(
            f"{API}/pedidos",
            json={
                "items": [{"producto_id": producto["id"], "cantidad": 1}],
                "forma_pago": "EFECTIVO",
                "direccion_entrega": "Calle Falsa 123",
            },
        )
        self.assertEqual(pedido.status_code, 201)
        pedido_id = pedido.json()["id"]

        self.registrar_cliente("otro_cliente", "otro_cliente@correo.com")
        self.login_cliente("otro_cliente")
        self.assertEqual(self.client.get(f"{API}/pedidos/{pedido_id}").status_code, 403)
        self.assertEqual(self.client.patch(f"{API}/pedidos/{pedido_id}/cancelar").status_code, 403)
        self.assertEqual(self.client.get(f"{API}/pedidos").json()["total"], 0)

        self.login_admin()
        self.assertEqual(
            self.client.put(
                f"{API}/productos/{producto['id']}",
                json={"nombre": "Nombre nuevo", "precio_base": producto["precio_base"] + 1000},
            ).status_code,
            200,
        )
        self.assertEqual(self.client.delete(f"{API}/productos/{producto['id']}").status_code, 204)
        self.login_cliente()
        historico = self.client.get(f"{API}/pedidos/{pedido_id}").json()
        self.assertEqual(historico["items"][0]["nombre_producto"], producto["nombre"])
        self.assertEqual(historico["items"][0]["precio_unitario"], producto["precio_base"])

    def test_producto_repetido_y_validaciones(self):
        self.registrar_cliente()
        self.login_cliente()
        producto = self.primer_producto()
        datos = {
            "items": [{"producto_id": producto["id"], "cantidad": 1}] * 2,
            "forma_pago": "EFECTIVO",
            "direccion_entrega": "Calle Falsa 123",
        }
        self.assertEqual(self.client.post(f"{API}/pedidos", json=datos).status_code, 400)
        datos["items"] = []
        self.assertEqual(self.client.post(f"{API}/pedidos", json=datos).status_code, 422)
        datos["items"] = [{"producto_id": producto["id"], "cantidad": 1}]
        datos["forma_pago"] = "TARJETA"
        self.assertEqual(self.client.post(f"{API}/pedidos", json=datos).status_code, 422)

    def test_admin_transiciones_resumen_y_usuarios(self):
        cliente = self.registrar_cliente()
        self.login_cliente()
        producto = self.primer_producto()
        pedido = self.client.post(
            f"{API}/pedidos",
            json={"items": [{"producto_id": producto["id"], "cantidad": 1}], "forma_pago": "EFECTIVO", "direccion_entrega": "Calle Falsa 123"},
        )
        pedido_id = pedido.json()["id"]
        self.assertEqual(self.client.patch(f"{API}/pedidos/{pedido_id}/estado", json={"estado": "ENTREGADO"}).status_code, 403)
        self.login_admin()
        self.assertEqual(self.client.patch(f"{API}/pedidos/{pedido_id}/estado", json={"estado": "ENTREGADO"}).status_code, 400)
        self.assertEqual(self.client.patch(f"{API}/pedidos/{pedido_id}/estado", json={"estado": "EN_PREPARACION"}).status_code, 200)
        self.assertEqual(self.client.patch(f"{API}/pedidos/{pedido_id}/estado", json={"estado": "ENTREGADO"}).status_code, 200)
        resumen = self.client.get(f"{API}/pedidos/resumen")
        self.assertEqual(resumen.status_code, 200)
        self.assertEqual(resumen.json()["entregados"], 1)
        self.assertEqual(resumen.json()["ingresos_entregados"], pedido.json()["total"])
        self.assertEqual(self.client.post(f"{API}/admin/usuarios/{cliente['id']}/desactivar").status_code, 200)
        self.assertEqual(self.client.post(f"{API}/admin/usuarios/{cliente['id']}/activar").status_code, 200)
        admin_id = self.client.get(f"{API}/auth/me").json()["id"]
        self.assertEqual(self.client.post(f"{API}/admin/usuarios/{admin_id}/desactivar").status_code, 400)

    def test_categoria_eliminada_conserva_nombre_y_productos(self):
        self.login_admin()
        categoria = self.client.get(f"{API}/categorias").json()[0]
        self.assertEqual(self.client.delete(f"{API}/categorias/{categoria['id']}").status_code, 204)
        self.assertEqual(self.client.get(f"{API}/categorias/{categoria['id']}").status_code, 404)
        self.assertEqual(self.client.put(f"{API}/categorias/{categoria['id']}", json={"nombre": "Otro nombre"}).status_code, 404)
        self.assertEqual(self.client.delete(f"{API}/categorias/{categoria['id']}").status_code, 404)
        self.assertEqual(self.client.post(f"{API}/categorias", json={"nombre": categoria["nombre"]}).status_code, 409)
        self.assertGreater(self.client.get(f"{API}/productos", params={"categoria_id": categoria["id"]}).json()["total"], 0)

    def test_sesion_desactivada_rechazada_y_acciones_idempotentes(self):
        cliente = self.registrar_cliente()
        self.login_cliente()
        cookie_cliente = self.client.cookies.get("access_token")
        self.login_admin()
        for _ in range(2):
            self.assertEqual(self.client.post(f"{API}/admin/usuarios/{cliente['id']}/desactivar").status_code, 200)
        self.assertEqual(self.client.post(f"{API}/admin/usuarios/99999/activar").status_code, 404)
        self.client.cookies.set("access_token", cookie_cliente, domain="testserver.local", path="/")
        self.assertEqual(self.client.get(f"{API}/auth/me").status_code, 400)
        self.assertEqual(self.client.post(f"{API}/auth/token", data={"username": "cliente", "password": "Clave1234!"}).status_code, 400)
        self.assertEqual(self.client.post(f"{API}/auth/token", data={"username": "cliente", "password": "incorrecta"}).status_code, 401)
        self.login_admin()
        for _ in range(2):
            self.assertEqual(self.client.post(f"{API}/admin/usuarios/{cliente['id']}/activar").status_code, 200)

    def test_cancelacion_admin_en_preparacion_restituye_solo_una_vez(self):
        self.registrar_cliente()
        self.login_cliente()
        producto = self.primer_producto()
        pedido = self.client.post(f"{API}/pedidos", json={
            "items": [{"producto_id": producto["id"], "cantidad": 2}],
            "forma_pago": "TRANSFERENCIA", "direccion_entrega": "Avenida Siempre Viva 742",
        }).json()
        self.login_admin()
        self.assertEqual(self.client.patch(f"{API}/pedidos/{pedido['id']}/estado", json={"estado": "EN_PREPARACION"}).status_code, 200)
        self.login_cliente()
        self.assertEqual(self.client.patch(f"{API}/pedidos/{pedido['id']}/cancelar").status_code, 400)
        self.login_admin()
        self.assertEqual(self.client.patch(f"{API}/pedidos/{pedido['id']}/estado", json={"estado": "CANCELADO"}).status_code, 200)
        self.assertEqual(self.client.patch(f"{API}/pedidos/{pedido['id']}/estado", json={"estado": "CANCELADO"}).status_code, 400)
        self.assertEqual(self.client.get(f"{API}/productos/{producto['id']}").json()["stock"], producto["stock"])
        self.assertEqual(self.client.delete(f"{API}/pedidos/{pedido['id']}").status_code, 405)
        self.assertEqual(self.client.put(f"{API}/pedidos/{pedido['id']}", json={"total": 0}).status_code, 405)

    def test_validaciones_limites_y_bloqueo_de_escritura(self):
        self.registrar_cliente()
        self.login_cliente()
        self.assertEqual(self.client.post(f"{API}/productos", json={"categoria_id": 1, "nombre": "Prueba", "precio_base": 10}).status_code, 403)
        for params in ({"limit": 101}, {"skip": -1}, {"categoria_id": 0}):
            self.assertEqual(self.client.get(f"{API}/productos", params=params).status_code, 422)
        datos = {"items": [{"producto_id": 1, "cantidad": 1}], "forma_pago": "EFECTIVO", "direccion_entrega": "     "}
        self.assertEqual(self.client.post(f"{API}/pedidos", json=datos).status_code, 422)
        datos["direccion_entrega"] = "Calle válida 123"
        datos["items"] = [{"producto_id": 99999, "cantidad": 1}]
        self.assertEqual(self.client.post(f"{API}/pedidos", json=datos).status_code, 404)
        self.login_admin()
        self.assertEqual(self.client.patch(f"{API}/productos/1/stock", json={"stock": -1}).status_code, 422)
        self.assertEqual(self.client.put(f"{API}/productos/1", json={"nombre": None}).status_code, 422)
        self.assertEqual(self.client.put(f"{API}/productos/1", json={"categoria_id": 99999}).status_code, 404)

    def test_cookie_y_contrasena_bcrypt_sin_truncamiento(self):
        self.login_admin()
        response = self.client.post(f"{API}/auth/token", data={"username": "admin", "password": "Admin1234!"})
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertIn("max-age=1800", cookie)
        self.assertNotIn("hashed_password", self.client.get(f"{API}/auth/me").json())
        response = self.client.post(f"{API}/auth/register", json={
            "username": "demasiado", "full_name": "Prueba", "email": "largo@correo.com", "password": "ñ" * 37,
        })
        self.assertEqual(response.status_code, 422)

    def test_cors_y_origen_en_operaciones_de_escritura(self):
        response = self.client.options(f"{API}/auth/token", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")
        self.assertEqual(response.headers["access-control-allow-credentials"], "true")
        response = self.client.post(f"{API}/auth/token", data={
            "username": "admin", "password": "Admin1234!",
        }, headers={"Origin": "https://origen-no-permitido.example"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.post(f"{API}/auth/logout", headers={"Origin": "http://testserver"}).status_code, 200)


if __name__ == "__main__":
    unittest.main()

