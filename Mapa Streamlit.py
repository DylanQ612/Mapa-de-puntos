# ... (todo el código anterior de conexión y carga de datos permanece igual)

# === INTERFAZ MODIFICADA PARA STREAMLIT ===
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
        # Almacenamos el estado del mapa al inicio
        st.session_state.map_state = {
            "center": {
                "lat": datos_filtrados["LATITUD"].mean(),
                "lon": datos_filtrados["LONGITUD"].mean()
            },
            "zoom": 12
        }

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("Anterior") and st.session_state.indice > 0:
            st.session_state.indice -= 1
    with col2:
        if st.button("Siguiente") and st.session_state.indice < len(datos_filtrados) - 1:
            st.session_state.indice += 1
    with col3:
        st.markdown(f"**Punto {st.session_state.indice + 1} de {len(datos_filtrados)}**")

    # Generación del hover text (igual que antes)
    datos_filtrados["HOVER_TEXT"] = datos_filtrados.apply(lambda row: (
        f"<b>Gestión #{row.name + 1}</b><br>"
        f"<b>Gestor:</b> {row['GESTOR']}<br>"
        f"<b>ID:</b> {row['ID_CLIENTE']}<br>"
        f"<b>Hora:</b> {row['HORA_GESTION']}<br>"
        f"<b>Tipo:</b> {'Presencial' if str(row.get('ACCION', '')).strip().upper() in ['VISITA A CASA', 'VISITA REFERENCIA'] else 'Virtual'}<br>"
        f"<b>Resultado:</b> {row['RESULTADO']}<br>"
        f"<b>Efectiva:</b> {row['EFECTIVA']}"
    ), axis=1)

    # Crear figura
    fig = go.Figure()

    # 1. Todos los puntos (base)
    fig.add_trace(go.Scattermapbox(
        lat=datos_filtrados["LATITUD"],
        lon=datos_filtrados["LONGITUD"],
        mode='markers',
        marker=dict(size=10, color='lightgray', opacity=0.4),
        hoverinfo='skip'
    ))

    # 2. Línea de ruta completa (base)
    fig.add_trace(go.Scattermapbox(
        lat=datos_filtrados["LATITUD"],
        lon=datos_filtrados["LONGITUD"],
        mode='lines',
        line=dict(width=1, color='gray'),
        hoverinfo='skip'
    ))

    idx = st.session_state.indice
    
    # 3. Puntos visitados (si hay)
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

        # 4. Línea de ruta recorrida
        fig.add_trace(go.Scattermapbox(
            lat=datos_filtrados["LATITUD"].iloc[:idx+1],
            lon=datos_filtrados["LONGITUD"].iloc[:idx+1],
            mode='lines',
            line=dict(width=2, color='blue'),
            hoverinfo='skip'
        ))

    # 5. Punto actual
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

    # Configuración DEL MAPA CON ESTADO PERSISTENTE
    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=st.session_state.map_state["center"],
            zoom=st.session_state.map_state["zoom"]
        ),
        margin=dict(r=0, t=0, l=0, b=0),
        uirevision="fixed_key"  # Clave fija para mantener el estado
    )

    # Usamos un contenedor especial para el mapa
    map_container = st.empty()
    
    # Solo actualizamos el mapa si cambia el índice
    if "prev_index" not in st.session_state or st.session_state.prev_index != idx:
        with map_container:
            st.plotly_chart(
                fig, 
                use_container_width=True, 
                config={'staticPlot': False}
            )
        st.session_state.prev_index = idx
    
    # Actualizamos el estado del mapa si el usuario interactúa con él
    if st.session_state.get("map_interaction"):
        st.session_state.map_state = {
            "center": st.session_state.map_interaction["center"],
            "zoom": st.session_state.map_interaction["zoom"]
        }

# JavaScript para capturar interacciones con el mapa
st.components.v1.html("""
<script>
document.addEventListener('DOMContentLoaded', function() {
    const observer = new MutationObserver(function(mutations) {
        const plotlyDivs = document.querySelectorAll('.plotly-graph-div');
        plotlyDivs.forEach(div => {
            div.on('plotly_relayout', function(eventdata) {
                const center = eventdata['mapbox.center'] || {};
                const zoom = eventdata['mapbox.zoom'];
                
                if (center && zoom) {
                    window.parent.postMessage({
                        type: 'plotly_interaction',
                        center: center,
                        zoom: zoom
                    }, '*');
                }
            });
        });
    });
    observer.observe(document.body, {childList: true, subtree: true});
});
</script>
""")

# Capturamos interacciones del usuario con el mapa
if st.session_state.get("map_interaction"):
    st.session_state.map_state = {
        "center": st.session_state.map_interaction["center"],
        "zoom": st.session_state.map_interaction["zoom"]
    }