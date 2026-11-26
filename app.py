"""Tu ahorro en euros de hoy: proyección del poder adquisitivo real con datos en vivo."""
import hmac
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import datos
from estilo import eur, pct, estilo_fig, hero, linea, mostrar, paleta
from finanzas import gasto_mensual_medio, mostrar_mis_finanzas
from simulacion import primer_ano, simular

st.set_page_config(page_title="Tu ahorro en euros de hoy", page_icon="💶", layout="wide")

N_SIMS = 500
ETFS = ["IWDA.AS", "VWCE.DE", "SPY", "QQQ"]


# --- Acceso con contraseña ---
def leer_secreto(nombre):
    try:
        return st.secrets.get(nombre)
    except Exception:  # sin archivo de secretos
        return None


def comprobar_acceso():
    """Pide la contraseña del secreto 'app_password'. Si no existe, la app queda abierta y lo avisa."""
    clave = leer_secreto("app_password")
    if not clave:
        st.sidebar.error("Esta app no tiene contraseña: cualquiera con el enlace ve tus datos. "
                         "Añade app_password en Settings › Secrets.")
        return
    if st.session_state.get("acceso_ok"):
        if st.sidebar.button("Cerrar sesión"):
            st.session_state["acceso_ok"] = False
            st.rerun()
        return

    _, centro, _ = st.columns([1, 1.2, 1])
    with centro:
        st.title("Tu ahorro en euros de hoy")
        st.write("Introduce la contraseña para ver tus finanzas.")
        with st.form("login"):
            intento = st.text_input("Contraseña", type="password")
            entrar = st.form_submit_button("Entrar", type="primary", width="stretch")
        if entrar:
            if hmac.compare_digest(intento.encode(), str(clave).encode()):
                st.session_state["acceso_ok"] = True
                st.rerun()
            st.error("La contraseña no es correcta.")
    st.stop()


comprobar_acceso()
p = paleta()

# --- Datos ---
df_personal, error_sheets = datos.cargar_hoja()
hay_hoja = error_sheets is None and not df_personal.empty


def limitar(valor, minimo, maximo):
    return float(min(max(valor, minimo), maximo))


# --- Barra lateral ---
with st.sidebar:
    st.header("Tus datos")
    if error_sheets:
        ahorro_hoja = datos.AHORRO_DEFECTO
        st.warning(f"No se pudo leer Google Sheets. Se usa un ahorro de {datos.AHORRO_DEFECTO} €/mes.")
    else:
        ahorro_hoja, aviso = datos.ahorro_medio(df_personal)
        if aviso:
            st.warning(f"{aviso} Se usa un ahorro de {datos.AHORRO_DEFECTO} €/mes.")
        else:
            st.caption(f"Google Sheets conectado. Inviertes de media {eur(ahorro_hoja)} al mes.")

    cap_ini = st.slider("Capital invertido hoy (€)", 0, 200000, 0, 1000)
    ahorro = st.slider("Ahorro mensual (€)", 0, 5000, int(limitar(ahorro_hoja, 0, 5000)), 50)
    indexar = st.checkbox("Subir el ahorro cada año con la inflación", value=True,
                          help="Activado: tu aportación crece con el IPC y mantiene su poder adquisitivo. "
                               "Desactivado: aportas siempre los mismos euros.")
    anos = st.slider("Horizonte (años)", 5, 35, 20, 1)
    saldo_previo = st.number_input("Efectivo que tenías antes de tu primer registro (€)", 0, 10_000_000, 0, 100,
                                   help="Se suma a tu Liquidez_Efectivo mensual para calcular tu colchón.")

    st.header("Mercado e inflación")
    ticker = st.selectbox("ETF de referencia", ETFS)
    cagr, vol, anos_hist, serie_etf, error_etf = datos.cargar_etf(ticker)
    inf_actual, fecha_ipc, serie_ipc, error_ipc = datos.cargar_inflacion()
    if error_etf:
        st.error(f"No se pudo descargar {ticker} de Yahoo Finance. Se usan {datos.CAGR_DEFECTO} % de "
                 f"rentabilidad y {datos.VOL_DEFECTO} % de volatilidad.")
    elif anos_hist < 9.5:
        st.info(f"{ticker} solo tiene {str(anos_hist).replace('.', ',')} años de histórico: su rentabilidad es más incierta.")
    if error_ipc:
        st.error(f"No se pudo descargar el IPC de FRED. Se usa una inflación del {datos.INF_DEFECTO} %.")

    r_base = st.slider("Rentabilidad anual (%)", -5.0, 25.0, limitar(round(cagr * 2) / 2, -5.0, 25.0), 0.5,
                       help=f"Histórico de {ticker}: {cagr} % anual" if not error_etf else "Valor por defecto") / 100
    vol_anual = st.slider("Volatilidad anual (%)", 5.0, 40.0, limitar(round(vol), 5.0, 40.0), 1.0,
                          help=f"Histórico de {ticker}: {vol} %" if not error_etf else "Valor por defecto") / 100
    inf_base = st.slider("Inflación anual (%)", -1.0, 12.0, limitar(round(inf_actual * 5) / 5, -1.0, 12.0), 0.2,
                         help=f"IPC Eurozona {fecha_ipc}: {inf_actual} %" if not error_ipc else "Valor por defecto") / 100

    with st.expander("Escenario de estanflación"):
        r_estres = st.slider("Rentabilidad anual (%)", -5.0, 10.0, 3.0, 0.5, key="r_estres") / 100
        inf_estres = st.slider("Inflación anual (%)", 0.0, 15.0, 5.0, 0.5, key="inf_estres") / 100

