import streamlit as st
import pandas as pd
#import login as login
import sqlite3
from datetime import datetime, date, timedelta
import config as cfg

import os, sys
ROOT = os.path.dirname(os.path.dirname(__file__))  # .../app
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import supabase_login_shim as auth
import ui_pages as ui
from api_client import (post_vacaciones, get_vacaciones, cancel_vacacion,
                        post_baja, get_bajas)

st.set_page_config(
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"Get help": None, "Report a bug": None, "About": None}
)

st.markdown("""
<style>
/* Streamlit antiguos */
#MainMenu { display: none !important; visibility: hidden !important; }
/* Streamlit recientes (data-testid) */
div[data-testid="stMainMenu"] { display: none !important; visibility: hidden !important; }
/* Si aún aparece, oculta toda la toolbar (incluye el icono de 3 puntos) */
div[data-testid="stToolbar"] { display: none !important; visibility: hidden !important; }
/* (Opcional) si ocultas la toolbar/encabezado y queda margen arriba, ajusta: */
/* header[data-testid="stHeader"] { height: 0 !important; } */
/* div.block-container { padding-top: 1rem !important; } */
</style>
""", unsafe_allow_html=True)


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




# ======== Config DB (SQLite) ========
DB_FILE = DB_RRHH
VAC_TABLE = "vacaciones"
BAJ_TABLE = "bajas"



def get_conn():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    return sqlite3.connect(DB_FILE)

def ensure_tables():
    with get_conn() as conn:
        cur = conn.cursor()
        # Vacaciones
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {VAC_TABLE}(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL,
                fecha_inicio TEXT NOT NULL,   -- YYYY-MM-DD
                fecha_fin    TEXT NOT NULL,   -- YYYY-MM-DD
                dias INTEGER NOT NULL,
                comentario TEXT,
                estado TEXT NOT NULL DEFAULT 'Pendiente',  -- Pendiente | Aprobado | Rechazado | Cancelado
                fecha_solicitud TEXT NOT NULL              -- YYYY-MM-DD HH:MM:SS
            );
        """)
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{VAC_TABLE}_usuario ON {VAC_TABLE}(usuario);")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{VAC_TABLE}_estado  ON {VAC_TABLE}(estado);")

        # Bajas / permisos
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {BAJ_TABLE}(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL,
                tipo TEXT NOT NULL,              -- Enfermedad común | Accidente laboral | Paternidad/Maternidad | Otros
                fecha_inicio TEXT NOT NULL,      -- YYYY-MM-DD
                fecha_fin TEXT,                  -- opcional
                descripcion TEXT,
                archivos TEXT,                   -- rutas separadas por ';'
                estado TEXT NOT NULL DEFAULT 'Notificada',
                fecha_registro TEXT NOT NULL     -- YYYY-MM-DD HH:MM:SS
            );
        """)
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{BAJ_TABLE}_usuario ON {BAJ_TABLE}(usuario);")
        conn.commit()

def guardar_vacaciones(usuario, fi, ff, dias, comentario):
    user_id = st.session_state["user_id"]
    return post_vacaciones(user_id, usuario, fi, ff, dias, comentario)

def listar_vacaciones(usuario):
    user_id = st.session_state["user_id"]
    data = get_vacaciones(user_id)
    return pd.DataFrame(data)

def cancelar_vacacion(id_, usuario):
    user_id = st.session_state["user_id"]
    return cancel_vacacion(user_id, id_)

def guardar_baja(usuario, tipo, fi, ff, descripcion, archivos_files):
    user_id = st.session_state["user_id"]
    # aquí pasamos los UploadedFile directamente (no guardamos al disco local)
    return post_baja(user_id, usuario, tipo, fi, ff, descripcion, archivos_files)

def listar_bajas(usuario):
    user_id = st.session_state["user_id"]
    data = get_bajas(user_id)
    return pd.DataFrame(data)


# ================= UI ==================
ensure_tables()

st.header("Ausencias")

if 'usuario' not in st.session_state:
    st.warning("Acceso denegado. Inicia sesión.")
    st.stop()

usuario_actual = st.session_state['usuario']

tab1, tab2 = st.tabs(["Vacaciones", "Bajas / Permisos"])

