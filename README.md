# 🎓 Proyecto Integrador — Base de Datos III

Sistema de **análisis académico y alerta temprana de deserción** construido sobre una
arquitectura de datos por capas (Data Lake + Data Warehouse).

El pipeline toma un dataset de rendimiento estudiantil, lo limpia en MongoDB y lo modela
en PostgreSQL con un **esquema en estrella**, para finalmente analizarlo y entrenar un
modelo predictivo de riesgo de abandono.

---

## 🏗️ Arquitectura

```text
 CSV crudo
    │
    ▼
┌──────────────────────────────┐
│  MongoDB Atlas               │
│  🥉 Bronze  estudiantes_raw   │  datos crudos (todo texto)
│  🥈 Silver  estudiantes_limpios│ datos tipados y validados
└──────────────┬───────────────┘
               │  ETL (pandas)
               ▼
┌──────────────────────────────┐
│  PostgreSQL                  │
│  🥇 Gold  dw_academico       │  esquema estrella + vistas
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  Análisis y dashboard        │  KPIs · Plotly · Random Forest
└──────────────────────────────┘
```

---

## 📁 Estructura del proyecto

```text
Integrador/
├── data/
│   ├── dataset_estudiantes_etl.csv     # Dataset original (5.000 filas)
│   └── dataset_estudiantes_v2.csv      # Dataset ampliado (generado, reproducible)
├── docs/
│   ├── REQUERIMIENTOS.txt              # Requerimientos del proyecto
│   ├── DEFENSA_PROYECTO.txt            # Material de defensa (arquitectura + Q&A)
│   └── VALIDACION_MODELO_V2.txt        # Evidencia reproducible del modelo
├── notebooks/
│   ├── 01_etl_mongo_limpieza.ipynb     # Bronze → Silver en MongoDB
│   ├── 02_etl_postgres_gold.ipynb      # Silver → Gold en PostgreSQL
│   └── 03_analisis_y_visualizacion.ipynb  # KPIs, gráficos y modelo ML
├── reports/                            # Gráficos exportados (se genera al ejecutar)
├── src/
│   ├── conn.py                         # Conexiones y escenario (variables de entorno)
│   ├── limpieza.py                     # Reglas Bronze → Silver
│   ├── gold.py                         # Transformaciones Silver → esquema estrella
│   ├── generar_dataset.py              # Generador del dataset ampliado (v2)
│   └── validar_modelo.py               # Validación reproducible del modelo
├── tests/                              # pytest: limpieza, gold y generador
├── .env.example                        # Plantilla de variables de entorno
├── .gitignore
├── README.md
└── requirements.txt
```

> La lógica de limpieza y de modelado dimensional vive en `src/`, no en las celdas
> de los notebooks. Los notebooks orquestan; las reglas se pueden testear sin Jupyter
> (`pytest -q`) y tienen una única fuente de verdad.

---

## ⚙️ Instalación

Requiere **Python 3.11+** (probado con 3.13).

```powershell
# 1. Crear y activar un entorno virtual (recomendado)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar dependencias
python -m pip install -r requirements.txt

# 3. Registrar el kernel de Jupyter apuntando a este entorno
python -m ipykernel install --prefix .venv --name integrador-db3 --display-name "Python (Integrador DB3 / .venv)"
```

> En VS Code / JupyterLab elegí el kernel **“Python (Integrador DB3 / .venv)”**.
> Si usás el kernel genérico, puede apuntar a otro Python y faltarle las dependencias.

---

## 🔐 Configuración

Copiá `.env.example` a `.env` y completá tus credenciales:

```powershell
Copy-Item .env.example .env
```

```dotenv
MONGO_URI=mongodb+srv://usuario:password@cluster.mongodb.net/?retryWrites=true&w=majority
PG_URI=postgresql+psycopg2://postgres:postgres@localhost:5432/dw_universidad

# Opcionales: escenario de ejecución (estos son los valores por defecto)
MONGO_DB=Estudiantes
PG_DB=dw_universidad
DATASET_CSV=data/dataset_estudiantes_etl.csv
```

> ⚠️ El archivo `.env` está en `.gitignore`. **No subas credenciales al repositorio.**
> El código no tiene credenciales de respaldo: si falta una variable, falla con un
> mensaje explícito en lugar de conectarse a un cluster hardcodeado.

