# pages/paginaDocumentos.py
import io, time, requests
from datetime import datetime
import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import fitz  # PyMuPDF

# App: login / menús (tu shim y helpers)
import supabase_login_shim as auth
import ui_pages as ui
from supabase import create_client

    
st.set_page_config(page_title="Documentos", layout="wide")

# ---- Login y menú estándar de tu app ----
# Tu shim hace stop() si no hay sesión "local" (cookie/CSV)
auth.generarLogin(__file__)
ui.generarMenuRoles(st.session_state.get("usuario", ""))

# ---- Supabase client (usa tus secrets) ----
from supabase import create_client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
# En tu proyecto la anon key está como VITE_SUPABASE_ANON_KEY (deja fallback por si acaso)
SUPABASE_ANON_KEY = st.secrets.get("VITE_SUPABASE_ANON_KEY") or st.secrets["SUPABASE_ANON_KEY"]
SR_KEY   = st.secrets.get("SUPABASE_SERVICE_ROLE")

sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ---------- Identidad (DEBE existir usuario autenticado en Supabase Auth) ----------
usuario_login = st.session_state.get("usuario", "").strip().lower()
if not usuario_login:
    st.warning("Acceso denegado. Inicia sesión.")
    st.stop()

user_id   = None
user_name = usuario_login.split("@")[0]
user_slug = user_name

# Si tenemos Service Role, intentamos resolver el user_id en Supabase Auth
if SR_KEY:
   try:
       admin = create_client(SUPABASE_URL, SR_KEY)
       page = admin.auth.admin.list_users(page=1, per_page=1000)
       users = page.get("users") if isinstance(page, dict) else getattr(page, "users", [])
       for u in users:
           email = (u.get("email") if isinstance(u, dict) else getattr(u, "email", "")) or ""
           if email.lower() == usuario_login:
               user_id = u.get("id") if isinstance(u, dict) else getattr(u, "id", None)
               break
   except Exception:
       pass 
if not user_id:
    st.error("No se pudo obtener tu usuario autenticado en Supabase.")

# ---------- Catálogo de documentos (rutas públicas en bucket 'docs') ----------
DOCS = [
    {
        "id": "IT-01-02",
        "title": "IT 01/02 Buenas prácticas de higiene",
        "url": "https://qsxftklemuciiodwfeot.supabase.co/storage/v1/object/public/docs/IT%2001-02%20BUENAS%20PRACTICAS%20DE%20HIGIENE%20(1).pdf",
    },
    {
        "id": "IT-03-02",
        "title": "IT 03/02 BP uso EPI/utillaje (incluye lavado)",
        "url": "https://qsxftklemuciiodwfeot.supabase.co/storage/v1/object/public/docs/IT%2003-02%20BP%20uso%20rops%20protecciOn%20(incluye%20lavado).pdf",
    },
    {
        "id": "IT-03-02-C",
        "title": "IT 03/02 C Instrucción de carga y descarga",
        "url": "https://qsxftklemuciiodwfeot.supabase.co/storage/v1/object/public/docs/IT%2003-02%20C%20INSTRUCCION%20DE%20CARGA%20Y%20DESCARGA%20DE%20MERCANCIAS%20rev01.pdf",
    },
    {
        "id": "MED-OBL",
        "title": "Medidas de obligado cumplimiento",
        "url": "https://qsxftklemuciiodwfeot.supabase.co/storage/v1/object/public/docs/MEDIDA%20OBLIGATORIAS%20LOGEFRUT.pdf",
    },
]

st.subheader("Documentos")

# ---------- Traer firmas del usuario (por user_id) ----------
if user_id:
    firmas = (
        sb.table("doc_signatures")
          .select("*")
          .eq("user_id", user_id)
          .execute()
          .data
    ) or []
else:
    firmas = []  # evita el error de UUID si aún no resolvimos el id

firmas_by_id = {r["doc_id"]: r for r in firmas}

