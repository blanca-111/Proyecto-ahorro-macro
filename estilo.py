"""Identidad visual: paleta del billete, formato de cifras y estilo común de los gráficos.

Paleta categórica (azul, ocre, turquesa) validada para daltonismo y contraste en
modo claro y oscuro. El gris se usa solo para cifras nominales / de referencia.
"""
import plotly.graph_objects as go
import streamlit as st

PALETAS = {
    "light": {
        "fondo": "#F2F3EE", "texto": "#17233A", "texto_2": "#5A6475", "rejilla": "#DADDD4",
        "real": "#2B55A6", "erosion": "#B07514", "liquidez": "#00937A", "nominal": "#8C94A0",
    },
    "dark": {
        "fondo": "#152033", "texto": "#E4E8EF", "texto_2": "#9AA4B5", "rejilla": "#26344B",
        "real": "#6E97E6", "erosion": "#D08E2E", "liquidez": "#2DB496", "nominal": "#7D8798",
    },
}
FUENTE = "Public Sans, sans-serif"


def paleta():
    """Colores del tema activo (claro u oscuro) según la configuración del visitante."""
    try:
        modo = st.context.theme.type or "light"
    except Exception:
        modo = "light"
    return PALETAS.get(modo, PALETAS["light"])


def eur(x):
    """441076.3 -> '441.076 €' (formato español)."""
    return f"{x:,.0f} €".replace(",", ".")


def pct(x, decimales=1):
    return f"{x:.{decimales}f} %".replace(".", ",")


def estilo_fig(fig, alto=380, titulo_y=None, titulo_x=None, leyenda=True, formato_y=",.0f", fechas=False):
    """Estilo común de Plotly: fondo transparente, rejilla discreta, leyenda arriba.

    fechas=True formatea el eje X como mes/año (Plotly no traduce los nombres de los meses).
    """
    p = paleta()
    fig.update_layout(
        template="none", height=alto, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FUENTE, color=p["texto"], size=13),
        margin=dict(l=8, r=8, t=40 if leyenda else 12, b=8),
        hovermode="x unified", showlegend=leyenda,
        legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom", font=dict(color=p["texto_2"])),
        hoverlabel=dict(bgcolor=p["fondo"], bordercolor=p["rejilla"], font=dict(family=FUENTE, color=p["texto"])),
        bargap=0.25,
    )
    ejes = dict(automargin=True, gridcolor=p["rejilla"], zeroline=False, linecolor=p["rejilla"], tickcolor=p["rejilla"],
                tickfont=dict(color=p["texto_2"]), title_font=dict(color=p["texto_2"], size=12))
    fig.update_xaxes(showgrid=False, title_text=titulo_x, tickformat="%m/%Y" if fechas else None, **ejes)
    fig.update_yaxes(showgrid=True, title_text=titulo_y, tickformat=formato_y, separatethousands=True, **ejes)
    fig.update_layout(separators=",.")
    return fig


def mostrar(fig):
    st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False})


def linea(fig, x, y, nombre, color, discontinua=False, ancho=2, **kw):
    fig.add_trace(go.Scatter(x=x, y=y, name=nombre, mode="lines",
                             line=dict(color=color, width=ancho, dash="dash" if discontinua else None), **kw))


CSS = """
<style>
.hero { margin: 0.25rem 0 1.5rem; }
.hero p { margin: 0; line-height: 1.25; }
.hero .frase { font-size: 1.05rem; color: var(--texto-2); }
.hero .cifra { font-family: 'Bricolage Grotesque', sans-serif; font-weight: 700;
               font-size: clamp(2.2rem, 5.5vw, 3.6rem); letter-spacing: -0.02em;
               font-variant-numeric: tabular-nums; display: block; margin: 0.1rem 0 0.9rem; }
.hero .cifra.nominal { color: var(--nominal); }
.hero .cifra.real { color: var(--real); }
.erosion { display: flex; height: 22px; border-radius: 4px; overflow: hidden; gap: 2px; margin-top: 0.4rem; }
.erosion .conservas { background: var(--real); }
.erosion .pierdes { background: repeating-linear-gradient(135deg, var(--erosion) 0 3px, transparent 3px 7px);
                    box-shadow: inset 0 0 0 1.5px var(--erosion); border-radius: 0 4px 4px 0; }
.erosion-leyenda { display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
                   margin-top: 0.5rem; font-size: 0.9rem; color: var(--texto-2); }
.erosion-leyenda b { color: var(--texto); font-weight: 600; font-variant-numeric: tabular-nums; }
.erosion-leyenda .marca { display: inline-block; width: 10px; height: 10px; border-radius: 2px;
                          margin-right: 0.4rem; vertical-align: baseline; }
@media (prefers-reduced-motion: no-preference) {
  .erosion .pierdes { animation: entra 900ms ease-out 200ms both; transform-origin: left; }
  @keyframes entra { from { transform: scaleX(0); } to { transform: scaleX(1); } }
}
</style>
"""


def hero(anos, nominal, real):
    """Bloque principal: cifra nominal frente a poder adquisitivo real, con la barra de erosión."""
    p = paleta()
    perdida = max(nominal - real, 0)
    frac_real = real / nominal * 100 if nominal > 0 else 100
    variables = ";".join(f"--{k.replace('_', '-')}:{v}" for k, v in p.items())
    st.html(f"""{CSS}
<section class="hero" style="{variables}" aria-label="Resumen de la proyección">
  <p class="frase">Dentro de {anos} años tendrás sobre el papel</p>
  <span class="cifra nominal">{eur(nominal)}</span>
  <p class="frase">Con la inflación, eso valdrá en euros de hoy</p>
  <span class="cifra real">{eur(real)}</span>
  <div class="erosion" role="img"
       aria-label="Conservas el {frac_real:.0f} % del valor; la inflación se lleva {eur(perdida)}">
    <div class="conservas" style="width:{frac_real:.2f}%"></div>
    <div class="pierdes" style="flex:1"></div>
  </div>
  <div class="erosion-leyenda">
    <span><span class="marca" style="background:var(--real)"></span>Poder adquisitivo que conservas <b>{pct(frac_real, 0)}</b></span>
    <span><span class="marca" style="background:var(--erosion)"></span>Se lo lleva la inflación <b>{eur(perdida)}</b></span>
  </div>
</section>""")
