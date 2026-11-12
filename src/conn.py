"""Conexión a MongoDB Atlas usando variables de entorno.

Uso:
    from src.conn import db, datos_estudiantes

Requiere un archivo .env en la raíz del proyecto con:
    MONGO_URI=mongodb+srv://usuario:password@cluster.mongodb.net/...
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError(
        "Falta la variable MONGO_URI. Copiá .env.example a .env y completá tus credenciales."
    )

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=15000)
db = client["Estudiantes"]
datos_estudiantes = db["turista"]
