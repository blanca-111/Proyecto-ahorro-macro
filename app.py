import streamlit as st
import pandas as pd

# Configuración de página
st.set_page_config(page_title="Simulador Macro-Financiero", layout="wide")

st.title("Simulador Macro-Financiero de Patrimonio e Inversión")
st.markdown("Analiza cómo afectan la **inflación** y los **escenarios de estrés** a tu ahorro real a largo plazo.")

# --- BARRA LATERAL: CONTROLES DESLIZANTES ---
st.sidebar.header("1. Tus Datos Financieros")
cap_ini = st.sidebar.slider("Capital Inicial Invertido (€)", min_value=0, max_value=200000, value=15000, step=1000)
ahorro = st.sidebar.slider("Ahorro Mensual Invertido (€)", min_value=0, max_value=5000, value=800, step=50)
anos = st.sidebar.slider("Horizonte Temporal (Años)", min_value=5, max_value=35, value=20, step=1)

st.sidebar.header("2. Escenario Base (Normal)")
r_base = st.sidebar.slider("Rentabilidad Anual Esperada (%)", min_value=1.0, max_value=15.0, value=7.5, step=0.5) / 100
inf_base = st.sidebar.slider("Inflación / IPC Anual (%)", min_value=0.0, max_value=10.0, value=2.8, step=0.2) / 100

st.sidebar.header("3. Banda de Estrés (Estanflación)")
r_estres = st.sidebar.slider("Rentabilidad en Crisis (%)", min_value=0.0, max_value=8.0, value=3.0, step=0.5) / 100
inf_estres = st.sidebar.slider("Inflación en Crisis (%)", min_value=2.0, max_value=15.0, value=5.0, step=0.5) / 100

# --- CÁLCULO DEL MODELO ---
datos = []
for y in range(1, anos + 1):
    m = y * 12
    
    # Escenario Base
    rm_base = r_base / 12
    nom_base = cap_ini * ((1 + rm_base)**m) + ahorro * (((1 + rm_base)**m - 1) / rm_base) if rm_base > 0 else cap_ini + ahorro * m
    real_base = nom_base / ((1 + inf_base)**y)
    
    # Escenario Estrés / Estanflación
    rm_estres = r_estres / 12
    nom_estres = cap_ini * ((1 + rm_estres)**m) + ahorro * (((1 + rm_estres)**m - 1) / rm_estres) if rm_estres > 0 else cap_ini + ahorro * m
    real_estres = nom_estres / ((1 + inf_estres)**y)
    
    # Efectivo sin invertir (ajustado a inflación base)
    efectivo_nom = cap_ini + (ahorro * m)
    efectivo_real = efectivo_nom / ((1 + inf_base)**y)
    
    datos.append({
        "Año": y,
        "1. Patrimonio Nominal (€)": round(nom_base, 2),
        "2. Poder Adquisitivo Real Base (€)": round(real_base, 2),
        "3. Banda Estrés / Estanflación Real (€)": round(real_estres, 2),
        "4. Efectivo sin Invertir Real (€)": round(efectivo_real, 2)
    })

df = pd.DataFrame(datos).set_index("Año")

# --- TARJETAS DE RESUMEN (KPIs AL FINAL DEL HORIZONTE) ---
ultimo = df.iloc[-1]
col1, col2, col3, col4 = st.columns(4)
col1.metric("Patrimonio Nominal", f"{ultimo['1. Patrimonio Nominal (€)']:,.0f} €")
col2.metric("Poder Adquisitivo Real", f"{ultimo['2. Poder Adquisitivo Real Base (€)']:,.0f} €")
col3.metric("En Estanflación (Real)", f"{ultimo['3. Banda Estrés / Estanflación Real (€)']:,.0f} €")
col4.metric("Efectivo Parado (Real)", f"{ultimo['4. Efectivo sin Invertir Real (€)']:,.0f} €")

st.divider()

# --- GRÁFICO PRINCIPAL ---
st.subheader(f"Evolución del Patrimonio a {anos} años")
st.line_chart(df)

# --- TABLA DE DATOS ---
with st.expander("Ver tabla detallada año a año"):
    st.dataframe(df, use_container_width=True)
