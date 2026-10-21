from datetime import datetime, timedelta, timezone
from http.cookies import CookieError, SimpleCookie
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import json
import secrets

from crud_usuarios_usss093025 import crud_usuarios_usss093025


PORT = 3000
SESSION_DURATION = timedelta(hours=8)
BASE_DIR = Path(__file__).resolve().parent
SESSIONS = {}


def crear_servidor(usuarios=None, host="localhost", port=PORT):
    if usuarios is None:
        usuarios = crud_usuarios_usss093025()

    class MiServidor(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(BASE_DIR), **kwargs)

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            super().end_headers()

        def _enviar_json(self, estado, datos, encabezados=()):
            respuesta = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self.send_response(estado)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(respuesta)))
            for nombre, valor in encabezados:
                self.send_header(nombre, valor)
            self.end_headers()
            self.wfile.write(respuesta)

        def _leer_json(self):
            try:
                longitud = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ValueError("La solicitud no es válida.") from None

            if longitud <= 0 or longitud > 16_384:
                raise ValueError("La solicitud está vacía o supera el tamaño permitido.")

            try:
                datos = json.loads(self.rfile.read(longitud).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ValueError("El cuerpo de la solicitud debe ser JSON válido.") from None
            if not isinstance(datos, dict):
                raise ValueError("Los datos enviados no tienen un formato válido.")
            return datos

        def _token_sesion(self):
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
            except (CookieError, ValueError, TypeError):
                return None
            if "session" not in cookie:
                return None
            token = cookie["session"].value
            expiracion = SESSIONS.get(token)
            if expiracion is None:
                return None
            if expiracion <= datetime.now(timezone.utc):
                SESSIONS.pop(token, None)
                return None
            return token

        def _requiere_sesion(self, es_api=False):
            if self._token_sesion():
                return True
            if es_api:
                self._enviar_json(401, {"ok": False, "msg": "Inicie sesión para continuar."})
            else:
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
            return False

        def do_GET(self):
            ruta = urlparse(self.path)
            if ruta.path == "/auth.css":
                self.path = "/auth.css"
                return super().do_GET()
            if ruta.path in ("/", "/login", "/login.html"):
                if self._token_sesion():
                    self.send_response(302)
                    self.send_header("Location", "/usuarios.html")
                    self.end_headers()
                    return
                self.path = "/login.html"
                return super().do_GET()

            if ruta.path == "/api/usuarios":
                if not self._requiere_sesion(es_api=True):
                    return
                buscar = parse_qs(ruta.query).get("buscar", [""])[0]
                try:
                    datos = usuarios.consultar(buscar)
                except RuntimeError as error:
                    self._enviar_json(500, {"ok": False, "msg": str(error)})
                    return
                self._enviar_json(200, {"ok": True, "usuarios": datos})
                return

            if not self._requiere_sesion():
                return
            if ruta.path in ("/usuarios", "/usuarios.html", "/index.html"):
                self.path = ruta.path if ruta.path.endswith(".html") else "/usuarios.html"
                return super().do_GET()

            self._enviar_json(404, {"ok": False, "msg": "Ruta no encontrada."})

        def do_POST(self):
            ruta = urlparse(self.path).path
            if ruta not in ("/api/login", "/api/registro", "/api/logout", "/api/usuarios"):
                self._enviar_json(404, {"ok": False, "msg": "Ruta no encontrada."})
                return

            try:
                datos = self._leer_json()
            except ValueError as error:
                self._enviar_json(400, {"ok": False, "msg": str(error)})
                return

            if ruta == "/api/login":
                try:
                    valido = usuarios.autenticar(datos.get("usuario"), datos.get("clave"))
                except RuntimeError as error:
                    self._enviar_json(500, {"ok": False, "msg": str(error)})
                    return
                if not valido:
                    self._enviar_json(
                        401,
                        {"ok": False, "msg": "Usuario o clave incorrectos."},
                    )
                    return

                token = secrets.token_urlsafe(32)
                SESSIONS[token] = datetime.now(timezone.utc) + SESSION_DURATION
                cookie = f"session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800"
                self._enviar_json(
                    200,
                    {"ok": True, "msg": "Inicio de sesión correcto."},
                    (("Set-Cookie", cookie),),
                )
                return

            if ruta == "/api/registro":
                try:
                    resultado = usuarios.registrar(datos)
                except ValueError as error:
                    self._enviar_json(400, {"ok": False, "msg": str(error)})
                    return
                except RuntimeError as error:
                    self._enviar_json(500, {"ok": False, "msg": str(error)})
                    return
                self._enviar_json(
                    201,
                    {
                        "ok": resultado == "ok",
                        "msg": "Cuenta creada. Ya puede iniciar sesión."
                        if resultado == "ok"
                        else "No se pudo completar el registro.",
                    },
                )
                return

            if not self._requiere_sesion(es_api=True):
                return

            if ruta == "/api/logout":
                token = self._token_sesion()
                if token:
                    SESSIONS.pop(token, None)
                self._enviar_json(
                    200,
                    {"ok": True, "msg": "Sesión cerrada."},
                    (("Set-Cookie", "session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"),),
                )
                return

            try:
                resultado = usuarios.administrar(datos)
            except ValueError as error:
                self._enviar_json(400, {"ok": False, "msg": str(error)})
                return
            except RuntimeError as error:
                self._enviar_json(500, {"ok": False, "msg": str(error)})
                return
            self._enviar_json(200, {"ok": resultado == "ok", "msg": resultado})

    return HTTPServer((host, port), MiServidor)


def main():
    servidor = crear_servidor()
    print(f"Servidor corriendo en http://localhost:{PORT}")
    servidor.serve_forever()


if __name__ == "__main__":
    main()
