import os

import mysql.connector
from mysql.connector import Error


class Conexion:
    def __init__(self):
        database = os.getenv("DB_NAME", "db_sistema_impuestos")
        try:
            self.conexion = mysql.connector.connect(
                host=os.getenv("DB_HOST", "localhost"),
                user=os.getenv("DB_USER", "root"),
                password=os.getenv("DB_PASSWORD", ""),
                database=database,
                charset="utf8mb4",
            )
        except Error as error:
            if error.errno == 1049:
                raise RuntimeError(
                    f"La base de datos MySQL '{database}' no existe en este servidor."
                ) from error
            if error.errno == 1045:
                raise RuntimeError(
                    "MySQL rechazó las credenciales. Revise DB_USER y DB_PASSWORD."
                ) from error
            raise RuntimeError(
                "No se pudo conectar a MySQL. Verifique la configuración de la base de datos."
            ) from error

    def consultar(self, sql, datos=()):
        cursor = None
        try:
            cursor = self.conexion.cursor(dictionary=True)
            cursor.execute(sql, datos)
            return cursor.fetchall()
        except Error as error:
            raise RuntimeError("No se pudo consultar la base de datos.") from error
        finally:
            if cursor is not None:
                cursor.close()

    def ejecutar(self, sql, datos=()):
        cursor = None
        try:
            cursor = self.conexion.cursor()
            cursor.execute(sql, datos)
            self.conexion.commit()
            return "ok"
        except Error as error:
            try:
                self.conexion.rollback()
            except Error as rollback_error:
                raise RuntimeError(
                    "Falló la operación y no se pudo revertir la transacción."
                ) from rollback_error
            raise RuntimeError("No se pudo guardar el cambio en la base de datos.") from error
        finally:
            if cursor is not None:
                cursor.close()
