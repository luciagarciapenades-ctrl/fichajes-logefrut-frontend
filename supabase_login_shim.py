
import os
import streamlit as st
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY")

_client = None
def _get_client():
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise RuntimeError("Falta SUPABASE_URL / SUPABASE_ANON_KEY (env o st.secrets)")
        _client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _client

def generarLogin(archivo_actual: str = "", go_to: str = "inicio.py"):
    """
    Muestra login si no hay sesión. Cuando el usuario entra,
    guarda user_id/email en session_state y navega a 'go_to' (inicio.py).
    Si ya hay sesión, simplemente retorna.
    """
    # Ya logueado → nada que hacer
    if st.session_state.get("user_id"):
        return

    st.subheader("Iniciar sesión")
    email = st.text_input("Email")
    pwd   = st.text_input("Contraseña", type="password")
    c1, c2 = st.columns(2)

    if c1.button("Entrar") and email and pwd:
        # Si las credenciales son válidas, guardamos y navegamos a Inicio
        res = _get_client().auth.sign_in_with_password({"email": email, "password": pwd})
        st.session_state["user_id"] = res.user.id
        st.session_state["usuario"] = res.user.email  # tu UI ya admite email o usuario
        st.success("Sesión iniciada")
        st.switch_page(go_to)  # <- la clave para no “quedarte” en el login

    if c2.button("Crear cuenta") and email and pwd:
        try:
            _get_client().auth.sign_up({"email": email, "password": pwd})
            st.info("Revisa tu email para confirmar la cuenta y vuelve a iniciar sesión.")
        except Exception as e:
            st.error(f"Error al crear cuenta: {e}")

    # Si aún no hay sesión, no ejecutes nada más de la página
    if not st.session_state.get("user_id"):
        st.stop()
