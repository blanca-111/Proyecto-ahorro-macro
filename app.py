import streamlit as st
import pandas as pd
import numpy as np
import gspread
import yfinance as yf
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
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}"

# --- 2. DESCARGA DE DATOS REALES DE MERCADO Y MACRO ---
# Valores por defecto si alguna fuente falla (se avisa en pantalla)
CAGR_DEFECTO, VOL_DEFECTO, INF_DEFECTO = 7.5, 15.0, 2.8
FRED_IPC_EUROZONA = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CP0000EZ19M086NEST"

@st.cache_data(ttl=3600)
def cargar_datos_etf(ticker):
    """Devuelve (cagr %, volatilidad %, años de histórico, serie, error)."""
    try:
        end = datetime.today()
        start = datetime(end.year - 10, end.month, 1)
        hist = yf.download(ticker, start=start, end=end, progress=False)['Close']
        if isinstance(hist, pd.DataFrame):
            hist = hist.iloc[:, 0]
        hist = hist.dropna()
        if len(hist) < 2:
            raise ValueError("sin datos de cotización")

        # Años reales cubiertos por los datos (un ETF puede tener menos de 10 años)
        anos_hist = (hist.index[-1] - hist.index[0]).days / 365.25
        cagr = ((hist.iloc[-1] / hist.iloc[0]) ** (1 / anos_hist) - 1) * 100
        volatilidad = hist.pct_change().std() * np.sqrt(252) * 100
        return round(float(cagr), 2), round(float(volatilidad), 2), round(anos_hist, 1), hist, None
    except Exception as e:
        return CAGR_DEFECTO, VOL_DEFECTO, None, None, f"{type(e).__name__}: {e}"

@st.cache_data(ttl=3600)
def cargar_inflacion():
    """Inflación interanual del IPC Eurozona (FRED). Devuelve (inflación %, fecha del dato, error)."""
    try:
        ipc = pd.read_csv(FRED_IPC_EUROZONA)
        ipc.columns = ["fecha", "valor"]
        ipc["fecha"] = pd.to_datetime(ipc["fecha"])
        ipc["valor"] = pd.to_numeric(ipc["valor"], errors="coerce")
        ipc = ipc.dropna().set_index("fecha")["valor"]

        ultima = ipc.index[-1]
        hace_un_ano = ultima - pd.DateOffset(years=1)
        if hace_un_ano not in ipc.index:
            raise ValueError("falta el dato de hace 12 meses")
        inf = (ipc.loc[ultima] / ipc.loc[hace_un_ano] - 1) * 100
        return round(float(inf), 2), ultima.strftime("%m/%Y"), None
    except Exception as e:
        return INF_DEFECTO, None, f"{type(e).__name__}: {e}"

df_personal, error_sheets = cargar_datos_personales()
conectado_sheets = error_sheets is None

# --- BARRA LATERAL ---
st.sidebar.header("1. Fuente de Datos en Vivo")
ticker_sel = st.sidebar.selectbox("ETF / Índice de referencia", ["IWDA.AS", "SPY", "QQQ", "VWCE.DE"], index=0)
cagr_real, vol_real, anos_hist, serie_etf, error_etf = cargar_datos_etf(ticker_sel)
inf_real, fecha_ipc, error_ipc = cargar_inflacion()

if error_etf:
    st.sidebar.error(f"No se pudo descargar {ticker_sel} de Yahoo Finance. Se usan valores por defecto "
                     f"({CAGR_DEFECTO}% rentabilidad, {VOL_DEFECTO}% volatilidad).")
elif anos_hist < 9.5:
    st.sidebar.info(f"{ticker_sel} solo tiene {anos_hist} años de histórico: la rentabilidad es más incierta.")
if error_ipc:
    st.sidebar.error(f"No se pudo descargar el IPC de FRED. Se usa una inflación por defecto del {INF_DEFECTO}%.")

ahorro_detectado = 800
if not conectado_sheets:
    st.sidebar.warning("No se pudo conectar con Google Sheets. Usando ahorro por defecto (800 €/mes).")
elif df_personal.empty:
    st.sidebar.warning("La hoja 'Mi_Ahorro_Mensual' está vacía. Usando ahorro por defecto (800 €/mes).")
elif 'Ahorro_Invertido' not in df_personal.columns:
    st.sidebar.warning("La hoja no tiene la columna 'Ahorro_Invertido'. Usando ahorro por defecto (800 €/mes).")
else:
    serie_ahorro = pd.to_numeric(df_personal['Ahorro_Invertido'], errors='coerce').dropna()
    if serie_ahorro.empty:
        st.sidebar.warning("La columna 'Ahorro_Invertido' no tiene números válidos. Usando ahorro por defecto.")
    else:
        ahorro_detectado = int(serie_ahorro.mean())
        st.sidebar.success(f"Google Sheets conectado (Media: {ahorro_detectado} €/mes)")

st.sidebar.header("2. Parámetros del Simulador")
cap_ini = st.sidebar.slider("Capital Inicial (€)", 0, 200000, 0, 1000)
ahorro = st.sidebar.slider("Ahorro Mensual (€)", 0, 5000, min(max(ahorro_detectado, 0), 5000), 50)
indexar_ahorro = st.sidebar.checkbox("Subir el ahorro mensual cada año con la inflación", value=True,
                                     help="Si está activado, tu aportación crece con el IPC (mantiene su poder adquisitivo). "
                                          "Si no, aportas siempre los mismos euros nominales.")
anos = st.sidebar.slider("Horizonte (Años)", 5, 35, 20, 1)

st.sidebar.header("3. Variables Macro y Riesgo")
def limitar(valor, minimo, maximo):
    return float(min(max(valor, minimo), maximo))

