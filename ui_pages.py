import os
import streamlit as st
import pandas as pd
from datetime import datetime
#from streamlit_cookies_controller import CookieController 
try:
    from streamlit_cookies_controller import CookieController
except Exception:
    class CookieController:
        def set(self, *a, **k): pass
        def get(self, *a, **k): return None
        def remove(self, *a, **k): pass



# Option 1: Use double backslashes
LOGO_MAIN = "assets/logefrut_logo_transparente.png"     # portada
LOGO_SIDEBAR = "assets/logefrut_logo_transparente.png" #sidebar

def apply_base_chrome(page_title: str = "Fichajes"):
    """
    Aplica la “piel” común de la app:
    - Quita header, menú (⋮) y footer de Streamlit
    - Reduce el padding superior
    - Inicia con el sidebar colapsado
    """
    # Debe ejecutarse lo primero de la página; por si acaso, protegemos doble llamada
    try:
        st.set_page_config(
            page_title=page_title,
            layout="wide",
            initial_sidebar_state="collapsed",
            menu_items={}
        )
    except Exception:
        # set_page_config solo puede llamarse una vez por página
        pass

    st.markdown("""
    <style>
      /* Oculta header/toolbar/menu/footers de Streamlit */
      header[data-testid="stHeader"] { display: none !important; }
      div[data-testid="stToolbar"]  { display: none !important; }
      div[data-testid="stMainMenu"] { display: none !important; }
      #MainMenu { visibility: hidden; }
      footer { visibility: hidden; }

      /* Reduce hueco superior e inferior del contenido */
      .block-container { padding-top: .25rem; padding-bottom: .5rem; }
      .stApp { margin-top: 0 !important; }

      /* (Opcional) Oculta la nav automática de multipage en el sidebar */
      div[data-testid="stSidebarNav"]{ display:none !important; }
    </style>
    """, unsafe_allow_html=True)

def collapse_sidebar_on_load():
    """
    Colapsa el sidebar al cargar la página (útil tras navegar).
    """
    components.html("""
    <script>
      (function(){
        const clickIt = () => {
          const doc = parent.document;
          const btn = doc.querySelector('[data-testid="stSidebarCollapseButton"]');
          const sb  = doc.querySelector('[data-testid="stSidebar"]');
          if (btn && sb && getComputedStyle(sb).display !== 'none') btn.click();
        };
        setTimeout(clickIt, 0);
      })();
    </script>
    """, height=0, width=0)


# =========================
# Cookies / Sesión
# =========================
controller = CookieController()

# =========================
# Utilidades Home (Inicio)
# =========================
def _spanish_date(d: datetime) -> str:
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    return f"Hoy, {d.day} de {meses[d.month-1]}"

def _saludo(hora: int) -> str:
    if 6 <= hora < 13: return "¡Buenos días"
    if 13 <= hora < 20: return "¡Buenas tardes"
    return "¡Buenas noches"

def _leer_notificaciones(usuario: str) -> pd.DataFrame:
    """
    Lee notificaciones desde un CSV sencillo:
    columnas: usuario,titulo,fecha,leido (0/1)
    """
    try:
        df = pd.read_csv("notificaciones.csv")
        if "leido" not in df.columns:
            df["leido"] = 0
        df["leido"] = df["leido"].fillna(0).astype(int)
        return df[df["usuario"] == usuario].copy()
    except FileNotFoundError:
        return pd.DataFrame(columns=["usuario","titulo","fecha","leido"])

def _marcar_todas_leidas(usuario: str):
    try:
        df_all = pd.read_csv("notificaciones.csv")
    except FileNotFoundError:
        return
    if "leido" not in df_all.columns:
        df_all["leido"] = 0
    df_all.loc[df_all["usuario"] == usuario, "leido"] = 1
    df_all.to_csv("notificaciones.csv", index=False)

