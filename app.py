import streamlit as st
import pandas as pd
import altair as alt
import google.genai as genai
import io
import re

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="Sabertec | Agente Inteligente de Auditoría", layout="wide")

GEMINI_API_KEY = "AQ.Ab8RN6JsAK9Sr2sqdsbF67Yn3wez6FlbAnMa_pWnrLsCn-qzoQ"

st.markdown("""
    <style>
    .stApp { background-color: #F8FAFC; }
    h1 { color: #0F172A; }
    .cta-box { background-color: #0F172A; color: #FFFFFF; padding: 20px; border-radius: 10px; text-align: center; margin-top: 30px; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Sabertec | Agente IA de Auditoría y Riesgos")
st.markdown("Sube tus archivos de **Conciliación, Ventas y Riesgo/Cumplimiento** para ejecutar el análisis completo, gráficos y reportes exportables.")

uploaded_files = st.file_uploader("Sube todos tus archivos (Excel o CSV)", accept_multiple_files=True, type=["csv", "xlsx"])
user_prompt = st.text_area("Instrucción para el agente:", value="Realiza una auditoría integral.", height=100)

# FUNCIÓN DE PDF CON DETECCIÓN INTELIGENTE DE SUBTÍTULOS EN NEGRITA
def create_clean_pdf(texto_informe, dfs_dict):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#0F172A'), alignment=1, spaceAfter=12)
    
    heading_style = ParagraphStyle('HeadingStyle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#0F172A'), spaceBefore=12, spaceAfter=4, fontName='Helvetica-Bold')
    
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#334155'), spaceAfter=5, leading=12)
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#1E293B'), leading=9)

    elements.append(Paragraph("SABERTEC - Dictamen Gerencial de Auditoría", title_style))
    elements.append(Spacer(1, 5))

    texto_limpio_ia = re.sub(r'\*\*', '', texto_informe)
    texto_limpio_ia = re.sub(r'#+\s?', '', texto_limpio_ia)

    elements.append(Paragraph("Informe Ejecutivo", heading_style))
    
    for paragraph in texto_limpio_ia.split('\n'):
        p_text = paragraph.strip()
        if p_text and not p_text.startswith('---'):
            es_subtitulo = (
                p_text.isupper() and len(p_text) > 4 or 
                p_text.endswith(':') or 
                any(keyword in p_text.upper() for keyword in ["RESUMEN EJECUTIVO", "HALLAZGOS", "DICTAMEN", "RECOMENDACIONES", "ÁREA"])
            )
            
            if es_subtitulo:
                elements.append(Paragraph(p_text, heading_style))
            else:
                elements.append(Paragraph(p_text, body_style))
    
    elements.append(Spacer(1, 10))

    ancho_pagina_util = 540 

    for nombre, df in dfs_dict.items():
        elements.append(Paragraph(f"Anexo: {nombre}", heading_style))
        
        df_sample = df.head(8).fillna("")
        
        table_data = []
        header_row = [Paragraph(f"<b>{str(col)}</b>", cell_style) for col in df_sample.columns]
        table_data.append(header_row)
        
        for _, row in df_sample.iterrows():
            row_data = [Paragraph(str(val), cell_style) for val in row.values]
            table_data.append(row_data)
            
        num_cols = len(df_sample.columns)
        col_width = ancho_pagina_util / max(num_cols, 1)
        col_widths = [col_width] * num_cols

        t = Table(table_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,0), 4),
            ('TOPPADDING', (0,0), (-1,0), 4),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F8FAFC')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 10))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

if st.button("🧠 Activar Razonamiento del Agente", type="primary"):
    if not uploaded_files or not user_prompt:
        st.warning("⚠️ Por favor, sube al menos un archivo y escribe una instrucción.")
    else:
        with st.spinner("🤖 El agente está leyendo los documentos y analizando..."):
            contexto_documentos = ""
            dfs_cargados = {}
            for arch in uploaded_files:
                try:
                    if arch.name.endswith(".xlsx"):
                        xls = pd.ExcelFile(arch)
                        for sheet_name in xls.sheet_names:
                            df_sheet = pd.read_excel(xls, sheet_name=sheet_name)
                            clave_nombre = f"{arch.name} - {sheet_name}"
                            dfs_cargados[clave_nombre] = df_sheet
                            contexto_documentos += f"\n\n=== ARCHIVO: {arch.name} | HOJA: {sheet_name} ===\n" + df_sheet.head(15).to_string()
                    else:
                        df_csv = pd.read_csv(arch)
                        dfs_cargados[arch.name] = df_csv
                        contexto_documentos += f"\n\n=== ARCHIVO CSV: {arch.name} ===\n" + df_csv.head(15).to_string()
                except Exception as e:
                    contexto_documentos += f"\nError leyendo {arch.name}: {str(e)}"

            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                instruccion_maestra_permanente = """
                ERES UN AGENTE AUDITOR SENIOR DE SABERTEC.
                Tus reglas de oro son:
                1. Realiza una auditoría integral cruzando la conciliación bancaria, el riesgo y las ventas.
                2. REGLA ESTRICTA: Redacta el informe única y exclusivamente en lenguaje gerencial, ejecutivo y de auditoría profesional. NO incluyas código de programación, bloques de código, ni menciones a Python o librerías técnicas en el texto del dictamen.
                3. Estructura el dictamen con resumen ejecutivo, hallazgos críticos y recomendaciones de acción concretas.
                """
                prompt_final = f"{instruccion_maestra_permanente}\nINSTRUCCIÓN DEL USUARIO: {user_prompt}\nA continuación tienes los datos extraídos:\n{contexto_documentos}"

                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=prompt_final
                )

                st.session_state['analisis_hecho'] = True
                st.session_state['informe_texto'] = response.text
                st.session_state['dfs_cargados'] = dfs_cargados
                st.session_state['pdf_data'] = create_clean_pdf(response.text, dfs_cargados)

            except Exception as err:
                st.error(f"⚠️ Error de conexión con Google Gemini: {str(err)}")

if st.session_state.get('analisis_hecho', False):
    st.success("✅ Análisis gerencial completado con éxito.")
    st.markdown("### 📋 Dictamen del Agente")
    st.markdown(st.session_state['informe_texto'])

    st.markdown("---")
    st.markdown("### 📊 Visualizaciones y Gráficos del Agente")
    col_g1, col_g2 = st.columns(2)
    dfs_cargados = st.session_state['dfs_cargados']
    
    with col_g1:
        st.markdown("#### 🏆 Top de Análisis / Ventas")
        grafico_pintado = False
        # 1. Intento con palabras clave tradicionales
        for nombre, df in dfs_cargados.items():
            if any(kw in nombre.upper() for kw in ["VENT", "PRODUCTO", "CLIENTE"]):
                num_cols = df.select_dtypes(include=['number']).columns
                cat_cols = df.select_dtypes(include=['object', 'category']).columns
                if len(num_cols) > 0 and len(cat_cols) > 0:
                    df_top = df.sort_values(by=num_cols[0], ascending=False).head(10)
                    chart = alt.Chart(df_top).mark_bar().encode(
                        x=alt.X(f'{cat_cols[0]}:N', sort='-y', title='Categoría'),
                        y=alt.Y(f'{num_cols[0]}:Q', title='Valor'),
                        color=alt.Color(f'{cat_cols[0]}:N', legend=None)
                    ).properties(height=300)
                    st.altair_chart(chart, use_container_width=True)
                    grafico_pintado = True
                    break
        # 2. Respaldo inteligente: Si no coincidió el nombre, toma el primer archivo con datos aptos
        if not grafico_pintado:
            for nombre, df in dfs_cargados.items():
                num_cols = df.select_dtypes(include=['number']).columns
                cat_cols = df.select_dtypes(include=['object', 'category']).columns
                if len(num_cols) > 0 and len(cat_cols) > 0:
                    df_top = df.head(10)
                    chart = alt.Chart(df_top).mark_bar().encode(
                        x=alt.X(f'{cat_cols[0]}:N', sort='-y', title='Categoría'),
                        y=alt.Y(f'{num_cols[0]}:Q', title='Valor'),
                        color=alt.Color(f'{cat_cols[0]}:N', legend=None)
                    ).properties(height=300)
                    st.altair_chart(chart, use_container_width=True)
                    break

    with col_g2:
        st.markdown("#### ⚠️ Análisis de Riesgo / Cumplimiento")
        grafico_riesgo_pintado = False
        # 1. Intento con palabras clave tradicionales
        for nombre, df in dfs_cargados.items():
            if any(kw in nombre.upper() for kw in ["RIESGO", "CUMPLIMIENTO", "MOR", "ESTADO"]):
                cat_cols = df.select_dtypes(include=['object', 'category']).columns
                if len(cat_cols) > 0:
                    col_conteo = cat_cols[0]
                    df_riesgo_counts = df[col_conteo].value_counts().reset_index()
                    df_riesgo_counts.columns = ['Nivel_Riesgo', 'Cantidad']
                    chart_risk = alt.Chart(df_riesgo_counts).mark_arc(innerRadius=50).encode(
                        theta=alt.Theta(field="Cantidad", type="quantitative"),
                        color=alt.Color(field="Nivel_Riesgo", type="nominal"),
                        tooltip=['Nivel_Riesgo', 'Cantidad']
                    ).properties(height=300)
                    st.altair_chart(chart_risk, use_container_width=True)
                    grafico_riesgo_pintado = True
                    break
        # 2. Respaldo inteligente para gráficos circulares
        if not grafico_riesgo_pintado:
            for nombre, df in dfs_cargados.items():
                cat_cols = df.select_dtypes(include=['object', 'category']).columns
                if len(cat_cols) > 0:
                    col_conteo = cat_cols[0]
                    df_riesgo_counts = df[col_conteo].value_counts().reset_index()
                    df_riesgo_counts.columns = ['Categoria', 'Cantidad']
                    chart_risk = alt.Chart(df_riesgo_counts).mark_arc(innerRadius=50).encode(
                        theta=alt.Theta(field="Cantidad", type="quantitative"),
                        color=alt.Color(field="Categoria", type="nominal"),
                        tooltip=['Categoria', 'Cantidad']
                    ).properties(height=300)
                    st.altair_chart(chart_risk, use_container_width=True)
                    break

    st.markdown("---")
    st.markdown("### 📥 Exportar Resultados y Reportes")
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for nombre, df in dfs_cargados.items():
                sheet_clean = nombre[:31].replace(":", "").replace("/", "-")
                df.to_excel(writer, sheet_name=sheet_clean, index=False)
        st.download_button("📊 Descargar Datos Consolidados en Excel", data=output.getvalue(), file_name="Auditoria_Sabertec_Consolidado.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with col_exp2:
        st.download_button("📄 Descargar Dictamen en PDF Profesional", data=st.session_state['pdf_data'], file_name="Dictamen_Gerencial_Sabertec.pdf", mime="application/pdf")

    st.markdown("""
        <div class="cta-box">
            <h3>🚀 ¿Quieres implementar este Agente IA en los procesos de tu empresa?</h3>
            <p>Optimiza tu contabilidad, detecta riesgos a tiempo y automatiza tus reportes con la tecnología de Sabertec.</p>
        </div>
    """, unsafe_allow_html=True)
    
    col_cta1, col_cta2 = st.columns(2)
    with col_cta1:
        email_lead = st.text_input("Ingresa tu correo corporativo:", placeholder="tu-correo@empresa.com", key="input_lead")
    with col_cta2:
        st.write("")
        st.write("")
        if st.button("📩 Solicitar Asesoría con Sabertec", type="primary"):
            if email_lead and "@" in email_lead:
                st.success(f"¡Gracias! Hemos registrado tu solicitud para el correo **{email_lead}**. Nos pondremos en contacto contigo.")
            else:
                st.warning("Por favor ingresa un correo electrónico válido.")
