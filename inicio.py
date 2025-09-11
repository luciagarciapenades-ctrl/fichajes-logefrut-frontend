import streamlit as st
import supabase_login_shim as auth
import ui_pages as ui  # <- tu archivo renombrado

st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# ---- Estilos base: sin header, sin menú y con menos margen superior ----
st.markdown("""
<style>
/* Oculta header y toolbar de Streamlit */
header[data-testid="stHeader"] { display: none; }
div[data-testid="stToolbar"] { display: none; }

/* Oculta el menú de los tres puntos y el footer */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* Reduce padding/margen superior del contenido */
.block-container { padding-top: 0.25rem; padding-bottom: 0.5rem; }
.stApp { margin-top: 0 !important; }
</style>
""", unsafe_allow_html=True)

# fuerza login; si no hay sesión, hace st.stop() dentro
auth.generarLogin(__file__, go_to="inicio.py")

# si estamos aquí, hay usuario logueado
ui.render_home(st.session_state["usuario"])

    
   