etiqueta_hist = f"Histórico {ticker_sel}: {cagr_real}%" if not error_etf else "por defecto"
etiqueta_vol = f"Histórico {ticker_sel}: {vol_real}%" if not error_etf else "por defecto"
etiqueta_ipc = f"IPC Eurozona {fecha_ipc}: {inf_real}%" if not error_ipc else "por defecto"
r_base = st.sidebar.slider(f"Rentabilidad Anual % ({etiqueta_hist})", -5.0, 25.0, limitar(round(cagr_real * 2) / 2, -5.0, 25.0), 0.5) / 100
vol_anual = st.sidebar.slider(f"Volatilidad Anual % ({etiqueta_vol})", 5.0, 40.0, limitar(round(vol_real), 5.0, 40.0), 1.0) / 100
inf_base = st.sidebar.slider(f"Inflación Anual % ({etiqueta_ipc})", -1.0, 12.0, limitar(round(inf_real * 5) / 5, -1.0, 12.0), 0.2) / 100

with st.sidebar.expander("Escenario de estrés / estanflación"):
    r_estres = st.slider("Rentabilidad anual en estrés %", -5.0, 10.0, 3.0, 0.5) / 100
    inf_estres = st.slider("Inflación anual en estrés %", 0.0, 15.0, 5.0, 0.5) / 100

# --- MOTOR COMÚN (mensual) ---
# Ambos modelos (determinista y Monte Carlo) usan las mismas reglas:
# - la cartera rinde en términos nominales y se aporta al inicio de cada mes;
# - la aportación sube con la inflación si 'indexar_ahorro' está activado;
# - el resultado real se obtiene descontando la inflación acumulada.
meses = anos * 12
t_meses = np.arange(meses)
inf_mensual = (1 + inf_base) ** (1 / 12) - 1

def aportaciones(inflacion_anual):
    if indexar_ahorro:
        return ahorro * (1 + inflacion_anual) ** (t_meses // 12)
    return np.full(meses, float(ahorro))

def simular(r_anual, inflacion_anual):
    """Devuelve las series mensuales (nominal, real, efectivo real), de longitud meses+1."""
    r_m = (1 + r_anual) ** (1 / 12) - 1
    infl_m = (1 + inflacion_anual) ** (1 / 12) - 1
    aport = aportaciones(inflacion_anual)
    nominal = np.zeros(meses + 1)
    nominal[0] = cap_ini
    for t in range(meses):
        nominal[t + 1] = (nominal[t] + aport[t]) * (1 + r_m)
    deflactor = (1 + infl_m) ** np.arange(meses + 1)
    efectivo = np.concatenate([[cap_ini], cap_ini + np.cumsum(aport)])
    return nominal, nominal / deflactor, efectivo / deflactor

nom_b, real_b, efectivo_b = simular(r_base, inf_base)
_, real_e, _ = simular(r_estres, inf_estres)

idx = np.arange(12, meses + 1, 12)
df_sim = pd.DataFrame({
    "Año": np.arange(1, anos + 1),
    "1. Patrimonio Nominal (€)": nom_b[idx].round(2),
    "2. Poder Adquisitivo Real (€)": real_b[idx].round(2),
    "3. Banda Estrés / Estanflación (€)": real_e[idx].round(2),
    "4. Efectivo sin Invertir Real (€)": efectivo_b[idx].round(2),
}).set_index("Año")

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
    rng = np.random.default_rng(42)
    n_sims = 500

    # Retornos mensuales nominales log-normales: la mediana de cada trayectoria
    # crece a la rentabilidad elegida y la volatilidad añade dispersión.
    sigma_m = vol_anual / np.sqrt(12)
    mu_log_m = np.log1p(r_base) / 12
    retornos_sim = np.expm1(rng.normal(mu_log_m, sigma_m, (meses, n_sims)))

    aport = aportaciones(inf_base)
    trayectorias = np.zeros((meses + 1, n_sims))
    trayectorias[0] = cap_ini
    for t in range(1, meses + 1):
        trayectorias[t] = (trayectorias[t - 1] + aport[t - 1]) * (1 + retornos_sim[t - 1])

    # Pasar a euros de hoy (poder adquisitivo real)
    trayectorias = trayectorias / ((1 + inf_mensual) ** np.arange(meses + 1))[:, None]

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
    
    st.plotly_chart(fig, width='stretch')
    
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Escenario Pesimista (P10)", f"{p10[-1]:,.0f} €", help="Solo un 10% de los escenarios acaban por debajo de esta cifra")
    col_m2.metric("Escenario Mediano (P50)", f"{p50[-1]:,.0f} €", help="El resultado central más probable tras 500 simulaciones")
    col_m3.metric("Escenario Optimista (P90)", f"{p90[-1]:,.0f} €", help="El 10% de mejores rachas bursátiles superan esta cifra")

with tab3:
    if serie_etf is not None:
        st.subheader(f"Cotización últimos {anos_hist} años: {ticker_sel} (CAGR: {cagr_real}% | Volatilidad: {vol_real}%)")
        st.line_chart(serie_etf)
    else:
        st.warning(f"No se pudo descargar el histórico de {ticker_sel}.")
        st.caption(error_etf)

with tab4:
    if conectado_sheets and not df_personal.empty:
        st.subheader("Datos leídos en vivo desde 'Mi_Ahorro_Mensual'")
        st.dataframe(df_personal, width='stretch')
    elif conectado_sheets:
        st.info("La hoja 'Mi_Ahorro_Mensual' está conectada pero no tiene registros.")
    else:
        st.info("No se pudo leer Google Sheets. Revisa las credenciales en Settings > Secrets "
                "y que la hoja esté compartida con la cuenta de servicio.")
        st.caption(error_sheets)
