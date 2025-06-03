#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sqlalchemy import create_engine, URL

# === CONEXIÓN A BASE DE DATOS ===
server = st.secrets["server"]
database = st.secrets["database"]
username = st.secrets["username"]
password = st.secrets["password"]

connection_url = URL.create(
    "mssql+pyodbc",
    username=username,
    password=password,
    host=server,
    database=database,
    query={"driver": "ODBC Driver 17 for SQL Server"}
)
engine = create_engine(connection_url)

# === CARGA DE DATOS ===
@st.cache_data
def cargar_datos():
    query = """SELECT * FROM GESTIONES_APVAP
               WHERE CONVERT(date, FECHAVISITA) = DATEADD(day, -14, CONVERT(date, GETDATE()))"""
    df = pd.read_sql(query, engine)
    df.columns = df.columns.str.strip().str.upper()
    df = df.rename(columns={
        'NOMBREVENDEDOR': 'GESTOR',
        'FECHAVISITA': 'FECHA_GESTION',
        'HORADEGESTION': 'HORA_GESTION',
        'IDCLIENTE': 'ID_CLIENTE',
        'NOMBREDECLIENTE': 'CLIENTE',
        'POSTURA': 'RESULTADO'
    })
    df = df.dropna(subset=["LATITUD", "LONGITUD", "GESTOR", "HORA_GESTION", "FECHA_GESTION"])
    df = df[(df["LATITUD"] != 0) & (df["LONGITUD"] != 0)]
    df["LATITUD"] = pd.to_numeric(df["LATITUD"], errors='coerce')
    df["LONGITUD"] = pd.to_numeric(df["LONGITUD"], errors='coerce')
    df = df.dropna(subset=["LATITUD", "LONGITUD"])
    df["FECHA_GESTION"] = pd.to_datetime(df["FECHA_GESTION"])
    df["HORA_ORDEN"] = pd.to_datetime(df["HORA_GESTION"], format="%I:%M%p", errors='coerce').dt.time
    df["EFECTIVA"] = np.where(df["RESULTADO"].isin(["PP", "DP"]), "Efectiva", "No Efectiva")
    df["COLOR"] = np.where(df["EFECTIVA"] == "Efectiva", "green", "red")
    df = df.sort_values(by=["GESTOR", "FECHA_GESTION", "HORA_ORDEN"])
    return df

df = cargar_datos()

# === INTERFAZ ===
st.title("Seguimiento de Gestiones de Cobranza")

gestor = st.selectbox("Seleccione un gestor", sorted(df["GESTOR"].unique()))
filtro = df[df["GESTOR"] == gestor]
fechas = filtro["FECHA_GESTION"].dt.strftime("%Y-%m-%d").unique()
fecha = st.selectbox("Seleccione una fecha", fechas)

datos_filtrados = df[(df["GESTOR"] == gestor) & (df["FECHA_GESTION"].dt.strftime("%Y-%m-%d") == fecha)]
datos_filtrados = datos_filtrados.sort_values("HORA_ORDEN").reset_index(drop=True)

if len(datos_filtrados) == 0:
    st.warning("No hay datos para mostrar.")
else:
    if "indice" not in st.session_state:
        st.session_state.indice = 0

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("Anterior") and st.session_state.indice > 0:
            st.session_state.indice -= 1
    with col2:
        if st.button("Siguiente") and st.session_state.indice < len(datos_filtrados) - 1:
            st.session_state.indice += 1
    with col3:
        st.markdown(f"**Punto {st.session_state.indice + 1} de {len(datos_filtrados)}**")

    datos_filtrados["HOVER_TEXT"] = datos_filtrados.apply(lambda row: (
        f"<b>Gestión #{row.name + 1}</b><br>"
        f"<b>Gestor:</b> {row['GESTOR']}<br>"
        f"<b>ID:</b> {row['ID_CLIENTE']}<br>"
        f"<b>Hora:</b> {row['HORA_GESTION']}<br>"
        f"<b>Tipo:</b> {'Presencial' if str(row.get('ACCION', '')).strip().upper() in ['VISITA A CASA', 'VISITA REFERENCIA'] else 'Virtual'}<br>"
        f"<b>Resultado:</b> {row['RESULTADO']}<br>"
        f"<b>Efectiva:</b> {row['EFECTIVA']}"
    ), axis=1)

    fig = go.Figure()

    fig.add_trace(go.Scattermapbox(
        lat=datos_filtrados["LATITUD"],
        lon=datos_filtrados["LONGITUD"],
        mode='markers',
        marker=dict(size=10, color='lightgray', opacity=0.4),
        hoverinfo='skip'
    ))

    fig.add_trace(go.Scattermapbox(
        lat=datos_filtrados["LATITUD"],
        lon=datos_filtrados["LONGITUD"],
        mode='lines',
        line=dict(width=1, color='gray'),
        hoverinfo='skip'
    ))

    idx = st.session_state.indice
    if idx > 0:
        prev = datos_filtrados.iloc[:idx]
        fig.add_trace(go.Scattermapbox(
            lat=prev["LATITUD"],
            lon=prev["LONGITUD"],
            mode='markers',
            marker=dict(size=12, color='blue'),
            hovertext=prev["HOVER_TEXT"],
            hoverinfo='text'
        ))

        fig.add_trace(go.Scattermapbox(
            lat=datos_filtrados["LATITUD"].iloc[:idx+1],
            lon=datos_filtrados["LONGITUD"].iloc[:idx+1],
            mode='lines',
            line=dict(width=2, color='blue'),
            hoverinfo='skip'
        ))

    actual = datos_filtrados.iloc[idx]
    fig.add_trace(go.Scattermapbox(
        lat=[actual["LATITUD"]],
        lon=[actual["LONGITUD"]],
        mode='markers+text',
        marker=dict(size=14, color='purple'),
        text=[str(idx+1)],
        textposition="top center",
        textfont=dict(color='black', size=14),
        hovertext=[actual["HOVER_TEXT"]],
        hoverinfo='text'
    ))

    if "view_config" not in st.session_state:
        st.session_state.view_config = {
            "lat": datos_filtrados["LATITUD"].mean(),
            "lon": datos_filtrados["LONGITUD"].mean(),
            "zoom": 12
        }

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(
                lat=st.session_state.view_config["lat"],
                lon=st.session_state.view_config["lon"]
            ),
            zoom=st.session_state.view_config["zoom"]
        ),
        margin=dict(r=0, t=0, l=0, b=0),
        uirevision="keep"
    )

    st.plotly_chart(fig, use_container_width=True)
