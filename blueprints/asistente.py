"""Blueprint para procesar las preguntas del asistente de voz."""

import logging
from flask import Blueprint, request, jsonify
from services.groq_agent import procesar_pregunta_voz

logger = logging.getLogger(__name__)
asistente_bp = Blueprint("asistente", __name__)


@asistente_bp.route("/preguntar", methods=["POST"])
def preguntar():
    """
    Endpoint invocado por el frontend de voz continua.
    Recibe: {"texto": "pregunta del usuario"}
    Responde: {"respuesta": "texto para leer en voz alta", "tools_usadas": [...]}
    """
    data = request.get_json(silent=True) or {}
    texto = data.get("texto", "").strip()

    if not texto:
        return jsonify({
            "error": "El campo 'texto' es requerido y no puede estar vacío."
        }), 400

    logger.info(f"Pregunta de voz recibida: '{texto}'")
    respuesta_texto, tools_usadas = procesar_pregunta_voz(texto)
    logger.info(f"Respuesta generada: '{respuesta_texto}' (Tools: {[t['tool'] for t in tools_usadas]})")

    return jsonify({
        "respuesta": respuesta_texto,
        "tools_usadas": tools_usadas
    }), 200