Las tres variables de escenario permiten correr el mismo pipeline sobre otra base y
otro dataset sin modificar una línea de código. Por defecto apunta al dataset original.

---

## ▶️ Cómo ejecutar

Ejecutá los notebooks **en orden**:

| # | Notebook | Qué hace |
|---|----------|----------|
| 1 | `01_etl_mongo_limpieza.ipynb` | Carga el CSV a Bronze, diagnostica y limpia → Silver |
| 2 | `02_etl_postgres_gold.ipynb` | Crea la base y el esquema estrella, carga dimensiones y hechos, crea vistas |
| 3 | `03_analisis_y_visualizacion.ipynb` | KPIs, gráficos y modelo de riesgo |

Desde JupyterLab:

```powershell
python -m jupyter lab
```

> El notebook 2 crea automáticamente la base `dw_universidad` si no existe.
> El notebook 3 exporta los gráficos a `reports/` como HTML autónomo.

### Tests

```bash
.venv/bin/python -m pytest -q
```

Cubren las reglas de limpieza (`src/limpieza.py`), las transformaciones del esquema
estrella (`src/gold.py`) y el generador del dataset ampliado
(`src/generar_dataset.py`). No necesitan MongoDB ni PostgreSQL: trabajan sobre
DataFrames en memoria.

### Escenario ampliado (dataset v2)

El dataset original tiene 5.000 filas de 200 alumnos, todos activos hasta el último
período: no permite validar un modelo de abandono porque no hay abandonos. Para eso
existe el escenario v2, que no modifica el dataset entregado (sigue siendo la fuente
del criterio de aceptación CA-01):

```bash
# 1. Generar el dataset (determinístico, semilla 7)
.venv/bin/python -m src.generar_dataset

# 2. Correr el pipeline sobre las bases del escenario v2
export MONGO_DB=Estudiantes_v2
export PG_DB=dw_universidad_v2
export DATASET_CSV=data/dataset_estudiantes_v2.csv
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/01_etl_mongo_limpieza.ipynb
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/02_etl_postgres_gold.ipynb
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/03_analisis_y_visualizacion.ipynb

# 3. Validar el modelo de abandono de forma aislada
PG_DB=dw_universidad_v2 .venv/bin/python -m src.validar_modelo
```

Resultado sobre v2 (400 alumnos, 23.577 evaluaciones, corte 2025-1):

| Métrica | Valor |
|---|---|
| Exactitud | 88,7% |
| AUC | 0,859 |
| Precisión (abandona) | 93,8% |
| Recall (abandona) | 71,4% |

El detalle y las limitaciones están en `docs/VALIDACION_MODELO_V2.txt`.

---

## 🗄️ Modelo de datos (Gold)

**Dimensiones**

| Tabla | Descripción |
|---|---|
| `dim_carrera` | Carreras universitarias |
| `dim_estudiante` | Alumno, edad y cohorte de ingreso |
| `dim_materia` | Materia, código y año de cursada |
| `dim_periodo` | Período lectivo (año y cuatrimestre) |
| `dim_instancia` | Tipo de evaluación (parcial, final, TP, etc.) |
| `dim_docente` | Docente / cátedra |

**Tabla de hechos**

`fact_rendimiento_academico`: nota, asistencias, porcentaje de asistencia,
estado de aprobación y referencias a las dimensiones.

**Vistas analíticas**

| Vista | Uso |
|---|---|
| `vw_rendimiento_por_materia` | Comparar materias por aprobación y asistencia |
| `vw_evolucion_periodo_carrera` | Evolución temporal por carrera y año |
| `vw_alerta_temprana_alumnos` | Semáforo de riesgo por alumno |

---

## 📊 Visualizaciones

El notebook 3 genera y exporta:

1. Tasa de no aprobación por materia (desaprobados vs. ausentes)
2. Evolución del promedio académico por cuatrimestre y carrera
3. Mapa de calor de desaprobación por carrera y año
4. Semáforo de riesgo por cohorte de ingreso
5. Distribución general del riesgo
6. Matriz de confusión del modelo A
7. Importancia de los factores del modelo A

En el escenario v2 se agregan dos más (9 en total):