# ---------- Listado ----------
for doc in DOCS:
    st.divider()
    left, right = st.columns([2, 1], vertical_alignment="center")

    with left:
        st.subheader(doc["title"])
        st.link_button("🔍 Ver documento", doc["url"])

        if doc["id"] in firmas_by_id:
            f = firmas_by_id[doc["id"]]
            dt_iso = f.get("signed_at") or f.get("uploaded_at")
            if dt_iso:
                # formateo simple sin depender de timezone
                fecha_txt = dt_iso.split(".")[0].replace("T", " ")
                st.caption(f"✅ Firmado — {fecha_txt}")
            else:
                st.caption("✅ Firmado")
        else:
            st.caption("⏳ Pendiente")

    with right:
        if doc["id"] in firmas_by_id:
            st.success("Ya está firmado")
            continue

        with st.expander("✍️ Firmar este documento", expanded=False):
            st.write("Traza tu firma en el recuadro (puedes usar el dedo).")

            canvas_res = st_canvas(
                fill_color="rgba(0,0,0,0)",
                stroke_color="#000000",
                background_color="#FFFFFF",
                height=180,
                width=480,
                drawing_mode="freedraw",
                stroke_width=2,
                key=f"canvas_{doc['id']}",
            )

            firmar = st.button("Firmar y enviar", type="primary", key=f"btn_{doc['id']}")
            if firmar:
                # 1) Firma dibujada
                imgdata = getattr(canvas_res, "image_data", None)
                if imgdata is None or (hasattr(imgdata, "any") and not imgdata.any()):
                    st.warning("Dibuja tu firma antes de enviar.")
                    st.stop()

                # 2) Descarga PDF original
                try:
                    pdf_resp = requests.get(doc["url"], timeout=20)
                    pdf_resp.raise_for_status()
                    pdf_bytes = pdf_resp.content
                except Exception as e:
                    st.error(f"No se pudo descargar el PDF original: {e}")
                    st.stop()

                # 3) Convierte firma a PNG y recorta
                img = Image.fromarray(imgdata.astype("uint8")).convert("RGBA")
                bbox = img.getbbox()
                if bbox:
                    img = img.crop(bbox)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                sig_png = buf.getvalue()

                # 4) Estampa firma en la última página (abajo derecha)
                pdf_in = fitz.open(stream=pdf_bytes, filetype="pdf")
                page = pdf_in[-1]
                rect = page.rect

                pix = fitz.Pixmap(sig_png)
                target_w = 180
                scale = target_w / pix.width
                new_w = target_w
                new_h = int(pix.height * scale)

                x = rect.x1 - new_w - 36
                y = rect.y1 - new_h - 36
                page.insert_image(fitz.Rect(x, y, x + new_w, y + new_h), stream=sig_png)

                text = f"Firmado por {user_name} — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                page.insert_text((36, rect.y1 - 36), text, fontsize=10, color=(0, 0, 0))

                out = io.BytesIO()
                pdf_in.save(out)
                pdf_in.close()
                signed_pdf = out.getvalue()

                # 5) Subir a Storage (bucket PRIVADO) guardando SOLO el PATH
                path = f"signed/{user_id}/{doc['id']}_{int(time.time())}.pdf"
                try:
                    sb.storage.from_("documentos_firmados").upload(
                        path, signed_pdf, {"content-type": "application/pdf"}
                    )
                    sb.table("doc_signatures").insert({
                        "user_id": user_id,
                        "doc_id": doc["id"],
                        "doc_title": doc["title"],
                        "signed_url": path,
                        "signed_at": datetime.utcnow().isoformat()
                    }).execute()
                except Exception as e:
                    st.error(f"No se pudo subir el documento firmado: {e}")
                    st.stop()

                # 6) Registrar en BD (user_id + path)
                sb.table("doc_signatures").insert({
                    "user_id": user_id,
                    "doc_id": doc["id"],
                    "doc_title": doc["title"],
                    "signed_url": path,                         # PATH en el bucket privado
                    "signed_at": datetime.utcnow().isoformat()  # para mostrar fecha
                }).execute()

                st.success("Documento firmado y enviado correctamente.")
                st.toast("¡Firmado!")
                st.rerun()
