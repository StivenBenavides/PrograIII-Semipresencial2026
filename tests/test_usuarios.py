import http.client
import json
import threading
import unittest

import app
from crud_usuarios_usss093025 import (
    _hash_clave,
    _verificar_hash,
    crud_usuarios_usss093025,
)


class BaseDatosFalsa:
    def __init__(self, filas=None):
        self.filas = filas or []
        self.consultas = []
        self.ejecuciones = []

    def consultar(self, sql, datos=()):
        self.consultas.append((sql, datos))
        return self.filas

    def ejecutar(self, sql, datos=()):
        self.ejecuciones.append((sql, datos))
        return "ok"


class PruebasCrudUsuarios(unittest.TestCase):
    def test_registro_inserta_hash_sin_exigir_sesion(self):
        db = BaseDatosFalsa()
        crud = crud_usuarios_usss093025(db)
        resultado = crud.registrar(
            {
                "usuario": "ana",
                "clave": "clave-segura-123",
                "nombre": "Ana Rodríguez",
                "direccion": "Calle 1",
                "telefono": "3883-8383",
            }
        )

        self.assertEqual(resultado, "ok")
        self.assertEqual(db.consultas[0][1], ("ana",))
        sql, valores = db.ejecuciones[0]
        self.assertIn("INSERT INTO usuarios_usss093025", sql)
        self.assertEqual(valores[0], "ana")
        self.assertEqual(valores[-1], "38838383")
        self.assertTrue(_verificar_hash("clave-segura-123", valores[1]))

    def test_registro_rechaza_nombre_de_usuario_existente(self):
        db = BaseDatosFalsa([{"idUsuario": 1}])
        crud = crud_usuarios_usss093025(db)
        with self.assertRaisesRegex(ValueError, "ya está registrado"):
            crud.registrar(
                {
                    "usuario": "ana",
                    "clave": "clave-segura-123",
                    "nombre": "Ana",
                    "direccion": "Calle 1",
                    "telefono": "88812345",
                }
            )
        self.assertEqual(db.ejecuciones, [])

    def test_hash_compatible_con_char_35_y_no_guarda_la_clave(self):
        db = BaseDatosFalsa()
        crud = crud_usuarios_usss093025(db)
        resultado = crud.administrar(
            {
                "accion": "nuevo",
                "usuario": "ana",
                "clave": "clave-segura-123",
                "nombre": "Ana Rodríguez",
                "direccion": "Calle 1",
                "telefono": "88812345",
            }
        )

        self.assertEqual(resultado, "ok")
        clave_guardada = db.ejecuciones[0][1][1]
        self.assertEqual(len(clave_guardada), 35)
        self.assertNotEqual(clave_guardada, "clave-segura-123")
        self.assertTrue(_verificar_hash("clave-segura-123", clave_guardada))
        self.assertFalse(_verificar_hash("incorrecta", clave_guardada))

    def test_login_valida_hash_y_rechaza_clave_incorrecta(self):
        clave_hash = _hash_clave("clave-segura-123")
        db = BaseDatosFalsa([{"idUsuario": 4, "clave": clave_hash}])
        crud = crud_usuarios_usss093025(db)

        self.assertTrue(crud.autenticar("ana", "clave-segura-123"))
        self.assertFalse(crud.autenticar("ana", "clave-incorrecta"))
        self.assertEqual(db.consultas[0][1], ("ana",))

    def test_login_actualiza_claves_anteriores_en_texto_plano(self):
        db = BaseDatosFalsa([{"idUsuario": 4, "clave": "clave-anterior"}])
        crud = crud_usuarios_usss093025(db)

        self.assertTrue(crud.autenticar("ana", "clave-anterior"))
        clave_actualizada = db.ejecuciones[0][1][0]
        self.assertEqual(len(clave_actualizada), 35)
        self.assertTrue(_verificar_hash("clave-anterior", clave_actualizada))

    def test_busqueda_usa_parametros_en_lugar_de_concatenar_entrada(self):
        db = BaseDatosFalsa()
        crud = crud_usuarios_usss093025(db)
        termino = "' OR 1=1 --"

        crud.consultar(termino)

        sql, parametros = db.consultas[0]
        self.assertNotIn(termino, sql)
        self.assertEqual(parametros, (f"%{termino}%", f"%{termino}%"))

    def test_telefono_rechaza_nueve_digitos(self):
        crud = crud_usuarios_usss093025(BaseDatosFalsa())
        with self.assertRaises(ValueError):
            crud.administrar(
                {
                    "accion": "nuevo",
                    "usuario": "ana",
                    "clave": "clave-segura-123",
                    "nombre": "Ana",
                    "direccion": "Calle 1",
                    "telefono": "888812345",
                }
            )

    def test_modificar_sin_clave_conserva_la_clave_actual(self):
        db = BaseDatosFalsa()
        crud = crud_usuarios_usss093025(db)

        resultado = crud.administrar(
            {
                "accion": "modificar",
                "idUsuario": 8,
                "usuario": "ana",
                "clave": "",
                "nombre": "Ana Rodríguez",
                "direccion": "Calle 2",
                "telefono": "88812345",
            }
        )

        self.assertEqual(resultado, "ok")
        sql, parametros = db.ejecuciones[0]
        self.assertNotIn("clave =", sql)
        self.assertEqual(parametros[-1], 8)

    def test_eliminar_usa_el_id_como_parametro(self):
        db = BaseDatosFalsa()
        crud = crud_usuarios_usss093025(db)

        self.assertEqual(
            crud.administrar({"accion": "eliminar", "idUsuario": "8"}),
            "ok",
        )
        sql, parametros = db.ejecuciones[0]
        self.assertIn("WHERE idUsuario = %s", sql)
        self.assertEqual(parametros, (8,))


