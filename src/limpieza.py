"""Reglas de limpieza del pipeline Bronze -> Silver.

Estas reglas vivían dentro del notebook 01. Se extrajeron a un módulo para
tener una única fuente de verdad, poder testearlas sin Jupyter y poder
re-ejecutar el ETL desde un script.

Principio rector: NO INVENTAR DATOS. Un valor imposible se convierte en nulo;
la decisión de imputar se toma recién en la capa Gold, donde está acotada y
documentada.
"""
from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

# --- Límites de dominio -------------------------------------------------
EDAD_MIN, EDAD_MAX = 16, 100
NOTA_MIN, NOTA_MAX = 0, 10
NOTA_APROBACION = 6

# --- Formatos aceptados -------------------------------------------------
RE_CODIGO = re.compile(r"^([A-Z]{2,3})-?(\d{2})$")
FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%y")

MAP_NOTA = {
    "cero": 0, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}
MAP_EDAD = {"veinte": 20, "dieciocho": 18, "veintidos": 22, "veinticinco": 25}

COLUMNAS_TEXTO = ["carrera", "nombre_materia", "tipo_instancia", "periodo_inscripcion", "id_alumno"]
COLUMNAS_ENTERO = ["cohorte", "anio_cursada"]


def normalizar_textos(df: pd.DataFrame) -> pd.DataFrame:
    """Quita espacios sobrantes y colapsa espacios internos."""
    for col in COLUMNAS_TEXTO:
        if col in df.columns:
            df[col] = df[col].str.strip().str.replace(r"\s+", " ", regex=True)
    return df


def normalizar_codigo_materia(serie: pd.Series) -> pd.Series:
    """Unifica variantes del código de materia al formato canónico XXX-NN."""
    limpio = serie.str.strip().str.upper()
    return limpio.str.replace(r"^([A-Z]{2,3})-?(\d{2})$", r"\1-\2", regex=True)


def normalizar_edad(serie: pd.Series) -> pd.Series:
    """Palabra -> número. Fuera de [16, 100] -> nulo."""
    edad = serie.str.strip().str.lower().replace(MAP_EDAD)
    edad = pd.to_numeric(edad, errors="coerce")
    return edad.mask(~edad.between(EDAD_MIN, EDAD_MAX)).astype("Int64")


def normalizar_nota(serie: pd.Series) -> pd.Series:
    """Palabra -> número, 'Ausente' -> nulo, fuera de [0, 10] -> nulo."""
    nota = serie.str.strip().str.lower().replace(MAP_NOTA)
    nota = nota.where(nota != "ausente")  # ausente = sin nota
    nota = pd.to_numeric(nota, errors="coerce")
    nota = nota.mask(~nota.between(NOTA_MIN, NOTA_MAX))
    # Entera si el dato lo es (caso del dataset base); decimal si viniera con .5
    if nota.notna().any() and (nota.dropna() % 1 != 0).any():
        return nota.round(1)
    return nota.astype("Int64")


def normalizar_asistencias(asistencias: pd.Series, clases_totales: pd.Series) -> pd.Series:
    """Descarta asistencias negativas o mayores a clases_totales."""
    asist = pd.to_numeric(asistencias, errors="coerce")
    clases = pd.to_numeric(clases_totales, errors="coerce")
    asist = asist.mask(asist < 0).mask(asist > clases)
    return asist.astype("Int64")


def parsear_fecha(valor) -> datetime | pd.NaT:
    """Acepta ISO (AAAA-MM-DD), DD/MM/AAAA y DD-MM-AA (día-mes-año)."""
    v = str(valor).strip()
    for fmt in FORMATOS_FECHA:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return pd.NaT


def normalizar_fechas(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie.map(parsear_fecha))


def calcular_pct_asistencia(asistencias: pd.Series, clases_totales: pd.Series) -> pd.Series:
    return (asistencias / clases_totales * 100).round(1)


