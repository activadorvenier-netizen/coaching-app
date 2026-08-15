import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_option_menu import option_menu
from datetime import datetime, date
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# ------------------------------------------------
# CONFIG APP
# ------------------------------------------------

st.set_page_config(
    page_title="Coaching Ventas",
    page_icon="📈",
    layout="wide"
)

if "form_id" not in st.session_state:
    st.session_state.form_id = 0

# ------------------------------------------------
# GOOGLE SHEETS CONFIG
# ------------------------------------------------

SHEET_ID = "1qRsvFn62DlMYx4xHtbboYNiOh2flj-JQcaiJ9taTmjE"

# ------------------------------------------------
# FUNCIONES GOOGLE SHEETS
# ------------------------------------------------

def conectar_gsheets():
    """Conecta a Google Sheets usando Service Account"""
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Buscar credentials.json en la misma carpeta
        script_dir = os.path.dirname(os.path.abspath(__file__))
        creds_path = os.path.join(script_dir, "credentials.json")
        
        if os.path.exists(creds_path):
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                creds_path, scope
            )
        else:
            st.error(f"""
            ❌ No se encuentra el archivo credentials.json
            
            📁 Buscado en: {creds_path}
            
            💡 Solución:
            1. Asegúrate de que el archivo credentials.json esté en la carpeta:
               {script_dir}
            2. O descarga las credenciales nuevamente desde Google Cloud Console
            """)
            return None
        
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID)
    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {e}")
        return None

def leer_hoja(hoja_nombre):
    """Lee una hoja de Google Sheets y la convierte en DataFrame"""
    try:
        sheet = conectar_gsheets()
        if sheet is None:
            return pd.DataFrame()
        
        worksheet = sheet.worksheet(hoja_nombre)
        data = worksheet.get_all_values()
        
        if len(data) == 0:
            return pd.DataFrame()
        
        # Primera fila como encabezados
        headers = data[0]
        rows = data[1:]
        
        df = pd.DataFrame(rows, columns=headers)
        return df
    except Exception as e:
        print(f"Error leyendo hoja {hoja_nombre}: {e}")
        return pd.DataFrame()

def guardar_hoja(df, hoja_nombre):
    """Guarda un DataFrame en Google Sheets (reemplaza toda la hoja)"""
    try:
        sheet = conectar_gsheets()
        if sheet is None:
            return False
        
        worksheet = sheet.worksheet(hoja_nombre)
        
        # Limpiar la hoja
        worksheet.clear()
        
        # Preparar datos: encabezados + filas
        if df.empty:
            worksheet.update([df.columns.tolist()])
        else:
            datos = [df.columns.tolist()] + df.values.tolist()
            worksheet.update(datos)
        
        return True
    except Exception as e:
        print(f"Error guardando hoja {hoja_nombre}: {e}")
        return False

def agregar_fila_hoja(df, hoja_nombre):
    """Agrega filas a una hoja (append)"""
    try:
        sheet = conectar_gsheets()
        if sheet is None:
            return False
        
        worksheet = sheet.worksheet(hoja_nombre)
        
        # Verificar que los encabezados coincidan
        existing = worksheet.get_all_values()
        if len(existing) == 0:
            # Si la hoja está vacía, crear encabezados
            worksheet.append_row(df.columns.tolist())
        
        # Agregar cada fila
        for _, row in df.iterrows():
            worksheet.append_row(row.astype(str).tolist())
        
        return True
    except Exception as e:
        print(f"Error agregando filas a {hoja_nombre}: {e}")
        return False

# ------------------------------------------------
# CARGA DE DATOS
# ------------------------------------------------

# Leer todas las hojas
df_auditores = leer_hoja("Auditor")
df_auditados = leer_hoja("Auditado")
df_empresas = leer_hoja("Empresas")
df_localidades = leer_hoja("Localidades")
df_notas = leer_hoja("Notas")
df_pilares = leer_hoja("Pilares")
df_preguntas = leer_hoja("Preguntas")
df_respuestas = leer_hoja("Respuestas")

# ------------------------------------------------
# LISTAS PARA SELECTORES
# ------------------------------------------------

# Auditores
lista_auditores = df_auditores["Auditor"].dropna().astype(str).tolist() if not df_auditores.empty else []

# Empresas
lista_empresas = df_empresas["Empresas"].dropna().astype(str).tolist() if not df_empresas.empty else []

# Localidades (con filtro por empresa)
def obtener_localidades(empresa=None):
    if df_localidades.empty:
        return []
    if empresa:
        return df_localidades[df_localidades["Empresa"] == empresa]["Localidad"].dropna().astype(str).tolist()
    return df_localidades["Localidad"].dropna().astype(str).tolist()

