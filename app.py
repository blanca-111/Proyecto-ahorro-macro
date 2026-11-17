import streamlit as st
import pandas as pd
import numpy as np
import gspread
import yfinance as yf
import pandas_datareader.data as web
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Dashboard Macro-Financiero Real", layout="wide")

st.title("Simulador Macro-Financiero en Tiempo Real")
st.markdown("Conectado en vivo a **Google Sheets** (tu ahorro real), **Yahoo Finance** (ETFs) y **FRED** (IPC Eurozona).")

# --- 1. CONEXIÓN EN VIVO A GOOGLE SHEETS ---
@st.cache_data(ttl=300)
def cargar_datos_personales():
    try:
        creds = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open("Mi_Ahorro_Mensual")
        df = pd.DataFrame(sh.sheet1.get_all_records())
        return df, True
    except Exception:
        return pd.DataFrame(), False

# --- 2. DESCARGA DE DATOS REALES DE MERCADO Y MACRO ---
@st.cache_data(ttl=3600)
def cargar_datos_macro(ticker):
    try:
        end = datetime.today()
        start = datetime(end.year - 10, end.month, 1)
        
        hist = yf.download(ticker, start=start, end=end, progress=False)['Close']
        if isinstance(hist, pd.DataFrame):
            hist = hist.iloc[:, 0]
            
        cagr = ((hist.iloc[-1] / hist.iloc[0]) ** (1 / 10) - 1) * 100
        # Volatilidad anualizada real del ETF
        volatilidad = hist.pct_change().std() * np.sqrt(252) * 100
        
        ipc = web.DataReader('CP0000EZ19M086NEST', 'fred', start, end)
        inf_actual = (ipc.iloc[-1].values[0] / ipc.iloc[-13].values[0] - 1) * 100
        
        return round(float(cagr), 2), round(float(volatilidad), 2), round(float(inf_actual), 2), hist
    except Exception:
        return 7.5, 15.0, 2.8, None

df_personal, conectado_sheets = cargar_datos_personales()

# --- BARRA LATERAL ---
st.sidebar.header("1. Fuente de Datos en Vivo")
ticker_sel = st.sidebar.selectbox("ETF / Índice de referencia", ["IWDA.AS", "SPY", "QQQ", "VWCE.DE"], index=0)
cagr_real, vol_real, inf_real, serie_etf = cargar_datos_macro(ticker_sel)

if conectado_sheets and not df_personal.empty:
    ahorro_detectado = int(df_personal['Ahorro_Invertido'].mean())
    st.sidebar.success(f"Google Sheets conectado (Media: {ahorro_detectado} €/mes)")
else:
    ahorro_detectado = 800
    st.sidebar.warning("Usando ahorro por defecto")

st.sidebar.header("2. Parámetros del Simulador")
cap_ini = st.sidebar.slider("Capital Inicial (€)", 0, 200000, 15000, 1000)
ahorro = st.sidebar.slider("Ahorro Mensual (€)", 0, 5000, ahorro_detectado, 50)
anos = st.sidebar.slider("Horizonte (Años)", 5, 35, 20, 1)

st.sidebar.header("3. Variables Macro y Riesgo")
r_base = st.sidebar.slider(f"Rentabilidad Anual % (Histórico {ticker_sel}: {cagr_real}%)", 1.0, 18.0, float(cagr_real), 0.5) / 100
vol_anual = st.sidebar.slider(f"Volatilidad Anual % (Histórico {ticker_sel}: {vol_real}%)", 5.0, 35.0, float(vol_real), 1.0) / 100
inf_base = st.sidebar.slider(f"Inflación Anual % (IPC Eurozona: {inf_real}%)", 0.0, 12.0, float(inf_real), 0.2) / 100

r_estres, inf_estres = 0.03, 0.05

# --- CÁLCULO DETERMINISTA ---
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
tab1, tab2, tab3, tab4 = st.tabs([
    "Proyección Macro", 
    "Simulación Monte Carlo (Interactivo)", 
    "Histórico Real del ETF", 
    "Mis Registros (Google Sheets)"
])

