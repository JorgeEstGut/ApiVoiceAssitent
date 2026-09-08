"""Agente de Groq con Function Calling diseñado para respuestas de voz."""

import json
import logging
import requests
from config import Config
from services.api_client import (
    listar_sensores,
    obtener_ultimo_valor,
    obtener_promedio,
    obtener_promedio_por_fecha,
    consultar_umbrales,
)

logger = logging.getLogger(__name__)

# Mapeo de nombres a funciones ejecutables
MAPA_TOOLS = {
    "listar_sensores": listar_sensores,
    "obtener_ultimo_valor": obtener_ultimo_valor,
    "obtener_promedio": obtener_promedio,
    "obtener_promedio_por_fecha": obtener_promedio_por_fecha,
    "consultar_umbrales": consultar_umbrales,
}

# Definición de herramientas para Groq (OpenAI Function Calling Schema)
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "listar_sensores",
            "description": "Lista todos los sensores disponibles en el sistema de incendios con su ID, nombre, tipo y estado. Úsala cuando pregunten qué sensores hay o se mencione un sensor por nombre para identificar su ID.",
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
            "description": "Obtiene la medición actual o más reciente de un sensor específico por su ID numérico. El sensor 1 es MQ-2 (gas/humo), el sensor 2 es MQ-135 (calidad de aire) y el sensor 3 es BME680 (temperatura y humedad simultáneamente).",
            "parameters": {
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "integer",
                        "description": "ID numérico del sensor (1, 2 o 3)"
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
            "description": "Calcula el promedio aritmético de las últimas N lecturas registradas de un sensor. Úsala para responder preguntas como 'cuál es el promedio de humedad de las últimas 20 lecturas'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sensor_id": {
                        "type": "integer",
                        "description": "ID numérico del sensor (1=Gas MQ-2, 2=Aire MQ-135, 3=Temp/Humedad BME680)"
                    },
                    "cantidad_lecturas": {
                        "type": ["integer", "null"],
                        "description": "Cantidad de lecturas a promediar (por defecto 20 si no se especifica)"
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
                        "description": "ID numérico del sensor"
                    },
                    "desde": {
                        "type": "string",
                        "description": "Fecha y hora inicial en formato ISO 8601 (ejemplo: 2026-09-07T00:00:00)"
                    },
                    "hasta": {
                        "type": "string",
                        "description": "Fecha y hora final en formato ISO 8601 (ejemplo: 2026-09-08T23:59:59)"
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
            "description": "Consulta los rangos de riesgo configurados en el sistema (Normal, Media, Alta, Crítica) para saber si un valor representa peligro.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

SYSTEM_PROMPT = """Eres el Asistente de Voz Inteligente del Sistema de Detección Temprana de Incendios Forestales.
Tu función es responder preguntas habladas sobre sensores, mediciones en tiempo real, promedios y alertas.

REGLAS ESTRICTAS DE RESPUESTA EN VOZ:
1. Tu respuesta será leída por un sintetizador de voz (Text-to-Speech) en el navegador del usuario.
2. Responde en español de manera 100% natural, fluida y concisa (máximo 2 o 3 frases breves).
3. PROHIBIDO USAR FORMATO MARKDOWN:
   - NO uses asteriscos (**negrita**).
   - NO uses listas con guiones (-) ni números ordenados.
   - NO uses tablas ni viñetas.
4. Expresa los números y unidades de forma que suenen bien al hablar (ejemplo: 'veinte grados centígrados', 'humedad del setenta y cinco por ciento', 'cincuenta partes por millón').
5. Basa siempre tus respuestas en los datos reales devueltos por las herramientas, nunca inventes mediciones.
6. Ten en cuenta que el sensor 3 (BME680) mide temperatura y humedad al mismo tiempo; cuando te pregunten por él, menciona ambos valores si corresponde.
7. Si una herramienta no arroja datos o hay un problema de conexión, dilo amablemente en una sola frase sencilla.
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
            if resp.status_code >= 400:
                logger.error(f"Error de Groq API HTTP {resp.status_code}: {resp.text}")
                return "Disculpa, hubo un problema al consultar el modelo de inteligencia artificial.", tools_usadas

            datos = resp.json()
            eleccion = datos["choices"][0]
            mensaje_asistente = eleccion["message"]
            tool_calls = mensaje_asistente.get("tool_calls")

            # Si no hay llamadas a herramientas, es la respuesta final
            if not tool_calls:
                respuesta_final = (mensaje_asistente.get("content") or "").strip()
                # Limpieza de seguridad por si el modelo incluyó algún asterisco
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
