import streamlit as st
import pandas as pd
import gspread
import yfinance as yf
import pandas_datareader.data as web
from datetime import datetime

st.set_page_config(page_title="Dashboard Macro-Financiero Real", layout="wide")

st.title("Simulador Macro-Financiero en Tiempo Real")
st.markdown("Conectado en vivo a **Google Sheets** (tu ahorro real), **Yahoo Finance** (ETFs) y **FRED** (IPC Eurozona).")

# --- 1. CONEXIÓN EN VIVO A GOOGLE SHEETS ---
@st.cache_data(ttl=300) # Guarda en caché 5 minutos para ir rápido
def cargar_datos_personales():
    try:
        creds = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open("Mi_Ahorro_Mensual")
        df = pd.DataFrame(sh.sheet1.get_all_records())
        return df, True
    except Exception as e:
        return pd.DataFrame(), False

# --- 2. DESCARGA DE DATOS REALES DE MERCADO Y MACRO ---
@st.cache_data(ttl=3600) # Actualiza datos de mercado cada hora
def cargar_datos_macro(ticker):
    try:
        end = datetime.today()
        start = datetime(end.year - 10, end.month, 1)
        
        # Rentabilidad anualizada histórica del ETF (CAGR 10 años)
        hist = yf.download(ticker, start=start, end=end, progress=False)['Close']
        if isinstance(hist, pd.DataFrame):
            hist = hist.iloc[:, 0]
        cagr = ((hist.iloc[-1] / hist.iloc[0]) ** (1 / 10) - 1) * 100
        
        # Última inflación interanual Eurozona (FRED)
        ipc = web.DataReader('CP0000EZ19M086NEST', 'fred', start, end)
        inf_actual = (ipc.iloc[-1].values[0] / ipc.iloc[-13].values[0] - 1) * 100
        
        return round(float(cagr), 2), round(float(inf_actual), 2), hist
    except Exception:
        return 7.5, 2.8, None

df_personal, conectado_sheets = cargar_datos_personales()

# --- BARRA LATERAL ---
st.sidebar.header("1. Fuente de Datos en Vivo")
ticker_sel = st.sidebar.selectbox("ETF / Índice de referencia", ["IWDA.AS", "SPY", "QQQ", "VWCE.DE"], index=0)
cagr_real, inf_real, serie_etf = cargar_datos_macro(ticker_sel)

if conectado_sheets and not df_personal.empty:
    ahorro_detectado = int(df_personal['Ahorro_Invertido'].mean())
    st.sidebar.success(f"Google Sheets conectado (Media: {ahorro_detectado} €/mes)")
else:
    ahorro_detectado = 800
    st.sidebar.warning("Usando ahorro por defecto (revisa Secrets si aún no conectaste Sheets)")

st.sidebar.header("2. Parámetros del Simulador")
cap_ini = st.sidebar.slider("Capital Inicial (€)", 0, 200000, 15000, 1000)
ahorro = st.sidebar.slider("Ahorro Mensual (€)", 0, 5000, ahorro_detectado, 50)
anos = st.sidebar.slider("Horizonte (Años)", 5, 35, 20, 1)

st.sidebar.header("3. Variables Macro (Pre-cargadas con datos reales)")
r_base = st.sidebar.slider(f"Rentabilidad Anual % (Histórico {ticker_sel}: {cagr_real}%)", 1.0, 18.0, float(cagr_real), 0.5) / 100
inf_base = st.sidebar.slider(f"Inflación Anual % (IPC Eurozona actual: {inf_real}%)", 0.0, 12.0, float(inf_real), 0.2) / 100

# Banda de estrés fija (Estanflación: 3% retorno, 5% inflación)
r_estres, inf_estres = 0.03, 0.05

# --- CÁLCULO DE PROYECCIÓN ---
datos = []
for y in range(1, anos + 1):
    m = y * 12
    rm = r_base / 12
    nom = cap_ini * ((1 + rm)**m) + ahorro * (((1 + rm)**m - 1) / rm) if rm > 0 else cap_ini + ahorro * m
    real = nom / ((1 + inf_base)**y)
    
    rm_e = r_estres / 12
    nom_e = cap_ini * ((1 + rm_e)**m) + ahorro * (((1 + rm_e)**m - 1) / rm_e)
    real_e = nom_e / ((1 + inf_estres)**y)
    
    efectivo_real = (cap_ini + ahorro * m) / ((1 + inf_base)**y)
    
    datos.append({
        "Año": y,
        "1. Patrimonio Nominal (€)": round(nom, 2),
        "2. Poder Adquisitivo Real (€)": round(real, 2),
        "3. Banda Estrés / Estanflación (€)": round(real_e, 2),
        "4. Efectivo sin Invertir Real (€)": round(efectivo_real, 2)
    })

df_sim = pd.DataFrame(datos).set_index("Año")

# --- MÉTRICAS SUPERIORES ---
ultimo = df_sim.iloc[-1]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Patrimonio Nominal", f"{ultimo['1. Patrimonio Nominal (€)']:,.0f} €")
c2.metric("Poder Adquisitivo Real", f"{ultimo['2. Poder Adquisitivo Real (€)']:,.0f} €")
c3.metric("En Estanflación (Real)", f"{ultimo['3. Banda Estrés / Estanflación (€)']:,.0f} €")
c4.metric("Efectivo Parado (Real)", f"{ultimo['4. Efectivo sin Invertir Real (€)']:,.0f} €")

st.divider()

# --- PESTAÑAS DE ANÁLISIS ---
tab1, tab2, tab3 = st.tabs(["Proyección Macro", "Histórico Real del ETF", "Mis Registros (Google Sheets)"])

with tab1:
    st.subheader(f"Proyección de Patrimonio a {anos} años")
    st.line_chart(df_sim)

with tab2:
    if serie_etf is not None:
        st.subheader(f"Cotización últimos 10 años: {ticker_sel} (CAGR: {cagr_real}% anual)")
        st.line_chart(serie_etf)

with tab3:
    if conectado_sheets and not df_personal.empty:
        st.subheader("Datos leídos en vivo desde 'Mi_Ahorro_Mensual'")
        st.dataframe(df_personal, use_container_width=True)
    else:
        st.info("Conecta tus credenciales en Settings > Secrets para visualizar aquí tu tabla de Google Sheets.")