# --- Simulaciones (un solo motor para todo) ---
anos_mc = max(anos, 40)  # horizonte largo para el objetivo de independencia financiera
nom_b, real_b, aportado = simular(cap_ini, ahorro, indexar, r_base, 0.0, inf_base, anos)
nom_b, real_b = nom_b[:, 0], real_b[:, 0]
real_e = simular(cap_ini, ahorro, indexar, r_estres, 0.0, inf_estres, anos)[1][:, 0]
efectivo = simular(cap_ini, ahorro, indexar, 0.0, 0.0, inf_base, anos)[1][:, 0]
_, tray_mc, _ = simular(cap_ini, ahorro, indexar, r_base, vol_anual, inf_base, anos_mc, N_SIMS)
ano_actual = datetime.today().year
eje = ano_actual + np.arange(anos + 1)

# --- Cabecera ---
hero(anos, nom_b[-1], real_b[-1])
c1, c2, c3 = st.columns(3)
c1.metric("Lo que pones de tu bolsillo", eur(aportado[-1]), border=True,
          delta=f"{eur(ahorro)} al mes durante {anos} años", delta_color="off", delta_arrow="off",
          help="Capital inicial más todas tus aportaciones, en euros nominales")
c2.metric("Si llega una estanflación", eur(real_e[-1]), border=True,
          delta=f"-{eur(real_b[-1] - real_e[-1])} frente al escenario base", delta_color="normal",
          help=f"Rentabilidad del {pct(r_estres * 100)} e inflación del {pct(inf_estres * 100)}, en euros de hoy")
c3.metric("Si lo dejas en efectivo", eur(efectivo[-1]), border=True,
          delta=f"-{eur(real_b[-1] - efectivo[-1])} frente a invertir", delta_color="normal",
          help="Sin invertir, solo pierde valor con la inflación. En euros de hoy")

st.space("medium")
tabs = st.tabs(["Mis finanzas", "Independencia financiera", "Proyección", "Monte Carlo", "ETF", "Datos de la hoja"])

# --- Mis finanzas ---
with tabs[0]:
    if hay_hoja:
        if error_ipc:
            st.caption("Sin datos del IPC: los importes no se ajustan por inflación.")
        mostrar_mis_finanzas(df_personal, serie_ipc, saldo_previo)
    else:
        st.info("Conecta Google Sheets para ver aquí el análisis de tus ingresos, gastos e inversión.")

# --- Independencia financiera ---
with tabs[1]:
    st.subheader("¿Cuándo podrías vivir de tus inversiones?")
    st.write("Con la regla del 4 %, si tu cartera vale 25 veces lo que gastas en un año, puedes retirar ese "
             "gasto cada año, ajustado por inflación, con muchas probabilidades de que dure 30 años o más.")

    gasto_hoja = gasto_mensual_medio(df_personal) if hay_hoja else None
    col_g, col_r = st.columns(2)
    gasto_mes = col_g.number_input(
        "Gasto mensual que quieres cubrir (€ de hoy)", min_value=100, max_value=50000, step=50,
        value=int(round(gasto_hoja / 50) * 50) if gasto_hoja else 1500,
        help="Por defecto, la media de Gastos_Fijos de tus últimos 12 meses. "
             "Súmale ocio, comida o viajes si no están incluidos.")
    tasa_retiro = col_r.slider("Tasa de retiro (%)", 2.5, 5.0, 4.0, 0.25,
                               help="Un 3,5 % es más prudente para jubilaciones muy largas.") / 100
    objetivo = gasto_mes * 12 / tasa_retiro

    prob = (tray_mc >= objetivo).mean(axis=1) * 100
    ano_50 = primer_ano(np.median(tray_mc, axis=1) >= objetivo)
    ano_90 = primer_ano(prob >= 90)

    def cuando(a):
        return f"{ano_actual + a}" if a is not None else f"Después de {ano_actual + anos_mc}"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tu objetivo", eur(objetivo), border=True, help=f"{eur(gasto_mes)} × 12 / {pct(tasa_retiro * 100, 2)}")
    c2.metric("Llevas", pct(min(cap_ini / objetivo * 100, 999)), border=True,
              help="Capital invertido hoy (barra lateral) / objetivo")
    c3.metric("Lo más probable", cuando(ano_50), border=True,
              help="En la mitad de los escenarios ya lo habrías alcanzado")
    c4.metric("Casi seguro", cuando(ano_90), border=True, help="Solo un 10 % de los escenarios tardan más")

    fig = go.Figure()
    fig.add_scatter(x=ano_actual + np.arange(anos_mc + 1), y=prob, mode="lines", name="Probabilidad",
                    line=dict(color=p["real"], width=2), fill="tozeroy",
                    fillcolor=p["real"] + "22", hovertemplate="%{x}: %{y:.0f} %<extra></extra>")
    for nivel in (50, 90):
        fig.add_hline(y=nivel, line=dict(color=p["nominal"], width=1, dash="dot"),
                      annotation_text=f"{nivel} %", annotation_font_color=p["texto_2"])
    fig.update_yaxes(range=[0, 100], ticksuffix=" %")
    mostrar(estilo_fig(fig, titulo_y="Probabilidad", leyenda=False))

    st.markdown("**¿Y si ahorrases un poco más?**")
    filas = []
    for extra in (0, 100, 250, 500):
        _, tr, _ = simular(cap_ini, ahorro + extra, indexar, r_base, vol_anual, inf_base, anos_mc, N_SIMS)
        a = primer_ano(np.median(tr, axis=1) >= objetivo)
        filas.append({"Ahorro mensual": eur(ahorro + extra), "Lo alcanzarías en": cuando(a),
                      "Años que adelantas": str(ano_50 - a) if None not in (a, ano_50) else "—"})
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.caption(f"Simulación orientativa con {N_SIMS} escenarios. No incluye impuestos ni comisiones.")

