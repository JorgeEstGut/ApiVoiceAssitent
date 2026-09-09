"""Agente de Groq con Function Calling integral para todos los endpoints del sistema."""

import json
import logging
import time
import requests
from config import Config
from services.api_client import (
    listar_sensores,
    obtener_ultimo_valor,
    obtener_promedio,
    obtener_promedio_por_fecha,
    consultar_total_lecturas,
    consultar_alertas,
    desactivar_alertas,
    consultar_umbrales,
    consultar_dispositivos,
    consultar_ubicaciones,
    consultar_usuarios,
    consultar_eventos_dispositivo,
)

logger = logging.getLogger(__name__)

# Mapeo de nombres a funciones ejecutables
MAPA_TOOLS = {
    "listar_sensores": listar_sensores,
    "obtener_ultimo_valor": obtener_ultimo_valor,
    "obtener_promedio": obtener_promedio,
    "obtener_promedio_por_fecha": obtener_promedio_por_fecha,
    "consultar_total_lecturas": consultar_total_lecturas,
    "consultar_alertas": consultar_alertas,
    "desactivar_alertas": desactivar_alertas,
    "consultar_umbrales": consultar_umbrales,
    "consultar_dispositivos": consultar_dispositivos,
    "consultar_ubicaciones": consultar_ubicaciones,
    "consultar_usuarios": consultar_usuarios,
    "consultar_eventos_dispositivo": consultar_eventos_dispositivo,
}

# Definición de herramientas para Groq (OpenAI Function Calling Schema)
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "consultar_alertas",
            "description": "Consulta las alertas de riesgo de incendio emitidas por el sistema. Úsala siempre que pregunten 'cuántas alertas tengo activas', 'hay alguna alerta', 'cuáles alertas se han disparado' o el estado de alertas de un sensor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "estado": {
                        "type": ["string", "null"],
                        "description": "Filtrar por estado: 'activa', 'resuelta' o null para ver todas."
                    },
                    "sensor_id": {
                        "type": ["integer", "null"],
                        "description": "ID numérico del sensor para filtrar sus alertas (opcional o null)."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desactivar_alertas",
            "description": "Desactiva (marca como resueltas) las alertas ambientales activas en el sistema. Úsala cuando el usuario ordene desactivar, apagar o resolver alertas (por ejemplo: 'desactiva todas las alertas', 'desactiva las alertas del sensor de gas', 'desactiva las 5 últimas alertas', 'apaga las alertas de hace una hora').",
            "parameters": {
                "type": "object",
                "properties": {
                    "todas": {
                        "type": ["boolean", "null"],
                        "description": "True para desactivar todas las alertas activas."
                    },
                    "sensor_id": {
                        "type": ["integer", "null"],
                        "description": "ID numérico del sensor si se pide desactivar alertas de un sensor específico (1=Gas MQ-2, 2=Calidad de aire MQ-135, 3=Temp/Humedad BME680)."
                    },
                    "limite": {
                        "type": ["integer", "null"],
                        "description": "Cantidad máxima de alertas a desactivar (ejemplo: 5 para 'desactiva las 5 últimas alertas')."
                    },
                    "minutos_atras": {
                        "type": ["integer", "null"],
                        "description": "Filtro de tiempo en minutos hacia atrás. Ejemplo: 60 para 'hace una hora', 30 para 'últimos 30 minutos', 120 para 'hace 2 horas'."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_total_lecturas",
            "description": "Devuelve la cantidad total de mediciones/lecturas registradas en la base de datos. Úsala para responder 'cuántas lecturas tengo en total' o 'cuántas lecturas tiene el sensor 1'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": ["integer", "null"],
                        "description": "ID numérico del sensor si se pregunta por uno en específico, o null para el total de todo el sistema."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_sensores",
            "description": "Lista los sensores disponibles con su ID, nombre, tipo y estado operativo. Úsala cuando pregunten qué sensores hay instalados o se mencione un sensor por nombre.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_ultimo_valor",
            "description": "Obtiene la medición actual más reciente de un sensor específico por su ID. El sensor 1 es MQ-2 (gas/humo), sensor 2 es MQ-135 (calidad de aire) y sensor 3 es BME680 (temperatura y humedad simultáneamente).",
            "parameters": {
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "integer",
                        "description": "ID numérico del sensor (1, 2 o 3)."
                    }
                },
                "required": ["sensor_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_promedio",
            "description": "Calcula el promedio aritmético de las últimas N lecturas registradas de un sensor (temperatura, humedad o ppm de gas).",
            "parameters": {
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "integer",
                        "description": "ID numérico del sensor (1=Gas MQ-2, 2=Aire MQ-135, 3=Temp/Humedad BME680)."
                    },
                    "cantidad_lecturas": {
                        "type": ["integer", "null"],
                        "description": "Cantidad de lecturas a promediar (por defecto 20 si no se especifica)."
                    }
                },
                "required": ["sensor_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_promedio_por_fecha",
            "description": "Calcula el promedio de mediciones de un sensor dentro de un rango de fechas en formato ISO 8601.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "integer",
                        "description": "ID numérico del sensor."
                    },
                    "desde": {
                        "type": "string",
                        "description": "Fecha y hora inicial en formato ISO 8601 (ejemplo: 2026-09-07T00:00:00)."
                    },
                    "hasta": {
                        "type": "string",
                        "description": "Fecha y hora final en formato ISO 8601 (ejemplo: 2026-09-08T23:59:59)."
                    }
                },
                "required": ["sensor_id", "desde", "hasta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_umbrales",
            "description": "Consulta los rangos de riesgo configurados en el sistema (Normal, Media, Alta, Crítica) para saber si una medición representa peligro o fuego.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_dispositivos",
            "description": "Consulta los microcontroladores y estaciones ESP32 instalados en campo y su ubicación física.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_ubicaciones",
            "description": "Consulta los puntos geográficos físicos, coordenadas y zonas de monitoreo de incendios.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_usuarios",
            "description": "Consulta los usuarios y brigadistas registrados en el sistema para recibir avisos de emergencia.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_eventos_dispositivo",
            "description": "Consulta los eventos técnicos de los dispositivos como reinicios, conexiones Wi-Fi y calibraciones.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dispositivo_id": {
                        "type": ["integer", "null"],
                        "description": "ID numérico del dispositivo para filtrar sus eventos (opcional o null)."
                    }
                },
                "required": []
            }
        }
    }
]

