import os
import sqlite3
from datetime import datetime, date, time, timedelta
import time as _time
import pandas as pd
import streamlit as st
#import login as login
import supabase_login_shim as auth
import login as ui
from api_client import get_fichajes

IS_CLOUD = "/mount/src" in os.getcwd()
DEFAULT_DATA_DIR = "/mount/data" if IS_CLOUD else os.path.join(os.path.dirname(__file__), "data")

BASE_DIR = st.secrets.get("DATA_DIR", DEFAULT_DATA_DIR)
os.makedirs(BASE_DIR, exist_ok=True)

DB_FICHAJES = os.path.join(BASE_DIR, "fichajes.db")
DB_RRHH     = os.path.join(BASE_DIR, "rrhh.db")
BAJAS_DIR   = os.path.join(BASE_DIR, "bajas_adjuntos")
os.makedirs(BAJAS_DIR, exist_ok=True)

auth.generarLogin(__file__)                      
ui.generarMenuRoles(st.session_state["usuario"])


DB_FILE = DB_FICHAJES
TABLE = "fichajes"

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

def fecha_corta_es(d, con_anio=False):
    fmt = "%d/%m/%Y" if con_anio else "%d/%m"
    return f"{DIAS_ES[d.weekday()]} {d.strftime(fmt)}"

def get_conn():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    return sqlite3.connect(DB_FILE)

def ensure_schema():
    # Garantiza que exista la tabla fichajes con el mismo esquema que paginaFichajeMovil
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empleado TEXT NOT NULL,
                fecha_local TEXT NOT NULL,   -- 'YYYY-MM-DD HH:MM:SS' (zona horaria local)
                fecha_utc   TEXT NOT NULL,   -- 'YYYY-MM-DD HH:MM:SS' (UTC)
                tipo TEXT NOT NULL CHECK (tipo IN ('Entrada','Salida')),
                observaciones TEXT,
                fuente TEXT DEFAULT 'movil',
                created_at_utc TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()

def _local_to_utc_str(dt_local: datetime) -> str:
    """Convierte un datetime 'naive' local a cadena UTC 'YYYY-MM-DD HH:MM:SS' sin libs externas."""
    # offset local = now_local - now_utc (aprox, válido para España con cambio horario)
    offset = datetime.now() - datetime.utcnow()
    dt_utc = dt_local - offset
    return dt_utc.strftime("%Y-%m-%d %H:%M:%S")

def insertar_par_manual(empleado: str, d: date, h_entrada: time, h_salida: time, nota: str = ""):
    """Inserta un par Entrada/Salida manual para un día."""
    if h_salida <= h_entrada:
        raise ValueError("La hora de salida debe ser posterior a la hora de entrada.")
    dt_e_local = datetime.combine(d, h_entrada)
    dt_s_local = datetime.combine(d, h_salida)
    e_local = dt_e_local.strftime("%Y-%m-%d %H:%M:%S")
    s_local = dt_s_local.strftime("%Y-%m-%d %H:%M:%S")
    e_utc = _local_to_utc_str(dt_e_local)
    s_utc = _local_to_utc_str(dt_s_local)
    obs = (nota or "").strip() or "ajuste manual desde app"
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {TABLE}(empleado, fecha_local, fecha_utc, tipo, observaciones, fuente) "
            f"VALUES (?, ?, ?, 'Entrada', ?, 'ajuste_movil');",
            (empleado, e_local, e_utc, obs)
        )
        cur.execute(
            f"INSERT INTO {TABLE}(empleado, fecha_local, fecha_utc, tipo, observaciones, fuente) "
            f"VALUES (?, ?, ?, 'Salida', ?, 'ajuste_movil');",
            (empleado, s_local, s_utc, obs)
        )
        conn.commit()

