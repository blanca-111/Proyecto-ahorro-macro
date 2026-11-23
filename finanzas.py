"""Análisis de las finanzas personales registradas en Google Sheets.

Columnas esperadas en la hoja 'Mi_Ahorro_Mensual':
Fecha | Ingresos_Netos | Gastos_Fijos | Ahorro_Invertido | Activo_Principal | Liquidez_Efectivo
"""
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

COLUMNAS_NUMERICAS = ["Ingresos_Netos", "Gastos_Fijos", "Ahorro_Invertido", "Liquidez_Efectivo"]
COLUMNAS_OBLIGATORIAS = ["Fecha", "Ingresos_Netos", "Gastos_Fijos", "Ahorro_Invertido"]

VERDE, ROJO, AZUL, GRIS, AMARILLO = "#2ecc71", "#e74c3c", "#3498db", "#95a5a6", "#f1c40f"


def a_numero(valor):
    """Convierte valores de Sheets ('1.234,56 €', '1234.5', 900) a float. Vacío -> NaN."""
    if isinstance(valor, (int, float, np.number)):
        return float(valor)
    if valor is None:
        return np.nan
    texto = re.sub(r"[€\s]", "", str(valor))
    if not texto:
        return np.nan
    if "," in texto and "." in texto:
        # El separador que aparece último es el decimal
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    elif texto.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", texto):
        # '1.200' o '1.200.000' -> separador de miles
        texto = texto.replace(".", "")
    try:
        return float(texto)
    except ValueError:
        return np.nan


def a_fecha(serie):
    """Fechas tipo '01/03/2025', '2025-03-01', '03/2025' o '2025-03' -> primer día del mes."""
    texto = serie.astype(str).str.strip().str.split(" ").str[0]  # quita la hora si la hay
    fechas = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")

    iso = texto.str.fullmatch(r"\d{4}-\d{1,2}(-\d{1,2})?")           # 2025-04-01 / 2025-04
    fechas[iso] = pd.to_datetime(texto[iso].str.slice(0, 7) + "-01", format="%Y-%m-%d", errors="coerce")

    solo_mes = texto.str.fullmatch(r"\d{1,2}[/-]\d{4}")               # 04/2025
    fechas[solo_mes] = pd.to_datetime("01/" + texto[solo_mes].str.replace("-", "/"), format="%d/%m/%Y", errors="coerce")

    resto = fechas.isna() & ~iso & ~solo_mes                          # 01/04/2025 (día primero)
    fechas[resto] = pd.to_datetime(texto[resto], dayfirst=True, format="mixed", errors="coerce")
    return fechas.dt.to_period("M").dt.to_timestamp()


def preparar_datos(df):
    """Limpia la hoja y devuelve (df mensual ordenado, lista de avisos)."""
    avisos = []
    faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in df.columns]
    if faltan:
        return pd.DataFrame(), [f"Faltan columnas en la hoja: {', '.join(faltan)}"]

    df = df.copy()
    df["Fecha"] = a_fecha(df["Fecha"])
    for c in COLUMNAS_NUMERICAS:
        if c in df.columns:
            df[c] = df[c].map(a_numero)

    sin_fecha = df["Fecha"].isna() & df[COLUMNAS_OBLIGATORIAS[1:]].notna().any(axis=1)
    if sin_fecha.any():
        avisos.append(f"{int(sin_fecha.sum())} fila(s) con fecha no reconocida se han ignorado.")
    df = df.dropna(subset=["Fecha"])
    df = df[df[COLUMNAS_OBLIGATORIAS[1:]].notna().any(axis=1)]

    duplicados = df["Fecha"].duplicated(keep=False)
    if duplicados.any():
        meses = sorted(df.loc[duplicados, "Fecha"].dt.strftime("%m/%Y").unique())
        avisos.append(f"Meses repetidos (se suman): {', '.join(meses)}.")
        agregaciones = {c: "sum" for c in COLUMNAS_NUMERICAS if c in df.columns}
        if "Liquidez_Efectivo" in agregaciones:
            agregaciones["Liquidez_Efectivo"] = "last"  # es un saldo, no un flujo
        if "Activo_Principal" in df.columns:
            agregaciones["Activo_Principal"] = "last"
        df = df.groupby("Fecha", as_index=False).agg(agregaciones)

    df = df.sort_values("Fecha").reset_index(drop=True)
    if not df.empty:
        todos = pd.date_range(df["Fecha"].min(), df["Fecha"].max(), freq="MS")
        huecos = todos.difference(df["Fecha"])
        if len(huecos):
            avisos.append(f"Faltan {len(huecos)} mes(es) sin registrar: "
                          f"{', '.join(huecos.strftime('%m/%Y')[:6])}{'…' if len(huecos) > 6 else ''}.")
    return df, avisos


