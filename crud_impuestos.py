import math
from mysql.connector.errors import Error
import conexion

db = conexion.Conexion()

class crud_impuestos:
    def calcular_precio(self, balance):
        sql = f"SELECT * FROM tarifas_impuestos WHERE {balance} >= desde AND {balance} <= hasta"
        tarifas = db.consultar(sql)
        
        if not tarifas:
            return {"error": "No existe una tarifa configurada para el balance indicado."}
        
        if len(tarifas) > 1:
            return {"error": "Existe mas de una tarifa aplicable. Corrija la tabla tarifaria."}
            
        t = tarifas[0]
        # Convertimos explicitamente a float para poder operar sin problemas
        porcentaje = float(t['porcentaje'])
        balance = float(balance)
        precio_base = float(t['precio_base'])
        
        if porcentaje > 0:
            impuesto = balance * (porcentaje / 100)
        else:
            excedente = balance - float(t['desde'])
            bloques = math.ceil(excedente / 1000.0)
            impuesto = precio_base + (bloques * float(t['adicional']))
            
        # CORRECCION: Solo devolvemos el precio calculado. 
        # Hemos quitado el diccionario 't' para evitar el error de serializacion JSON.
        return {"precio_calculado": round(impuesto, 2)}

    def administrar_periodo(self, datos):
        try:
            cliente = db.consultar(f"SELECT tipo FROM clientes WHERE idCliente={datos['idCliente']}")
            if not cliente or cliente[0]['tipo'] != 'empresa':
                return "El Impuesto a las Actividades Economicas requiere un cliente de tipo empresa."

            sql_check = f"""
                SELECT idPeriodo FROM periodos_impuestos 
                WHERE idCliente={datos['idCliente']} AND producto='{datos['producto']}'
                AND (fecha_desde < '{datos['fecha_hasta']}' AND fecha_hasta > '{datos['fecha_desde']}')
            """
            if db.consultar(sql_check):
                return "El periodo indicado se superpone con un periodo existente."

            if datos['accion'] == 'nuevo':
                sql = """
                    INSERT INTO periodos_impuestos(idCliente, producto, fecha_desde, fecha_hasta, balance, precio, estado)
                    VALUES(%s,%s,%s,%s,%s,%s,'Vigente')
                """
                valores = (datos['idCliente'], datos['producto'], datos['fecha_desde'], datos['fecha_hasta'], datos['balance'], datos['precio'])
                return db.ejecutar(sql, valores)
        except Error as e:
            return f"Error al guardar el periodo: {e}"