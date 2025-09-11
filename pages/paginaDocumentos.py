# pages/paginaDocumentos.py
import io, time, base64, requests
from datetime import datetime
import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import fitz  # PyMuPDF

import supabase_login_shim as auth
import ui_pages as ui

st.set_page_config(page_title="Documentos", layout="wide")

# login/menú/permisos estándar de tu app
auth.generarLogin(__file__)  # tu shim ya corta si no hay sesión
ui.generarMenuRoles(st.session_state.get("usuario",""))  # o generarMenu(...)

# ---------- Config Supabase (usa tus helpers si ya tienes uno) ----------
from supabase import create_client
SUPABASE_URL = st.secrets["SUPABASE_URL"]  # ya lo usas en la app
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Datos del usuario
usuario_login = st.session_state.get("usuario","")
user_email = usuario_login
user_key = user_email.lower().strip()
user_name = user_key.split("@")[0]
user = sb.auth.get_user()
user_id = user.user.id if user and user.user else None

if not user_id:
    st.error("No se pudo obtener tu usuario autenticado.")
    st.stop()

# ---------- Catálogo de documentos (id, título y ruta en bucket 'docs') ----------
DOCS = [
    {"id":"IT-01-02", "title":"IT 01/02 Buenas prácticas de higiene",
     "url": "https://qsxftklemuciiodwfeot.supabase.co/storage/v1/object/public/docs/IT%2001-02%20BUENAS%20PRACTICAS%20DE%20HIGIENE%20(1).pdf"},
    {"id":"IT-03-02", "title":"IT 03/02 Buenas prácticas: EPI / envases",
     "url": https://qsxftklemuciiodwfeot.supabase.co/storage/v1/object/public/docs/IT%2003-02%20BP%20uso%20rops%20protecciOn%20(incluye%20lavado).pdf"},
    {"id":"IT-03-02-C", "title":"IT 03/02 C Instrucción carga y descarga",
     "url": "https://qsxftklemuciiodwfeot.supabase.co/storage/v1/object/public/docs/IT%2003-02%20C%20INSTRUCCION%20DE%20CARGA%20Y%20DESCARGA%20DE%20MERCANCIAS%20rev01.pdf"},
    {"id":"MED-OBL", "title":"Medidas de obligado cumplimiento",
     "url": "https://qsxftklemuciiodwfeot.supabase.co/storage/v1/object/public/docs/MEDIDA%20OBLIGATORIAS%20LOGEFRUT.pdf"},
]

st.title("📄 Documentos para firma")

# Trae firmas existentes para marcar estado
firmas = sb.table("doc_signatures").select("*").eq("user_id", user_id).execute().data
firmas_by_id = {r["doc_id"]: r for r in (firmas or [])}

for doc in DOCS:
    st.divider()
    left, right = st.columns([2,1], vertical_alignment="center")
    with left:
        st.subheader(doc["title"])
        st.link_button("🔍 Ver documento", doc["url"])
        estado = "✅ Firmado" if doc["id"] in firmas_by_id else "⏳ Pendiente"
        if doc["id"] in firmas_by_id:
            f = firmas_by_id[doc["id"]]
            st.caption(f"{estado} — {datetime.fromisoformat(f['signed_at']).strftime('%d/%m/%Y %H:%M')}")
        else:
            st.caption(estado)

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
                key=f"canvas_{doc['id']}"
            )

            firmar = st.button("Firmar y enviar", type="primary", key=f"btn_{doc['id']}")
            if firmar:
                if not canvas_res.image_data.any():
                    st.warning("Dibuja tu firma antes de enviar.")
                    st.stop()

                # 1) Descarga PDF original
                pdf_bytes = requests.get(doc["url"]).content

                # 2) Convierte la firma (PNG) desde el canvas
                img = Image.fromarray((canvas_res.image_data).astype("uint8")).convert("RGBA")
                # recorta bordes en blanco
                bbox = img.getbbox()
                if bbox:
                    img = img.crop(bbox)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                sig_png = buf.getvalue()

                # 3) Estampa la firma en la última página (abajo a la derecha)
                pdf_in = fitz.open(stream=pdf_bytes, filetype="pdf")
                page = pdf_in[-1]
                zoom = 1.0
                sig = fitz.Pixmap(sig_png)
                # escala firma a ancho ~180 px a 72dpi
                target_w = 180
                scale = target_w / sig.width
                new_w = target_w
                new_h = int(sig.height * scale)

                # posición (margen 36pt)
                rect = page.rect
                x = rect.x1 - new_w - 36
                y = rect.y1 - new_h - 36
                page.insert_image(fitz.Rect(x, y, x+new_w, y+new_h), stream=sig_png)

                # fecha y nombre
                text = f"Firmado por {user_name} — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                page.insert_text((36, rect.y1 - 36), text, fontsize=10, color=(0,0,0))

                out = io.BytesIO()
                pdf_in.save(out)
                pdf_in.close()
                signed_pdf = out.getvalue()

                # 4) Sube a Storage (signed-docs)
                path = f"signed/{user_id}/{doc['id']}_{int(time.time())}.pdf"
                sb.storage.from_("signed-docs").upload(path, signed_pdf, {"content-type":"application/pdf"})

                # 5) Inserta registro
                public_url = sb.storage.from_("signed-docs").get_public_url(path)  # si bucket es privado, omite esto
                sb.table("doc_signatures").insert({
                    "user_id": user_id,
                    "doc_id": doc["id"],
                    "doc_title": doc["title"],
                    "signed_url": path,
                }).execute()

                st.success("Documento firmado y enviado correctamente.")
                st.toast("¡Firmado!")
                st.rerun()
