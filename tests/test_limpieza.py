"""Tests de las reglas de limpieza Bronze -> Silver."""
from __future__ import annotations

import pandas as pd
import pytest

from src.limpieza import (
    limpiar_dataframe,
    normalizar_asistencias,
    normalizar_codigo_materia,
    normalizar_edad,
    normalizar_nota,
    parsear_fecha,
)


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("alg01", "ALG-01"),
        (" ALG-01 ", "ALG-01"),
        ("Pl-01", "PL-01"),
        ("BD-03", "BD-03"),
        ("FIS 01", "FIS 01"),  # espacio no es una variante aceptada: no se inventa
    ],
)
def test_normalizar_codigo_materia(entrada, esperado):
    assert normalizar_codigo_materia(pd.Series([entrada])).iloc[0] == esperado


def test_codigo_normalizado_colapsa_variantes():
    variantes = pd.Series(["alg-01", "ALG01", "Alg-01", " ALG-01 "])
    assert normalizar_codigo_materia(variantes).nunique() == 1


def test_normalizar_edad_palabra_y_rangos():
    serie = pd.Series(["veinte", "20", "150", "15", "abc", ""])
    resultado = normalizar_edad(serie).tolist()
    assert resultado[0] == 20
    assert resultado[1] == 20
    assert resultado[2] is pd.NA  # fuera de 16-100
    assert resultado[3] is pd.NA  # fuera de 16-100
    assert resultado[4] is pd.NA
    assert resultado[5] is pd.NA


def test_normalizar_nota_palabras_ausente_y_rango():
    serie = pd.Series(["Diez", "ausente", "47", "8", "-2", ""])
    resultado = normalizar_nota(serie)
    assert resultado.iloc[0] == 10
    assert resultado.iloc[1] is pd.NA
    assert resultado.iloc[2] is pd.NA  # fuera de 0-10
    assert resultado.iloc[3] == 8
    assert resultado.iloc[4] is pd.NA
    assert resultado.iloc[5] is pd.NA
    assert str(resultado.dtype) == "Int64"


def test_normalizar_nota_con_decimales():
    resultado = normalizar_nota(pd.Series(["8.5", "6"]))
    assert resultado.iloc[0] == pytest.approx(8.5)
    assert resultado.iloc[1] == pytest.approx(6.0)


def test_normalizar_asistencias_descarta_negativas_y_excedidas():
    asistencias = pd.Series(["-3", "50", "15", ""])
    clases = pd.Series(["40", "40", "40", "40"])
    resultado = normalizar_asistencias(asistencias, clases).tolist()
    assert resultado == [pd.NA, pd.NA, 15, pd.NA]


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("2024-03-15", "2024-03-15"),
        ("15/03/2024", "2024-03-15"),
        ("16-06-24", "2024-06-16"),  # DD-MM-AA, no AA-MM-DD
        ("21/11/2025", "2025-11-21"),
    ],
)
def test_parsear_fecha_tres_formatos(entrada, esperado):
    assert parsear_fecha(entrada).strftime("%Y-%m-%d") == esperado


def test_parsear_fecha_invalida():
    assert pd.isna(parsear_fecha("2024-13-45"))


def test_limpiar_dataframe_elimina_infracciones(df_bronze):
    limpio, reporte = limpiar_dataframe(df_bronze)

    assert reporte["filas"] == len(df_bronze)
    assert reporte["fechas_sin_parsear"] == 0
    assert reporte["notas_fuera_rango"] == 0
    assert reporte["edades_fuera_rango"] == 0
    assert reporte["asistencias_inconsistentes"] == 0
    assert reporte["materias_unicas"] == 2
    assert reporte["rango_fechas"] == "2024-04-10 -> 2024-06-16"


def test_pct_asistencia_se_calcula(df_bronze):
    limpio, _ = limpiar_dataframe(df_bronze)
    primera = limpio.iloc[0]
    assert primera["pct_asistencia"] == pytest.approx(15 / 40 * 100)


def test_limpiar_dataframe_no_inventa_valores(df_bronze):
    limpio, _ = limpiar_dataframe(df_bronze)
    fila_ausente = limpio[limpio["nota"].isna()].iloc[0]
    assert pd.isna(fila_ausente["nota"])
