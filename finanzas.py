"""Análisis de las finanzas personales registradas en Google Sheets.

Columnas esperadas en la hoja 'Mi_Ahorro_Mensual':
Fecha | Ingresos_Netos | Gastos_Fijos | Ahorro_Invertido | Activo_Principal | Liquidez_Efectivo

Liquidez_Efectivo es lo que se aparta cada mes en efectivo (un flujo), no el saldo total.
"""
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from estilo import eur, estilo_fig, linea, mostrar, paleta, pct

COLUMNAS_NUMERICAS = ["Ingresos_Netos", "Gastos_Fijos", "Ahorro_Invertido", "Liquidez_Efectivo"]
COLUMNAS_OBLIGATORIAS = ["Fecha", "Ingresos_Netos", "Gastos_Fijos", "Ahorro_Invertido"]


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
        mes_pasado = (pd.Timestamp.today().to_period("M") - 1).to_timestamp()
        if df["Fecha"].max() < mes_pasado:
            sin_datos = len(pd.date_range(df["Fecha"].max(), mes_pasado, freq="MS")) - 1
            avisos.append(f"El último registro es de {df['Fecha'].max():%m/%Y}: faltan {sin_datos} mes(es) "
                          f"hasta {mes_pasado:%m/%Y}. Los resúmenes no incluyen esos meses.")
    return df, avisos


def gasto_mensual_medio(df_bruto, meses=12):
    """Media de Gastos_Fijos de los últimos 'meses' registrados (None si no hay datos)."""
    df, _ = preparar_datos(df_bruto)
    if df.empty or df["Gastos_Fijos"].dropna().empty:
        return None
    return float(df["Gastos_Fijos"].dropna().tail(meses).mean())


