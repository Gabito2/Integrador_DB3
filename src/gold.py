"""Transformaciones de la capa Gold (Silver -> esquema estrella).

Vivían dentro del notebook 02. Se extrajeron para poder testearlas y para
tener una sola definición del grano, de las claves y de las reglas de
negocio.

Correcciones respecto de la versión anterior del notebook:
  1. La carrera del hecho se deriva del ALUMNO (carrera canónica), no de la
     fila. Antes, 1.362 de 5.000 hechos quedaban con una carrera distinta a
     la de su propio alumno en dim_estudiante.
  2. La asistencia solo se imputa donde falta. Antes se recalculaba
     `asistencias` para todas las filas y se sobreescribía el dato original.
  3. Si el dataset trae docente, se carga en dim_docente; si no, se usa el
     registro placeholder DOC-000.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .limpieza import NOTA_APROBACION

DOCENTE_PLACEHOLDER = {"legajo_docente": "DOC-000", "nombre_docente": "Cátedra General"}


def carrera_canonica(df: pd.DataFrame) -> pd.Series:
    """Una carrera por alumno: la más frecuente en sus registros.

    El dataset de origen puede traer la carrera repetida de forma
    inconsistente entre filas del mismo alumno. El alumno cursa una sola
    carrera, así que se consolida por moda y los empates se resuelven
    alfabéticamente para que el resultado sea determinístico.
    """
    def _moda(serie: pd.Series) -> str:
        conteo = serie.value_counts()
        maximos = conteo[conteo == conteo.max()].index
        return sorted(maximos)[0]

    return df.groupby("id_alumno")["carrera"].apply(_moda)


def consolidar_edad(df: pd.DataFrame) -> pd.Series:
    """Mediana válida de cada alumno; mediana general si no tiene ninguna."""
    mediana_general = df["edad_alumno"].dropna().median()
    mediana_general = int(mediana_general) if pd.notna(mediana_general) else None
    return df.groupby("id_alumno")["edad_alumno"].transform(
        lambda s: int(s.dropna().median()) if not s.dropna().empty else mediana_general
    )


def imputar_asistencia(df: pd.DataFrame) -> pd.DataFrame:
    """Imputa pct_asistencia solo donde falta y conserva el dato original."""
    df = df.copy()
    faltante = df["pct_asistencia"].isna()

    pct_alumno = df.groupby("id_alumno")["pct_asistencia"].transform("median")
    pct_materia = df.groupby("codigo_materia")["pct_asistencia"].transform("median")
    df["pct_asistencia"] = (
        df["pct_asistencia"].fillna(pct_alumno).fillna(pct_materia).round(2)
    )

    # Solo se recalcula la asistencia donde el dato no existía.
    df["asistencias"] = df["asistencias"].where(
        ~faltante,
        np.round(df["pct_asistencia"] / 100.0 * df["clases_totales"]).astype("Int64"),
    )
    return df


def clasificar_aprobacion(df: pd.DataFrame) -> pd.DataFrame:
    """Aprobado si nota >= 6; Desaprobado si nota < 6; Ausente si no hay nota."""
    df = df.copy()
    nota = pd.to_numeric(df["nota"], errors="coerce")
    aprueba = (nota >= NOTA_APROBACION).fillna(False).astype(bool)
    df["estado_aprobacion"] = np.select(
        [nota.isna(), aprueba],
        ["Ausente", "Aprobado"],
        default="Desaprobado",
    )
    df["es_aprobado"] = df["estado_aprobacion"] == "Aprobado"
    return df


def preparar_hechos(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica las reglas de negocio antes de cargar el DW."""
    df = df.copy()
    df["edad_consolidada"] = consolidar_edad(df)
    df = imputar_asistencia(df)
    df = clasificar_aprobacion(df)

    canonica = carrera_canonica(df)
    df["carrera_canonica"] = df["id_alumno"].map(canonica)
    return df


