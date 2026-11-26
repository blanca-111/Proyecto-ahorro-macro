"""Carga de datos externos: Google Sheets, Yahoo Finance y FRED.

Cada función devuelve un valor utilizable aunque la fuente falle, junto con el
mensaje de error, para que la app siga funcionando y pueda avisar en pantalla.
"""
from datetime import datetime

import gspread
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from finanzas import a_numero

# Valores por defecto si alguna fuente falla
CAGR_DEFECTO, VOL_DEFECTO, INF_DEFECTO, AHORRO_DEFECTO = 7.5, 15.0, 2.8, 800
FRED_IPC_EUROZONA = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CP0000EZ19M086NEST"
HOJA = "Mi_Ahorro_Mensual"


@st.cache_data(ttl=300)
def cargar_hoja():
    """Primera pestaña de la hoja de Google Sheets. Devuelve (DataFrame, error)."""
    try:
        gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
        return pd.DataFrame(gc.open(HOJA).sheet1.get_all_records()), None
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


def ahorro_medio(df):
    """Media de Ahorro_Invertido. Devuelve (ahorro €/mes, aviso o None)."""
    if df.empty:
        return AHORRO_DEFECTO, f"La hoja '{HOJA}' está vacía."
    if "Ahorro_Invertido" not in df.columns:
        return AHORRO_DEFECTO, "La hoja no tiene la columna 'Ahorro_Invertido'."
    serie = df["Ahorro_Invertido"].map(a_numero).dropna()
    if serie.empty:
        return AHORRO_DEFECTO, "La columna 'Ahorro_Invertido' no tiene números válidos."
    return int(serie.mean()), None


@st.cache_data(ttl=3600)
def cargar_etf(ticker):
    """Hasta 10 años de cierres. Devuelve (cagr %, volatilidad %, años de histórico, serie, error)."""
    try:
        fin = datetime.today()
        hist = yf.download(ticker, start=datetime(fin.year - 10, fin.month, 1), end=fin, progress=False)["Close"]
        if isinstance(hist, pd.DataFrame):
            hist = hist.iloc[:, 0]
        hist = hist.dropna()
        if len(hist) < 2:
            raise ValueError("sin datos de cotización")
        # Años reales cubiertos por los datos (un ETF puede tener menos de 10)
        anos = (hist.index[-1] - hist.index[0]).days / 365.25
        cagr = ((hist.iloc[-1] / hist.iloc[0]) ** (1 / anos) - 1) * 100
        vol = hist.pct_change().std() * np.sqrt(252) * 100
        return round(float(cagr), 2), round(float(vol), 2), round(anos, 1), hist, None
    except Exception as e:
        return CAGR_DEFECTO, VOL_DEFECTO, None, None, f"{type(e).__name__}: {e}"


@st.cache_data(ttl=3600)
def cargar_ipc_mensual():
    """Serie mensual del IPC Eurozona (FRED), indexada por el primer día de cada mes."""
    ipc = pd.read_csv(FRED_IPC_EUROZONA)
    ipc.columns = ["fecha", "valor"]
    ipc["fecha"] = pd.to_datetime(ipc["fecha"])
    ipc["valor"] = pd.to_numeric(ipc["valor"], errors="coerce")
    return ipc.dropna().set_index("fecha")["valor"]


def cargar_inflacion():
    """Inflación interanual del IPC Eurozona. Devuelve (inflación %, fecha del dato, serie IPC, error)."""
    try:
        ipc = cargar_ipc_mensual()
        ultima = ipc.index[-1]
        hace_un_ano = ultima - pd.DateOffset(years=1)
        if hace_un_ano not in ipc.index:
            raise ValueError("falta el dato de hace 12 meses")
        inf = (ipc.loc[ultima] / ipc.loc[hace_un_ano] - 1) * 100
        return round(float(inf), 2), ultima.strftime("%m/%Y"), ipc, None
    except Exception as e:
        return INF_DEFECTO, None, None, f"{type(e).__name__}: {e}"
