from flask import Flask, render_template, request, redirect, url_for, flash
from db import get_connection
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import os
from werkzeug.utils import secure_filename
from io import BytesIO
import base64
import pandas as pd

app = Flask(__name__)
app.secret_key = 'clave_super_secreta'

# Carpeta para subir documentos
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# -----------------------
# Página de Inicio
# -----------------------
@app.route('/')
def index():
    query = """
        SELECT p.id, p.nombres, p.apellidop, p.apellidom, p.correo, p.numero_empleado,
               p.estatus, p.telefono_uno, p.telefono_dos,
               b.motivo AS motivo_baja,
               pu.nombre AS puesto
        FROM persona p
        LEFT JOIN baja_persona b ON p.id = b.id_persona
        LEFT JOIN asigna_puesto ap ON p.id = ap.id_persona
        LEFT JOIN puesto pu ON ap.id_puesto = pu.id
        ORDER BY p.apellidop, p.apellidom, p.nombres
    """
    data = []
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        for row in rows:
            data.append({
                'id': row['id'],
                'nombres': row['nombres'],
                'apellidop': row['apellidop'],
                'apellidom': row['apellidom'],
                'nombre_completo': f"{row['apellidop']} {row['apellidom']} {row['nombres']}",
                'correo': row['correo'],
                'numero_empleado': row['numero_empleado'],
                'estatus': row['estatus'],
                'telefono_uno': row['telefono_uno'],
                'telefono_dos': row['telefono_dos'],
                'motivo_baja': row['motivo_baja'],
                'puesto': row['puesto'] or ''
            })
    return render_template('index.html', data=data)