class UsuariosFalsos:
    def __init__(self):
        self.acciones = []
        self.registros = []

    def consultar(self, buscar=""):
        return [{"idUsuario": 1, "usuario": "ana", "nombre": "Ana",
                 "direccion": "Calle 1", "telefono": "88812345"}]

    def autenticar(self, usuario, clave):
        return usuario == "ana" and clave == "clave"

    def administrar(self, datos):
        self.acciones.append(datos)
        return "ok"

    def registrar(self, datos):
        self.registros.append(datos)
        return "ok"


class PruebasServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repositorio = UsuariosFalsos()
        cls.servidor = app.crear_servidor(
            cls.repositorio, host="127.0.0.1", port=0
        )
        cls.hilo = threading.Thread(target=cls.servidor.serve_forever, daemon=True)
        cls.hilo.start()
        cls.host, cls.puerto = cls.servidor.server_address

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        cls.hilo.join(timeout=2)
        app.SESSIONS.clear()

    def _solicitar(self, metodo, ruta, datos=None, cookie=None):
        conexion = http.client.HTTPConnection(self.host, self.puerto)
        encabezados = {}
        cuerpo = None
        if datos is not None:
            cuerpo = json.dumps(datos)
            encabezados["Content-Type"] = "application/json"
        if cookie:
            encabezados["Cookie"] = cookie.split(";", 1)[0]
        conexion.request(metodo, ruta, body=cuerpo, headers=encabezados)
        respuesta = conexion.getresponse()
        contenido = respuesta.read()
        encabezados_respuesta = dict(respuesta.getheaders())
        conexion.close()
        return respuesta.status, encabezados_respuesta, contenido

    def test_login_protege_la_pagina_y_las_rutas_api(self):
        estado, _, contenido = self._solicitar("GET", "/")
        self.assertEqual(estado, 200)
        self.assertIn(b"Iniciar sesi", contenido)

        estado, encabezados, _ = self._solicitar("GET", "/usuarios.html")
        self.assertEqual(estado, 302)
        self.assertEqual(encabezados["Location"], "/")

        estado, _, _ = self._solicitar("GET", "/api/usuarios")
        self.assertEqual(estado, 401)

        estado, _, contenido = self._solicitar(
            "POST",
            "/api/registro",
            {
                "usuario": "nueva",
                "clave": "clave-segura",
                "nombre": "Nueva Cuenta",
                "direccion": "Calle 2",
                "telefono": "88812346",
            },
        )
        self.assertEqual(estado, 201)
        self.assertIn(b'"ok": true', contenido)
        self.assertEqual(self.repositorio.registros[0]["usuario"], "nueva")

        estado, _, _ = self._solicitar(
            "POST", "/api/login", {"usuario": "ana", "clave": "incorrecta"}
        )
        self.assertEqual(estado, 401)

        estado, encabezados, _ = self._solicitar(
            "POST", "/api/login", {"usuario": "ana", "clave": "clave"}
        )
        self.assertEqual(estado, 200)
        cookie = encabezados["Set-Cookie"]

        estado, _, _ = self._solicitar("GET", "/usuarios.html", cookie=cookie)
        self.assertEqual(estado, 200)

        estado, _, contenido = self._solicitar(
            "GET", "/api/usuarios", cookie=cookie
        )
        self.assertEqual(estado, 200)
        self.assertIn(b'"usuario": "ana"', contenido)

        estado, _, contenido = self._solicitar(
            "POST",
            "/api/usuarios",
            {"accion": "eliminar", "idUsuario": 1},
            cookie=cookie,
        )
        self.assertEqual(estado, 200)
        self.assertIn(b'"ok": true', contenido)
        self.assertEqual(self.repositorio.acciones[0]["accion"], "eliminar")

        estado, _, _ = self._solicitar(
            "POST", "/api/logout", {}, cookie=cookie
        )
        self.assertEqual(estado, 200)
        estado, _, _ = self._solicitar("GET", "/usuarios.html", cookie=cookie)
        self.assertEqual(estado, 302)


if __name__ == "__main__":
    unittest.main()