8. Curva ROC del abandono observado
9. Importancia de los factores del abandono

---

## 🤖 Modelo predictivo

Hay **dos modelos** y es importante no confundirlos:

| Modelo | Target | Qué demuestra | Estado |
|---|---|---|---|
| **A** | `semaforo_riesgo == "Riesgo Alto"` | Que el pipeline reproduce su propia regla SQL | Control de consistencia, **no predictivo** |
| **B** | Abandono observado después del corte | Que hay señal real para anticipar deserción | Validado sobre v2 |

El modelo A usa como features las mismas variables con las que se calcula la etiqueta
en SQL: aprende la regla que ya escribimos. Su exactitud alta (88% en v1, 95% en v2) no
es un hallazgo, es una consecuencia. Se mantiene porque verifica que las features del
notebook coinciden con las de la vista, y está rotulado como tal.

El modelo B usa solo información **anterior** al período de corte y predice un hecho
posterior: que el alumno deje de registrarse. Sobre el dataset original no se puede
calcular (no hay abandonos), por eso se valida sobre el v2. Los egresados quedan
excluidos del target: dejan de cursar por título, no por abandono.

---

## 🧯 Solución de problemas

| Error | Causa | Solución |
|---|---|---|
| `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xab` | La base `dw_universidad` no existe y psycopg2 no decodifica el mensaje en español (`«...»`, cp1252) | El notebook 2 crea la base automáticamente. Si no, ejecutá `CREATE DATABASE dw_universidad;` |
| `immutabledict is not a sequence` | El SQL tiene `%` literales y pandas pasa un `immutabledict` a psycopg2 | Envolver el SQL en `text(...)` o escapar `%` como `%%` |
| `UnicodeEncodeError` al imprimir emojis en consola | Codepage de Windows | `chcp 65001` o `$env:PYTHONUTF8=1` |
| `InternalError: discordancia en la versión de «collation» de la base de datos patrón «template1»` | El SO actualizó glibc (ej. 2.43 → 2.44) y las bases quedaron con la versión anterior registrada; `CREATE DATABASE` copia `template1` y falla | Conectado como superusuario: `ALTER DATABASE template1 REFRESH COLLATION VERSION;` (repetir para `postgres` y las bases existentes) |
| `ModuleNotFoundError: No module named 'dotenv'` | El kernel de Jupyter usa un Python distinto al del `.venv` (el del sistema), donde no están las dependencias | Elegí el kernel **“Python (Integrador DB3 / .venv)”**; si no aparece, corré `python -m ipykernel install --prefix .venv --name integrador-db3 --display-name "Python (Integrador DB3 / .venv)"` |

---

## 🧪 Tecnologías

- **MongoDB Atlas** — Data Lake (Bronze/Silver)
- **PostgreSQL 16** — Data Warehouse (Gold)
- **Python** — pandas, SQLAlchemy, psycopg2, PyMongo
- **Plotly** — visualizaciones interactivas
- **scikit-learn** — Random Forest (control de la regla + abandono observado)
- **pytest** — 40 tests de limpieza, transformaciones Gold y generador

---

## ⚠️ Limitaciones declaradas

Están acá y en `docs/DEFENSA_PROYECTO.txt` sección 11, no escondidas:

1. **El dataset original no permite comparar carreras ni validar abandono.** La carrera
   se asigna fila por fila, así que consolidada queda una sola; y todos los alumnos
   aparecen hasta el último período, así que no hay abandonos. El escenario v2 resuelve
   ambas cosas sin tocar el archivo entregado.
2. **Los datos son sintéticos.** Las métricas demuestran que el pipeline y el modelo
   funcionan; no son un pronóstico de una universidad real.
3. **El modelo B usa un solo corte** (2025-1). Una validación walk-forward con varios
   cortes queda como trabajo futuro.
4. **La credencial de MongoDB estuvo en el historial de git.** Se quitó del código, pero
   hay que rotarla en Atlas y purgar el historial.
5. **Los umbrales del semáforo son criterio propio**, no salen del enunciado. Se
   defienden como parámetros de negocio auditables.
6. **`dim_docente` en v1 tiene un registro placeholder** porque el CSV original no trae
   docente. En v2 hay 4 docentes reales.