SYSTEM_PROMPT = """Eres el Asistente de Voz Inteligente del Sistema de Detección Temprana de Incendios Forestales.
Tienes acceso directo y completo a toda la base de datos y endpoints de la API:
- Para preguntas sobre alertas (activas, resueltas, cantidad de alertas o peligro): usa siempre 'consultar_alertas'.
- Para desactivar, apagar o resolver alertas (todas, de un sensor, las últimas N, o de un periodo de tiempo): usa siempre 'desactivar_alertas'.
- Para preguntas sobre cantidad de lecturas o conteos en el sistema o por sensor: usa siempre 'consultar_total_lecturas'.
- Para preguntas sobre qué sensores hay o su estado: usa 'listar_sensores'.
- Para mediciones actuales: usa 'obtener_ultimo_valor'.
- Para promedios: usa 'obtener_promedio' o 'obtener_promedio_por_fecha'.
- Para límites y riesgos: usa 'consultar_umbrales'.
- Para hardware, estaciones, ubicaciones o brigadistas: usa 'consultar_dispositivos', 'consultar_ubicaciones' o 'consultar_usuarios'.

NUNCA digas que no tienes acceso a esos datos sin antes invocar la herramienta correspondiente.

REGLAS ESTRICTAS DE VOZ:
1. Tu respuesta será leída en voz alta por el navegador mediante un sintetizador de voz (Text-to-Speech).
2. Responde en español de forma 100% natural, fluida y concisa (máximo 2 o 3 frases).
3. PROHIBIDO USAR FORMATO MARKDOWN:
   - NO uses asteriscos (**negrita**).
   - NO uses guiones (-) ni listas numeradas.
   - NO uses tablas ni viñetas.
4. Expresa números y unidades de forma que suenen bien al hablar (ejemplo: 'veinte grados centígrados', 'humedad del noventa por ciento', 'cincuenta partes por millón', 'treinta lecturas en total').
5. Basa siempre tus respuestas en los datos reales devueltos por las herramientas.
"""


