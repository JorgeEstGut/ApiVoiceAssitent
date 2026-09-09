"""Cliente HTTP completo para consumir todos los endpoints del sistema de prevención de incendios."""

import logging
import requests
from config import Config

logger = logging.getLogger(__name__)


def listar_sensores() -> list:
    """Consulta la lista de sensores registrados en el sistema con su estado y ubicación."""
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
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en listar_sensores: {e}")
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
            total = data.get("data", {}).get("total", len(items))
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
                "total_lecturas_registradas": total,
                "valores": valores,
            }
        return {"error": f"Error HTTP {resp.status_code} al consultar lecturas del sensor {sensor_id}."}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en obtener_ultimo_valor: {e}")
        return {"error": "No se pudo conectar con el sensor en este momento."}


def obtener_promedio(sensor_id: int, cantidad_lecturas: int = 20) -> dict:
    """
    Calcula en Python el promedio aritmético de las últimas N lecturas de un sensor
    para cada parámetro medido (temperatura, humedad, ppm).
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
    """Calcula el promedio de mediciones en un rango de fechas ISO 8601."""
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


def consultar_total_lecturas(sensor_id: int = None) -> dict:
    """
    Devuelve la cantidad total de lecturas registradas en el sistema o para un sensor específico.
    Permite responder preguntas como '¿cuántas lecturas tengo en total?' o '¿cuántas tiene el sensor 1?'.
    """
    url = f"{Config.API_ORIGINAL_URL}/lecturas"
    params = {"per_page": 1, "page": 1}
    if sensor_id is not None:
        params["sensor_id"] = sensor_id

    try:
        resp = requests.get(url, params=params, timeout=Config.API_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            total = data.get("total", 0)
            items = data.get("items", [])
            sensor_nombre = items[0].get("sensor_nombre") if items else None
            return {
                "total_lecturas": total,
                "sensor_id": sensor_id,
                "sensor_nombre": sensor_nombre or ("Todo el sistema" if not sensor_id else f"Sensor {sensor_id}"),
            }
        return {"error": f"Error HTTP {resp.status_code} al contar lecturas."}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en consultar_total_lecturas: {e}")
        return {"error": "No se pudo consultar el total de lecturas."}


def consultar_alertas(estado: str = None, sensor_id: int = None) -> dict:
    """
    Consulta las alertas ambientales emitidas por el sistema.
    Permite filtrar por estado ('activa' o 'resuelta') y por sensor.
    Permite responder preguntas como '¿cuántas alertas tengo activas?' o '¿hay alguna alerta crítica?'.
    """
    url = f"{Config.API_ORIGINAL_URL}/alertas"
    params = {"per_page": 20, "page": 1}
    if estado:
        params["estado"] = estado
    if sensor_id is not None:
        params["sensor_id"] = sensor_id

    try:
        resp = requests.get(url, params=params, timeout=Config.API_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            items = data.get("items", [])
            total = data.get("total", len(items))
            lista = []
            for a in items:
                lista.append({
                    "id": a.get("id"),
                    "sensor_nombre": a.get("sensor_nombre"),
                    "nivel": a.get("nivel_riesgo_nombre") or a.get("nivel"),
                    "valor": a.get("valor_medido"),
                    "estado": a.get("estado"),
                    "fecha": a.get("timestamp"),
                })
            return {
                "total_alertas": total,
                "filtro_estado": estado or "todas",
                "alertas": lista,
            }
        return {"error": f"Error HTTP {resp.status_code} al consultar alertas."}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en consultar_alertas: {e}")
        return {"error": "No se pudo conectar con el servicio de alertas."}


def consultar_umbrales() -> list:
    """Obtiene los niveles de riesgo y rangos mínimos y máximos de alerta configurados."""
    url = f"{Config.API_ORIGINAL_URL}/umbrales-alerta"
    try:
        resp = requests.get(url, timeout=Config.API_TIMEOUT)
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
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


def consultar_dispositivos() -> list:
    """Consulta los dispositivos de hardware ESP32 y sus ubicaciones."""
    url = f"{Config.API_ORIGINAL_URL}/dispositivos"
    try:
        resp = requests.get(url, timeout=Config.API_TIMEOUT)
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
            return [
                {
                    "id": d.get("id"),
                    "nombre": d.get("nombre"),
                    "ubicacion": d.get("ubicacion_nombre"),
                    "zona_horaria": d.get("zona_horaria_iana"),
                }
                for d in items
            ]
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en consultar_dispositivos: {e}")
        return []


def consultar_ubicaciones() -> list:
    """Consulta los puntos geográficos de monitoreo y reservas naturales."""
    url = f"{Config.API_ORIGINAL_URL}/ubicaciones"
    try:
        resp = requests.get(url, timeout=Config.API_TIMEOUT)
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
            return [
                {
                    "id": u.get("id"),
                    "nombre": u.get("nombre"),
                    "latitud": u.get("latitud"),
                    "longitud": u.get("longitud"),
                    "zona_horaria": u.get("zona_horaria_nombre"),
                }
                for u in items
            ]
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en consultar_ubicaciones: {e}")
        return []


def consultar_usuarios() -> list:
    """Consulta la lista de personas y brigadistas registrados para recibir alertas."""
    url = f"{Config.API_ORIGINAL_URL}/usuarios"
    try:
        resp = requests.get(url, timeout=Config.API_TIMEOUT)
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
            return [
                {
                    "id": usr.get("id"),
                    "nombre": usr.get("nombre"),
                    "email": usr.get("email"),
                    "rol": usr.get("rol_nombre"),
                    "activo": usr.get("activo"),
                }
                for usr in items
            ]
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en consultar_usuarios: {e}")
        return []


def consultar_eventos_dispositivo(dispositivo_id: int = None) -> list:
    """Consulta eventos de hardware como reinicios, conexiones y calibraciones del ESP32."""
    url = f"{Config.API_ORIGINAL_URL}/eventos-dispositivo"
    params = {"per_page": 10, "page": 1}
    if dispositivo_id is not None:
        params["dispositivo_id"] = dispositivo_id

    try:
        resp = requests.get(url, params=params, timeout=Config.API_TIMEOUT)
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("items", [])
            return [
                {
                    "id": ev.get("id"),
                    "dispositivo": ev.get("dispositivo_nombre"),
                    "tipo_evento": ev.get("tipo_evento_nombre"),
                    "detalle": ev.get("detalle"),
                    "fecha": ev.get("timestamp"),
                }
                for ev in items
            ]
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en consultar_eventos_dispositivo: {e}")
        return []


def desactivar_alertas(sensor_id: int = None, limite: int = None, minutos_atras: int = None, todas: bool = True) -> dict:
    """
    Desactiva (marca como resueltas) las alertas ambientales activas en el sistema.
    Permite desactivar:
    - Todas las alertas activas (por defecto).
    - Alertas de un sensor específico (sensor_id=1 para gas MQ-2, etc.).
    - Las últimas N alertas activas (ej. limite=5).
    - Alertas generadas en los últimos N minutos (ej. minutos_atras=60 para 'hace una hora').
    """
    url_get = f"{Config.API_ORIGINAL_URL}/alertas"
    params = {"estado": "activa", "per_page": 100, "page": 1}
    if sensor_id is not None:
        params["sensor_id"] = sensor_id

    try:
        resp = requests.get(url_get, params=params, timeout=Config.API_TIMEOUT)
        if resp.status_code != 200:
            return {"error": f"Error HTTP {resp.status_code} al consultar alertas activas."}

        data = resp.json().get("data", {})
        alertas_activas = data.get("items", [])

        if not alertas_activas:
            sensor_str = f" para el sensor {sensor_id}" if sensor_id else ""
            return {
                "alertas_desactivadas": 0,
                "mensaje": f"No hay alertas activas en el sistema{sensor_str}."
            }

        # Filtrar por tiempo si se especificó minutos_atras
        if minutos_atras is not None and minutos_atras > 0:
            from datetime import datetime, timezone
            ahora = datetime.now(timezone.utc)
            filtradas = []
            for a in alertas_activas:
                ts_str = a.get("timestamp")
                if ts_str:
                    try:
                        ts_dt = datetime.fromisoformat(ts_str)
                        if ts_dt.tzinfo is None:
                            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                        minutos_dif = (ahora - ts_dt.astimezone(timezone.utc)).total_seconds() / 60
                        if minutos_dif <= minutos_atras:
                            filtradas.append(a)
                    except Exception:
                        filtradas.append(a)
                else:
                    filtradas.append(a)
            alertas_activas = filtradas

        # Filtrar por límite si se especificó (ej. 'las 5 últimas')
        if limite is not None and limite > 0:
            alertas_activas = alertas_activas[:limite]

        if not alertas_activas:
            return {
                "alertas_desactivadas": 0,
                "mensaje": "No se encontraron alertas activas que cumplan con el criterio especificado."
            }

        desactivadas_ids = []
        fallidas_ids = []

        for a in alertas_activas:
            a_id = a.get("id")
            if not a_id:
                continue
            url_put = f"{Config.API_ORIGINAL_URL}/alertas/{a_id}"
            try:
                put_resp = requests.put(url_put, json={"estado": "resuelta"}, timeout=Config.API_TIMEOUT)
                if put_resp.status_code == 200:
                    desactivadas_ids.append(a_id)
                else:
                    fallidas_ids.append(a_id)
            except requests.exceptions.RequestException:
                fallidas_ids.append(a_id)

        total_desactivadas = len(desactivadas_ids)
        sensor_str = f" del sensor {sensor_id}" if sensor_id else ""
        return {
            "alertas_desactivadas": total_desactivadas,
            "ids_resueltos": desactivadas_ids,
            "sensor_id": sensor_id,
            "mensaje": f"Se desactivaron exitosamente {total_desactivadas} alerta(s){sensor_str}."
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error en desactivar_alertas: {e}")
        return {"error": "No se pudo conectar con el servidor para desactivar las alertas."}

