import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import sqlite3
import hmac, hashlib, base64, time

# Login y componentes
#import login as login
import os, sys
ROOT = os.path.dirname(os.path.dirname(__file__))  # .../app
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import supabase_login_shim as auth
import ui_pages as ui
from api_client import post_fichaje as _post_fichaje, get_fichajes as _get_fichajes
from streamlit_geolocation import streamlit_geolocation
from geopy.distance import geodesic

# Dependencias opcionales para QR
# - streamlit_qrcode_scanner (preferido si está instalado)
# - Pillow + pyzbar como fallback por imagen
try:
    from streamlit_qrcode_scanner import qrcode_scanner  # type: ignore
except Exception:
    qrcode_scanner = None

try:
    from PIL import Image
    from pyzbar.pyzbar import decode as decode_qr  # type: ignore
except Exception:
    Image = None
    decode_qr = None

# ======== Config ========
BASE_DIR = st.secrets.get("DATA_DIR", "C:\\FichajesMovil\\data")
DB_FICHAJES = os.path.join(BASE_DIR, "fichajes.db")
DB_RRHH     = os.path.join(BASE_DIR, "rrhh.db")
BAJAS_DIR   = os.path.join(BASE_DIR, "bajas_adjuntos")
os.makedirs(BAJAS_DIR, exist_ok=True)

# Coordenadas de la oficina (lat, lon) y radio permitido (km)
OFFICE_COORD = (41.51762, 2.19930)
DISTANCIA_MAXIMA = 0.1  # 100 m

# ======== Login ========
auth.generarLogin(__file__)    # garantiza sesión
ui.generarMenuRoles(st.session_state["usuario"])

# ======== DB (SQLite) ========
DB_FILE = DB_FICHAJES
TABLE = "fichajes"