def cargar_fichajes_semana(empleado: str, d_ini: date, d_fin: date) -> pd.DataFrame:
    import pandas as pd
    user_id = st.session_state["user_id"]
    data = get_fichajes(user_id, limit=1000)  # traemos y filtramos
    df = pd.DataFrame(data)
    if df.empty: 
        return df
    df = df[df["empleado"] == empleado]
    df["fecha_local"] = pd.to_datetime(df["fecha_local"])
    mask = (df["fecha_local"].dt.date >= d_ini) & (df["fecha_local"].dt.date <= d_fin)
    return df.loc[mask, ["id","empleado","fecha_local","tipo","observaciones","fuente"]]



def _pair_and_sum(day_df: pd.DataFrame) -> tuple[list[str], float]:
    """Devuelve lista de marcas 'HH:MM - HH:MM' y total de horas (float)."""
    marcas = []
    total_seconds = 0
    # Ordena por fecha_local
    df = day_df.sort_values("fecha_local").reset_index(drop=True)
    times = [(row["tipo"], datetime.strptime(row["fecha_local"], "%Y-%m-%d %H:%M:%S")) for _, row in df.iterrows()]
    i = 0
    while i < len(times):
        tipo, t = times[i]
        if tipo == "Entrada" and i + 1 < len(times) and times[i+1][0] == "Salida":
            t2 = times[i+1][1]
            marcas.append(f"{t.strftime('%H:%M')} - {t2.strftime('%H:%M')}")
            total_seconds += (t2 - t).total_seconds()
            i += 2
        else:
            # marca impar o desordenada
            marcas.append(f"{t.strftime('%H:%M')} - ?")
            i += 1
    total_horas = round(total_seconds / 3600.0, 2)
    return marcas, total_horas

def _iso_week_start(d: date) -> date:
    # Lunes de la semana ISO del día d
    return d - timedelta(days=d.weekday())

def _week_dates(d: date) -> list[date]:
    start = _iso_week_start(d)
    return [start + timedelta(days=i) for i in range(7)]


ensure_schema()

st.header("Modificar fichaje")

if "usuario" not in st.session_state:
    st.warning("Inicia sesión para continuar.")
    st.stop()

empleado = st.session_state["usuario"]

# Selector de semana (referencia por día)
hoy = date.today()
ref_day = st.date_input("Semana de...", value=hoy)
semana = _week_dates(ref_day)
d_ini, d_fin = semana[0], semana[-1]

iso_year, iso_week, _ = ref_day.isocalendar()
st.caption(f"Semana: **{iso_week}** ")

df_sem = cargar_fichajes_semana(empleado, d_ini, d_fin)

if not df_sem.empty:
    df_sem["fecha_local"] = pd.to_datetime(df_sem["fecha_local"]).dt.strftime("%Y-%m-%d %H:%M:%S")
else:
    # Si viene vacío, fuerza dtype de string para que .str no de error
    df_sem["fecha_local"] = df_sem.get("fecha_local", pd.Series(dtype="string")).astype("string")

# Construye visión por día
rows = []
for d in semana:
    day_str = d.strftime("%Y-%m-%d")
    day_df = df_sem[df_sem["fecha_local"].str.startswith(day_str)]
    marcas, total_h = _pair_and_sum(day_df)
    rows.append({
        "fecha": fecha_corta_es(d),
        "marcas": " · ".join(marcas) if marcas else "—",
        "horas": total_h
    })
df_view = pd.DataFrame(rows)
# Renombrar las columnas del DataFrame
df_view = df_view.rename(columns={
    "fecha": "Fecha",
    "marcas": "Marcas",
    "horas": "Horas"
})

st.dataframe(df_view, use_container_width=True)

st.markdown("---")
st.subheader("Añadir fichaje")

col1, col2, col3 = st.columns([2,1,1])
with col1:
    dia_sel = st.selectbox("Día", options=semana, format_func=lambda d: fecha_corta_es(d, con_anio=True))
with col2:
    h_in = st.time_input("Entrada", value=time(9, 0))
with col3:
    h_out = st.time_input("Salida", value=time(17, 0))

nota = st.text_input("Motivo / observación (opcional)")

# donde está el botón "Guardar par Entrada/Salida"
if st.button("Guardar par Entrada/Salida", type="primary", disabled=True):
    st.info("El guardado manual se habilitará cuando añadamos el endpoint /fichajes/manual en el backend.")