with tab1:
    st.subheader(f"Proyección Determinista a {anos} años")
    st.line_chart(df_sim)

with tab2:
    st.subheader(f"Simulación Estocástica de Monte Carlo ({anos} años - Poder Adquisitivo Real)")
    st.markdown("Simula **500 escenarios aleatorios** usando la volatilidad real del mercado y descontando la inflación. **Pasa el ratón, haz zoom o selecciona áreas del gráfico.**")
    
    # Motor de Monte Carlo (500 simulaciones mensuales)
    np.random.seed(42)
    n_sims = 500
    meses = anos * 12
    
    # Retorno mensual esperado y volatilidad mensual
    mu_m = (r_base - inf_base) / 12 # Retorno real mensual
    sigma_m = vol_anual / np.sqrt(12)
    
    # Matriz de retornos aleatorios (meses x simulaciones)
    retornos_sim = np.random.normal(mu_m, sigma_m, (meses, n_sims))
    trayectorias = np.zeros((meses + 1, n_sims))
    trayectorias[0] = cap_ini
    
    for t in range(1, meses + 1):
        trayectorias[t] = (trayectorias[t - 1] + ahorro) * (1 + retornos_sim[t - 1])
        
    # Extraer cierre de cada año y calcular percentiles
    trayectorias_anuales = trayectorias[::12]
    eje_anos = list(range(0, anos + 1))
    
    p90 = np.percentile(trayectorias_anuales, 90, axis=1) # Escenario muy optimista
    p50 = np.percentile(trayectorias_anuales, 50, axis=1) # Escenario mediano (más probable)
    p10 = np.percentile(trayectorias_anuales, 10, axis=1) # Escenario pesimista (malas rachas)
    
    # Gráfico Interactivo con Plotly
    fig = go.Figure()
    
    # Banda sombreada entre el percentil 10 y el 90 (80% de probabilidad)
    fig.add_trace(go.Scatter(
        x=eje_anos + eje_anos[::-1],
        y=list(p90) + list(p10[::-1]),
        fill='toself',
        fillcolor='rgba(46, 204, 113, 0.15)',
        line=dict(color='rgba(255,255,255,0)'),
        hoverinfo="skip",
        name='Rango 80% Probabilidad (P10 - P90)'
    ))
    
    fig.add_trace(go.Scatter(x=eje_anos, y=p90, mode='lines', name='Escenario Optimista (P90)', line=dict(color='#27ae60', dash='dot')))
    fig.add_trace(go.Scatter(x=eje_anos, y=p50, mode='lines+markers', name='Escenario Mediano (P50)', line=dict(color='#2ecc71', width=3)))
    fig.add_trace(go.Scatter(x=eje_anos, y=p10, mode='lines', name='Escenario Pesimista (P10)', line=dict(color='#e74c3c', dash='dash')))
    
    fig.update_layout(
        xaxis_title="Años",
        yaxis_title="Patrimonio Real Ajustado por Inflación (€)",
        hovermode="x unified",
        template="plotly_dark",
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Escenario Pesimista (P10)", f"{p10[-1]:,.0f} €", help="Solo un 10% de los escenarios acaban por debajo de esta cifra")
    col_m2.metric("Escenario Mediano (P50)", f"{p50[-1]:,.0f} €", help="El resultado central más probable tras 500 simulaciones")
    col_m3.metric("Escenario Optimista (P90)", f"{p90[-1]:,.0f} €", help="El 10% de mejores rachas bursátiles superan esta cifra")

with tab3:
    if serie_etf is not None:
        st.subheader(f"Cotización últimos 10 años: {ticker_sel} (CAGR: {cagr_real}% | Volatilidad: {vol_real}%)")
        st.line_chart(serie_etf)

with tab4:
    if conectado_sheets and not df_personal.empty:
        st.subheader("Datos leídos en vivo desde 'Mi_Ahorro_Mensual'")
        st.dataframe(df_personal, use_container_width=True)
    else:
        st.info("Conecta tus credenciales en Settings > Secrets para visualizar aquí tu tabla de Google Sheets.")
