
import os
import streamlit as st
from supabase import create_client

# Mostrar solo mensajes de usuario (sin tracebacks) en producción
st.set_option("client.showErrorDetails", False)

# Import específico de los errores de autenticación de Supabase (gotrue)
try:
    from gotrue.errors import AuthApiError  # pip install supabase
except Exception:  # por si cambia el paquete
    class AuthApiError(Exception):
        pass

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
        try:
            with st.spinner("Verificando credenciales..."):
                res = _get_client().auth.sign_in_with_password({"email": email, "password": pwd})
        except AuthApiError:
            # Caso típico: "Invalid login credentials"
            st.error("Credenciales no válidas. Inténtalo de nuevo.")
            st.stop()
        except Exception:
            # Otros fallos (red, servidor, etc.) sin mostrar traceback
            st.error("No se pudo iniciar sesión. Revisa la conexión e inténtalo más tarde.")
            st.stop()
        else:
            # Extra por seguridad si la librería no lanzó error pero no devolvió user
            if not res or not getattr(res, "user", None):
                st.error("No se pudo iniciar sesión. Inténtalo de nuevo.")
                st.stop()

            st.session_state["user_id"] = res.user.id
            st.session_state["usuario"] = res.user.email
            st.success("Sesión iniciada")
            try:
                st.switch_page(go_to)
            except Exception:
                # Si no estás en multipage, al menos refrescamos
                st.experimental_rerun()

    if c2.button("Crear cuenta") and email and pwd:
        try:
            _get_client().auth.sign_up({"email": email, "password": pwd})
            st.info("Revisa tu email para confirmar la cuenta y vuelve a iniciar sesión.")
        except Exception as e:
            st.error(f"Error al crear cuenta: {e}")

    # Si aún no hay sesión, no ejecutes nada más de la página
    if not st.session_state.get("user_id"):
        st.stop()

