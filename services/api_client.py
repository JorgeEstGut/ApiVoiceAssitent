"""Cliente HTTP para consumir la API original del sistema de prevención de incendios."""

import logging
import requests
from config import Config

logger = logging.getLogger(__name__)


def listar_sensores() -> list:
    """Consulta la lista de sensores registrados en el sistema."""
    url = f"{Config.API_ORIGINAL_URL}/sensores"
    try:
        resp = requests.get(url, timeout=Config.API_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            sensores = []
            for s in items:
                sensores.append({
                    "id": s.get("id"),
                    "nombre": s.get("nombre"),
                    "tipo": s.get("tipo_sensor_nombre"),
                    "estado": s.get("estado_nombre"),
                    "dispositivo": s.get("dispositivo_nombre"),
                    "ubicacion": s.get("ubicacion_nombre"),
                })
            return sensores
        logger.warning(f"Error al listar sensores: HTTP {resp.status_code}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Error de conexión en listar_sensores: {e}")
        return []


def obtener_ultimo_valor(sensor_id: int) -> dict:
    """Obtiene la medición más reciente de un sensor específico."""
    url = f"{Config.API_ORIGINAL_URL}/lecturas"
    params = {"sensor_id": sensor_id, "per_page": 1, "page": 1}
    try:
        resp = requests.get(url, params=params, timeout=Config.API_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            if not items:
                return {"error": f"No hay lecturas registradas para el sensor con ID {sensor_id}."}
            ultima = items[0]
            valores = []
            for v in ultima.get("valores", []):
                valores.append({
                    "parametro": v.get("parametro_nombre"),
                    "unidad": v.get("parametro_unidad"),
                    "valor": v.get("valor"),
                })
            return {
                "sensor_id": sensor_id,
                "sensor_nombre": ultima.get("sensor_nombre"),
                "fecha_hora": ultima.get("timestamp"),
                "valores": valores,
            }
        return {"error": f"Error HTTP {resp.status_code} al consultar lecturas del sensor {sensor_id}."}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en obtener_ultimo_valor: {e}")
        return {"error": "No se pudo conectar con el sensor en este momento."}


def obtener_promedio(sensor_id: int, cantidad_lecturas: int = 20) -> dict:
    """
    Obtiene las últimas N lecturas de un sensor y calcula en Python el promedio
    aritmético de cada parámetro medido (ppm, temperatura, humedad).
    """
    url = f"{Config.API_ORIGINAL_URL}/lecturas"
    params = {"sensor_id": sensor_id, "per_page": max(1, min(cantidad_lecturas, 100)), "page": 1}
    try:
        resp = requests.get(url, params=params, timeout=Config.API_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            if not items:
                return {"error": f"No hay lecturas suficientes para calcular el promedio del sensor {sensor_id}."}

            sensor_nombre = items[0].get("sensor_nombre", f"Sensor {sensor_id}")
            acumulados = {}

            for lectura in items:
                for v in lectura.get("valores", []):
                    param = v.get("parametro_nombre")
                    unidad = v.get("parametro_unidad")
                    valor = v.get("valor")
                    if param and valor is not None:
                        if param not in acumulados:
                            acumulados[param] = {"valores": [], "unidad": unidad}
                        acumulados[param]["valores"].append(float(valor))

            promedios = []
            for param, info in acumulados.items():
                valores_lista = info["valores"]
                if valores_lista:
                    promedio = round(sum(valores_lista) / len(valores_lista), 2)
                    promedios.append({
                        "parametro": param,
                        "unidad": info["unidad"],
                        "promedio": promedio,
                        "minimo": round(min(valores_lista), 2),
                        "maximo": round(max(valores_lista), 2),
                    })

            return {
                "sensor_id": sensor_id,
                "sensor_nombre": sensor_nombre,
                "lecturas_analizadas": len(items),
                "promedios": promedios,
            }
        return {"error": f"Error HTTP {resp.status_code} al consultar promedio."}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en obtener_promedio: {e}")
        return {"error": "No se pudo conectar con el servidor para calcular el promedio."}


def obtener_promedio_por_fecha(sensor_id: int, desde: str, hasta: str) -> dict:
    """
    Obtiene las lecturas en un rango de fechas ISO 8601 y calcula el promedio en Python.
    """
    url = f"{Config.API_ORIGINAL_URL}/lecturas"
    params = {
        "sensor_id": sensor_id,
        "desde": desde,
        "hasta": hasta,
        "per_page": 100,
        "page": 1,
    }
    try:
        resp = requests.get(url, params=params, timeout=Config.API_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            if not items:
                return {"mensaje": f"No se registraron lecturas entre {desde} y {hasta} para el sensor {sensor_id}."}

            sensor_nombre = items[0].get("sensor_nombre", f"Sensor {sensor_id}")
            acumulados = {}

            for lectura in items:
                for v in lectura.get("valores", []):
                    param = v.get("parametro_nombre")
                    unidad = v.get("parametro_unidad")
                    valor = v.get("valor")
                    if param and valor is not None:
                        if param not in acumulados:
                            acumulados[param] = {"valores": [], "unidad": unidad}
                        acumulados[param]["valores"].append(float(valor))

            promedios = []
            for param, info in acumulados.items():
                valores_lista = info["valores"]
                if valores_lista:
                    promedio = round(sum(valores_lista) / len(valores_lista), 2)
                    promedios.append({
                        "parametro": param,
                        "unidad": info["unidad"],
                        "promedio": promedio,
                    })

            return {
                "sensor_id": sensor_id,
                "sensor_nombre": sensor_nombre,
                "rango_desde": desde,
                "rango_hasta": hasta,
                "lecturas_analizadas": len(items),
                "promedios": promedios,
            }
        return {"error": f"Error HTTP {resp.status_code} al consultar lecturas por fecha."}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en obtener_promedio_por_fecha: {e}")
        return {"error": "Error al conectar con el servidor para el rango de fechas."}


def consultar_umbrales() -> list:
    """Obtiene los niveles de riesgo y rangos mínimos y máximos de alerta configurados."""
    url = f"{Config.API_ORIGINAL_URL}/umbrales-alerta"
    try:
        resp = requests.get(url, timeout=Config.API_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            umbrales = []
            for u in items:
                umbrales.append({
                    "parametro": u.get("parametro_nombre"),
                    "nivel": u.get("nivel_riesgo_nombre"),
                    "minimo": u.get("valor_minimo"),
                    "maximo": u.get("valor_maximo"),
                })
            return umbrales
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en consultar_umbrales: {e}")
        return []
