# Guion de presentación (2-3 minutos)

Guion para presentar el proyecto en una entrevista, un vídeo de portfolio o una demo. Adapta las frases a tu manera de hablar y a tu experiencia real con la app.

---

## 1. Gancho (15 s)

> "Si hoy te digo que en 20 años tendrás 400.000 €, suena genial. Pero con la inflación, esos euros
> pueden valer un tercio menos. Quería saber cuánto poder adquisitivo **real** iba a tener yo, con
> **mis** datos, no con supuestos genéricos. Así que construí esta app."

## 2. Qué es (20 s)

> "Es una aplicación web en Python y Streamlit que une tres fuentes de datos en vivo:
> mi Google Sheets, donde registro cada mes ingresos, gastos e inversión; Yahoo Finance, para la
> rentabilidad y volatilidad reales de mi ETF; y FRED, para la inflación oficial de la Eurozona.
> Con eso proyecta mi patrimonio en euros de hoy."

## 3. Demo (60-90 s)

*(Ir pasando por las pestañas mientras se habla.)*

1. **Login**: "Como muestra datos personales, está protegida con contraseña. Las credenciales
   nunca están en el código, sino en los Secrets de Streamlit."
2. **Mis Finanzas**: "Aquí veo mi tasa de ahorro, cuánto he aportado en euros nominales y en euros
   de hoy, y cuántos meses de colchón tengo. Este gráfico compara cuánto suben mis gastos
   con el IPC: mi inflación personal."
3. **Barra lateral**: "Los valores por defecto salen de los datos reales: mi ahorro medio, la
   rentabilidad histórica del ETF y la inflación actual. Puedo moverlos para probar escenarios."
4. **Monte Carlo**: "En lugar de una única cifra, simulo 500 escenarios de mercado con la
   volatilidad real. Veo el caso mediano y la banda entre el escenario pesimista y el optimista."
5. **Independencia Financiera**: "Con la regla del 4 %, la app calcula cuánto necesito para vivir de
   mis inversiones y la probabilidad de conseguirlo cada año. Y esta tabla me dice cuántos
   años antes llegaría si ahorro 100, 250 o 500 € más al mes."

## 4. Lo técnico (30-40 s)

> "Por dentro hay varias decisiones que me parecen interesantes:
> - Las simulaciones determinista y Monte Carlo usan **el mismo motor mensual**, con rendimientos
>   nominales que luego se deflactan. Así sus resultados son coherentes entre sí.
> - El Monte Carlo usa **rendimientos log-normales vectorizados con NumPy** y caché, para que
>   responda al instante al mover un parámetro.
> - El CAGR se calcula con los **años reales** de histórico, porque algunos ETFs tienen menos de 10.
> - Los datos introducidos a mano son imperfectos, así que hay una capa de **limpieza y validación**
>   que entiende formatos de números y fechas españoles y avisa de meses que faltan o no cuadran.
> - Si una fuente externa falla, la app **lo dice** en vez de mostrar cifras inventadas sin avisar.
> - Lo probé con el framework de testing de Streamlit, simulando las APIs externas."

## 5. Cierre (15 s)

> "Me ha servido para tomar decisiones reales, como cuánto aumentar mi aportación mensual, y
> para practicar integración de APIs, análisis de datos con pandas, simulación estadística y
> despliegue de una app en producción. Lo siguiente que quiero añadir es la rentabilidad real de mi
> cartera y una comparación entre lo planificado y lo real."

---

## Frases cortas para el CV / LinkedIn

**Una línea:**
> Dashboard financiero en Python/Streamlit que integra Google Sheets, Yahoo Finance y FRED para proyectar el poder adquisitivo real con simulación Monte Carlo.

**Versión con viñetas:**
- Desarrollé y desplegué una app web (Python, Streamlit, Plotly) que integra en tiempo real Google Sheets API, Yahoo Finance y FRED.
- Implementé un motor de proyección mensual ajustado por inflación y una simulación Monte Carlo de 500 escenarios con rendimientos log-normales vectorizados con NumPy.
- Calculé la probabilidad de alcanzar la independencia financiera (regla del 4 %) y el impacto de aumentar el ahorro mensual.
- Diseñé una capa de validación de datos (formatos de número y fecha, meses que faltan o se repiten) y degradación controlada ante fallos de APIs externas.
- Protegí el acceso con contraseña y gestión de secretos; añadí pruebas automatizadas con `streamlit.testing` y mocks.

## Preguntas que te pueden hacer (y respuesta corta)

- **¿Por qué log-normal y no normal?** Los precios no pueden ser negativos, y con rendimientos log-normales la mediana crece exactamente a la rentabilidad elegida, lo que hace coherentes las dos simulaciones.
- **¿Por qué la regla del 4 %?** Es la referencia clásica del estudio Trinity: retirar un 4 % el primer año y ajustarlo por inflación ha aguantado históricamente 30 años en la mayoría de escenarios. En la app la tasa se puede ajustar, por ejemplo a un 3,5 % para ser más prudente.
- **¿Limitaciones?** No tiene en cuenta impuestos ni comisiones, asume rentabilidad y volatilidad constantes, y la inflación futura es un supuesto.
- **¿Por qué Streamlit?** Permite construir y desplegar un dashboard interactivo solo con Python, sin frontend aparte; ideal para un proyecto de análisis de datos.
