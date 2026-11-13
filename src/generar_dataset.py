"""Generador reproducible del dataset ampliado (v2).

Diferencia con el dataset base: acá el dato tiene estructura real, no columnas
independientes. Es lo que permite validar el modelo predictivo.

  - Cada alumno pertenece a UNA carrera (atributo del alumno, no de la fila).
  - La asistencia depende de la constancia del alumno y la nota depende de la
    asistencia, la capacidad y la dificultad de la materia.
  - Algunos alumnos abandonan: dejan de inscribirse. Eso da una etiqueta
    OBSERVADA ("¿siguió cursando después del corte?") que no se deriva de las
    features del modelo.
  - Se inyectan los mismos defectos de calidad que trae el dataset base
    (palabras, notas fuera de rango, asistencias negativas, tres formatos de
    fecha, variantes de código) para que el ETL se ejercite igual.
  - Trae docente por materia, para que dim_docente tenga datos reales.

Uso:
    python -m src.generar_dataset --alumnos 400 --seed 7
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

CARRERAS = [
    ("Ingeniería en Sistemas", 0.38),
    ("Licenciatura en Análisis de Datos", 0.24),
    ("Licenciatura en Administración", 0.22),
    ("Ingeniería Industrial", 0.16),
]

# (código, nombre, año de cursada, dificultad 0-1)
MATERIAS = [
    ("ALG-01", "Algoritmos", 1, 0.25),
    ("PL-01", "Programación Lógica", 1, 0.30),
    ("FIS-01", "Física", 1, 0.45),
    ("EST-01", "Estadística Aplicada", 2, 0.32),
    ("SO-01", "Sistemas Operativos", 3, 0.36),
    ("BD-03", "Base de Datos III", 4, 0.48),
    ("ADM-02", "Gestión de Proyectos", 4, 0.18),
    ("PI-01", "Procesamiento de Imágenes", 5, 0.42),
]

DOCENTES = [
    ("DOC-001", "Laura Giménez"),
    ("DOC-002", "Martín Sosa"),
    ("DOC-003", "Carla Ferreyra"),
    ("DOC-004", "Diego Paz"),
]

INSTANCIAS = ["Parcial 1", "Parcial 2", "TP Práctico", "Final", "Recuperatorio"]
AJUSTE_INSTANCIA = {
    "Parcial 1": -0.35, "Parcial 2": -0.10, "TP Práctico": 0.55,
    "Final": -0.60, "Recuperatorio": -0.90,
}
MESES_INICIO = {1: (3, 15), 2: (8, 5)}

MAP_NOTA_PALABRA = {
    0: "Cero", 1: "Uno", 2: "Dos", 3: "Tres", 4: "Cuatro",
    5: "Cinco", 6: "Seis", 7: "Siete", 8: "Ocho", 9: "Nueve", 10: "Diez",
}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def generar(
    alumnos: int = 400,
    seed: int = 7,
    inicio: int = 2019,
    fin: int = 2026,
    defectos: float = 1.0,
    riesgo_abandono: float = 2.5,
    abandono_aleatorio: float = 0.010,
    pendiente: float = 2.2,
) -> pd.DataFrame:
    """Devuelve el dataset en formato Bronze (todo texto) listo para el ETL."""
    rng = np.random.default_rng(seed)

    periodos = [(a, c) for a in range(inicio, fin + 1) for c in (1, 2)]
    periodos = [p for p in periodos if p <= (fin, 1)]

    nombres_carrera = [c for c, _ in CARRERAS]
    pesos_carrera = [w for _, w in CARRERAS]

    filas = []
    cohortes = list(range(inicio, fin - 1))

    for i in range(alumnos):
        id_alumno = f"A{i + 1:04d}"
        carrera = str(rng.choice(nombres_carrera, p=pesos_carrera))
        cohorte = int(rng.choice(cohortes))
        capacidad = float(rng.normal(0, 1))
        constancia = float(np.clip(rng.normal(0.74, 0.14), 0.35, 0.99))

        inicio_idx = periodos.index((cohorte, 1))
        activo = True
        aprobadas: set[str] = set()
        ultimas_notas: list[float] = []

        for (anio, cuatri) in periodos[inicio_idx:]:
            if not activo:
                break
            antiguedad = anio - cohorte + 1
            disponibles = [
                m for m in MATERIAS
                if m[2] <= max(antiguedad, 1) and m[0] not in aprobadas
            ]
            if len(aprobadas) >= len(MATERIAS):
                break  # egresó: deja de cursar por título, no por abandono
            if not disponibles:
                disponibles = [m for m in MATERIAS if m[0] not in aprobadas] or list(MATERIAS)
            cantidad = int(rng.integers(1, min(4, len(disponibles)) + 1))
            elegidas = rng.choice(len(disponibles), size=cantidad, replace=False)

            notas_periodo = []
            for idx_materia in elegidas:
                codigo, nombre, anio_materia, dificultad = disponibles[int(idx_materia)]
                legajo, docente = DOCENTES[MATERIAS.index(
                    next(m for m in MATERIAS if m[0] == codigo)
                ) % len(DOCENTES)]

                asistencia_ratio = float(np.clip(
                    constancia + rng.normal(0, 0.09), 0.05, 1.0
                ))
                clases_totales = int(rng.choice([32, 40, 48]))
                asistencias = int(round(asistencia_ratio * clases_totales))

                instancias = _instancias_del_periodo(asistencia_ratio, rng)
                for instancia in instancias:
                    rendido = rng.random() > (0.04 + 0.30 * (1 - asistencia_ratio))
                    if not rendido:
                        nota_cruda = "Ausente"
                        notas_periodo.append(None)
                    else:
                        latente = (
                            2.2
                            + 6.4 * asistencia_ratio
                            + 1.1 * capacidad
                            - 3.8 * dificultad
                            + AJUSTE_INSTANCIA[instancia]
                            + rng.normal(0, 1.05)
                        )
                        nota = int(np.clip(round(latente), 0, 10))
                        nota_cruda = nota
                        notas_periodo.append(nota)
                        if instancia in ("Final", "Recuperatorio") and nota >= 6:
                            aprobadas.add(codigo)

                    mes, dia_inicio = MESES_INICIO[cuatri]
                    fecha = date(anio, mes, dia_inicio) + timedelta(
                        days=int(rng.integers(0, 90))
                    )
                    edad = int(np.clip(18 + (anio - cohorte) + rng.normal(0, 1), 17, 60))

                    filas.append({
                        "id_alumno": id_alumno,
                        "edad_alumno": edad,
                        "carrera": carrera,
                        "cohorte": cohorte,
                        "codigo_materia": codigo,
                        "nombre_materia": nombre,
                        "anio_cursada": anio_materia,
                        "periodo_inscripcion": f"{anio}-{cuatri}",
                        "tipo_instancia": instancia,
                        "fecha_examen": fecha,
                        "nota": nota_cruda,
                        "asistencias": asistencias,
                        "clases_totales": clases_totales,
                        "legajo_docente": legajo,
                        "nombre_docente": docente,
                    })

            # Riesgo de abandonar según el rendimiento del período
            validas = [n for n in notas_periodo if n is not None]
            promedio = float(np.mean(validas)) if validas else 0.0
            ultimas_notas.append(promedio)
            reciente = float(np.mean(ultimas_notas[-3:])) if ultimas_notas else 0.0
            prob_abandono = abandono_aleatorio + 0.12 * riesgo_abandono * _sigmoid(
                pendiente * (3.6 - reciente)
            )
            if rng.random() < prob_abandono:
                activo = False

    df = pd.DataFrame(filas)
    df = _inyectar_defectos(df, rng, factor=defectos)
    return df


def _instancias_del_periodo(asistencia_ratio: float, rng) -> list[str]:
    """Todas las materias rinden parciales; el final aparece si hubo riesgo."""
    instancias = ["Parcial 1", "TP Práctico", "Parcial 2"]
    if asistencia_ratio > 0.55 and rng.random() < 0.55:
        instancias.append("Final")
    elif rng.random() < 0.25:
        instancias.append("Recuperatorio")
    return instancias


def _inyectar_defectos(df: pd.DataFrame, rng, factor: float = 1.0) -> pd.DataFrame:
    """Ensuciar el dataset con los mismos defectos que trae el archivo original."""
    df = df.copy()
    df["nota"] = df["nota"].astype(object)
    df["edad_alumno"] = df["edad_alumno"].astype(object)
    df["asistencias"] = df["asistencias"].astype(object)
    n = len(df)
    idx = df.index.to_numpy()

    def elegir(proporcion: float) -> np.ndarray:
        cantidad = int(n * proporcion * factor)
        return rng.choice(idx, size=min(cantidad, n), replace=False)

    # 1. Notas escritas con palabras
    sel = elegir(0.06)
    df.loc[sel, "nota"] = [
        MAP_NOTA_PALABRA[int(v)] if isinstance(v, (int, np.integer)) else v
        for v in df.loc[sel, "nota"]
    ]

    # 2. Notas fuera de rango (dato imposible)
    sel = elegir(0.03)
    df.loc[sel, "nota"] = rng.choice([-2, 11, 47, 99], size=len(sel))

    # 3. Edad escrita con palabras y edades imposibles
    sel = elegir(0.02)
    df.loc[sel, "edad_alumno"] = "veinte"
    sel = elegir(0.02)
    df.loc[sel, "edad_alumno"] = rng.choice([8, 150, 210], size=len(sel))

    # 4. Asistencias negativas o mayores a las clases
    sel = elegir(0.04)
    df.loc[sel, "asistencias"] = -rng.integers(1, 6, size=len(sel))
    sel = elegir(0.04)
    df.loc[sel, "asistencias"] = df.loc[sel, "clases_totales"] + rng.integers(
        1, 9, size=len(sel)
    )

    # 5. Variantes del código de materia
    sel = elegir(0.20)
    df.loc[sel, "codigo_materia"] = df.loc[sel, "codigo_materia"].str.lower()
    sel = elegir(0.10)
    df.loc[sel, "codigo_materia"] = (
        df.loc[sel, "codigo_materia"].str.replace("-", "", regex=False)
    )
    sel = elegir(0.05)
    df.loc[sel, "codigo_materia"] = " " + df.loc[sel, "codigo_materia"] + " "

    # 6. Tres formatos de fecha
    fechas = pd.to_datetime(df["fecha_examen"])
    df["fecha_examen"] = fechas.dt.strftime("%Y-%m-%d")
    sel = elegir(0.20)
    df.loc[sel, "fecha_examen"] = fechas.loc[sel].dt.strftime("%d/%m/%Y")
    sel = elegir(0.20)
    df.loc[sel, "fecha_examen"] = fechas.loc[sel].dt.strftime("%d-%m-%y")

    # 7. Espacios sobrantes en textos
    sel = elegir(0.05)
    df.loc[sel, "carrera"] = " " + df.loc[sel, "carrera"] + "  "
    sel = elegir(0.05)
    df.loc[sel, "nombre_materia"] = df.loc[sel, "nombre_materia"] + " "

    # 8. Todo a texto, como llega un CSV crudo
    return df.astype(str)


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el dataset sintético ampliado (v2)")
    parser.add_argument("--alumnos", type=int, default=400)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--inicio", type=int, default=2019)
    parser.add_argument("--fin", type=int, default=2026)
    parser.add_argument("--defectos", type=float, default=1.0)
    parser.add_argument("--riesgo-abandono", type=float, default=2.5)
    parser.add_argument("--abandono-aleatorio", type=float, default=0.010)
    parser.add_argument("--pendiente", type=float, default=2.2)
    parser.add_argument("--out", default="data/dataset_estudiantes_v2.csv")
    args = parser.parse_args()

    df = generar(
        alumnos=args.alumnos, seed=args.seed,
        inicio=args.inicio, fin=args.fin, defectos=args.defectos,
        riesgo_abandono=args.riesgo_abandono,
        abandono_aleatorio=args.abandono_aleatorio,
        pendiente=args.pendiente,
    )

    destino = Path(args.out)
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destino, index=False)

    print(f"Dataset generado: {destino}")
    print(f"  filas: {len(df):,} | columnas: {len(df.columns)}")
    codigos = (
        df["codigo_materia"].str.strip().str.upper()
        .str.replace(r"^([A-Z]{2,3})-?(\d{2})$", r"\1-\2", regex=True)
    )
    print(f"  alumnos: {df['id_alumno'].nunique():,} | carreras: "
          f"{df['carrera'].str.strip().nunique()} | materias: {codigos.nunique()}")
    print(f"  defensor: seed={args.seed} (reproducible)")


if __name__ == "__main__":
    main()
