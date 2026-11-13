"""Conexiones del proyecto, configuradas por variables de entorno.

Uso:
    from src.conn import get_mongo_db, get_pg_engine, get_dataset_path

    db = get_mongo_db()                 # base indicada por MONGO_DB
    engine = get_pg_engine()            # base indicada por PG_DB
    csv = get_dataset_path()            # ruta indicada por DATASET_CSV

Requiere un archivo .env en la raíz del proyecto (ver .env.example).
Ninguna credencial está escrita en el código: si falta una variable, falla
con un mensaje explícito en lugar de usar un valor por defecto.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_CSV = "data/dataset_estudiantes_etl.csv"


def _requerido(nombre: str) -> str:
    valor = os.getenv(nombre)
    if not valor:
        raise RuntimeError(
            f"Falta la variable {nombre}. Copiá .env.example a .env y completá tus credenciales."
        )
    return valor


def get_dataset_path() -> Path:
    """Ruta del CSV a procesar (permite cambiar de escenario sin tocar el código)."""
    ruta = Path(os.getenv("DATASET_CSV", DEFAULT_CSV))
    return ruta if ruta.is_absolute() else BASE_DIR / ruta


def get_mongo_db(nombre: str | None = None):
    """Devuelve la base de MongoDB del escenario activo."""
    from pymongo import MongoClient

    cliente = MongoClient(_requerido("MONGO_URI"), serverSelectionTimeoutMS=15000)
    return cliente[nombre or os.getenv("MONGO_DB", "Estudiantes")]


def get_pg_engine(base: str | None = None) -> Engine:
    """Devuelve un engine de SQLAlchemy apuntando a la base del escenario activo."""
    url = make_url(_requerido("PG_URI"))
    return create_engine(url.set(database=base or os.getenv("PG_DB", "dw_universidad")))


if __name__ == "__main__":  # chequeo rápido de configuración
    print("Mongo ping:", get_mongo_db().client.admin.command("ping"))
    with get_pg_engine().connect() as conn:
        print("Postgres SELECT 1:", conn.exec_driver_sql("SELECT 1").scalar())
    print("Dataset:", get_dataset_path())