##eliminar 3 puntos 
def boot():
    st.set_page_config(
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={"Get help": None, "Report a bug": None, "About": None}
    )
    st.markdown("""
    <style>
      /* Ocultar menú 3 puntos y footer */
      div[data-testid="stMainMenu"] { visibility: hidden; }
      #MainMenu { visibility: hidden; } /* compat */
      footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

def get_conn():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    return sqlite3.connect(DB_FILE)

def ensure_schema():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empleado TEXT NOT NULL,
                fecha_local TEXT NOT NULL,   -- 'YYYY-MM-DD HH:MM:SS'
                fecha_utc   TEXT NOT NULL,   -- 'YYYY-MM-DD HH:MM:SS' (UTC)
                tipo TEXT NOT NULL CHECK (tipo IN ('Entrada','Salida')),
                observaciones TEXT,
                fuente TEXT DEFAULT 'movil',
                created_at_utc TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()

def insertar_fichaje(empleado: str, tipo: str, observaciones: str, *, fuente: str = "movil") -> dict:
    """Inserta el fichaje en el backend."""
    user_id = st.session_state["user_id"]
    try:
        return _post_fichaje(
            user_id=user_id,
            empleado=empleado,
            tipo=tipo,
            observ=observaciones,
            fuente=fuente,
        )
    except Exception as e:
        st.error(f"No se pudo registrar el fichaje: {e}")
        raise


def cargar_historial(limit: int = 100, empleado_filtro: str | None = None) -> pd.DataFrame:
    """Carga historial desde el backend, mantiene filtro por empleado y orden DESC."""
    user_id = st.session_state["user_id"]
    try:
        data = _get_fichajes(user_id=user_id, limit=limit)
        df = pd.DataFrame(data)

        if df.empty:
            return df

        # Asegurar columnas esperadas por tu UI
        for col in ["empleado", "fecha_local", "tipo", "observaciones", "fuente"]:
            if col not in df.columns:
                df[col] = ""

        # Filtro por empleado (si lo usabas)
        if empleado_filtro:
            df = df[df["empleado"] == empleado_filtro]

        # Orden descendente como hacías con ORDER BY id DESC
        df["fecha_local"] = pd.to_datetime(df["fecha_local"])
        df = df.sort_values("fecha_local", ascending=False).head(limit).reset_index(drop=True)

        # Devolver en el mismo orden de columnas que pintas en la tabla
        return df[["empleado", "fecha_local", "tipo", "observaciones", "fuente"]]
    except Exception as e:
        st.error(f"No se pudo cargar el historial: {e}")
        return pd.DataFrame(columns=["empleado", "fecha_local", "tipo", "observaciones", "fuente"])


# ===== Rotación de QR cada ~48h =====
# Usamos HMAC-SHA256 sobre un contador de tiempo (epoch // periodo)
# El secreto debe estar en secrets: QR_SECRET="tu_uuid_super_secreto"
QR_SECRET = st.secrets.get("QR_SECRET", "cambia_esto_por_un_uuid_largo_y_secreto")
QR_PREFIX = "FICHAJE:"  # prefijo para reconocer nuestros QR
QR_PERIOD_HOURS = int(st.secrets.get("QR_PERIOD_HOURS", 48))  # periodo ~2 días
QR_ALLOWED_SKEW = 1  # aceptamos el periodo actual +/- 1 para tolerar reloj

def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("utf-8")

def _token_for_counter(counter: int) -> str:
    mac = hmac.new(QR_SECRET.encode("utf-8"), str(counter).encode("utf-8"), hashlib.sha256).digest()
    return _b64url(mac)[:12]  # 12 caracteres, suficiente y legible

def current_qr_token(at_ts: float | None = None) -> str:
    if at_ts is None:
        at_ts = time.time()
    period = QR_PERIOD_HOURS * 3600
    counter = int(at_ts // period)
    return _token_for_counter(counter)

def valid_qr_tokens(at_ts: float | None = None) -> list[str]:
    if at_ts is None:
        at_ts = time.time()
    period = QR_PERIOD_HOURS * 3600
    counter = int(at_ts // period)
    tokens = []
    for c in range(counter - QR_ALLOWED_SKEW, counter + QR_ALLOWED_SKEW + 1):
        tokens.append(_token_for_counter(c))
    return tokens

def build_qr_payload(token: str) -> str:
    return f"{QR_PREFIX}{token}"

def is_qr_payload_valid(payload: str) -> bool:
    if not payload or not payload.startswith(QR_PREFIX):
        return False
    token = payload[len(QR_PREFIX):].strip()
    return token in valid_qr_tokens()

# ====== UI ======
ensure_schema()

st.header("Fichaje")

# Usuario autenticado
usuario_log = st.session_state.get("usuario")
if not usuario_log:
    st.warning("Inicia sesión para fichar.")
    st.stop()

# --- Método de fichaje: Geolocalización o QR ---
metodo = st.radio("¿Cómo quieres fichar?", ["Geolocalización", "QR"], horizontal=True)

permitir_fichaje = False
motivo_bloqueo = None
fuente_registro = "movil_geo" if metodo == "Geolocalización" else "movil_qr"

if metodo == "Geolocalización":
    location = streamlit_geolocation()
    if location and location.get("latitude"):
        user_coords = (location["latitude"], location["longitude"])
        distancia = geodesic(user_coords, OFFICE_COORD).km
        st.info(f"Distancia a la oficina: {distancia*1000:.2f} metros")
        permitir_fichaje = distancia <= DISTANCIA_MAXIMA
        if not permitir_fichaje:
            motivo_bloqueo = f"Estás a más de {int(DISTANCIA_MAXIMA*1000)} m de la oficina."
    else:
        motivo_bloqueo = "No se pudo obtener tu ubicación. Permite el acceso a la ubicación en tu navegador."
else:
    st.caption("Escanea el QR de la oficina.")
    qr_texto = None
    error_escanner = None

    if qrcode_scanner is not None:
        try:
            qr_texto = qrcode_scanner("Abrir cámara y escanear")
        except Exception as e:
            error_escanner = str(e)
            st.info("No se pudo usar el escáner directo. Probamos con la cámara del móvil como alternativa.")

    # 2) Intento B (fallback): usar la cámara nativa de Streamlit y decodificar la foto
    if not qr_texto:
        img_file = st.camera_input("Usar cámara del móvil (foto del QR)")
        if img_file and Image is not None and decode_qr is not None:
            try:
                img = Image.open(img_file)
                results = decode_qr(img)
                if results:
                    qr_texto = results[0].data.decode("utf-8", errors="ignore")
                    st.write(f"QR leído: `{qr_texto}`")
                else:
                    st.warning("No se detectó ningún QR en la imagen. Acerca un poco más y asegúrate de que esté enfocado.")
            except Exception as e:
                st.error(f"No se pudo procesar la imagen del QR: {e}")
        elif img_file and (Image is None or decode_qr is None):
            st.error("Falta instalar Pillow/pyzbar para decodificar el QR a partir de la foto.")

    # Validación del QR y estado de fichaje
    if qr_texto:
        if is_qr_payload_valid(qr_texto):
            st.success("QR válido. Puedes fichar.")
            permitir_fichaje = True
        else:
            motivo_bloqueo = "QR no válido o caducado."
    else:
        if error_escanner:
            st.warning(f"No se pudo abrir la cámara con el escáner directo: {error_escanner}")
        if motivo_bloqueo is None:
            motivo_bloqueo = "Aún no has escaneado un QR válido."

    

# Observaciones
observaciones = st.text_area("Observaciones (opcional)", placeholder="Escribe un comentario si lo necesitas")

# Botones de fichaje
c1, c2 = st.columns(2)
if permitir_fichaje:
    with c1:
        if st.button("Fichar ENTRADA", type="primary", use_container_width=True):
            try:
                reg = insertar_fichaje(usuario_log, "Entrada", observaciones, fuente=fuente_registro)
                fecha_txt = reg.get("fecha_local") or reg.get("fecha_utc") \
                            or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success(f"Entrada registrada — {'fecha_txt'}")
                st.cache_data.clear()
                
            except Exception as e:
                st.error(f"Error al registrar la entrada: {e}")
            else:
                st.rerun()
    with c2:
        if st.button("Fichar SALIDA", use_container_width=True):
            try:
                reg = insertar_fichaje(usuario_log, "Salida", observaciones, fuente=fuente_registro)
                fecha_txt = reg.get("fecha_local") or reg.get("fecha_utc") \
                            or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success(f"Salida registrada — {'fecha_txt'}")
                st.cache_data.clear()
                
            except Exception as e:
                st.error(f"Error al registrar la salida: {e}")
            else:
                st.rerun()
else:
    if motivo_bloqueo:
        st.warning(motivo_bloqueo)



# ===== Historial del usuario =====
st.subheader("Tus últimos fichajes")
df_hist = cargar_historial(limit=200, empleado_filtro=usuario_log)
if not df_hist.empty:
    df_hist = df_hist.rename(columns={
        "empleado": "Empleado",
        "fecha_local": "Fecha y hora",
        "tipo": "Tipo de fichaje",
        "observaciones": "Observaciones",
        "fuente": "Método",
    })
st.dataframe(df_hist, use_container_width=True)






