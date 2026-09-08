"""Aplicación principal Flask para el Asistente de Voz IA."""

import logging
from pathlib import Path
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

from config import Config
from blueprints.asistente import asistente_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AsistenteVozIA")


def create_app() -> Flask:
    """Factory de la aplicación Flask."""
    app = Flask(__name__, static_folder="static")
    app.config.from_object(Config)

    # Habilitar CORS para permitir llamadas desde navegadores o dominios remotos
    CORS(app)

    # Registrar el blueprint del asistente (soporta /preguntar y /api/preguntar)
    app.register_blueprint(asistente_bp, url_prefix="")
    app.register_blueprint(asistente_bp, url_prefix="/api", name="asistente_api")

    @app.route("/")
    def index():
        """Sirve el frontend de conversación continua por voz."""
        return send_from_directory("static", "index.html")

    @app.route("/favicon.ico")
    def favicon():
        """Sirve el favicon también desde la raíz."""
        return send_from_directory("static", "favicon.ico", mimetype="image/x-icon")

    @app.route("/manifest.webmanifest")
    def manifest():
        """Sirve el manifiesto PWA con el mimetype correcto (Windows no lo registra)."""
        return send_from_directory(
            "static", "manifest.webmanifest", mimetype="application/manifest+json"
        )

    @app.route("/health")
    def health():
        """Health check para Render."""
        return jsonify({
            "status": "healthy",
            "service": "AsistenteVozIA",
            "groq_configurado": bool(Config.GROQ_API_KEY),
            "api_original": Config.API_ORIGINAL_URL
        }), 200

    return app


app = create_app()

if __name__ == "__main__":
    logger.info(f"Iniciando Asistente de Voz IA en http://0.0.0.0:{Config.PORT}")
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
