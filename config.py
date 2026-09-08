"""Configuración para el Asistente de Voz IA de Incendios Forestales."""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # Clave de Groq y modelo
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    GROQ_URL = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")

    # API original del sistema de prevención de incendios
    API_ORIGINAL_URL = os.getenv(
        "API_ORIGINAL_URL",
        "https://api-sistemaprevencionincendios.onrender.com/api"
    ).rstrip("/")
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "5"))

    # Configuración del servidor
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