# ---- Tab Vacaciones ----
with tab1:
    st.subheader("Solicitud de vacaciones")
    col1, col2 = st.columns(2)
    with col1:
        fi = st.date_input("Fecha de inicio", min_value=date.today(), value=date.today())
    with col2:
        ff = st.date_input("Fecha de fin", min_value=fi, value=max(fi, date.today()))

    if ff < fi:
        st.error("La fecha de fin no puede ser anterior a la fecha de inicio.")
    else:
        dias = (ff - fi).days + 1
        st.info(f"Días solicitados: **{dias}**")

    comentario = st.text_area("Comentario (opcional)")

    cols_btn = st.columns(2)
    with cols_btn[0]:
        if st.button("Enviar solicitud", type="primary", use_container_width=True, disabled=ff < fi):
            try:
                guardar_vacaciones(usuario_actual, fi, ff, dias, comentario)
                st.success("Solicitud enviada. Estado: Pendiente")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar la solicitud: {e}")

    st.markdown("---")
    st.caption("Tus solicitudes")
    dfv = listar_vacaciones(usuario_actual)
    if dfv.empty:
        st.info("Aún no has realizado solicitudes de vacaciones.")
    else:
        # Botón de cancelar para las pendientes
        for _, row in dfv.iterrows():
            with st.container(border=True):
                st.write(f"📅 {row['fecha_inicio']} → {row['fecha_fin']}  ·  {row['dias']} día(s)  ·  **{row['estado']}**")
                if str(row['comentario']).strip():
                    st.caption(row['comentario'])
                if row['estado'] == 'Pendiente':
                    if st.button("Cancelar", key=f"cancel_{row['id']}"):
                        cancelar_vacacion(int(row['id']), usuario_actual)
                        st.success("Solicitud cancelada.")
                        st.rerun()

# ---- Tab Bajas / Permisos ----
with tab2:
    st.subheader("Comunicar baja o permiso")
    tipos = ["Enfermedad común", "Accidente laboral", "Paternidad/Maternidad", "Hospitalización familiar", "Cita médica", "Otros"]
    tipo = st.selectbox("Tipo", tipos)
    c1, c2 = st.columns(2)
    with c1:
        fi_b = st.date_input("Fecha de inicio", value=date.today())
    with c2:
        ff_b = st.date_input("Fecha de fin (opcional)", value=date.today())
        usar_fin = st.checkbox("Indicar fecha fin", value=False)
    descripcion = st.text_area("Descripción / Observaciones (opcional)")

    st.write("Adjuntar documentos (PDF/JPG/PNG/DOCX)")
    files = st.file_uploader("Selecciona archivos", type=["pdf","jpg","jpeg","png","docx"], accept_multiple_files=True)

    # Guardar
    if st.button("Notificar baja / permiso", type="primary"):
        try:
            # Guardar adjuntos
            carpeta = os.path.join(cfg.BAJAS_DIR, usuario_actual)
            os.makedirs(carpeta, exist_ok=True)
            saved = []
            if files:
                for f in files:
                    safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{f.name}"
                    path = os.path.join(carpeta, safe_name)
                    with open(path, "wb") as out:
                        out.write(f.getbuffer())
                    saved.append(path)
            guardar_baja(usuario_actual, tipo, fi_b, (ff_b if usar_fin else None), descripcion, saved)
            st.success("Baja / permiso registrado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"Error al registrar la baja: {e}")

    st.markdown("---")
    st.caption("Tus bajas / permisos comunicados")
    dfb = listar_bajas(usuario_actual)
    if dfb.empty:
        st.info("No hay bajas ni permisos registrados.")
    else:
        # Mostrar con posibilidad de descargar adjuntos
        for _, row in dfb.iterrows():
            with st.container(border=True):
                rango = f"{row['fecha_inicio']}" + (f" → {row['fecha_fin']}" if str(row['fecha_fin']).strip() else "")
                st.write(f"🧾 **{row['tipo']}** · {rango} · **{row['estado']}**")
                if str(row['descripcion']).strip():
                    st.caption(row['descripcion'])
                if str(row['archivos']).strip():
                    st.caption("Adjuntos:")
                    rutas = str(row['archivos']).split(';')
                    for i, ruta in enumerate([r for r in rutas if r]):
                        try:
                            with open(ruta, "rb") as f:
                                st.download_button(f"Descargar adjunto {i+1}", f.read(), file_name=os.path.basename(ruta), key=f"dl_{row['id']}_{i}")
                        except Exception:

                            st.caption(f"• {os.path.basename(ruta)} (no encontrado)")

                            st.caption(f"• {os.path.basename(ruta)} (no encontrado)")





