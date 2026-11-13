"""Fixtures compartidas por los tests del pipeline."""
from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def df_bronze() -> pd.DataFrame:
    """Miniatura de la capa Bronze: todo texto, con los defectos típicos."""
    filas = [
        # id, edad, carrera, cohorte, codigo, materia, anio, periodo, instancia, fecha, nota, asist, clases
        ("A0001", "20", "Ingeniería en Sistemas", "2020", "alg-01", "Algoritmos", "1",
         "2024-1", "Parcial 1", "2024-04-10", "8", "15", "40"),
        ("A0001", "21", "Ingeniería en Sistemas", "2020", "ALG-01", "Algoritmos", "1",
         "2024-1", "Parcial 2", "2024-05-10", "Diez", "20", "40"),
        ("A0001", "22", "Licenciatura en Análisis de Datos", "2020", "ALG-01", "Algoritmos", "1",
         "2024-2", "Final", "16/06/2024", "ausente", "", "40"),
        ("A0002", "veinte", "Ingeniería en Sistemas", "2021", "pl-01", "Programación Lógica", "1",
         "2024-1", "TP Práctico", "16-06-24", "47", "-3", "40"),
        ("A0002", "25", "Ingeniería en Sistemas", "2021", "PL01", "Programación Lógica", "1",
         "2024-1", "TP Práctico", "2024-06-16", "6", "50", "40"),
    ]
    columnas = [
        "id_alumno", "edad_alumno", "carrera", "cohorte", "codigo_materia",
        "nombre_materia", "anio_cursada", "periodo_inscripcion", "tipo_instancia",
        "fecha_examen", "nota", "asistencias", "clases_totales",
    ]
    return pd.DataFrame(filas, columns=columnas)


@pytest.fixture
def mapas_identidad() -> dict[str, dict]:
    """Mapas de claves naturales a sk, simulando lo que devuelve la base."""
    return {
        "carrera": {"Ingeniería en Sistemas": 1, "Licenciatura en Análisis de Datos": 2},
        "estudiante": {"A0001": 1, "A0002": 2},
        "materia": {"ALG-01": 1, "PL-01": 2},
        "periodo": {"2024-1": 1, "2024-2": 2},
        "instancia": {"Parcial 1": 1, "Parcial 2": 2, "Final": 3, "TP Práctico": 4},
        "docente": {"DOC-000": 1},
    }