def procesar_pregunta_voz(texto_pregunta: str) -> tuple[str, list]:
    """
    Ejecuta el loop de function calling de Groq con la pregunta hablada del usuario.
    Devuelve una tupla: (texto_para_leer_en_voz_alta, lista_de_tools_usadas).
    """
    if not Config.GROQ_API_KEY:
        return "Disculpa, la clave de inteligencia artificial no está configurada en el servidor.", []

    mensajes = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": texto_pregunta},
    ]

    tools_usadas = []
    headers = {
        "Authorization": f"Bearer {Config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    # Bucle de hasta 4 iteraciones para resolver llamadas a herramientas
    for _ in range(4):
        payload = {
            "model": Config.GROQ_MODEL,
            "messages": mensajes,
            "tools": TOOLS_SCHEMA,
            "tool_choice": "auto",
            "temperature": 0.2,
        }

        try:
            resp = requests.post(Config.GROQ_URL, headers=headers, json=payload, timeout=25)
            if resp.status_code == 429:
                logger.warning("Rate limit 429 alcanzado en Groq. Esperando 3.5 segundos para reintentar...")
                time.sleep(3.5)
                resp = requests.post(Config.GROQ_URL, headers=headers, json=payload, timeout=25)

            if resp.status_code >= 400:
                logger.error(f"Error de Groq API HTTP {resp.status_code}: {resp.text}")
                return "Disculpa, hubo un problema al consultar el modelo de inteligencia artificial.", tools_usadas

            datos = resp.json()
            eleccion = datos["choices"][0]
            mensaje_asistente = eleccion["message"]
            tool_calls = mensaje_asistente.get("tool_calls")

            # Si no hay llamadas a herramientas, ya es la respuesta final
            if not tool_calls:
                respuesta_final = (mensaje_asistente.get("content") or "").strip()
                # Limpieza de seguridad por si el modelo incluyó algún asterisco o formato markdown
                respuesta_final = respuesta_final.replace("**", "").replace("*", "").replace("#", "")
                return respuesta_final or "No obtuve una respuesta clara para tu consulta.", tools_usadas

            # Agregar mensaje del asistente con las llamadas de herramienta al historial
            mensajes.append(mensaje_asistente)

            # Ejecutar cada herramienta solicitada
            for call in tool_calls:
                func_info = call["function"]
                nombre_func = func_info["name"]
                args_raw = func_info.get("arguments", "{}")
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
                except json.JSONDecodeError:
                    args = {}

                # Filtrar valores None/null en los argumentos
                args = {k: v for k, v in args.items() if v is not None}

                tools_usadas.append({"tool": nombre_func, "args": args})
                logger.info(f"Invocando tool '{nombre_func}' con argumentos {args}")

                funcion = MAPA_TOOLS.get(nombre_func)
                if funcion:
                    try:
                        resultado = funcion(**args)
                    except Exception as ex:
                        logger.error(f"Excepción en {nombre_func}: {ex}")
                        resultado = {"error": str(ex)}
                else:
                    resultado = {"error": f"La herramienta {nombre_func} no está registrada"}

                mensajes.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(resultado, ensure_ascii=False),
                })

        except requests.exceptions.Timeout:
            logger.error("Timeout consultando a Groq API.")
            return "Lo siento, la respuesta tardó más de lo esperado. Intenta preguntar de nuevo.", tools_usadas
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión con Groq: {e}")
            return "No pude conectar con el servicio de inteligencia artificial en este momento.", tools_usadas

    return "No se pudo completar la consulta en el tiempo establecido.", tools_usadas