# --- Proyección ---
with tabs[2]:
    st.subheader(f"Cómo crece tu patrimonio en {anos} años")
    fig = go.Figure()
    linea(fig, eje, nom_b, "Sobre el papel (nominal)", p["nominal"], discontinua=True)
    linea(fig, eje, real_b, "En euros de hoy", p["real"], ancho=3)
    linea(fig, eje, real_e, "Con estanflación", p["erosion"])
    linea(fig, eje, efectivo, "En efectivo, sin invertir", p["liquidez"])
    fig.update_traces(hovertemplate="%{y:,.0f} €")
    fig.update_yaxes(ticksuffix=" €")
    mostrar(estilo_fig(fig, alto=440))
    st.caption("Todas las líneas salvo la nominal están en euros de hoy, descontando la inflación.")

# --- Monte Carlo ---
with tabs[3]:
    st.subheader(f"{N_SIMS} escenarios de mercado en euros de hoy")
    st.write(f"Cada escenario usa la volatilidad de {ticker}. La banda contiene el 80 % de los resultados.")
    tr = tray_mc[: anos + 1]
    p10, p50, p90 = (np.percentile(tr, q, axis=1) for q in (10, 50, 90))
    fig = go.Figure()
    fig.add_scatter(x=np.concatenate([eje, eje[::-1]]), y=np.concatenate([p90, p10[::-1]]), fill="toself",
                    fillcolor=p["real"] + "26", line=dict(width=0), hoverinfo="skip", name="80 % de los escenarios")
    linea(fig, eje, p90, "Optimista (P90)", p["real"], discontinua=True, ancho=1.5)
    linea(fig, eje, p50, "Mediano (P50)", p["real"], ancho=3)
    linea(fig, eje, p10, "Pesimista (P10)", p["erosion"], discontinua=True, ancho=1.5)
    fig.update_traces(hovertemplate="%{y:,.0f} €", selector=dict(mode="lines"))
    mostrar(estilo_fig(fig, alto=460, titulo_y="€ de hoy"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Pesimista", eur(p10[-1]), border=True, help="Solo un 10 % de los escenarios acaba por debajo")
    c2.metric("Mediano", eur(p50[-1]), border=True, help="La mitad de los escenarios acaba por encima")
    c3.metric("Optimista", eur(p90[-1]), border=True, help="Solo un 10 % de los escenarios acaba por encima")

# --- ETF ---
with tabs[4]:
    if serie_etf is not None:
        st.subheader(f"{ticker} en los últimos {str(anos_hist).replace('.', ',')} años")
        c1, c2 = st.columns(2)
        c1.metric("Rentabilidad anual media", pct(cagr), border=True)
        c2.metric("Volatilidad anual", pct(vol), border=True)
        fig = go.Figure()
        linea(fig, serie_etf.index, serie_etf.values, ticker, p["real"], hovertemplate="%{y:,.2f}")
        mostrar(estilo_fig(fig, titulo_y="Precio de cierre", leyenda=False, fechas=True))
    else:
        st.warning(f"No se pudo descargar el histórico de {ticker}. Vuelve a intentarlo en unos minutos.")
        st.caption(error_etf)

# --- Datos de la hoja ---
with tabs[5]:
    if hay_hoja:
        st.subheader(f"Tu hoja '{datos.HOJA}'")
        st.dataframe(df_personal, width="stretch", hide_index=True)
    elif error_sheets:
        st.info("No se pudo leer Google Sheets. Revisa las credenciales en Settings › Secrets y que la hoja "
                "esté compartida con la cuenta de servicio.")
        st.caption(error_sheets)
    else:
        st.info(f"La hoja '{datos.HOJA}' está conectada pero aún no tiene registros.")
