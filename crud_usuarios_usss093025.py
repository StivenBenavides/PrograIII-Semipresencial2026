import base64
import hashlib
import hmac
import re
import secrets

import conexion


TABLA_USUARIOS = "usuarios_usss093025"
ITERACIONES_CLAVE = 310_000


def _hash_clave(clave):
    sal = secrets.token_bytes(10)
    derivada = hashlib.pbkdf2_hmac(
        "sha256", clave.encode("utf-8"), sal, ITERACIONES_CLAVE, dklen=13
    )
    sal_codificada = base64.urlsafe_b64encode(sal).decode("ascii").rstrip("=")
    hash_codificado = base64.urlsafe_b64encode(derivada).decode("ascii").rstrip("=")
    return f"1${sal_codificada}${hash_codificado}"


def _verificar_hash(clave, almacenada):
    try:
        version, sal_codificada, hash_codificado = almacenada.split("$")
        if version != "1":
            return False
        sal = base64.urlsafe_b64decode(sal_codificada + "==")
        esperado = base64.urlsafe_b64decode(hash_codificado + "==")
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256", clave.encode("utf-8"), sal, ITERACIONES_CLAVE, dklen=13
    )
    return hmac.compare_digest(actual, esperado)


class crud_usuarios_usss093025:
    def __init__(self, db=None):
        self.db = db if db is not None else conexion.Conexion()

    def registrar(self, datos):
        usuario, nombre, direccion, telefono = self._validar_datos(datos)
        clave = self._validar_clave(datos.get("clave"))
        existentes = self.db.consultar(
            f"SELECT idUsuario FROM {TABLA_USUARIOS} WHERE usuario = %s LIMIT 1",
            (usuario,),
        )
        if existentes:
            raise ValueError("Ese nombre de usuario ya está registrado.")

        return self.db.ejecutar(
            f"""
                INSERT INTO {TABLA_USUARIOS}
                    (usuario, clave, nombre, direccion, telefono)
                VALUES (%s, %s, %s, %s, %s)
            """,
            (usuario, _hash_clave(clave), nombre, direccion, telefono),
        )

    def consultar(self, buscar=""):
        buscar = (buscar or "").strip()
        sql = f"""
            SELECT idUsuario, usuario, nombre, direccion, telefono
            FROM {TABLA_USUARIOS}
            WHERE usuario LIKE %s OR nombre LIKE %s
            ORDER BY nombre, usuario
        """
        termino = f"%{buscar}%"
        return self.db.consultar(sql, (termino, termino))

    def administrar(self, datos):
        accion = datos.get("accion")

        if accion == "eliminar":
            id_usuario = self._validar_id(datos.get("idUsuario"))
            return self.db.ejecutar(
                f"DELETE FROM {TABLA_USUARIOS} WHERE idUsuario = %s",
                (id_usuario,),
            )

        if accion == "nuevo":
            usuario, nombre, direccion, telefono = self._validar_datos(datos)
            clave = self._validar_clave(datos.get("clave"))
            return self.db.ejecutar(
                f"""
                    INSERT INTO {TABLA_USUARIOS}
                        (usuario, clave, nombre, direccion, telefono)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                (usuario, _hash_clave(clave), nombre, direccion, telefono),
            )

        if accion == "modificar":
            id_usuario = self._validar_id(datos.get("idUsuario"))
            usuario, nombre, direccion, telefono = self._validar_datos(datos)
            clave = datos.get("clave", "")
            if not isinstance(clave, str):
                raise ValueError("La clave no es válida.")
            if clave:
                clave = self._validar_clave(clave)
                return self.db.ejecutar(
                    f"""
                        UPDATE {TABLA_USUARIOS}
                        SET usuario = %s, clave = %s, nombre = %s,
                            direccion = %s, telefono = %s
                        WHERE idUsuario = %s
                    """,
                    (
                        usuario,
                        _hash_clave(clave),
                        nombre,
                        direccion,
                        telefono,
                        id_usuario,
                    ),
                )
            return self.db.ejecutar(
                f"""
                    UPDATE {TABLA_USUARIOS}
                    SET usuario = %s, nombre = %s, direccion = %s,
                        telefono = %s
                    WHERE idUsuario = %s
                """,
                (usuario, nombre, direccion, telefono, id_usuario),
            )

        raise ValueError("La acción solicitada no es válida.")

    def autenticar(self, usuario, clave):
        if not isinstance(usuario, str) or not isinstance(clave, str):
            return False
        usuario = usuario.strip()
        if not usuario or not clave or len(usuario) > 35 or len(clave) > 35:
            return False

        filas = self.db.consultar(
            f"SELECT idUsuario, clave FROM {TABLA_USUARIOS} WHERE usuario = %s LIMIT 1",
            (usuario,),
        )
        if not filas:
            return False

        fila = filas[0]
        almacenada = fila["clave"].rstrip()
        if almacenada.startswith("1$"):
            return _verificar_hash(clave, almacenada)

        if not hmac.compare_digest(clave, almacenada):
            return False

        resultado = self.db.ejecutar(
            f"UPDATE {TABLA_USUARIOS} SET clave = %s WHERE idUsuario = %s",
            (_hash_clave(clave), fila["idUsuario"]),
        )
        if resultado != "ok":
            raise RuntimeError("No se pudo proteger la clave almacenada.")
        return True

    @staticmethod
    def _validar_id(valor):
        try:
            id_usuario = int(valor)
        except (TypeError, ValueError):
            raise ValueError("El identificador del usuario no es válido.") from None
        if id_usuario <= 0:
            raise ValueError("El identificador del usuario no es válido.")
        return id_usuario

    @staticmethod
    def _validar_datos(datos):
        campos = ("usuario", "nombre", "direccion", "telefono")
        valores = {}
        limites = {"usuario": 35, "nombre": 85, "direccion": 100}
        for campo in campos:
            valor = datos.get(campo)
            if not isinstance(valor, str) or not valor.strip():
                raise ValueError("Complete todos los campos del usuario.")
            valor = valor.strip()
            if len(valor) > limites.get(campo, 9):
                raise ValueError(f"El campo {campo} supera la longitud permitida.")
            valores[campo] = valor

        if not re.fullmatch(r"[0-9]{9}", valores["telefono"]):
            raise ValueError("El teléfono debe contener exactamente 9 dígitos.")
        return tuple(valores[campo] for campo in campos)

    @staticmethod
    def _validar_clave(valor):
        if not isinstance(valor, str) or not 8 <= len(valor) <= 35:
            raise ValueError("La clave debe tener entre 8 y 35 caracteres.")
        return valor
