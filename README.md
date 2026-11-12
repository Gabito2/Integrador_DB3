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
│   └── dataset_estudiantes_etl.csv     # Dataset original
├── docs/
│   └── REQUERIMIENTOS.txt              # Requerimientos del proyecto
├── notebooks/
│   ├── 01_etl_mongo_limpieza.ipynb     # Bronze → Silver en MongoDB
│   ├── 02_etl_postgres_gold.ipynb      # Silver → Gold en PostgreSQL
│   └── 03_analisis_y_visualizacion.ipynb  # KPIs, gráficos y modelo ML
├── reports/                            # Gráficos exportados (se genera al ejecutar)
├── src/
│   └── conn.py                         # Helper de conexión a MongoDB
├── .env.example                        # Plantilla de variables de entorno
├── .gitignore
├── README.md
└── requirements.txt
```

---

## ⚙️ Instalación

Requiere **Python 3.11+** (probado con 3.13).

```powershell
# 1. Crear y activar un entorno virtual (recomendado)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar dependencias
python -m pip install -r requirements.txt
```

---

## 🔐 Configuración

Copiá `.env.example` a `.env` y completá tus credenciales:

```powershell
Copy-Item .env.example .env
```

```dotenv
MONGO_URI=mongodb+srv://usuario:password@cluster.mongodb.net/?retryWrites=true&w=majority
PG_URI=postgresql+psycopg2://postgres:postgres@localhost:5432/dw_universidad
```

> ⚠️ El archivo `.env` está en `.gitignore`. **No subas credenciales al repositorio.**

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
6. Matriz de confusión del modelo
7. Importancia de los factores de riesgo

---

## 🧯 Solución de problemas

| Error | Causa | Solución |
|---|---|---|
| `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xab` | La base `dw_universidad` no existe y psycopg2 no decodifica el mensaje en español (`«...»`, cp1252) | El notebook 2 crea la base automáticamente. Si no, ejecutá `CREATE DATABASE dw_universidad;` |
| `immutabledict is not a sequence` | El SQL tiene `%` literales y pandas pasa un `immutabledict` a psycopg2 | Envolver el SQL en `text(...)` o escapar `%` como `%%` |
| `UnicodeEncodeError` al imprimir emojis en consola | Codepage de Windows | `chcp 65001` o `$env:PYTHONUTF8=1` |

---

## 🧪 Tecnologías

- **MongoDB Atlas** — Data Lake (Bronze/Silver)
- **PostgreSQL 16** — Data Warehouse (Gold)
- **Python** — pandas, SQLAlchemy, psycopg2, PyMongo
- **Plotly** — visualizaciones interactivas
- **scikit-learn** — Random Forest para riesgo de abandono

---

## 👤 Autor

**Gabriel** · Base de Datos III · UNdeC