def diagnosticar_calidad(df: pd.DataFrame) -> pd.DataFrame:
    """Cuantifica los problemas de la capa Bronze, columna por columna.

    Se usa en el notebook 01 para justificar cada regla de limpieza.
    """
    cod = df["codigo_materia"].str.strip().str.upper()
    nota = df["nota"].str.strip().str.lower()
    num_nota = pd.to_numeric(nota.where(nota.str.fullmatch(r"-?\d+(\.\d+)?")), errors="coerce")
    edad = df["edad_alumno"].str.strip().str.lower()
    num_edad = pd.to_numeric(edad.where(edad.str.fullmatch(r"-?\d+(\.\d+)?")), errors="coerce")
    asist = pd.to_numeric(df["asistencias"].where(df["asistencias"].str.strip() != ""), errors="coerce")
    clases = pd.to_numeric(df["clases_totales"], errors="coerce")
    fecha = df["fecha_examen"].str.strip()

    filas = {
        "codigo_materia · variantes (deben ser 6)": df["codigo_materia"].nunique(),
        "codigo_materia · formato no normalizado": int((~cod.str.match(RE_CODIGO)).sum()),
        "nota · vacíos": int(nota.eq("").sum()),
        "nota · escritas con palabras (Diez/Ocho/Ausente)": int(
            ((nota != "") & nota.str.fullmatch(r"[a-záéíóú]+")).sum()
        ),
        "nota · fuera de rango 0-10": int((num_nota.notna() & ~num_nota.between(0, 10)).sum()),
        "edad · vacíos": int(edad.eq("").sum()),
        "edad · texto ('veinte')": int(edad.str.fullmatch(r"[a-záéíóú]+").sum()),
        "edad · outliers (fuera de 16-100)": int((num_edad.notna() & ~num_edad.between(16, 100)).sum()),
        "asistencias · vacías": int(asist.isna().sum()),
        "asistencias · negativas": int((asist < 0).sum()),
        "asistencias · mayores a clases_totales": int((asist > clases).sum()),
        "fecha · formato ISO (AAAA-MM-DD)": int(fecha.str.fullmatch(r"\d{4}-\d{2}-\d{2}").sum()),
        "fecha · formato DD/MM/AAAA": int(fecha.str.fullmatch(r"\d{2}/\d{2}/\d{4}").sum()),
        "fecha · formato DD-MM-AA": int(fecha.str.fullmatch(r"\d{2}-\d{2}-\d{2}").sum()),
    }
    return pd.DataFrame({"cantidad": filas})


def limpiar_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Aplica todas las reglas Bronze -> Silver y devuelve el reporte de calidad."""
    df_l = df.copy()
    df_l = normalizar_textos(df_l)

    df_l["codigo_materia"] = normalizar_codigo_materia(df_l["codigo_materia"])
    df_l["edad_alumno"] = normalizar_edad(df_l["edad_alumno"])
    df_l["nota"] = normalizar_nota(df_l["nota"])

    clases = pd.to_numeric(df_l["clases_totales"], errors="coerce")
    df_l["asistencias"] = normalizar_asistencias(df_l["asistencias"], clases)
    df_l["clases_totales"] = clases.astype("Int64")

    for col in COLUMNAS_ENTERO:
        if col in df_l.columns:
            df_l[col] = pd.to_numeric(df_l[col], errors="coerce").astype("Int64")

    df_l["fecha_examen"] = normalizar_fechas(df_l["fecha_examen"])
    df_l["pct_asistencia"] = calcular_pct_asistencia(df_l["asistencias"], df_l["clases_totales"])

    reporte = {
        "filas": len(df_l),
        "nulos": df_l.isna().sum().to_dict(),
        "materias_unicas": int(df_l["codigo_materia"].nunique()),
        "fechas_sin_parsear": int(df_l["fecha_examen"].isna().sum()),
        "notas_fuera_rango": int((~df_l["nota"].dropna().between(NOTA_MIN, NOTA_MAX)).sum()),
        "edades_fuera_rango": int((~df_l["edad_alumno"].dropna().between(EDAD_MIN, EDAD_MAX)).sum()),
        "asistencias_inconsistentes": int(
            (
                df_l["asistencias"].notna()
                & (
                    (df_l["asistencias"] < 0)
                    | (df_l["asistencias"] > df_l["clases_totales"])
                )
            ).sum()
        ),
        "rango_fechas": (
            f"{df_l['fecha_examen'].min():%Y-%m-%d} -> {df_l['fecha_examen'].max():%Y-%m-%d}"
            if df_l["fecha_examen"].notna().any()
            else "sin fechas válidas"
        ),
    }
    return df_l, reporte
