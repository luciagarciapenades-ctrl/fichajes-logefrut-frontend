import streamlit as st
import supabase_login_shim as auth
import ui_pages as ui  # <- tu archivo renombrado

st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# ---- Estilos base: sin header, sin menú y con menos margen superior ----
st.markdown("""
<style>
/* Oculta el menú de los tres puntos de Streamlit (versiones nuevas) */
#div[data-testid="stMainMenu"] { display: none !important; }
/* Compatibilidad con versiones antiguas */
MainMenu { visibility: hidden; }

/* Oculta header/toolbar y footer */
header[data-testid="stHeader"] { display: none !important; }
div[data-testid="stToolbar"] { display: none !important; }
footer { visibility: hidden; }

/* Reduce el hueco superior */
.block-container { padding-top: 0.25rem; padding-bottom: 0.5rem; }
.stApp { margin-top: 0 !important; }
</style>
""", unsafe_allow_html=True)

# fuerza login; si no hay sesión, hace st.stop() dentro
auth.generarLogin(__file__, go_to="inicio.py")

# si estamos aquí, hay usuario logueado
ui.render_home(st.session_state["usuario"])

    
   
