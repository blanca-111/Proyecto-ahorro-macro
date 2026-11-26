"""Motor de proyección mensual, común a todas las simulaciones.

Reglas:
- la cartera rinde en términos nominales y se aporta al inicio de cada mes;
- la aportación sube cada año con la inflación si `indexar` es True;
- los rendimientos mensuales son log-normales: con volatilidad 0 el resultado es la
  proyección determinista, y con volatilidad > 0 cada columna es un escenario Monte Carlo.
"""
import numpy as np
import streamlit as st


@st.cache_data(show_spinner=False)
def simular(cap_ini, ahorro, indexar, r_anual, vol, inflacion, anos, n_sims=1, semilla=42):
    """Devuelve (nominal, real, aportado), matrices de forma (anos+1, n_sims) a cierre de cada año."""
    rng = np.random.default_rng(semilla)
    m = anos * 12
    ret = np.expm1(rng.normal(np.log1p(r_anual) / 12, vol / np.sqrt(12), (m, n_sims)))
    aport = ahorro * (1 + inflacion) ** (np.arange(m) // 12) if indexar else np.full(m, float(ahorro))

    nominal = np.empty((m + 1, n_sims))
    nominal[0] = cap_ini
    for i in range(m):
        nominal[i + 1] = (nominal[i] + aport[i]) * (1 + ret[i])

    deflactor = (1 + inflacion) ** (np.arange(m + 1) / 12)
    aportado = np.concatenate([[cap_ini], cap_ini + np.cumsum(aport)])
    return nominal[::12], (nominal / deflactor[:, None])[::12], aportado[::12]


def primer_ano(condicion):
    """Primer índice (año) en el que se cumple la condición, o None."""
    pos = np.flatnonzero(condicion)
    return int(pos[0]) if len(pos) else None
