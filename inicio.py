import streamlit as st
import supabase_login_shim as auth
import ui_pages as ui  # <- tu archivo renombrado

st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# fuerza login; si no hay sesión, hace st.stop() dentro
auth.generarLogin(__file__, go_to="inicio.py")

# si estamos aquí, hay usuario logueado
ui.render_home(st.session_state["usuario"])

    
   