# ----------------------- #
# Registrar Persona
# ----------------------- #
@app.route('/registrar_persona', methods=['GET', 'POST'])
def registrar_persona():
    with get_connection() as conn:
        cursor = conn.cursor()

        # Traer departamentos activos
        cursor.execute(
            "SELECT id, nombre FROM departamento WHERE activo=1 ORDER BY nombre"
        )
        departamentos = cursor.fetchall()  # lista de tuplas (id, nombre)

        # Traer todos los puestos activos con depto y nivel
        cursor.execute(
            "SELECT id, nombre, departamento_id, nivel FROM puesto WHERE activo=1 ORDER BY nivel"
        )
        puestos = cursor.fetchall()  # (id, nombre, departamento_id, nivel)

        # Traer todos los jefes posibles con depto y nivel
        cursor.execute("""
            SELECT p.id, p.nombres, p.apellidop, p.apellidom, pu.departamento_id, pu.nivel
            FROM persona p
            INNER JOIN asigna_puesto ap ON ap.id_persona = p.id AND ap.activo=1
            INNER JOIN puesto pu ON pu.id = ap.id_puesto
            ORDER BY pu.nivel ASC, p.apellidop, p.apellidom
        """)
        jefes = cursor.fetchall()  # (id, nombres, apellidop, apellidom, departamento_id, nivel)

    if request.method == 'POST':
        nombres = request.form['nombres']
        apellidop = request.form['apellidop']
        apellidom = request.form.get('apellidom')
        telefono_uno = request.form.get('telefono_uno')
        telefono_dos = request.form.get('telefono_dos')
        numero_empleado = request.form.get('numero_empleado')
        correo = request.form.get('correo')
        puesto_id = request.form.get('puesto_id')
        jefe_id = request.form.get('jefe_id')
        username = request.form.get('username')
        password = request.form.get('password')

        with get_connection() as conn:
            cursor = conn.cursor()

            # Insertar persona
            cursor.execute("""
                INSERT INTO persona (nombres, apellidop, apellidom, telefono_uno, telefono_dos, numero_empleado, correo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (nombres, apellidop, apellidom, telefono_uno, telefono_dos, numero_empleado, correo))
            conn.commit()
            persona_id = cursor.lastrowid

            # Asignar puesto
            if puesto_id:
                cursor.execute(
                    "INSERT INTO asigna_puesto (id_persona, id_puesto) VALUES (%s, %s)",
                    (persona_id, puesto_id)
                )
                conn.commit()

            # Asignar jefe
            if jefe_id:
                cursor.execute(
                    "INSERT INTO asigna_jefe (id_persona, id_jefe, fecha_inicio) VALUES (%s, %s, CURDATE())",
                    (persona_id, jefe_id)
                )
                conn.commit()

        flash("Persona registrada correctamente.", "success")
        return redirect('/registrar_persona')

    return render_template(
        'registrar_persona.html',
        departamentos=departamentos,
        puestos=puestos,
        jefes=jefes
    )


# -----------------------
# Editar Persona
# -----------------------
@app.route('/editar_persona/<int:persona_id>', methods=['GET','POST'])
def editar_persona(persona_id):
    with get_connection() as conn:
        cursor = conn.cursor()

        # Traer departamentos activos
        cursor.execute("SELECT id, nombre FROM departamento WHERE activo=1 ORDER BY nombre")
        departamentos = cursor.fetchall()

        # Traer todos los puestos activos con depto y nivel
        cursor.execute("SELECT id, nombre, departamento_id, nivel FROM puesto WHERE activo=1 ORDER BY nivel")
        puestos = cursor.fetchall()

        # Traer todos los jefes posibles con depto y nivel, excluyendo la persona actual
        cursor.execute("""
            SELECT p.id, p.nombres, p.apellidop, p.apellidom, pu.departamento_id, pu.nivel
            FROM persona p
            INNER JOIN asigna_puesto ap ON ap.id_persona = p.id AND ap.activo=1
            INNER JOIN puesto pu ON pu.id = ap.id_puesto
            WHERE p.id != %s
            ORDER BY pu.nivel ASC, p.apellidop, p.apellidom
        """, (persona_id,))
        jefes = cursor.fetchall()

        # Traer datos de la persona
        cursor.execute("SELECT * FROM persona WHERE id=%s", (persona_id,))
        persona = cursor.fetchone()

        # Traer puesto actual
        cursor.execute("SELECT id_puesto FROM asigna_puesto WHERE id_persona=%s", (persona_id,))
        current_puesto = cursor.fetchone()
        current_puesto_id = current_puesto['id_puesto'] if current_puesto else None

        # Traer jefe actual
        cursor.execute("SELECT id_jefe FROM asigna_jefe WHERE id_persona=%s AND fecha_fin IS NULL", (persona_id,))
        current_jefe = cursor.fetchone()
        current_jefe_id = current_jefe['id_jefe'] if current_jefe else None

        if request.method == 'POST':
            nombres = request.form['nombres']
            apellidop = request.form['apellidop']
            apellidom = request.form.get('apellidom')
            telefono_uno = request.form.get('telefono_uno')
            telefono_dos = request.form.get('telefono_dos')
            numero_empleado = request.form.get('numero_empleado')
            correo = request.form.get('correo')
            puesto_id = request.form.get('puesto_id')
            jefe_id = request.form.get('jefe_id')

            # Actualizar datos de persona
            cursor.execute("""
                UPDATE persona
                SET nombres=%s, apellidop=%s, apellidom=%s, telefono_uno=%s, telefono_dos=%s,
                    numero_empleado=%s, correo=%s
                WHERE id=%s
            """, (nombres, apellidop, apellidom, telefono_uno, telefono_dos, numero_empleado, correo, persona_id))
            conn.commit()

            # Actualizar puesto
            cursor.execute("DELETE FROM asigna_puesto WHERE id_persona=%s", (persona_id,))
            if puesto_id:
                cursor.execute("INSERT INTO asigna_puesto (id_persona, id_puesto) VALUES (%s, %s)",
                               (persona_id, puesto_id))
                conn.commit()

            # Actualizar jefe
            cursor.execute("UPDATE asigna_jefe SET fecha_fin=CURDATE() WHERE id_persona=%s AND fecha_fin IS NULL",
                           (persona_id,))
            if jefe_id:
                cursor.execute("INSERT INTO asigna_jefe (id_persona, id_jefe, fecha_inicio) VALUES (%s, %s, CURDATE())",
                               (persona_id, jefe_id))
                conn.commit()

            flash("Persona actualizada correctamente.", "success")
            return redirect(url_for('index'))

    return render_template(
        'editar_persona.html',
        persona=persona,
        departamentos=departamentos,
        puestos=puestos,
        jefes=jefes,
        current_puesto_id=current_puesto_id,
        current_jefe_id=current_jefe_id
    )


# -----------------------
# Documentación Persona
# -----------------------
@app.route('/documentacion_persona/<int:persona_id>', methods=['GET','POST'])
def documentacion_persona(persona_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documento WHERE activo=1 ORDER BY nombre")
        documentos = cursor.fetchall()

        if request.method == 'POST':
            documento_id = request.form['documento_id']
            file = request.files.get('archivo')
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{persona_id}_{int(datetime.now().timestamp())}.{ext}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)
                cursor.execute(
                    "INSERT INTO carga_documento_persona (id_persona, id_documento, archivo) VALUES (%s,%s,%s)",
                    (persona_id, documento_id, filename)
                )
                conn.commit()
                flash("Documento cargado correctamente.", "success")
            else:
                flash("Archivo inválido o no seleccionado.", "danger")
            return redirect(url_for('documentacion_persona', persona_id=persona_id))

        cursor.execute(""" 
            SELECT cd.id, d.nombre AS documento, cd.archivo, cd.fecha_carga, cd.valido 
            FROM carga_documento_persona cd 
            JOIN documento d ON cd.id_documento = d.id 
            WHERE cd.id_persona=%s 
            ORDER BY cd.fecha_carga DESC
        """, (persona_id,))
        cargados = cursor.fetchall()

    return render_template('documentacion_persona.html', persona_id=persona_id, documentos=documentos, cargados=cargados)

# -----------------------
# Borrar Documento
# -----------------------
@app.route('/borrar_documento/<int:doc_id>/<int:persona_id>', methods=['POST'])
def borrar_documento(doc_id, persona_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT archivo FROM carga_documento_persona WHERE id=%s", (doc_id,))
        row = cursor.fetchone()
        if row:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], row['archivo'])
            if os.path.exists(file_path):
                os.remove(file_path)
            cursor.execute("DELETE FROM carga_documento_persona WHERE id=%s", (doc_id,))
            conn.commit()
            flash("Documento eliminado correctamente.", "success")
        else:
            flash("Documento no encontrado.", "danger")
    return redirect(url_for('documentacion_persona', persona_id=persona_id))

# -----------------------
# Baja Persona
# -----------------------
@app.route('/baja_persona/<int:persona_id>', methods=['GET','POST'])
def baja_persona(persona_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM persona WHERE id=%s", (persona_id,))
        p = cursor.fetchone()
        nombre_completo = f"{p['apellidop']} {p['apellidom']} {p['nombres']}"
        persona = {'nombre': nombre_completo}

        if request.method == 'POST':
            motivo = request.form['motivo']
            cursor.execute("INSERT INTO baja_persona (id_persona, motivo) VALUES (%s,%s)",
                           (persona_id, motivo))
            cursor.execute("UPDATE persona SET estatus='Baja' WHERE id=%s", (persona_id,))
            conn.commit()
            flash(f"Persona {nombre_completo} dada de baja correctamente.", "success")
            return redirect(url_for('index'))

    return render_template('baja_persona.html', persona=persona)

# ----------------------------
# Vista Organigrama Mejorado
# ----------------------------
# ===============================================
#   RUTA PRINCIPAL – MUESTRA EL SELECTOR
# ===============================================
@app.route('/nivel_jerarquico')
def nivel_jerarquico():
    departamentos = {
        1: "Auditoría",
        2: "Call Center",
        3: "Campo 1-7",
        4: "Campo 8-21",
        5: "Campo 22+",
        6: "Sabuesos",
        7: "Cobranza"
    }
    return render_template('nivel_jerarquico.html', departamentos=departamentos)


# ===============================================
#   RUTA – GENERA ORGANIGRAMA INTERACTIVO
# ===============================================
@app.route('/nivel_jerarquico/<int:dep_id>')
def nivel_jerarquico_dep(dep_id):
    import matplotlib.pyplot as plt
    import networkx as nx
    from networkx.drawing.nx_pydot import graphviz_layout
    import colorsys
    import mpld3
    from mpld3 import plugins

    # ---------------------------
    # Obtener datos
    # ---------------------------
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, nivel, departamento_id 
            FROM puesto 
            WHERE activo = 1
        """)
        puestos = cursor.fetchall()
        puesto_map = {p['id']: p for p in puestos}

        cursor.execute("""
            SELECT p.id, 
                   CONCAT(p.apellidop,' ',p.apellidom,' ',p.nombres) AS nombre_completo,
                   ap.id_puesto, 
                   aj.id_jefe
            FROM persona p
            JOIN asigna_puesto ap ON p.id = ap.id_persona
            LEFT JOIN asigna_jefe aj 
                  ON p.id = aj.id_persona 
                 AND (aj.fecha_fin IS NULL OR aj.fecha_fin >= CURDATE())
            WHERE p.estatus != 'Baja'
        """)
        personas = cursor.fetchall() or []

    # ---------------------------
    # Filtrar por departamento
    # ---------------------------
    personas_dep = [
        p for p in personas
        if puesto_map[p['id_puesto']]['departamento_id'] == dep_id
    ]
    if not personas_dep:
        return "<p class='text-center'>No hay datos para este departamento.</p>"

    # ---------------------------
    # FUNCION PARA GENERAR GRAFICA INTERACTIVA
    # ---------------------------
    def generar_grafica_interactiva(personas_dep):
    import matplotlib.pyplot as plt
    import networkx as nx
    from networkx.drawing.nx_pydot import graphviz_layout
    import colorsys
    import mpld3
    from mpld3 import plugins

    G = nx.DiGraph()
    nodos_map = {}
    niveles_map = {}

    # Crear nodos
    for persona in personas_dep:
        puesto = puesto_map[persona['id_puesto']]
        nodo = f"{persona['nombre_completo']}\n({puesto['nombre']})"

        info_html = (
            f"<b>{persona['nombre_completo']}</b><br>"
            f"Puesto: {puesto['nombre']}<br>"
            f"Nivel: {puesto['nivel']}"
        )

        G.add_node(nodo, tooltip=info_html)
        nodos_map[persona['id']] = nodo
        niveles_map[nodo] = puesto['nivel']

    # Crear relaciones jefe → subordinado
    for persona in personas_dep:
        if persona.get('id_jefe'):
            jefe_nodo = nodos_map.get(persona['id_jefe'])
            if jefe_nodo:
                G.add_edge(jefe_nodo, nodos_map[persona['id']])

    # Layout vertical jerárquico
    try:
        pos = graphviz_layout(G, prog='dot')  # Top→Down
    except:
        pos = nx.spring_layout(G)

    # Colores pastel por niveles
    niveles_unicos = sorted(set(niveles_map.values()))
    def pastel(h):
        r, g, b = colorsys.hls_to_rgb(h, 0.8, 0.6)
        return (r, g, b)
    color_map = {nivel: pastel(i / len(niveles_unicos)) for i, nivel in enumerate(niveles_unicos)}
    node_colors = [color_map[niveles_map[n]] for n in G.nodes()]

    # Tamaños proporcionales
    max_size = 3000
    min_size = 1500
    nivel_max = max(niveles_unicos)
    nivel_min = min(niveles_unicos)
    node_sizes = [
        min_size + (niveles_map[n] - nivel_min) / (nivel_max - nivel_min) * (max_size - min_size)
        if nivel_max != nivel_min else max_size
        for n in G.nodes()
    ]

    # Dibujar
    fig, ax = plt.subplots(figsize=(12, 8))
    scatter = nx.draw_networkx_nodes(
        G, pos, node_color=node_colors, node_size=node_sizes, ax=ax
    )
    nx.draw_networkx_edges(G, pos, arrows=True, edge_color="#555555", connectionstyle="arc3,rad=0.2", ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=8, ax=ax)

    # Quitar ejes y bordes
    ax.set_axis_off()
    plt.tight_layout()

    # Tooltips
    tooltips = [G.nodes[n]['tooltip'] for n in G.nodes()]
    tooltip = plugins.PointHTMLTooltip(scatter, tooltips, voffset=10, hoffset=10)
    plugins.connect(fig, tooltip)

    html_graph = mpld3.fig_to_html(fig)
    plt.close()
    return html_graph


    # Generar gráfico interactivo
    graph_html = generar_grafica_interactiva(personas_dep)

    return render_template('nivel_jerarquico_dep.html', graph_html=graph_html, dep_id=dep_id)


# -----------------------
# Run App
# -----------------------
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)