def render_home(usuario: str):
    # Portada sin navegación lateral automática y con FONDO en degradado
    #st.set_page_config(layout="wide", initial_sidebar_state="collapsed")
    st.markdown("""
    <style>
      /* Oculta la navegación automática del sidebar (pero no el sidebar entero) */
      div[data-testid="stSidebarNav"]{ display:none !important; }

      /* Fondo de TODA la app en degradado suave */
      [data-testid="stAppViewContainer"]{
        background: linear-gradient(180deg,#DDF1FA 0%,#FAF7E9 85%) !important;
      }

      /* Badge de notificaciones */
      .notif-badge{
        display:inline-block; background:#E11D48; color:#fff;
        border-radius:999px; font-size:12px; padding:2px 6px; line-height:1;
        margin-left:6px;
      }
    </style>
    """, unsafe_allow_html=True)

    # 1 Cargar notificaciones 
    ahora = datetime.now()
    df_notif = _leer_notificaciones(usuario)
    pendientes = df_notif[df_notif["leido"] == 0]
    n_pend = int(pendientes.shape[0])


    #st.image(LOGO_MAIN, use_column_width=True, width=220)

    # Saludo y fecha
    st.markdown('<div class="hero">', unsafe_allow_html=True)
    st.markdown(f"<h2 style='margin:0'>{_saludo(ahora.hour)}, {usuario}!</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='font-size:20px;opacity:.8;margin-top:6px'>{_spanish_date(ahora)}</p>", unsafe_allow_html=True)
    bell = st.button("🔔", key="home_bell", help="Ver notificaciones")
    if n_pend > 0:
        st.markdown(f"<div class='badge'>{n_pend}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Listado de notificaciones
    if bell:
        st.session_state["show_notifs"] = True
    if st.session_state.get("show_notifs", False):
        with st.expander(f"Notificaciones ({n_pend} pendientes)", expanded=True):
            if n_pend == 0:
                st.info("No tienes notificaciones pendientes.")
            else:
                for _, r in pendientes.iterrows():
                    st.markdown(f"**• {r.get('titulo','(sin título)')}** — {r.get('fecha','')}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Marcar todas como leídas"):
                    _marcar_todas_leidas(usuario)
                    st.session_state["show_notifs"] = False
                    st.rerun()
            with c2:
                if st.button("Cerrar"):
                    st.session_state["show_notifs"] = False
                    st.rerun()

    st.markdown("### ")
    # Accesos tipo “barra inferior”
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("🗓️ Fichaje", use_container_width=True):
            st.switch_page("pages/paginaFichajeMovil.py")   
    with c2:
        if st.button("🧾 Ausencias", use_container_width=True):
            st.switch_page("pages/paginaAusenciaMovil.py")
    with c3:
        if st.button("🧾 Modificar fechas", use_container_width=True):
            st.switch_page("pages/paginaModFechaMovil.py")
    with c4:
        if st.button("🧾 Documentos", use_container_width=True):
            st.switch_page("pages/paginaDocumentos.py")

    


# =========================
# Lógica original (menús/permisos)
# =========================
USUARIOS_CSV = os.path.join(os.path.dirname(__file__), "usuarios.csv")
PAGINAS_CSV = os.path.join(os.path.dirname(__file__), "rol_paginas.csv")

# ---------- Helpers robustos para cargar/filtrar usuarios ----------
def _load_users() -> pd.DataFrame:
    """Lee usuarios.csv y, si no existe 'usuario' pero sí 'email',
    crea 'usuario' como el prefijo del email."""
    df = pd.read_csv(USUARIOS_CSV)
    cols = {c.lower(): c for c in df.columns}
    if "usuario" not in cols and "email" in cols:
        c_email = cols["email"]
        df["usuario"] = df[c_email].astype(str).str.split("@").str[0]
    return df

def _match_user(df: pd.DataFrame, input_id: str) -> pd.DataFrame:
    """Devuelve las filas cuyo 'usuario' (prefijo) o 'email' coinciden
    con lo que escribió el usuario (insensible a mayúsculas/espacios)."""
    key = str(input_id).strip().lower()
    user_key = key.split("@")[0]

    cols = {c.lower(): c for c in df.columns}
    mask = pd.Series(False, index=df.index)

    if "usuario" in cols:
        cu = cols["usuario"]
        ser = df[cu].astype(str).str.strip().str.lower()
        mask |= ser.eq(user_key) | ser.eq(key)           # por si guardaste email entero en 'usuario'
    if "email" in cols:
        ce = cols["email"]
        mask |= df[ce].astype(str).str.strip().str.lower().eq(key)

    return df[mask]


def validarUsuario(usuario, clave):
    """Valida usuario/clave admitiendo email o usuario."""
    dfusuarios = _load_users()
    cand = _match_user(dfusuarios, usuario)
    ok = (not cand.empty) and (str(cand.iloc[0].get("clave", "")) == str(clave))
    return bool(ok)


def generarMenu(usuario):
    """Menú lateral simple con enlaces fijos por rol (robusto a email/usuario)."""
    with st.sidebar:
        st.markdown("""
        <style>
        [data-testid="stSidebar"] img{
            max-width: 140px;     
            margin: 8px auto 12px;
            display: block;
        }
        </style>
        """, unsafe_allow_html=True)

        st.image(LOGO_SIDEBAR, width=140) 
        dfusuarios = _load_users()
        dfUsuario = _match_user(dfusuarios, usuario)

        if dfUsuario.empty:
            st.warning("Usuario no encontrado en usuarios.csv")
            return

        row = dfUsuario.iloc[0]
        nombre = row.get("nombre", usuario)
        rol = row.get("rol", "")

        st.write(f"Hola **:blue-background[{nombre}]** ")
        st.caption(f"Rol: {rol}")
        st.subheader("Tableros")
        if rol in ['Fichaje','admin', 'empleado']:
            st.page_link("pages/paginaFichajeMovil.py", label="Fichajes", icon=":material/sell:")
        if rol in ['Ausencia','admin','empleado']:
            st.page_link("pages/paginaAusenciaMovil.py", label="Ausencia", icon=":material/group:")
        if rol in ['Modificación fecha','admin','empleado']:
            st.page_link("pages/paginaModFechaMovil.py", label="Modificaciones de fechas", icon=":material/group:")

        btnSalir = st.button("Salir")
        if btnSalir:
            st.session_state.clear()
            controller.remove('usuario')
            st.rerun()


def validarPagina(pagina, usuario):
    """Valida si un usuario tiene permiso a 'pagina' usando rol_paginas.csv o secrets."""
    dfusuarios = _load_users()
    dfPaginas = pd.read_csv(PAGINAS_CSV)

    dfUsuario = _match_user(dfusuarios, usuario)
    if dfUsuario.empty:
        return False

    rol = dfUsuario.iloc[0].get("rol", "")
    dfPagina = dfPaginas[(dfPaginas['pagina'].str.contains(pagina))]
    if len(dfPagina) > 0:
        if rol in dfPagina['roles'].values[0] or rol == "admin" or st.secrets.get("tipoPermiso","rol") == "rol":
            return True
        else:
            return False
    else:
        return False


def generarMenuRoles(usuario):
    """Menú lateral según csv de páginas/roles, con opción de ocultar o deshabilitar."""
    with st.sidebar:
        st.markdown("""
        <style>
        [data-testid="stSidebar"] img{
            max-width: 140px;
            margin: 8px auto 12px;
            display: block;
        }
        </style>
        """, unsafe_allow_html=True)

        st.image(LOGO_SIDEBAR, width=140)
        dfusuarios = _load_users()
        dfPaginas = pd.read_csv(PAGINAS_CSV)

        dfUsuario = _match_user(dfusuarios, usuario)
        if dfUsuario.empty:
            st.warning("Usuario no encontrado en usuarios.csv")
            return
        row = dfUsuario.iloc[0]
        nombre = row.get("nombre", usuario)
        rol = row.get("rol", "")

        st.write(f"Hola **:blue-background[{nombre}]** ")
        st.caption(f"Rol: {rol}")
        st.subheader("Opciones")

        ocultar = str(st.secrets.get("ocultarOpciones", "False")) == "True"
        if ocultar:
            if rol != 'admin':
                dfPaginas = dfPaginas[dfPaginas['roles'].str.contains(rol)]
            for _, r in dfPaginas.iterrows():
                st.page_link(r['pagina'], label=r['nombre'], icon=f":material/{r['icono']}:")
        else:
            for _, r in dfPaginas.iterrows():
                deshabilitarOpcion = not ((rol in r["roles"]) or rol == "admin")
                st.page_link(r['pagina'], label=r['nombre'], icon=f":material/{r['icono']}:", disabled=deshabilitarOpcion)

        btnSalir = st.button("Salir")
        if btnSalir:
            st.session_state.clear()
            controller.remove('usuario')
            st.rerun()


# =========================
# Login / Routing
# =========================
def generarLogin(archivo):
    """Monta el login, portada y menús."""
    # Recupera cookie si existe
    usuario = controller.get('usuario')
    if usuario:
        st.session_state['usuario'] = usuario

    if 'usuario' in st.session_state:
        # Portada Inicio limpia con notificaciones
        if archivo.lower() == "inicio.py":
            render_home(st.session_state['usuario'])
        else:
            # Menú lateral (por roles de página o por roles simples)
            if st.secrets.get("tipoPermiso","rol") == "rolpagina":
                generarMenuRoles(st.session_state['usuario'])
            else:
                generarMenu(st.session_state['usuario'])

            # Validación de permisos para la página actual
            if not validarPagina(archivo, st.session_state['usuario']):
                st.error(f"No tiene permisos para acceder a esta página {archivo}", icon=":material/gpp_maybe:")
                st.stop()
    else:
        # Formulario de login
        with st.form('frmLogin'):
            parUsuario = st.text_input('Usuario')
            parPassword = st.text_input('Password', type='password')
            btnLogin = st.form_submit_button('Ingresar', type='primary')
            if btnLogin:
                if validarUsuario(parUsuario, parPassword):
                    st.session_state['usuario'] = parUsuario
                    controller.set('usuario', parUsuario)
                    st.rerun()
                else:
                    st.error("Usuario o clave inválidos", icon=":material/gpp_maybe:")