def construir_dimensiones(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Devuelve las dimensiones con sus claves naturales (los sk los asigna la DB)."""
    canonica = carrera_canonica(df)

    dim_carrera = (
        pd.DataFrame({"nombre_carrera": sorted(canonica.unique())})
        .sort_values("nombre_carrera")
        .reset_index(drop=True)
    )

    dim_estudiante = (
        df.groupby("id_alumno", as_index=False)
        .agg(
            edad_actual=("edad_consolidada", "first"),
            cohorte_ingreso=("cohorte", "min"),
        )
        .assign(carrera=lambda d: d["id_alumno"].map(canonica))
        .rename(columns={"carrera": "nombre_carrera"})
        .sort_values("id_alumno")
        .reset_index(drop=True)
    )

    dim_materia = (
        df.groupby("codigo_materia", as_index=False)
        .agg(
            nombre_materia=("nombre_materia", "first"),
            anio_cursada=("anio_cursada", "first"),
        )
        .sort_values("codigo_materia")
        .reset_index(drop=True)
    )

    periodos = df["periodo_inscripcion"].drop_duplicates().sort_values()
    partes = periodos.str.split("-", expand=True)
    dim_periodo = pd.DataFrame(
        {
            "periodo_inscripcion": periodos.to_numpy(),
            "anio_lectivo": partes[0].astype(int).to_numpy(),
            "cuatrimestre": partes[1].astype(int).to_numpy(),
        }
    )

    dim_instancia = pd.DataFrame(
        {"tipo_instancia": sorted(df["tipo_instancia"].dropna().unique())}
    )

    if {"legajo_docente", "nombre_docente"}.issubset(df.columns):
        dim_docente = (
            df[["legajo_docente", "nombre_docente"]]
            .dropna()
            .drop_duplicates()
            .sort_values("legajo_docente")
            .reset_index(drop=True)
        )
    else:
        dim_docente = pd.DataFrame([DOCENTE_PLACEHOLDER])

    return {
        "dim_carrera": dim_carrera,
        "dim_estudiante": dim_estudiante,
        "dim_materia": dim_materia,
        "dim_periodo": dim_periodo,
        "dim_instancia": dim_instancia,
        "dim_docente": dim_docente,
    }


def construir_hechos(df: pd.DataFrame, mapas: dict[str, dict]) -> pd.DataFrame:
    """Arma la tabla de hechos resolviendo cada sk contra las dimensiones.

    `mapas` debe traer: carrera, estudiante, materia, periodo, instancia y
    docente, cada uno como dict clave_natural -> sk.
    """
    def traducir(columna: str, mapa: dict[str, int]) -> pd.Series:
        faltantes = set(df[columna].dropna().unique()) - set(mapa)
        if faltantes:
            raise ValueError(f"Claves sin dimensión en '{columna}': {sorted(faltantes)[:5]}")
        return df[columna].map(mapa)

    docente_col = "legajo_docente" if "legajo_docente" in df.columns else None

    hechos = pd.DataFrame(
        {
            "sk_estudiante": traducir("id_alumno", mapas["estudiante"]),
            "sk_materia": traducir("codigo_materia", mapas["materia"]),
            "sk_carrera": traducir("carrera_canonica", mapas["carrera"]),
            "sk_periodo": traducir("periodo_inscripcion", mapas["periodo"]),
            "sk_instancia": traducir("tipo_instancia", mapas["instancia"]),
            "sk_docente": (
                traducir("legajo_docente", mapas["docente"])
                if docente_col
                else mapas["docente"][DOCENTE_PLACEHOLDER["legajo_docente"]]
            ),
            "fecha_examen": pd.to_datetime(df["fecha_examen"]).dt.date,
            "nota": df["nota"].astype(float),
            "asistencias": df["asistencias"].astype("object").where(df["asistencias"].notna(), None),
            "clases_totales": df["clases_totales"].astype("int64"),
            "pct_asistencia": df["pct_asistencia"].astype(float),
            "estado_aprobacion": df["estado_aprobacion"],
            "es_aprobado": df["es_aprobado"],
        }
    )
    if hechos["sk_estudiante"].isna().any():
        raise ValueError("Hay hechos sin sk_estudiante: revisá la carga de dimensiones.")
    for col in ["sk_estudiante", "sk_materia", "sk_carrera", "sk_periodo", "sk_instancia", "sk_docente"]:
        hechos[col] = hechos[col].astype("int64")
    return hechos
