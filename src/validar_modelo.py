"""Validación reproducible del modelo de abandono sobre la capa Gold.

Entrena el modelo con información ANTERIOR al período de corte y evalúa si
predice un hecho OBSERVADO posterior: que el alumno deje de registrarse.

Uso:
    python -m src.validar_modelo                       # base indicada por PG_DB
    python -m src.validar_modelo --corte 2025-1 --json
    PG_DB=dw_universidad_v2 python -m src.validar_modelo

El script no escribe en la base: solo lee.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sqlalchemy import text

from src.conn import get_pg_engine

SEMILLA = 42
FEATURES = [
    "asistencia_promedio",
    "promedio_general",
    "tasa_reprobacion",
    "cantidad_ausentes",
    "materias_aprobadas",
    "evaluaciones",
]
ETIQUETAS = {
    "asistencia_promedio": "Asistencia promedio",
    "promedio_general": "Promedio general",
    "tasa_reprobacion": "Tasa de reprobación",
    "cantidad_ausentes": "Exámenes ausentes",
    "materias_aprobadas": "Materias aprobadas",
    "evaluaciones": "Evaluaciones rendidas",
}


def clave_periodo(periodo: str) -> int:
    """2019-2 -> 20192. Ordena cronológicamente sin ambigüedad."""
    anio, cuatrimestre = periodo.split("-")
    return int(anio) * 10 + int(cuatrimestre)


def construir_dataset(engine, corte: str | None = None) -> tuple[pd.DataFrame, pd.Series, str, int]:
    """Devuelve (features, target, corte usado, total de materias)."""
    periodos = pd.read_sql(
        text("SELECT DISTINCT periodo_inscripcion FROM dw_academico.dim_periodo"), engine
    )["periodo_inscripcion"].sort_values().tolist()
    corte = corte or periodos[-3]
    if corte not in periodos:
        raise SystemExit(f"El corte {corte} no existe en el DW. Períodos: {periodos}")

    historial = pd.read_sql(
        text(
            """
            SELECT e.id_alumno, e.cohorte_ingreso, p.periodo_inscripcion,
                   f.sk_materia, f.nota, f.es_aprobado, f.pct_asistencia,
                   f.estado_aprobacion
            FROM dw_academico.fact_rendimiento_academico f
            JOIN dw_academico.dim_estudiante e USING (sk_estudiante)
            JOIN dw_academico.dim_periodo p USING (sk_periodo)
            """
        ),
        engine,
    )
    historial["clave"] = historial["periodo_inscripcion"].map(clave_periodo)
    corte_clave = clave_periodo(corte)

    base = historial[historial["clave"] <= corte_clave]
    activos_despues = set(historial.loc[historial["clave"] > corte_clave, "id_alumno"])
    total_materias = int(historial["sk_materia"].nunique())

    features = base.groupby("id_alumno").agg(
        evaluaciones=("nota", "size"),
        asistencia_promedio=("pct_asistencia", "mean"),
        promedio_general=("nota", "mean"),
        tasa_reprobacion=("es_aprobado", lambda s: 100.0 * (1 - s.mean())),
        cantidad_ausentes=("estado_aprobacion", lambda s: int((s == "Ausente").sum())),
        cohorte_ingreso=("cohorte_ingreso", "first"),
    )
    features["materias_aprobadas"] = (
        base[base["es_aprobado"]]
        .groupby("id_alumno")["sk_materia"]
        .nunique()
        .reindex(features.index)
        .fillna(0)
    )

    # Historia mínima para que las features tengan sentido, y cohorte con al
    # menos dos años de antigüedad en el corte.
    filtro = (features["evaluaciones"] >= 4) & (
        features["cohorte_ingreso"] <= int(corte[:4]) - 2
    )
    # Un egresado deja de cursar por título, no por abandono: fuera del target.
    filtro &= features["materias_aprobadas"] < total_materias
    features = features[filtro]

    target = pd.Series(
        (~features.index.isin(activos_despues)).astype(int),
        index=features.index,
        name="abandono",
    )
    return features[FEATURES], target, corte, total_materias


def evaluar(engine, corte: str | None = None, json_out: bool = False) -> dict:
    X, y, corte_usado, total_materias = construir_dataset(engine, corte)

    if y.nunique() < 2:
        raise SystemExit(
            f"Con corte {corte_usado} no hay abandono observable: el dataset no permite validar."
        )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=SEMILLA, stratify=y
    )
    modelo = RandomForestClassifier(
        n_estimators=300,
        max_depth=4,
        random_state=SEMILLA,
        class_weight="balanced",
    )
    modelo.fit(X_train, y_train)

    y_pred = modelo.predict(X_test)
    y_proba = modelo.predict_proba(X_test)[:, 1]

    resultado = {
        "base": engine.url.database,
        "corte": corte_usado,
        "materias": total_materias,
        "alumnos_evaluados": int(len(y)),
        "abandonaron": int(y.sum()),
        "tasa_abandono": round(float(y.mean()) * 100, 1),
        "casos_prueba": int(len(y_test)),
        "accuracy": round(float(accuracy_score(y_test, y_pred)) * 100, 1),
        "auc": round(float(roc_auc_score(y_test, y_proba)), 3),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)) * 100, 1),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)) * 100, 1),
        "matriz_confusion": confusion_matrix(y_test, y_pred).tolist(),
        "importancias": {
            ETIQUETAS[f]: round(float(w) * 100, 1)
            for f, w in zip(FEATURES, modelo.feature_importances_)
        },
        "semilla": SEMILLA,
    }

    if json_out:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return resultado

    print(f"Base: {resultado['base']} | corte: {corte_usado} | semilla: {SEMILLA}")
    print(
        f"Alumnos evaluados: {resultado['alumnos_evaluados']} | "
        f"abandonaron: {resultado['abandonaron']} ({resultado['tasa_abandono']}%)"
    )
    print(
        f"Exactitud {resultado['accuracy']}% | AUC {resultado['auc']} | "
        f"precisión {resultado['precision']}% | recall {resultado['recall']}% | "
        f"n={resultado['casos_prueba']}"
    )
    print(classification_report(y_test, y_pred, target_names=["Sigue activo", "Abandona"], digits=3))
    print("Importancia de variables (%):")
    for nombre, peso in sorted(resultado["importancias"].items(), key=lambda kv: -kv[1]):
        print(f"  {peso:5.1f}  {nombre}")
    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida el modelo de abandono observado")
    parser.add_argument("--corte", default=os.getenv("CUT_PERIODO"))
    parser.add_argument("--json", action="store_true", help="salida JSON")
    args = parser.parse_args()
    evaluar(get_pg_engine(), corte=args.corte, json_out=args.json)


if __name__ == "__main__":
    sys.exit(main())