# Auditados (con filtro por empresa y auditor)
def obtener_auditados(empresa=None, auditor=None):
    if df_auditados.empty:
        return []
    df_filtrado = df_auditados.copy()
    if empresa:
        df_filtrado = df_filtrado[df_filtrado["Empresa"] == empresa]
    if auditor:
        df_filtrado = df_filtrado[df_filtrado["Auditor"] == auditor]
    return df_filtrado["Auditado"].dropna().astype(str).tolist()

# Pilares
lista_pilares = df_pilares["Pilar"].dropna().astype(str).tolist() if not df_pilares.empty else []

# Notas
df_notas = df_notas.sort_values("Peso") if not df_notas.empty else df_notas
lista_notas = df_notas["Nota"].dropna().astype(str).tolist() if not df_notas.empty else []

# Preguntas (con filtro por pilar y puesto)
def obtener_preguntas(pilar=None, puesto=None):
    if df_preguntas.empty:
        return pd.DataFrame()
    df_filtrado = df_preguntas.copy()
    if pilar:
        df_filtrado = df_filtrado[df_filtrado["Pilar"] == pilar]
    if puesto:
        df_filtrado = df_filtrado[df_filtrado["Puesto"] == puesto]
    return df_filtrado

# ------------------------------------------------
# FUNCIONES DE NEGOCIO
# ------------------------------------------------

def calcular_puntaje_final(nota, puntos_maximo):
    """Calcula el puntaje final: peso * puntos_maximo"""
    if df_notas.empty:
        return 0
    peso_row = df_notas[df_notas["Nota"] == nota]
    if peso_row.empty:
        return 0
    peso = float(peso_row["Peso"].iloc[0])
    return peso * puntos_maximo

def obtener_categoria_mejorar(df_preguntas_filtrado, respuestas):
    """Determina la categoría con peor performance"""
    if df_preguntas_filtrado.empty or not respuestas:
        return ""
    
    # Calcular promedio por categoría
    categorias = {}
    for _, row in df_preguntas_filtrado.iterrows():
        pregunta = row["Pregunta"]
        categoria = row["Categoría"]
        puntos_max = float(row["Puntos Máximo"])
        
        if pregunta in respuestas:
            nota = respuestas[pregunta]
            peso_row = df_notas[df_notas["Nota"] == nota]
            if not peso_row.empty:
                peso = float(peso_row["Peso"].iloc[0])
                puntaje = peso * puntos_max
                if categoria not in categorias:
                    categorias[categoria] = {"total": 0, "count": 0}
                categorias[categoria]["total"] += puntaje
                categorias[categoria]["count"] += 1
    
    # Calcular promedios
    promedios = {}
    for cat, datos in categorias.items():
        promedios[cat] = datos["total"] / datos["count"] if datos["count"] > 0 else 0
    
    # Encontrar la categoría con menor promedio
    if promedios:
        peor_categoria = min(promedios, key=promedios.get)
        return peor_categoria
    return ""

# ------------------------------------------------
# SIDEBAR
# ------------------------------------------------

st.sidebar.image(
    "Logo Grupo Venier.png",
    use_container_width=True
)