def euros(x):
    return f"{x:,.0f} €".replace(",", ".")


def pct(x):
    return f"{x:.1f} %".replace(".", ",")


def mostrar_mis_finanzas(df_bruto, ipc_mensual):
    """Pinta la pestaña 'Mis finanzas'. ipc_mensual: serie del IPC indexada por mes (o None)."""
    df, avisos = preparar_datos(df_bruto)
    for a in avisos:
        st.warning(a)
    if df.empty:
        st.info("No hay registros válidos para analizar.")
        return

    ing, gas, inv = df["Ingresos_Netos"].fillna(0), df["Gastos_Fijos"].fillna(0), df["Ahorro_Invertido"].fillna(0)
    df["Sobrante"] = ing - gas - inv
    df["Tasa_Ahorro"] = np.where(ing > 0, (ing - gas) / ing * 100, np.nan)
    df["Tasa_Inversion"] = np.where(ing > 0, inv / ing * 100, np.nan)
    df["Aportado_Acumulado"] = inv.cumsum()

    # --- Ajuste por inflación: todo en euros del último mes con IPC disponible ---
    hay_ipc = ipc_mensual is not None and len(ipc_mensual) > 0
    if hay_ipc:
        ipc_meses = ipc_mensual.reindex(pd.date_range(min(ipc_mensual.index.min(), df["Fecha"].min()),
                                                      max(ipc_mensual.index.max(), df["Fecha"].max()), freq="MS")).ffill().bfill()
        ipc_ref = ipc_meses.iloc[-1]
        factor = (ipc_ref / ipc_meses.reindex(df["Fecha"]).to_numpy())
        df["Aportado_Real"] = (inv * factor).cumsum()
        df["Gastos_Reales"] = gas * factor
        df["Ingresos_Reales"] = ing * factor

    ultimos12 = df.tail(12)
    n = len(ultimos12)
    gasto_medio = ultimos12["Gastos_Fijos"].mean()
    liquidez = df["Liquidez_Efectivo"].dropna().iloc[-1] if "Liquidez_Efectivo" in df and df["Liquidez_Efectivo"].notna().any() else None

    # --- KPIs ---
    st.subheader(f"Resumen de los últimos {n} meses")
    c1, c2, c3, c4 = st.columns(4)
    tasa = ultimos12["Tasa_Ahorro"].mean()
    tasa_prev = df.iloc[-24:-12]["Tasa_Ahorro"].mean() if len(df) > 12 else np.nan
    c1.metric("Tasa de ahorro media", pct(tasa),
              delta=None if np.isnan(tasa_prev) else f"{tasa - tasa_prev:+.1f} pp vs. 12 meses anteriores",
              help="(Ingresos − Gastos fijos) / Ingresos")
    c2.metric("Invertido / ingresos", pct(ultimos12["Tasa_Inversion"].mean()),
              help="Parte de tus ingresos que acaba invertida")
    c3.metric("Total aportado", euros(df["Aportado_Acumulado"].iloc[-1]),
              delta=f"{euros(df['Aportado_Real'].iloc[-1])} en euros de hoy" if hay_ipc else None,
              delta_color="off", help="Suma de Ahorro_Invertido. En euros de hoy: cada aportación revalorizada con el IPC")
    if liquidez is not None and gasto_medio > 0:
        meses_colchon = liquidez / gasto_medio
        c4.metric("Fondo de emergencia", f"{meses_colchon:.1f} meses".replace(".", ","),
                  delta="OK (≥ 6 meses)" if meses_colchon >= 6 else "Por debajo de 6 meses",
                  delta_color="normal" if meses_colchon >= 6 else "inverse",
                  help=f"Liquidez actual ({euros(liquidez)}) / gasto fijo medio ({euros(gasto_medio)})")
    else:
        c4.metric("Fondo de emergencia", "—", help="Rellena Liquidez_Efectivo para calcularlo")

    sobrante_medio = ultimos12["Sobrante"].mean()
    if sobrante_medio > 50:
        st.info(f"Cada mes te quedan de media **{euros(sobrante_medio)}** sin gastar ni invertir "
                f"(ingresos − gastos − inversión). Si no es liquidez que quieras mantener, es capacidad de inversión extra.")
    elif sobrante_medio < -50:
        st.warning(f"De media gastas e inviertes **{euros(-sobrante_medio)}** más de lo que ingresas al mes: "
                   "revisa si estás tirando de liquidez.")

    # --- Flujo mensual ---
    st.subheader("Flujo mensual")
    fig = go.Figure()
    fig.add_bar(x=df["Fecha"], y=df["Gastos_Fijos"], name="Gastos fijos", marker_color=ROJO)
    fig.add_bar(x=df["Fecha"], y=df["Ahorro_Invertido"], name="Invertido", marker_color=VERDE)
    fig.add_bar(x=df["Fecha"], y=df["Sobrante"].clip(lower=0), name="Sobrante", marker_color=GRIS)
    fig.add_scatter(x=df["Fecha"], y=df["Ingresos_Netos"], name="Ingresos netos", mode="lines+markers",
                    line=dict(color=AZUL, width=3))
    fig.update_layout(barmode="stack", template="plotly_dark", height=420, hovermode="x unified",
                      yaxis_title="€ / mes", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, width="stretch")

    # --- Tasa de ahorro ---
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Tasa de ahorro")
        fig = go.Figure()
        fig.add_bar(x=df["Fecha"], y=df["Tasa_Ahorro"], name="Mensual", marker_color=VERDE, opacity=0.5)
        fig.add_scatter(x=df["Fecha"], y=df["Tasa_Ahorro"].rolling(3, min_periods=1).mean(),
                        name="Media móvil 3 meses", line=dict(color=AMARILLO, width=3))
        fig.update_layout(template="plotly_dark", height=350, yaxis_title="%", hovermode="x unified",
                          legend=dict(orientation="h", y=1.15))
        st.plotly_chart(fig, width="stretch")

    # --- Aportado nominal vs real ---
    with col_b:
        st.subheader("Capital aportado")
        fig = go.Figure()
        fig.add_scatter(x=df["Fecha"], y=df["Aportado_Acumulado"], name="Nominal (lo que pusiste)",
                        line=dict(color=GRIS, dash="dash"))
        if hay_ipc:
            fig.add_scatter(x=df["Fecha"], y=df["Aportado_Real"], name="En euros de hoy (IPC)",
                            line=dict(color=VERDE, width=3))
        fig.update_layout(template="plotly_dark", height=350, yaxis_title="€", hovermode="x unified",
                          legend=dict(orientation="h", y=1.15))
        st.plotly_chart(fig, width="stretch")
        if hay_ipc:
            st.caption("Para no perder poder adquisitivo, tu cartera debería valer al menos la línea verde.")

    # --- Inflación personal ---
    if hay_ipc and len(df) >= 13:
        st.subheader("Tus gastos frente a la inflación")
        g = df.set_index("Fecha")["Gastos_Fijos"]
        ipc_df = ipc_meses.reindex(df["Fecha"])
        anos = (df["Fecha"].iloc[-1] - df["Fecha"].iloc[0]).days / 365.25
        crec_gasto_total = (g.tail(3).mean() / g.head(3).mean()) ** (1 / anos) - 1 if anos > 0 and g.head(3).mean() > 0 else np.nan
        crec_ipc = (ipc_df.iloc[-1] / ipc_df.iloc[0]) ** (1 / anos) - 1 if anos > 0 else np.nan
        c1, c2 = st.columns(2)
        c1.metric("Tus gastos fijos crecen", pct(crec_gasto_total * 100) + " /año",
                  help="Media de los 3 últimos meses frente a los 3 primeros, anualizado")
        c2.metric("IPC Eurozona en el mismo periodo", pct(crec_ipc * 100) + " /año",
                  delta=f"{(crec_gasto_total - crec_ipc) * 100:+.1f} pp tu inflación personal vs IPC",
                  delta_color="inverse")
        base_g, base_i = g.head(3).mean(), ipc_df.iloc[0]
        fig = go.Figure()
        fig.add_scatter(x=df["Fecha"], y=g.rolling(3, min_periods=1).mean() / base_g * 100,
                        name="Tus gastos fijos (media 3m)", line=dict(color=ROJO, width=3))
        fig.add_scatter(x=df["Fecha"], y=ipc_df.to_numpy() / base_i * 100, name="IPC Eurozona",
                        line=dict(color=AZUL, dash="dash"))
        fig.update_layout(template="plotly_dark", height=350, yaxis_title="Índice (inicio = 100)",
                          hovermode="x unified", legend=dict(orientation="h", y=1.15))
        st.plotly_chart(fig, width="stretch")

    # --- Activos ---
    if "Activo_Principal" in df.columns:
        activos = df["Activo_Principal"].astype(str).str.strip()
        activos = activos[activos.ne("") & activos.ne("nan")]
        if len(activos) and pd.to_numeric(activos, errors="coerce").isna().all():
            st.subheader("¿Dónde inviertes?")
            reparto = df.loc[activos.index].groupby(activos)["Ahorro_Invertido"].sum().sort_values(ascending=False)
            fig = go.Figure(go.Pie(labels=reparto.index, values=reparto.values, hole=0.5))
            fig.update_layout(template="plotly_dark", height=350)
            st.plotly_chart(fig, width="stretch")

    with st.expander("Ver datos procesados"):
        st.dataframe(df, width="stretch")
