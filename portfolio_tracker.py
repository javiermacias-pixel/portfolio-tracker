import streamlit as st
import pandas as pd
import os
from datetime import datetime

# Nombre del fichero donde se guardan los datos
DATA_FILE = "transactions.csv"

# Configuración básica de la página
st.set_page_config(page_title="Portfolio Tracker", layout="wide")

st.title("📊 Portfolio Tracker – Demo IA & Prompt Engineering")
st.write(
    "Aplicación sencilla para seguir una cartera de inversión con distintos activos y divisas. "
    "Los datos se guardan en el fichero `transactions.csv` en la misma carpeta."
)

# --- Cargar datos ---
if os.path.exists(DATA_FILE):
    df = pd.read_csv(DATA_FILE, parse_dates=["fecha"])
else:
    df = pd.DataFrame(
        columns=[
            "fecha",
            "activo",
            "nombre_activo",
            "tipo_operacion",
            "cantidad",
            "precio",
            "divisa",
            "fx_a_eur",
            "importe_eur",
        ]
    )

# Normalizar tipos de dato
if not df.empty:
    df["fecha"] = pd.to_datetime(df["fecha"])
    num_cols = ["cantidad", "precio", "fx_a_eur", "importe_eur"]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# --- Formulario de nueva operación en la barra lateral ---
st.sidebar.header("➕ Añadir operación")

with st.sidebar.form("nuevo_movimiento"):
    fecha = st.date_input("Fecha", value=datetime.today())
    activo = st.text_input("Ticker / Activo", help="Ej: AAPL, MSFT, BTC, Fondo01")
    nombre_activo = st.text_input("Nombre del activo", help="Ej: Apple Inc.")
    tipo_operacion = st.selectbox(
        "Tipo de operación",
        ["Compra", "Venta"],
        help="Para simplificar, consideramos Compra como aportación y Venta como retirada.",
    )
    cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0)
    precio = st.number_input("Precio por unidad", min_value=0.0, step=0.01)
    divisa = st.selectbox("Divisa", ["EUR", "USD", "GBP", "Otra"])
    fx_a_eur = st.number_input(
        "Tipo de cambio a EUR",
        min_value=0.0,
        step=0.0001,
        help="Ej: si 1 USD = 0.92 EUR, introduce 0.92",
    )

    submitted = st.form_submit_button("Guardar operación")

    if submitted:
        if not activo:
            st.warning("Debes indicar al menos el ticker/activo.")
        else:
            # sign = +1 para Compra, -1 para Venta
            sign = 1 if tipo_operacion == "Compra" else -1

            # Importe en EUR con signo (Compra suma, Venta resta)
            importe_eur = sign * cantidad * precio * fx_a_eur

            new_row = {
                "fecha": fecha,
                "activo": activo,
                "nombre_activo": nombre_activo,
                "tipo_operacion": tipo_operacion,
                "cantidad": sign * cantidad,  # guardamos la cantidad ya con signo
                "precio": precio,
                "divisa": divisa,
                "fx_a_eur": fx_a_eur,
                "importe_eur": importe_eur,
            }

            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(DATA_FILE, index=False)
            st.success("✅ Operación guardada correctamente. Actualiza la página si no ves los cambios.")

# --- Registro de operaciones ---
st.subheader("📜 Registro de operaciones")

if df.empty:
    st.info("Todavía no hay operaciones. Añade la primera desde la barra lateral.")
else:
    st.dataframe(df.sort_values("fecha"), use_container_width=True)

    # --- Cálculos de cartera ---
    st.subheader("📈 Resumen de cartera")

    # Aportación neta total (en EUR)
    aportacion_neta = df["importe_eur"].sum()

    # Agrupar por activo para obtener posición y métricas
    resumen_activos = (
        df.groupby("activo")
        .agg(
            nombre_activo=("nombre_activo", "last"),
            cantidad_neta=("cantidad", "sum"),
            importe_neto_eur=("importe_eur", "sum"),
            ultima_divisa=("divisa", "last"),
            ultimo_precio=("precio", "last"),
            ultimo_fx_a_eur=("fx_a_eur", "last"),
        )
        .reset_index()
    )

    # Valor estimado actual: usamos último precio y último tipo de cambio
    resumen_activos["valor_actual_eur"] = (
        resumen_activos["cantidad_neta"]
        * resumen_activos["ultimo_precio"]
        * resumen_activos["ultimo_fx_a_eur"]
    )

    # Rentabilidad por activo
    resumen_activos["rentabilidad_eur"] = (
        resumen_activos["valor_actual_eur"] - resumen_activos["importe_neto_eur"]
    )

    resumen_activos["rentabilidad_pct"] = resumen_activos.apply(
        lambda row: (row["rentabilidad_eur"] / row["importe_neto_eur"] * 100)
        if row["importe_neto_eur"] != 0
        else 0,
        axis=1,
    )

    # Rentabilidad total de la cartera
    valor_total_actual = resumen_activos["valor_actual_eur"].sum()
    rentab_total_eur = valor_total_actual - aportacion_neta
    rentab_total_pct = (
        rentab_total_eur / aportacion_neta * 100 if aportacion_neta != 0 else 0
    )

    # Mostrar métricas principales
    col1, col2, col3 = st.columns(3)
    col1.metric("Aportación neta (EUR)", f"{aportacion_neta:,.2f}")
    col2.metric("Valor estimado actual (EUR)", f"{valor_total_actual:,.2f}")
    col3.metric("Rentabilidad total (%)", f"{rentab_total_pct:,.2f}")

    # Tabla con detalle por activo
    st.markdown("### 🧩 Detalle por activo")
    st.dataframe(
        resumen_activos[
            [
                "activo",
                "nombre_activo",
                "cantidad_neta",
                "importe_neto_eur",
                "valor_actual_eur",
                "rentabilidad_eur",
                "rentabilidad_pct",
                "ultima_divisa",
            ]
        ],
        use_container_width=True,
    )

    # --- Evolución en el tiempo ---
    st.subheader("📆 Evolución de las aportaciones en el tiempo")

    # Agrupamos por fecha la aportación neta y calculamos acumulado
    df_by_date = (
        df.sort_values("fecha")
        .groupby("fecha")["importe_eur"]
        .sum()
        .cumsum()
        .reset_index()
    )
    df_by_date.rename(columns={"importe_eur": "aportacion_acumulada_eur"}, inplace=True)

    st.line_chart(
        df_by_date.set_index("fecha")["aportacion_acumulada_eur"],
        y_label="Aportaciones acumuladas (EUR)",
    )