def mostrar_mis_finanzas(df_bruto, ipc_mensual, saldo_inicial=0):
    """Pinta la pestaña 'Mis finanzas'.

    ipc_mensual: serie del IPC indexada por mes (o None).
    saldo_inicial: efectivo que ya había antes del primer mes registrado.
    """
    p = paleta()
    df, avisos = preparar_datos(df_bruto)
    for a in avisos:
        st.warning(a)
    if df.empty:
        st.info("La hoja no tiene registros válidos. Añade al menos un mes con fecha, ingresos, gastos e inversión.")
        return

    ing, gas, inv = df["Ingresos_Netos"].fillna(0), df["Gastos_Fijos"].fillna(0), df["Ahorro_Invertido"].fillna(0)
    df["Sobrante"] = ing - gas - inv
    df["Tasa_Ahorro"] = np.where(ing > 0, (ing - gas) / ing * 100, np.nan)
    df["Tasa_Inversion"] = np.where(ing > 0, inv / ing * 100, np.nan)
    df["Aportado_Acumulado"] = inv.cumsum()

    # Ajuste por inflación: todo en euros del último mes con IPC disponible
    hay_ipc = ipc_mensual is not None and len(ipc_mensual) > 0
    if hay_ipc:
        meses_ipc = pd.date_range(min(ipc_mensual.index.min(), df["Fecha"].min()),
                                  max(ipc_mensual.index.max(), df["Fecha"].max()), freq="MS")
        ipc_meses = ipc_mensual.reindex(meses_ipc).ffill().bfill()
        df["Aportado_Real"] = (inv * ipc_meses.iloc[-1] / ipc_meses.reindex(df["Fecha"]).to_numpy()).cumsum()

    # Liquidez_Efectivo es lo que apartas en efectivo cada mes; si no existe, se usa el sobrante
    tiene_liquidez = "Liquidez_Efectivo" in df and df["Liquidez_Efectivo"].notna().any()
    df["Efectivo_Mes"] = df["Liquidez_Efectivo"].fillna(0) if tiene_liquidez else df["Sobrante"].clip(lower=0)
    liquidez = saldo_inicial + df["Efectivo_Mes"].sum()
    ultimos12 = df.tail(12)
    gasto_medio = ultimos12["Gastos_Fijos"].mean()

    # --- Resumen ---
    st.subheader(f"Tus últimos {len(ultimos12)} meses")
    c1, c2, c3, c4 = st.columns(4)
    tasa = ultimos12["Tasa_Ahorro"].mean()
    tasa_prev = df.iloc[-24:-12]["Tasa_Ahorro"].mean() if len(df) > 12 else np.nan
    c1.metric("Ahorras", pct(tasa), border=True,
              delta=f"{eur(ultimos12['Ingresos_Netos'].mean() - gasto_medio)} al mes" if np.isnan(tasa_prev)
              else f"{tasa - tasa_prev:+.1f} puntos en un año".replace(".", ","),
              delta_color="off" if np.isnan(tasa_prev) else "normal",
              help="(Ingresos − gastos fijos) / ingresos. La variación compara con los 12 meses anteriores")
    c2.metric("Inviertes", pct(ultimos12["Tasa_Inversion"].mean()), border=True,
              delta=f"{eur(ultimos12['Ahorro_Invertido'].mean())} al mes", delta_color="off", delta_arrow="off",
              help="Parte de tus ingresos que acaba invertida")
    c3.metric("Has aportado", eur(df["Aportado_Acumulado"].iloc[-1]), border=True,
              delta=f"{eur(df['Aportado_Real'].iloc[-1])} en euros de hoy" if hay_ipc else None,
              delta_color="off", delta_arrow="off",
              help="Suma de Ahorro_Invertido. En euros de hoy: cada aportación revalorizada con el IPC")
    if gasto_medio > 0:
        meses_colchon = liquidez / gasto_medio
        c4.metric("Colchón de emergencia", f"{meses_colchon:.1f} meses".replace(".", ","), border=True,
                  delta="Cubre 6 meses o más" if meses_colchon >= 6 else "Por debajo de 6 meses",
                  delta_color="normal" if meses_colchon >= 6 else "inverse", delta_arrow="off",
                  help=f"Efectivo acumulado estimado ({eur(liquidez)}) / gasto fijo medio ({eur(gasto_medio)})")
    else:
        c4.metric("Colchón de emergencia", "—", border=True, help="Rellena Gastos_Fijos para calcularlo")

    sobrante_medio = ultimos12["Sobrante"].mean()
    sin_asignar = (ultimos12["Sobrante"] - ultimos12["Efectivo_Mes"]).mean() if tiene_liquidez else 0
    if tiene_liquidez and abs(sin_asignar) > 20:
        st.warning(f"Tus cifras no cuadran: de media quedan **{eur(sin_asignar)}** al mes sin registrar "
                   "(ingresos − gastos − inversión − liquidez). ¿Falta algún gasto variable?")
    if sobrante_medio < -50:
        st.warning(f"De media gastas e inviertes **{eur(-sobrante_medio)}** más de lo que ingresas al mes. "
                   "Revisa si estás tirando de tus ahorros.")

    # --- Flujo mensual ---
    st.subheader("A dónde va cada euro que ingresas")
    fig = go.Figure()
    for col, nombre, color in (("Gastos_Fijos", "Gastos fijos", p["erosion"]),
                               ("Ahorro_Invertido", "Invertido", p["real"]),
                               ("Efectivo_Mes", "Liquidez apartada", p["liquidez"])):
        fig.add_bar(x=df["Fecha"], y=df[col], name=nombre, marker=dict(color=color, line=dict(color=p["fondo"], width=1)),
                    hovertemplate="%{y:,.0f} €")
    linea(fig, df["Fecha"], df["Ingresos_Netos"], "Ingresos netos", p["texto"], hovertemplate="%{y:,.0f} €")
    fig.update_layout(barmode="stack")
    mostrar(estilo_fig(fig, alto=400, titulo_y="€ al mes", fechas=True))

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Tasa de ahorro")
        fig = go.Figure()
        fig.add_bar(x=df["Fecha"], y=df["Tasa_Ahorro"], name="Cada mes", marker_color=p["nominal"],
                    opacity=0.45, hovertemplate="%{y:.1f} %")
        linea(fig, df["Fecha"], df["Tasa_Ahorro"].rolling(3, min_periods=1).mean(), "Media de 3 meses",
              p["real"], hovertemplate="%{y:.1f} %")
        fig.update_yaxes(ticksuffix=" %")
        mostrar(estilo_fig(fig, alto=340, fechas=True))

    with col_b:
        st.subheader("Lo que has aportado")
        fig = go.Figure()
        linea(fig, df["Fecha"], df["Aportado_Acumulado"], "Lo que pusiste", p["nominal"], discontinua=True,
              hovertemplate="%{y:,.0f} €")
        if hay_ipc:
            linea(fig, df["Fecha"], df["Aportado_Real"], "En euros de hoy", p["real"], hovertemplate="%{y:,.0f} €")
        fig.update_yaxes(ticksuffix=" €")
        mostrar(estilo_fig(fig, alto=340, fechas=True))
        if hay_ipc:
            st.caption("Para no perder poder adquisitivo, tu cartera debería valer al menos la línea azul.")

    # --- Inflación personal ---
    if hay_ipc and len(df) >= 13:
        st.subheader("Tus gastos frente a la inflación")
        g = df.set_index("Fecha")["Gastos_Fijos"]
        ipc_df = ipc_meses.reindex(df["Fecha"])
        anos = (df["Fecha"].iloc[-1] - df["Fecha"].iloc[0]).days / 365.25
        crec_gasto = (g.tail(3).mean() / g.head(3).mean()) ** (1 / anos) - 1 if anos > 0 and g.head(3).mean() > 0 else np.nan
        crec_ipc = (ipc_df.iloc[-1] / ipc_df.iloc[0]) ** (1 / anos) - 1 if anos > 0 else np.nan
        c1, c2 = st.columns(2)
        c1.metric("Tus gastos fijos suben", pct(crec_gasto * 100) + " al año", border=True,
                  delta=f"{eur(g.tail(3).mean())} al mes ahora", delta_color="off", delta_arrow="off",
                  help="Media de los 3 últimos meses frente a los 3 primeros, anualizada")
        c2.metric("El IPC sube", pct(crec_ipc * 100) + " al año", border=True,
                  delta=f"{(crec_gasto - crec_ipc) * 100:+.1f} puntos de inflación personal".replace(".", ","),
                  delta_color="inverse")
        fig = go.Figure()
        linea(fig, df["Fecha"], g.rolling(3, min_periods=1).mean() / g.head(3).mean() * 100,
              "Tus gastos fijos (media de 3 meses)", p["erosion"], hovertemplate="%{y:.1f}")
        linea(fig, df["Fecha"], ipc_df.to_numpy() / ipc_df.iloc[0] * 100, "IPC Eurozona", p["nominal"],
              discontinua=True, hovertemplate="%{y:.1f}")
        mostrar(estilo_fig(fig, alto=340, titulo_y="Índice (inicio = 100)", fechas=True))

    # --- Activos ---
    if "Activo_Principal" in df.columns:
        activos = df["Activo_Principal"].astype(str).str.strip()
        activos = activos[activos.ne("") & activos.ne("nan")]
        if len(activos) and pd.to_numeric(activos, errors="coerce").isna().all():
            st.subheader("Dónde inviertes")
            reparto = df.loc[activos.index].groupby(activos)["Ahorro_Invertido"].sum().sort_values()
            fig = go.Figure(go.Bar(x=reparto.values, y=reparto.index, orientation="h", marker_color=p["real"],
                                   text=[f"{eur(v)} ({pct(v / reparto.sum() * 100, 0)})" for v in reparto.values],
                                   textposition="outside", textfont=dict(color=p["texto"]),
                                   hovertemplate="%{y}: %{x:,.0f} €<extra></extra>"))
            fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, reparto.max() * 1.35])
            fig.update_yaxes(showgrid=False)
            mostrar(estilo_fig(fig, alto=80 + 44 * len(reparto), leyenda=False))

    with st.expander("Ver los datos procesados"):
        st.dataframe(df, width="stretch", hide_index=True)