with st.sidebar:
    seleccion = option_menu(
        menu_title="Coaching Ventas",
        options=[
            "Nuevo Coaching",
            "Dashboard",
            "Categorías a Mejorar",
            "Historial",
            "Maestros"
        ],
        icons=[
            "clipboard-check",
            "bar-chart",
            "exclamation-triangle",
            "clock-history",
            "gear"
        ],
        default_index=0
    )

    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray; font-size: 12px; padding: 10px;'>
            By Pato Frangi
        </div>
        """,
        unsafe_allow_html=True
    )

# =========================================================
# NUEVO COACHING
# =========================================================

if seleccion == "Nuevo Coaching":
    st.title("📝 Nuevo Coaching")

    # ------------------------------------------------
    # DATOS DEL COACHING
    # ------------------------------------------------

    st.subheader("👤 Datos del Coaching")

    col1, col2 = st.columns(2)

    with col1:
        fecha = st.date_input("Fecha")
        
        # Auditor
        auditor = st.selectbox(
            "Auditor",
            lista_auditores,
            index=0 if lista_auditores else None,
            key=f"{st.session_state.form_id}_auditor"
        )
        
        # Empresa (filtra localidades y auditados)
        empresa = st.selectbox(
            "Empresa",
            [""] + lista_empresas,
            index=0,
            key=f"{st.session_state.form_id}_empresa"
        )

    with col2:
        # Localidad (filtrada por empresa)
        localidades_disponibles = obtener_localidades(empresa) if empresa else obtener_localidades()
        localidad = st.selectbox(
            "Localidad",
            [""] + localidades_disponibles,
            index=0,
            key=f"{st.session_state.form_id}_localidad"
        )
        
        # Auditado (filtrado por empresa y auditor)
        auditados_disponibles = obtener_auditados(empresa, auditor) if empresa or auditor else obtener_auditados()
        auditado = st.selectbox(
            "Auditado",
            [""] + auditados_disponibles,
            index=0,
            key=f"{st.session_state.form_id}_auditado"
        )

    st.divider()

    # ------------------------------------------------
    # OBTENER PUESTO DEL AUDITADO
    # ------------------------------------------------

    puesto_auditado = ""
    if auditado and not df_auditados.empty:
        puesto_row = df_auditados[df_auditados["Auditado"] == auditado]
        if not puesto_row.empty:
            puesto_auditado = puesto_row["Puesto"].iloc[0]

    if puesto_auditado:
        st.info(f"📌 Puesto del auditado: **{puesto_auditado}**")

    # ------------------------------------------------
    # SELECCIÓN DE PILAR
    # ------------------------------------------------

    st.subheader("📂 Evaluación")

    pilar = st.selectbox(
        "Pilar / Competencia",
        [""] + lista_pilares,
        index=0,
        key=f"{st.session_state.form_id}_pilar"
    )

    st.divider()

    # ------------------------------------------------
    # MOSTRAR PREGUNTAS
    # ------------------------------------------------

    respuestas = {}
    df_preguntas_filtrado = pd.DataFrame()

    if pilar and puesto_auditado:
        # Filtrar preguntas por pilar y puesto
        df_preguntas_filtrado = obtener_preguntas(pilar, puesto_auditado)
        
        if df_preguntas_filtrado.empty:
            st.warning(f"⚠️ No hay preguntas para el pilar '{pilar}' y puesto '{puesto_auditado}'")
        else:
            st.subheader(f"📋 Preguntas - {pilar}")
            st.caption(f"Puesto: {puesto_auditado}")
            
            # Mostrar preguntas
            for idx, (_, row) in enumerate(df_preguntas_filtrado.iterrows(), 1):
                pregunta = row["Pregunta"]
                puntos_maximo = float(row["Puntos Máximo"])
                categoria = row["Categoría"]
                
                st.markdown(f"**{idx}. {pregunta}**")
                st.caption(f"⚖️ Puntos Máximo: {puntos_maximo} | 📂 Categoría: {categoria}")
                
                # Selector de nota
                nota = st.selectbox(
                    "Nota",
                    [""] + lista_notas,
                    key=f"{st.session_state.form_id}_pregunta_{row['ID']}",
                    label_visibility="collapsed"
                )
                
                if nota:
                    respuestas[pregunta] = nota
                
                st.divider()

    st.divider()

    # ------------------------------------------------
    # BOTON GUARDAR
    # ------------------------------------------------

    guardar = st.button("💾 Guardar Coaching", use_container_width=True)

    # ========================================================
    # GUARDAR
    # ========================================================

    if guardar:
        # Validar campos obligatorios
        campos_faltantes = []
        
        if not auditor:
            campos_faltantes.append("Auditor")
        if not auditado:
            campos_faltantes.append("Auditado")
        if not empresa:
            campos_faltantes.append("Empresa")
        if not localidad:
            campos_faltantes.append("Localidad")
        if not pilar:
            campos_faltantes.append("Pilar")
        if not puesto_auditado:
            campos_faltantes.append("Puesto del auditado (verificar en maestros)")
        
        # Verificar que todas las preguntas tengan respuesta
        preguntas_sin_respuesta = []
        if not df_preguntas_filtrado.empty:
            for _, row in df_preguntas_filtrado.iterrows():
                pregunta = row["Pregunta"]
                if pregunta not in respuestas or not respuestas[pregunta]:
                    preguntas_sin_respuesta.append(pregunta)
        
        if preguntas_sin_respuesta:
            st.error(f"⚠️ Faltan responder {len(preguntas_sin_respuesta)} preguntas")
            # Mostrar las primeras 5 preguntas faltantes
            for p in preguntas_sin_respuesta[:5]:
                st.warning(f"❓ {p}")
            if len(preguntas_sin_respuesta) > 5:
                st.warning(f"... y {len(preguntas_sin_respuesta) - 5} más")
            st.stop()
        
        if campos_faltantes:
            st.error(f"⚠️ Completar campos obligatorios: {', '.join(campos_faltantes)}")
            st.stop()
        
        # Preparar datos para guardar
        datos_coaching = []
        
        for _, row in df_preguntas_filtrado.iterrows():
            pregunta = row["Pregunta"]
            puntos_maximo = float(row["Puntos Máximo"])
            nota = respuestas.get(pregunta, "")
            
            # Calcular peso y puntaje final
            peso = 0
            puntaje_final = 0
            if nota:
                peso_row = df_notas[df_notas["Nota"] == nota]
                if not peso_row.empty:
                    peso = float(peso_row["Peso"].iloc[0])
                    puntaje_final = peso * puntos_maximo
            
            datos_coaching.append({
                "Fecha": str(fecha),
                "Auditor": auditor,
                "Auditado": auditado,
                "Empresa": empresa,
                "Localidad": localidad,
                "Pilar": pilar,
                "Pregunta": pregunta,
                "Nota": nota,
                "Peso": peso,
                "Puntos Máximo": puntos_maximo,
                "Puntaje Final": puntaje_final,
                "Categoría a Mejorar": ""  # Se calculará después
            })
        
        # Calcular categoría a mejorar
        df_guardado = pd.DataFrame(datos_coaching)
        categoria_mejorar = obtener_categoria_mejorar(df_preguntas_filtrado, respuestas)
        
        # Asignar la categoría a todas las filas
        df_guardado["Categoría a Mejorar"] = categoria_mejorar
        
        # Guardar en Google Sheets
        if agregar_fila_hoja(df_guardado, "Respuestas"):
            st.success("✅ Coaching guardado correctamente")
            
            # Mostrar resumen
            if categoria_mejorar:
                st.info(f"🎯 Categoría a Mejorar: **{categoria_mejorar}**")
            
            # Calcular score total
            if not df_guardado.empty:
                total_puntaje = df_guardado["Puntaje Final"].sum()
                total_maximo = df_guardado["Puntos Máximo"].sum()
                score = (total_puntaje / total_maximo * 100) if total_maximo > 0 else 0
                
                if score >= 80:
                    st.success(f"🏆 Score: {score:.1f}% - ¡Excelente!")
                elif score >= 60:
                    st.info(f"📊 Score: {score:.1f}% - Buen desempeño")
                else:
                    st.warning(f"📈 Score: {score:.1f}% - Área de oportunidad")
            
            st.balloons()
            import time
            time.sleep(2)
            st.session_state.form_id += 1
            st.rerun()
        else:
            st.error("❌ Error al guardar en Google Sheets")

# =========================================================
# DASHBOARD
# =========================================================

elif seleccion == "Dashboard":
    st.title("📊 Dashboard Coaching Ventas")

    # Leer respuestas
    try:
        df_dashboard = leer_hoja("Respuestas")
    except:
        st.warning("⚠️ No existen sesiones de coaching cargadas")
        st.stop()

    if df_dashboard.empty:
        st.warning("⚠️ No existen sesiones de coaching cargadas")
        st.stop()

    # Convertir tipos
    df_dashboard["Fecha"] = pd.to_datetime(df_dashboard["Fecha"], errors="coerce")
    df_dashboard["Puntaje Final"] = pd.to_numeric(df_dashboard["Puntaje Final"], errors="coerce")
    df_dashboard["Puntos Máximo"] = pd.to_numeric(df_dashboard["Puntos Máximo"], errors="coerce")
    df_dashboard["Peso"] = pd.to_numeric(df_dashboard["Peso"], errors="coerce")

    # Calcular % de cumplimiento por pregunta
    df_dashboard["% Cumplimiento"] = (
        df_dashboard["Puntaje Final"] / df_dashboard["Puntos Máximo"] * 100
    ).round(2)

    # Filtros
    st.subheader("🔎 Filtros")

    col1, col2, col3 = st.columns(3)

    with col1:
        auditados_dash = ["Todos"] + sorted(df_dashboard["Auditado"].dropna().unique().tolist())
        auditado_filtro = st.selectbox("👤 Auditado", auditados_dash)

    with col2:
        pilares_dash = ["Todos"] + sorted(df_dashboard["Pilar"].dropna().unique().tolist())
        pilar_filtro = st.selectbox("🏆 Pilar", pilares_dash)

    with col3:
        empresas_dash = ["Todos"] + sorted(df_dashboard["Empresa"].dropna().unique().tolist())
        empresa_filtro = st.selectbox("🏢 Empresa", empresas_dash)

    # Aplicar filtros
    df_filtrado = df_dashboard.copy()

    if auditado_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Auditado"] == auditado_filtro]

    if pilar_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Pilar"] == pilar_filtro]

    if empresa_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Empresa"] == empresa_filtro]

    # KPIs
    st.subheader("📌 Indicadores Generales")

    col1, col2, col3, col4 = st.columns(4)

    total_coachings = df_filtrado["Fecha"].nunique() if not df_filtrado.empty else 0
    total_preguntas = len(df_filtrado) if not df_filtrado.empty else 0
    
    # Score promedio por sesión (promedio de % cumplimiento)
    score_promedio = df_filtrado.groupby("Fecha")["% Cumplimiento"].mean().mean() if not df_filtrado.empty else 0
    
    # Total de categorías a mejorar
    total_mejoras = df_filtrado["Categoría a Mejorar"].dropna().nunique() if not df_filtrado.empty else 0

    with col1:
        st.metric("📋 Sesiones", total_coachings)
    with col2:
        st.metric("📝 Preguntas", total_preguntas)
    with col3:
        st.metric("🎯 Score Promedio", f"{score_promedio:.1f}%")
    with col4:
        st.metric("🎯 Categorías a Mejorar", total_mejoras)

    st.divider()

    if not df_filtrado.empty:
        # Score por Auditado
        st.subheader("👤 Score por Auditado")

        score_auditado = (
            df_filtrado
            .groupby("Auditado", as_index=False)
            .agg({
                "% Cumplimiento": "mean",
                "Fecha": "nunique"
            })
        )
        score_auditado.columns = ["Auditado", "Score", "Sesiones"]
        score_auditado = score_auditado.sort_values("Score", ascending=False)

        top_5 = score_auditado.head(5)
        bottom_5 = score_auditado.sort_values("Score", ascending=True).head(5)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 🏆 Top 5 Mejores Auditados")
            for _, fila in top_5.iterrows():
                st.markdown(
                    f"""
                    <div style="padding:12px;border-radius:10px;background-color:#f5f7fa;color:#000000;margin-bottom:8px;border:1px solid #dfe6ee;">
                        <b>👤 {fila['Auditado']}</b><br>
                        📋 Sesiones: {fila['Sesiones']}<br>
                        🎯 Score: <b>{fila['Score']:.1f}%</b>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        with col2:
            st.markdown("### ⚠️ Top 5 Peores Auditados")
            for _, fila in bottom_5.iterrows():
                st.markdown(
                    f"""
                    <div style="padding:12px;border-radius:10px;background-color:#fff5f5;color:#000000;margin-bottom:8px;border:1px solid #f0d0d0;">
                        <b>👤 {fila['Auditado']}</b><br>
                        📋 Sesiones: {fila['Sesiones']}<br>
                        🎯 Score: <b>{fila['Score']:.1f}%</b>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        st.divider()

        # Score por Pilar
        st.subheader("🏆 Score por Pilar")

        score_pilar = (
            df_filtrado
            .groupby("Pilar", as_index=False)
            .agg({
                "% Cumplimiento": "mean",
                "Fecha": "nunique"
            })
        )
        score_pilar.columns = ["Pilar", "Score", "Sesiones"]
        score_pilar = score_pilar.sort_values("Score", ascending=False)

        for _, fila in score_pilar.iterrows():
            st.markdown(
                f"""
                <div style="padding:15px;border-radius:12px;background-color:#f5f7fa;color:#000000;margin-bottom:10px;border:1px solid #dfe6ee;">
                    <h4 style="margin:0;">🏆 {fila['Pilar']}</h4>
                    <p style="margin:5px 0 0 0;">
                        📋 Sesiones: <b>{fila['Sesiones']}</b>
                        &nbsp;&nbsp;&nbsp;
                        🎯 Score: <b>{fila['Score']:.1f}%</b>
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.divider()

        # Preguntas más débiles
        st.subheader("❌ Preguntas con Menor Cumplimiento")

        preguntas_debiles = (
            df_filtrado
            .groupby("Pregunta", as_index=False)
            .agg({
                "% Cumplimiento": "mean",
                "Fecha": "nunique"
            })
        )
        preguntas_debiles.columns = ["Pregunta", "Score", "Cantidad"]
        preguntas_debiles = preguntas_debiles.sort_values("Score", ascending=True)
        preguntas_debiles = preguntas_debiles.head(5)

        for _, fila in preguntas_debiles.iterrows():
            st.markdown(
                f"""
                <div style="padding:15px;border-radius:12px;background-color:#fff4f4;color:#000000;margin-bottom:10px;border:1px solid #f5c2c2;">
                    <h4 style="margin:0;">❌ {fila['Pregunta'][:80]}...</h4>
                    <p style="margin:5px 0 0 0;">
                        📋 Evaluaciones: <b>{fila['Cantidad']}</b>
                        &nbsp;&nbsp;&nbsp;
                        🎯 Cumplimiento: <b>{fila['Score']:.1f}%</b>
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.divider()

        # Evolución mensual
        st.subheader("📈 Evolución Mensual")

        # Agrupar por mes
        df_filtrado["Mes"] = df_filtrado["Fecha"].dt.strftime("%m-%Y")
        evolucion = (
            df_filtrado
            .groupby("Mes", as_index=False)
            .agg({
                "% Cumplimiento": "mean"
            })
        )
        evolucion = evolucion.sort_values("Mes")

        if not evolucion.empty:
            fig = px.line(
                evolucion,
                x="Mes",
                y="% Cumplimiento",
                markers=True,
                text=evolucion["% Cumplimiento"].round(1).astype(str) + "%",
                title="Evolución Mensual del Score"
            )
            fig.update_traces(textposition="top center")
            fig.update_layout(
                xaxis_title="Mes",
                yaxis_title="Score (%)",
                yaxis_range=[0, 100]
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos suficientes para mostrar evolución")

    else:
        st.info("No hay datos para mostrar con los filtros seleccionados.")

# =========================================================
# CATEGORÍAS A MEJORAR
# =========================================================

elif seleccion == "Categorías a Mejorar":
    st.title("🎯 Categorías a Mejorar")

    try:
        df_mejoras = leer_hoja("Respuestas")
    except:
        st.warning("⚠️ No existen sesiones de coaching cargadas")
        st.stop()

    if df_mejoras.empty:
        st.success("✅ No hay categorías a mejorar pendientes")
        st.stop()

    # Filtrar solo las que tienen categoría a mejorar
    df_mejoras = df_mejoras[
        df_mejoras["Categoría a Mejorar"].notna() &
        (df_mejoras["Categoría a Mejorar"] != "")
    ]

    if df_mejoras.empty:
        st.success("✅ No hay categorías a mejorar pendientes")
        st.stop()

    # Convertir fechas
    df_mejoras["Fecha"] = pd.to_datetime(df_mejoras["Fecha"], errors="coerce")

    # KPIs
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("📋 Total de Mejoras", len(df_mejoras))

    with col2:
        auditados_mejora = df_mejoras["Auditado"].nunique()
        st.metric("👤 Auditados con Mejoras", auditados_mejora)

    with col3:
        # Categorías únicas
        categorias_unicas = df_mejoras["Categoría a Mejorar"].nunique()
        st.metric("📂 Categorías Identificadas", categorias_unicas)

    st.divider()

    # Mostrar categorías
    st.subheader("📋 Listado de Categorías a Mejorar")

    # Filtros
    col1, col2 = st.columns(2)

    with col1:
        auditados_filtro = ["Todos"] + sorted(df_mejoras["Auditado"].dropna().unique().tolist())
        auditado_mejora = st.selectbox("Filtrar por Auditado", auditados_filtro)

    with col2:
        categorias_filtro = ["Todos"] + sorted(df_mejoras["Categoría a Mejorar"].dropna().unique().tolist())
        categoria_mejora = st.selectbox("Filtrar por Categoría", categorias_filtro)

    # Aplicar filtros
    df_filtrado_mejoras = df_mejoras.copy()

    if auditado_mejora != "Todos":
        df_filtrado_mejoras = df_filtrado_mejoras[
            df_filtrado_mejoras["Auditado"] == auditado_mejora
        ]

    if categoria_mejora != "Todos":
        df_filtrado_mejoras = df_filtrado_mejoras[
            df_filtrado_mejoras["Categoría a Mejorar"] == categoria_mejora
        ]

    # Mostrar
    for _, fila in df_filtrado_mejoras.iterrows():
        st.markdown(
            f"""
            <div style="padding:15px;border-radius:12px;background-color:#fff8e1;color:#000000;margin-bottom:10px;border:1px solid #ffd54f;">
                <h4 style="margin:0;">📌 {fila['Categoría a Mejorar']}</h4>
                <p style="margin:5px 0 0 0;">
                    👤 <b>{fila['Auditado']}</b>
                    &nbsp;&nbsp;&nbsp;
                    🏢 {fila['Empresa']}
                    &nbsp;&nbsp;&nbsp;
                    🏆 {fila['Pilar']}
                    &nbsp;&nbsp;&nbsp;
                    📅 {fila['Fecha'].strftime('%d-%m-%Y') if pd.notna(fila['Fecha']) else ''}
                </p>
                <p style="margin:5px 0 0 0; font-size:14px; color:#666;">
                    📝 <i>{fila['Pregunta'][:100]}...</i>
                </p>
                <p style="margin:5px 0 0 0; font-size:13px; color:#888;">
                    🎯 Puntaje: {fila['Puntaje Final']:.1f}/{fila['Puntos Máximo']:.1f}
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Exportar
    if st.button("📥 Exportar a Excel"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_filtrado_mejoras.to_excel(writer, sheet_name="Categorías a Mejorar", index=False)
        buffer.seek(0)

        st.download_button(
            label="📥 Descargar Excel",
            data=buffer,
            file_name=f"Categorias_Mejorar_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# =========================================================
# HISTORIAL
# =========================================================

elif seleccion == "Historial":
    st.title("📂 Historial de Coaching")

    try:
        df_historial = leer_hoja("Respuestas")
    except:
        st.warning("No existen sesiones de coaching cargadas.")
        st.stop()

    if df_historial.empty:
        st.warning("No existen sesiones de coaching cargadas.")
        st.stop()

    # Convertir tipos
    df_historial["Fecha"] = pd.to_datetime(df_historial["Fecha"], errors="coerce")
    df_historial["Puntaje Final"] = pd.to_numeric(df_historial["Puntaje Final"], errors="coerce")
    df_historial["Puntos Máximo"] = pd.to_numeric(df_historial["Puntos Máximo"], errors="coerce")

    # Calcular score
    df_historial["% Cumplimiento"] = (
        df_historial["Puntaje Final"] / df_historial["Puntos Máximo"] * 100
    ).round(1)

    # Resumen por sesión
    resumen = (
        df_historial
        .groupby(["Fecha", "Auditor", "Auditado", "Empresa", "Localidad", "Pilar"], as_index=False)
        .agg({
            "% Cumplimiento": "mean",
            "Pregunta": "count",
            "Categoría a Mejorar": lambda x: x.dropna().unique()[0] if len(x.dropna().unique()) > 0 else ""
        })
    )
    resumen.columns = ["Fecha", "Auditor", "Auditado", "Empresa", "Localidad", "Pilar", "Score", "Preguntas", "Categoría a Mejorar"]

    resumen["Fecha"] = resumen["Fecha"].dt.strftime("%d-%m-%Y")
    resumen = resumen.sort_values("Fecha", ascending=False)

    # Filtros
    st.subheader("🔎 Filtros")

    col1, col2, col3 = st.columns(3)

    with col1:
        auditados_hist = ["Todos"] + sorted(resumen["Auditado"].dropna().unique().tolist())
        auditado_hist = st.selectbox("👤 Auditado", auditados_hist)

    with col2:
        pilares_hist = ["Todos"] + sorted(resumen["Pilar"].dropna().unique().tolist())
        pilar_hist = st.selectbox("🏆 Pilar", pilares_hist)

    with col3:
        empresas_hist = ["Todos"] + sorted(resumen["Empresa"].dropna().unique().tolist())
        empresa_hist = st.selectbox("🏢 Empresa", empresas_hist)

    # Aplicar filtros
    df_filtrado_hist = resumen.copy()

    if auditado_hist != "Todos":
        df_filtrado_hist = df_filtrado_hist[df_filtrado_hist["Auditado"] == auditado_hist]

    if pilar_hist != "Todos":
        df_filtrado_hist = df_filtrado_hist[df_filtrado_hist["Pilar"] == pilar_hist]

    if empresa_hist != "Todos":
        df_filtrado_hist = df_filtrado_hist[df_filtrado_hist["Empresa"] == empresa_hist]

    st.divider()

    # Mostrar tabla
    st.subheader("📋 Sesiones de Coaching")
    st.dataframe(df_filtrado_hist, use_container_width=True)

    # Exportar
    if st.button("📥 Exportar Historial a Excel"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_filtrado_hist.to_excel(writer, sheet_name="Historial", index=False)
            # También exportar detalle
            df_detalle = df_historial[
                df_historial["Auditado"].isin(df_filtrado_hist["Auditado"].unique())
            ]
            df_detalle.to_excel(writer, sheet_name="Detalle", index=False)
        buffer.seek(0)

        st.download_button(
            label="📥 Descargar Excel",
            data=buffer,
            file_name=f"Historial_Coaching_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# =========================================================
# MAESTROS
# =========================================================

elif seleccion == "Maestros":
    st.title("⚙️ Gestión de Maestros")

    tablas = {
        "": "",
        "Auditores": "Auditor",
        "Auditados": "Auditado",
        "Empresas": "Empresas",
        "Localidades": "Localidades",
        "Notas": "Notas",
        "Pilares": "Pilares",
        "Preguntas": "Preguntas"
    }

    opcion_tabla = st.selectbox("Seleccionar módulo", list(tablas.keys()), index=0)

    if opcion_tabla != "":
        hoja_excel = tablas[opcion_tabla]
        df_admin = leer_hoja(hoja_excel)

        st.subheader(f"📋 {opcion_tabla}")
        st.dataframe(df_admin, use_container_width=True)

        st.divider()

        # Agregar nuevo registro según la tabla
        st.subheader(f"➕ Agregar {opcion_tabla[:-1] if opcion_tabla.endswith('s') else opcion_tabla}")

        if hoja_excel == "Auditor":
            col1, col2 = st.columns(2)
            with col1:
                nuevo_auditor = st.text_input("Auditor")
            with col2:
                nuevo_puesto = st.text_input("Puesto")
            
            if st.button("➕ Agregar Auditor"):
                if nuevo_auditor and nuevo_puesto:
                    nuevo_df = pd.DataFrame({
                        "Auditor": [nuevo_auditor],
                        "Puesto": [nuevo_puesto]
                    })
                    df_admin = pd.concat([df_admin, nuevo_df], ignore_index=True)
                    if guardar_hoja(df_admin, hoja_excel):
                        st.success("✅ Auditor agregado")
                        st.rerun()

        elif hoja_excel == "Auditado":
            col1, col2 = st.columns(2)
            with col1:
                nuevo_auditado = st.text_input("Auditado")
                nuevo_puesto_aud = st.text_input("Puesto")
            with col2:
                nueva_empresa_aud = st.selectbox("Empresa", [""] + lista_empresas)
                nuevo_auditor_aud = st.selectbox("Auditor", [""] + lista_auditores)
            
            if st.button("➕ Agregar Auditado"):
                if nuevo_auditado and nuevo_puesto_aud and nueva_empresa_aud and nuevo_auditor_aud:
                    nuevo_df = pd.DataFrame({
                        "Auditado": [nuevo_auditado],
                        "Puesto": [nuevo_puesto_aud],
                        "Empresa": [nueva_empresa_aud],
                        "Auditor": [nuevo_auditor_aud]
                    })
                    df_admin = pd.concat([df_admin, nuevo_df], ignore_index=True)
                    if guardar_hoja(df_admin, hoja_excel):
                        st.success("✅ Auditado agregado")
                        st.rerun()

        elif hoja_excel == "Localidades":
            col1, col2 = st.columns(2)
            with col1:
                nueva_localidad = st.text_input("Localidad")
            with col2:
                nueva_empresa_loc = st.selectbox("Empresa", [""] + lista_empresas)
            
            if st.button("➕ Agregar Localidad"):
                if nueva_localidad and nueva_empresa_loc:
                    nuevo_df = pd.DataFrame({
                        "Localidad": [nueva_localidad],
                        "Empresa": [nueva_empresa_loc]
                    })
                    df_admin = pd.concat([df_admin, nuevo_df], ignore_index=True)
                    if guardar_hoja(df_admin, hoja_excel):
                        st.success("✅ Localidad agregada")
                        st.rerun()

        elif hoja_excel == "Preguntas":
            col1, col2 = st.columns(2)
            with col1:
                nuevo_id = st.text_input("ID")
                nueva_pregunta = st.text_area("Pregunta")
                nuevo_pilar = st.selectbox("Pilar", [""] + lista_pilares)
            with col2:
                nuevo_puntos = st.number_input("Puntos Máximo", min_value=1, step=1)
                nueva_categoria = st.text_input("Categoría")
                nuevo_puesto = st.selectbox("Puesto", ["", "Promotor", "Merchand", "Supervisor"])
            
            if st.button("➕ Agregar Pregunta"):
                if nuevo_id and nueva_pregunta and nuevo_pilar and nuevo_puntos and nueva_categoria and nuevo_puesto:
                    nuevo_df = pd.DataFrame({
                        "ID": [nuevo_id],
                        "Pregunta": [nueva_pregunta],
                        "Pilar": [nuevo_pilar],
                        "Puntos Máximo": [nuevo_puntos],
                        "Categoría": [nueva_categoria],
                        "Puesto": [nuevo_puesto]
                    })
                    df_admin = pd.concat([df_admin, nuevo_df], ignore_index=True)
                    if guardar_hoja(df_admin, hoja_excel):
                        st.success("✅ Pregunta agregada")
                        st.rerun()

        else:
            # Hojas simples (una o dos columnas)
            columnas = df_admin.columns.tolist()
            nuevos_valores = {}
            
            for col in columnas:
                nuevos_valores[col] = st.text_input(f"{col}")
            
            if st.button("➕ Agregar"):
                if all(nuevos_valores.values()):
                    nuevo_df = pd.DataFrame([nuevos_valores])
                    df_admin = pd.concat([df_admin, nuevo_df], ignore_index=True)
                    if guardar_hoja(df_admin, hoja_excel):
                        st.success(f"✅ {opcion_tabla[:-1]} agregado")
                        st.rerun()
                else:
                    st.warning("⚠️ Complete todos los campos")

        st.divider()

        # Eliminar registro
        st.subheader("🗑️ Eliminar")

        if not df_admin.empty:
            columna_principal = df_admin.columns[0]
            lista_eliminar = [""] + df_admin[columna_principal].astype(str).tolist()
            eliminar_valor = st.selectbox("Seleccionar valor a eliminar", lista_eliminar, index=0)

            if st.button("🗑️ Eliminar"):
                if eliminar_valor:
                    df_admin = df_admin[df_admin[columna_principal].astype(str) != eliminar_valor]
                    if guardar_hoja(df_admin, hoja_excel):
                        st.success("✅ Valor eliminado")
                        st.rerun()
        else:
            st.info("No hay datos para eliminar")

# =========================================================
# NOTA FINAL
# =========================================================

st.sidebar.info("""
### 📌 Estructura de datos

- **Auditores**: Personas que realizan el coaching
- **Auditados**: Personas evaluadas
- **Pilares**: Competencias evaluadas
- **Preguntas**: Filtradas por Pilar y Puesto
- **Notas**: Escala de evaluación (Nunca → Siempre)
""")