# ODD — Corrección del ETL, dataset ampliado y validación del modelo

Proyecto: Integrador DB3 · Entrega: pipeline CSV → MongoDB (Bronze/Silver) → PostgreSQL (Gold) + análisis/ML
Rama: main · Runner: pytest (tests/) + jupyter nbconvert (pipeline)
Estrategia de entrega: work-unit commits en `main` (árbol ya tenía cambios locales previos; no se commitea sin confirmación)

## Specs

S1. El usuario detectó que se afirmó que hay errores en los notebooks y pidió corregirlos:
   "y vos decis que tengo errores en los notebooks? si es asi corrije y propon cosas"
   Alcance: corregir defectos reales de código, no solo regenerar outputs.
S2. El dataset original `data/dataset_estudiantes_etl.csv` (5.000 filas) NO se modifica:
   es la fuente de `CA-01` ("El pipeline procesa las 5.000 filas del dataset original")
   y de los resultados ya documentados en `docs/REQUERIMIENTOS.txt`.
S3. El usuario autorizó ampliar los datos para poder validar el modelo:
   "puedes modificar el dataset para crear mas datos y poder validarlos y demas"
   Implementación: segundo dataset generado de forma reproducible (`data/dataset_estudiantes_v2.csv`)
   con generador versionado en `src/generar_dataset.py`, sin sobreescribir el original.
S4. El modelo predictivo debe predecir un resultado OBSERVADO (abandono real: el alumno deja de
   registrarse en periodos posteriores), no una regla derivada de sus propias features.
   El modelo actual (target = semáforo) queda como "modelo A: réplica de la regla" con advertencia
   explícita de circularidad.
S5. Las credenciales no deben estar escritas en el código. `MONGO_URI` y `PG_URI` se leen de `.env`;
   `.env` está en `.gitignore`. Se elimina el fallback hardcodeado de los notebooks 01 y 02.
S6. Las reglas de limpieza deben vivir en un módulo importable y testeado (`src/limpieza.py`),
   no solo dentro de una celda de notebook. Tests en `tests/`.
S7. Consistencia dimensional: `dim_estudiante.sk_carrera` y `fact_rendimiento_academico.sk_carrera`
   deben coincidir para todo alumno (hoy difieren en 1.362 de 5.000 hechos).
S8. Las conclusiones del notebook 03 deben estar respaldadas por los datos que el propio notebook
   calcula (hoy afirma una relación asistencia→reprobación que la correlación no sostiene).
S9. Todo cambio debe quedar verificado ejecutando el pipeline completo (01 → 02 → 03) sobre el
   dataset base y devolver los mismos resultados que antes de la corrección, salvo los defectos
   corregidos.

## Tasks

| ID | Spec | Ruta | Estado |
|----|------|------|--------|
| T1 | S5,S6 | `src/limpieza.py`, `.env`, `src/conn.py` | hecho (src/limpieza.py, src/conn.py env-only, .env gitignored) |
| T2 | S6 | `tests/test_limpieza.py` (RED → GREEN) | hecho (tests/test_limpieza.py, 12 casos) |
| T3 | S1,S5,S6 | Parche notebook 01 (import módulo, sin credenciales, sin `utcnow`) | hecho + ejecutado v1 |
| T4 | S7,S1 | Parche notebook 02 (carrera canónica, asistencias sin sobreescritura, docente real) | hecho + ejecutado v1 (carrera canónica, asistencia sin sobreescritura, docente real/placeholder) |
| T5 | S7 | Validación dimensional automatizada en notebook 02 | hecho (7 FK, 0 inconsistentes, 0 huérfanos) + ejecutado v1 |
| T6 | S3 | `src/generar_dataset.py` + `data/dataset_estudiantes_v2.csv` | hecho (23.577 filas, seed 7) + test_generar_dataset.py |
| T7 | S4,S8 | Parche notebook 03 (modelo A honesto + modelo B abandono observado, conclusiones) | hecho + ejecutado v1 (Modelo B se omite con explicación) |
| T8 | S9 | Ejecución completa sobre dataset base (regresión) | hecho (v1 re-ejecutado: 200 alumnos, 7 gráficos, 88,0% determinístico) |
| T9 | S3,S4,S9 | Ejecución completa sobre dataset v2 + métricas reales | hecho (v2: 246 alumnos, AUC 0,859, prec 93,8, recall 71,4) + src/validar_modelo.py |
| T10 | S1 | `README.md` y `docs/DEFENSA_PROYECTO.txt` actualizados | hecho (README, DEFENSA, VALIDACION_MODELO_V2.txt) |

## Log

L1 (verbatim):
"y vos decis que tengo errores en los notebooks? si es asi corrije y propon cosas, puedes modificar el dataset para crear mas datos y poder validarlos y demas"

L2 — Auditoría previa (verificada contra la base en ejecución):
- Notebook 02 agrega `carrera=("carrera","first")` en `dim_estudiante` pero carga en el hecho la
  carrera de la fila: 1.362/5.000 hechos (27,2%) con `sk_carrera` distinto del de `dim_estudiante`.
  Consecuencia: `vw_alerta_temprana_alumnos` devuelve 396 filas para 200 alumnos.
- Notebook 02 recalcula `asistencias` para TODAS las filas a partir del `pct_asistencia` imputado,
  sobreescribiendo el dato original (deriva por redondeo).
- Notebook 02 fija `sk_docente = 1` para todos los hechos.
- Notebook 01/02 tienen `MONGO_URI` con credenciales reales como fallback.
- `src/conn.py` apunta a la colección `turista`, no a `estudiantes_raw`/`estudiantes_limpios`.
- Notebook 03: target del modelo derivado de las mismas features (circularidad); output guardado
  93,9% no reproducible (81,8% sobre la base actual); conclusión asistencia→reprobación no sostenida
  (corr = -0,004).

L3 — Decisión de alcance: el dataset original queda intacto (S2). El dataset ampliado vive en un
archivo y una base separados, seleccionables por variables de entorno (`DATASET_CSV`, `MONGO_DB`,
`PG_DB`), para no invalidar los criterios de aceptación ya documentados.

L4 — Cierre y verificación (estado final):
- `src/validar_modelo.py` agrega una validación reproducible del modelo B por comando
  (`PG_DB=dw_universidad_v2 python -m src.validar_modelo [--json]`), sin escribir en la base.
- Defecto nuevo encontrado al documentar: `train_test_split` repartía según el orden de filas y la
  vista devuelve empates de `score_riesgo` en orden no determinístico → la misma corrida daba 78,0%
  y 88,0%. Se ordena por `id_alumno` antes del split; el número queda estable (88,0%, AUC 0,935).
- Documentación: `docs/VALIDACION_MODELO_V2.txt` (evidencia), `docs/DEFENSA_PROYECTO.txt`
  (reescrito con números corregidos y sección 11 = corregido vs. pendiente), `README.md`
  (módulos, tests, escenario v2, limitaciones), `.env.example` (escenario), `.gitignore`
  (`.pytest_cache/`), `requirements.txt` (pytest).
- Regresión v1 verificada: notebooks 01→02→03 re-ejecutados; 5.000 hechos, 200 alumnos,
  1 carrera canónica, 200 filas en la vista, 7 gráficos, correlación -0,004, Modelo B omitido.
- Tests: 40 passed.
