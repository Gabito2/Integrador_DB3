"""Tests de las transformaciones Gold y del grano del esquema estrella."""
from __future__ import annotations

import pandas as pd
import pytest

from src.gold import (
    carrera_canonica,
    clasificar_aprobacion,
    construir_dimensiones,
    construir_hechos,
    imputar_asistencia,
    preparar_hechos,
)
from src.limpieza import limpiar_dataframe


@pytest.fixture
def df_silver(df_bronze):
    limpio, _ = limpiar_dataframe(df_bronze)
    return limpio


def test_carrera_canonica_una_por_alumno(df_silver):
    canonica = carrera_canonica(df_silver)
    assert canonica["A0001"] == "Ingeniería en Sistemas"  # 2 registros vs 1


def test_hechos_usan_la_carrera_del_alumno(df_silver):
    preparado = preparar_hechos(df_silver)
    por_alumno = preparado.groupby("id_alumno")["carrera_canonica"].nunique()
    assert (por_alumno == 1).all(), "un alumno no puede tener dos carreras en el hecho"

    canonica = carrera_canonica(df_silver)
    for id_alumno, fila in preparado.iterrows():
        assert fila["carrera_canonica"] == canonica[fila["id_alumno"]]


def test_imputar_asistencia_no_sobreescribe_el_dato_original(df_silver):
    preparado = imputar_asistencia(df_silver)
    original = df_silver.set_index(df_silver.index)["asistencias"]

    conocidos = original.notna()
    pd.testing.assert_series_equal(
        preparado.loc[conocidos, "asistencias"],
        original[conocidos].astype("Int64"),
        check_names=False,
    )


def test_imputar_asistencia_completa_los_faltantes(df_silver):
    preparado = imputar_asistencia(df_silver)
    # A0001 tiene una fila sin asistencia y otras dos con dato -> se imputa
    a0001 = preparado[preparado["id_alumno"] == "A0001"]
    assert a0001["pct_asistencia"].notna().all()
    assert a0001["asistencias"].notna().all()


def test_imputar_asistencia_no_inventa_sin_referencia(df_silver):
    preparado = imputar_asistencia(df_silver)
    # A0002 no tiene ninguna asistencia válida (negativa y mayor a clases):
    # no hay mediana de alumno ni de materia, así que queda nulo en vez de
    # inventar un valor.
    a0002 = preparado[preparado["id_alumno"] == "A0002"]
    assert a0002["pct_asistencia"].isna().all()


def test_imputar_asistencia_usa_la_mediana_del_alumno(df_silver):
    preparado = imputar_asistencia(df_silver)
    fila = preparado[(preparado["id_alumno"] == "A0001") & (preparado["nota"].isna())]
    assert fila["pct_asistencia"].iloc[0] == pytest.approx(43.75)  # (37.5 + 50.0) / 2


@pytest.mark.parametrize(
    "nota,esperado",
    [(10, "Aprobado"), (6, "Aprobado"), (5, "Desaprobado"), (0, "Desaprobado")],
)
def test_clasificar_aprobacion(nota, esperado):
    df = pd.DataFrame({"nota": [nota]})
    assert clasificar_aprobacion(df)["estado_aprobacion"].iloc[0] == esperado


def test_clasificar_aprobacion_ausente():
    df = pd.DataFrame({"nota": [pd.NA]})
    resultado = clasificar_aprobacion(df)
    assert resultado["estado_aprobacion"].iloc[0] == "Ausente"
    assert resultado["es_aprobado"].iloc[0] == False  # noqa: E712


def test_construir_dimensiones_un_registro_por_alumno(df_silver):
    preparado = preparar_hechos(df_silver)
    dims = construir_dimensiones(preparado)
    assert len(dims["dim_estudiante"]) == preparado["id_alumno"].nunique()
    assert dims["dim_estudiante"]["id_alumno"].is_unique
    assert len(dims["dim_carrera"]) == preparado["carrera_canonica"].nunique()
    assert len(dims["dim_materia"]) == 2


def test_construir_hechos_no_mezcla_carreras(df_silver, mapas_identidad):
    preparado = preparar_hechos(df_silver)
    dims = construir_dimensiones(preparado)
    hechos = construir_hechos(preparado, mapas_identidad)

    assert len(hechos) == len(preparado)
    assert hechos["sk_estudiante"].notna().all()
    assert hechos["sk_carrera"].notna().all()

    # El sk de carrera de cada hecho debe ser el de la carrera del alumno
    esperado = (
        dims["dim_estudiante"].set_index("id_alumno")["nombre_carrera"].map(mapas_identidad["carrera"])
    )
    obtenido = hechos.assign(id_alumno=preparado["id_alumno"].to_numpy()).set_index("id_alumno")["sk_carrera"]
    assert (obtenido == esperado.loc[obtenido.index]).all()


def test_construir_hechos_falla_si_falta_una_dimension(df_silver):
    preparado = preparar_hechos(df_silver)
    mapas = {
        "carrera": {"Ingeniería en Sistemas": 1, "Licenciatura en Análisis de Datos": 2},
        "estudiante": {"A0001": 1, "A0002": 2},
        "materia": {"ALG-01": 1},  # falta PL-01
        "periodo": {"2024-1": 1, "2024-2": 2},
        "instancia": {"Parcial 1": 1, "Parcial 2": 2, "Final": 3, "TP Práctico": 4},
        "docente": {"DOC-000": 1},
    }
    with pytest.raises(ValueError, match="PL-01"):
        construir_hechos(preparado, mapas)
