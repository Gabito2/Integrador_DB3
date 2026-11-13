"""Tests del generador del dataset ampliado (v2)."""
from __future__ import annotations

import pandas as pd
import pytest

from src.generar_dataset import MATERIAS, generar
from src.limpieza import limpiar_dataframe


@pytest.fixture(scope="module")
def dataset_v2():
    return generar(alumnos=80, seed=11)


def test_columnas_esperadas(dataset_v2):
    esperadas = {
        "id_alumno", "edad_alumno", "carrera", "cohorte", "codigo_materia",
        "nombre_materia", "anio_cursada", "periodo_inscripcion", "tipo_instancia",
        "fecha_examen", "nota", "asistencias", "clases_totales",
        "legajo_docente", "nombre_docente",
    }
    assert esperadas == set(dataset_v2.columns)


def test_es_reproducible():
    a = generar(alumnos=40, seed=3)
    b = generar(alumnos=40, seed=3)
    pd.testing.assert_frame_equal(a, b)


def test_una_carrera_por_alumno(dataset_v2):
    carreras = dataset_v2.assign(carrera=dataset_v2["carrera"].str.strip()) \
        .groupby("id_alumno")["carrera"].nunique()
    assert (carreras == 1).all(), "en el dataset v2 la carrera es atributo del alumno"


def test_trae_docentes_reales(dataset_v2):
    limpio, _ = limpiar_dataframe(dataset_v2)
    assert limpio["legajo_docente"].nunique() >= 3
    assert "Cátedra General" not in set(limpio["nombre_docente"])


def test_incluye_defectos_de_calidad(dataset_v2):
    assert dataset_v2["nota"].str.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóú]+").any()
    assert dataset_v2["fecha_examen"].str.contains("/").any()
    assert dataset_v2["fecha_examen"].str.fullmatch(r"\d{2}-\d{2}-\d{2}").any()


def test_el_etl_deja_el_dataset_limpio(dataset_v2):
    limpio, reporte = limpiar_dataframe(dataset_v2)
    assert reporte["fechas_sin_parsear"] == 0
    assert reporte["notas_fuera_rango"] == 0
    assert reporte["edades_fuera_rango"] == 0
    assert reporte["asistencias_inconsistentes"] == 0
    assert reporte["materias_unicas"] == len(MATERIAS)


def test_la_asistencia_explica_la_nota(dataset_v2):
    """La razón de ser del v2: acá sí hay señal entre asistencia y nota."""
    limpio, _ = limpiar_dataframe(dataset_v2)
    correlacion = limpio[["nota", "pct_asistencia"]].corr().iloc[0, 1]
    assert correlacion > 0.30, f"correlación insuficiente: {correlacion:.3f}"


def test_hay_abandono_observable(dataset_v2):
    limpio, _ = limpiar_dataframe(dataset_v2)
    ultimo = limpio.groupby("id_alumno")["periodo_inscripcion"].max()
    assert (ultimo < ultimo.max()).mean() > 0.10, "el dataset v2 debe tener abandonos"
