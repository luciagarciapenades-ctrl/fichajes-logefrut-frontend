import streamlit as st
import supabase_login_shim as auth      
import ui_pages as ui                    

st.set_page_config(page_title="Fichajes", page_icon="🕒", layout="centered")

# Muestra el login (si no está logueado hace st.stop())
auth.generarLogin(__file__)

# Si llega aquí, hay usuario → dibuja la home de tu app
ui.render_home(st.session_state["usuario"])


    
   