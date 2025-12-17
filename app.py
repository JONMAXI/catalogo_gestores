from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from db import get_connection
from datetime import datetime
import plotly.express as px
import os
from io import BytesIO
import base64
import matplotlib
matplotlib.use("Agg")

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
               pu.nombre AS puesto, dep.nombre as departamento
        FROM persona p
        LEFT JOIN baja_persona b ON p.id = b.id_persona
        LEFT JOIN asigna_puesto ap ON p.id = ap.id_persona
        LEFT JOIN puesto pu ON ap.id_puesto = pu.id
        LEFT JOIN departamento dep ON dep.id = pu.departamento_id
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
                'nombre_completo': f"{row['nombres']} {row['apellidop']} {row['apellidom']}",
                'correo': row['correo'],
                'numero_empleado': row['numero_empleado'],
                'estatus': row['estatus'],
                'telefono_uno': row['telefono_uno'],
                'telefono_dos': row['telefono_dos'],
                'motivo_baja': row['motivo_baja'],
                'puesto': row['puesto'] or '',
                'departamento': row['departamento']
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

        # Traer todos los puestos activos
        cursor.execute("SELECT id, nombre, departamento_id, nivel FROM puesto WHERE activo=1 ORDER BY nivel")
        puestos = cursor.fetchall()

        # Traer todos los jefes posibles con depto y nivel
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

        # Puesto actual
        cursor.execute("SELECT id_puesto FROM asigna_puesto WHERE id_persona=%s", (persona_id,))
        current_puesto = cursor.fetchone()
        current_puesto_id = current_puesto['id_puesto'] if current_puesto else None

        # Jefe actual
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

            # -------------------------------------------
            # Detectar si CAMBIÓ EL PUESTO
            # -------------------------------------------
            cambio_puesto = (str(puesto_id) != str(current_puesto_id))

            # Actualizar puesto
            cursor.execute("DELETE FROM asigna_puesto WHERE id_persona=%s", (persona_id,))
            if puesto_id:
                cursor.execute("""
                    INSERT INTO asigna_puesto (id_persona, id_puesto) 
                    VALUES (%s, %s)
                """, (persona_id, puesto_id))
            conn.commit()

            # -------------------------------------------
            # ***********************************+
            # REGLA DE JERARQUÍA → SOLO SI CAMBIÓ EL PUESTO
            # ***********************************+
            if cambio_puesto:

                # Obtener jefe directo actual antes de cambiar
                cursor.execute("""
                    SELECT id_jefe 
                    FROM asigna_jefe 
                    WHERE id_persona=%s AND fecha_fin IS NULL
                """, (persona_id,))
                row = cursor.fetchone()
                jefe_directo_actual = row['id_jefe'] if row else None

                # Obtener subordinados de esta persona
                cursor.execute("""
                    SELECT id_persona
                    FROM asigna_jefe
                    WHERE id_jefe=%s AND fecha_fin IS NULL
                """, (persona_id,))
                subordinados = [s['id_persona'] for s in cursor.fetchall()]

                # Cerrar relación actual con subordinados
                cursor.execute("""
                    UPDATE asigna_jefe
                    SET fecha_fin = CURDATE()
                    WHERE id_jefe=%s AND fecha_fin IS NULL
                """, (persona_id,))

                # Reasignar subordinados al JEFE DIRECTO de esta persona
                if jefe_directo_actual:
                    for sub in subordinados:
                        cursor.execute("""
                            INSERT INTO asigna_jefe (id_persona, id_jefe, fecha_inicio)
                            VALUES (%s, %s, CURDATE())
                        """, (sub, jefe_directo_actual))

                conn.commit()
            # ***********************************+
            # FIN DE REGLA DE JERARQUÍA
            # -------------------------------------------

            # Limpiar relaciones previas jefe → persona
            cursor.execute("DELETE FROM asigna_jefe WHERE id_persona=%s", (persona_id,))

            # Insertar nuevo jefe
            if jefe_id:
                cursor.execute("""
                    INSERT INTO asigna_jefe (id_persona, id_jefe, fecha_inicio) 
                    VALUES (%s, %s, CURDATE())
                """, (persona_id, jefe_id))

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
# Editar Persona
# -----------------------
@app.route('/editar_persona_arbol/<int:persona_id>', methods=['GET','POST'])
def editar_persona_arbol(persona_id):
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
            return redirect(url_for('nivel_jerarquico'))

    return render_template(
        'editar_persona_arbol.html',
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
# ===============================================
#   RUTA: CONTAR EMPLEADOS POR PUESTO Y DEPARTAMENTO
# ===============================================
@app.route('/nivel_jerarquico/count/<int:dep_id>')
def nivel_jerarquico_count(dep_id):
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                pu.id AS id_puesto,
                pu.nombre AS puesto,
                pu.nivel,
                d.nombre AS departamento,
                COUNT(ap.id_persona) AS total_empleados
            FROM puesto pu
            LEFT JOIN asigna_puesto ap 
                   ON ap.id_puesto = pu.id AND ap.activo = 1
            LEFT JOIN departamento d 
                   ON d.id = pu.departamento_id
            WHERE pu.activo = 1
              AND pu.departamento_id = %s
            GROUP BY pu.id, pu.nombre, pu.nivel, d.nombre
            ORDER BY pu.nivel DESC, pu.nombre;
        """, (dep_id,))

        data = cursor.fetchall()

    return jsonify(data)
    
# ===============================================
#   RUTA PRINCIPAL – MUESTRA EL SELECTOR
# ===============================================
@app.route('/nivel_jerarquico')
def nivel_jerarquico():
    departamentos = {
        1: "Auditoría",
        2: "Call Center",
        3: "Campo 1-14",
        4: "Campo 15-21",
        5: "Sabuesos",
        6: "Cobranza"
    }

    return render_template('nivel_jerarquico.html', departamentos=departamentos)


# =====================================================================================================================================================================================
#   RUTA: OBTENER PERSONAS DE MAYOR RANGO
# ======================================================================================================================================
@app.route('/nivel_jerarquico/personas/<int:dep_id>')
def nivel_jerarquico_personas(dep_id):
    with get_connection() as conn:
        cursor = conn.cursor()

        print(f"🔍 Consultando personas de mayor rango del departamento ID: {dep_id}")

        # Puestos del departamento
        cursor.execute("""
            SELECT id, nombre, nivel
            FROM puesto
            WHERE activo = 1 AND nombre != 'Gestor 1-14' AND departamento_id = %s
        """, (dep_id,))
        puestos = cursor.fetchall()

        print(f"📋 Puestos encontrados: {len(puestos)}")

        if not puestos:
            print("⚠️ No hay puestos activos en este departamento.")
            return jsonify([])

        nivel_max = max(p['nivel'] for p in puestos)
        puestos_top = [p['id'] for p in puestos if p['nivel'] == nivel_max]

        print(f"🏆 Nivel jerárquico más alto: {nivel_max}")
        print(f"🧩 Puestos top IDs: {puestos_top}")

        # Personas que ocupan esos puestos
        cursor.execute("""
            SELECT p.id,
                   CONCAT(p.apellidop,' ',p.apellidom,' ',p.nombres) AS nombre,
                   ap.id_puesto
            FROM persona p
            JOIN asigna_puesto ap ON p.id = ap.id_persona
            WHERE ap.id_puesto IN %s
              AND p.estatus != 'Baja'
        """, (tuple(puestos_top),))

        personas_top = cursor.fetchall()

        print(f"👤 Personas de mayor rango encontradas: {len(personas_top)}")

    return jsonify(personas_top)



# ===============================================
#   NUEVA RUTA: ORGANIGRAMA DESDE UN COLABORADOR
# ===============================================
@app.route('/nivel_jerarquico/colaborador/<int:persona_id>')
def nivel_jerarquico_colaborador(persona_id):
    import matplotlib.pyplot as plt
    import networkx as nx
    from networkx.drawing.nx_pydot import graphviz_layout
    from io import BytesIO
    import base64
    import colorsys
    import time

    print("\n" + "="*60)
    print(f"📊 [INICIO] Generando organigrama desde colaborador ID: {persona_id}")
    inicio = time.time()

    with get_connection() as conn:
        cursor = conn.cursor()

        print("🔍 Consultando personas y relaciones jerárquicas...")
        cursor.execute("""
            SELECT p.id,
                   p.nombres,
                   p.apellidop,
                   ap.id_puesto,
                   aj.id_jefe
            FROM persona p
            JOIN asigna_puesto ap ON p.id = ap.id_persona
            LEFT JOIN asigna_jefe aj 
                  ON p.id = aj.id_persona 
                 AND (aj.fecha_fin IS NULL OR aj.fecha_fin >= CURDATE())
            WHERE p.estatus != 'Baja'
        """)
        personas = cursor.fetchall()
        print(f"✅ Personas activas obtenidas: {len(personas)}")

        cursor.execute("SELECT id, nombre, nivel FROM puesto")
        puestos = cursor.fetchall()
        print(f"✅ Puestos cargados: {len(puestos)}")

        puesto_map = {p['id']: p for p in puestos}

    # Encontrar subárbol empezando en persona_id
    print("🌳 Construyendo subárbol jerárquico...")
    hijos = []
    pendientes = [persona_id]

    while pendientes:
        actual = pendientes.pop(0)
        hijos.append(actual)
        for p in personas:
            if p.get('id_jefe') == actual:
                pendientes.append(p['id'])

    personas_filtradas = [p for p in personas if p['id'] in hijos]
    print(f"✅ Subárbol construido con {len(personas_filtradas)} personas.\n")

    # ---------------------------------------------------
    # REUTILIZAR LA FUNCIÓN DE GENERAR GRÁFICA
    # ---------------------------------------------------
    def generar_grafica(personas_dep):
        import matplotlib.pyplot as plt
        import networkx as nx
        from networkx.drawing.nx_pydot import graphviz_layout
        from io import BytesIO
        import base64
        import colorsys

        print("🎨 [GRAFICANDO] Iniciando render del organigrama...")
        G = nx.DiGraph()
        nodos_map = {}
        niveles_map = {}

        for persona in personas_dep:
            puesto = puesto_map.get(persona['id_puesto'])
            if not puesto:
                print(f"⚠️ Puesto no encontrado para persona ID {persona['id']}")
                continue
           # Agregar gestores_count al nodo solo si hay gestores bajo este jefe
            # Crear nodo principal del jefe
            nodo = f"{persona['nombres']}\n{persona['apellidop']}\n({puesto['nombre']})"
            G.add_node(nodo)
            nodos_map[persona['id']] = nodo
            niveles_map[nodo] = puesto['nivel']

            # --- NUEVO: agregar nodo de Gestores ---
            # --- NUEVO: agregar nodo de Gestores ---
            count = persona.get('gestores_count', 0)
            if count > 0:
                # ID único para que cada jefe tenga su propio nodo de gestores
                nodo_gestores_id = f"gestores_{persona['id']}"
                # Etiqueta visual del nodo (lo que se mostrará en la gráfica)
                etiqueta_gestores = f"{count} Gestores"
                
                # Crear nodo único pero con etiqueta visible igual
                G.add_node(nodo_gestores_id, label=etiqueta_gestores)
                niveles_map[nodo_gestores_id] = puesto['nivel'] + 0.5
                G.add_edge(nodo, nodo_gestores_id)


        print(f"✅ Nodos creados: {len(G.nodes())}")

        relaciones = 0
        for persona in personas_dep:
            if persona.get('id_jefe'):
                jefe_nodo = nodos_map.get(persona['id_jefe'])
                if jefe_nodo:
                    G.add_edge(jefe_nodo, nodos_map[persona['id']])
                    relaciones += 1

        print(f"🧩 Relaciones jerárquicas detectadas: {relaciones}")

        # Intentar con graphviz primero
        try:
            pos = graphviz_layout(G, prog='dot')
            print("✅ Layout generado con Graphviz.")
        except Exception as e:
            print(f"⚠️ Error con Graphviz ({e}), usando spring_layout...")
            pos = nx.spring_layout(G)
            print("✅ Layout alternativo generado con spring_layout.")

        niveles_unicos = sorted(set(niveles_map.values()))
        print(f"🌈 Niveles jerárquicos detectados: {len(niveles_unicos)}")

        def pastel(h):
            r, g, b = colorsys.hls_to_rgb(h, 0.8, 0.6)
            return (r, g, b)

        color_map = {
            nivel: pastel(i / len(niveles_unicos))
            for i, nivel in enumerate(niveles_unicos)
        }
        # Define un color fijo para todos los nodos "gestores"
        color_gestores = (0.95, 0.90, 0.65)  # tono beige claro, puedes cambiarlo

        node_colors = []
        for n in G.nodes():
            if str(n).startswith("gestores_"):
                node_colors.append(color_gestores)
            else:
                node_colors.append(color_map[niveles_map[n]])

        max_size = 2000
        min_size = 1000
        nivel_max = max(niveles_unicos)
        nivel_min = min(niveles_unicos)
        node_sizes = [
            min_size + (niveles_map[n] - nivel_min) / (nivel_max - nivel_min) * (max_size - min_size)
            if nivel_max != nivel_min else max_size
            for n in G.nodes()
        ]

        plt.figure(figsize=(14, 6))
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes)
        labels = {n: G.nodes[n].get('label', n) for n in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=7)
        nx.draw_networkx_edges(G, pos, arrows=False)
        plt.axis('off')

        img = BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight')
        plt.close()
        img.seek(0)

        print("✅ Imagen del organigrama generada correctamente.\n")
        return base64.b64encode(img.read()).decode('utf-8')

    from collections import defaultdict
    import copy

    # Crear copia para no alterar el original
    personas_filtradas_pre = copy.deepcopy(personas_filtradas)

    # Contar gestores por jefe
    gestores_count = defaultdict(int)
    for p in personas_filtradas_pre:
        if p['id_puesto'] == 1 and p.get('id_jefe'):
            gestores_count[p['id_jefe']] += 1

    # Marcar jefes con la cantidad de gestores
    for p in personas_filtradas_pre:
        count = gestores_count.get(p['id'], 0)
        if count > 0:
            # Agregar campo extra para mostrar en la etiqueta del nodo
            p['gestores_count'] = count
        else:
            p['gestores_count'] = 0

    # Eliminar los nodos individuales de los gestores para que no se dibujen
    personas_filtradas_pre = [p for p in personas_filtradas_pre if p['id_puesto'] != 1]

    # Ahora pasas personas_filtradas_pre a tu función original
    graph_base64 = generar_grafica(personas_filtradas_pre)


    fin = time.time()
    print(f"⏱️ [FIN] Organigrama del colaborador ID {persona_id} generado en {fin - inicio:.2f} segundos.")
    print("="*60 + "\n")

    return render_template('nivel_jerarquico_dep.html',
                           graph_base64=graph_base64)




# -----------------------
@app.route('/nivel_jerarquico/colaborador_tabla/<int:persona_id>')
def nivel_jerarquico_colaborador_tabla(persona_id):
    """
    Devuelve en JSON todos los empleados bajo un colaborador
    incluyendo al colaborador mismo, similar a la tabla del index.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Obtener personas y su puesto
        cursor.execute("""
            SELECT p.id, p.nombres, p.apellidop, p.apellidom, p.correo, p.numero_empleado,
                   p.estatus, p.telefono_uno, p.telefono_dos, 
                   pu.id AS id_puesto, pu.nombre AS puesto, pu.departamento_id,
                   aj.id_jefe, dep.nombre as departamento,
                   CONCAT(j.nombres, ' ', j.apellidop, ' ', j.apellidom) AS nombre_jefe,
                   pu_jefe.nombre AS puesto_jefe
            FROM persona p
            JOIN asigna_puesto ap 
                ON ap.id_persona = p.id 
                AND ap.activo = 1
            LEFT JOIN puesto pu 
                ON pu.id = ap.id_puesto
            LEFT JOIN departamento dep 
                ON dep.id = pu.departamento_id
            LEFT JOIN asigna_jefe aj 
                ON aj.id_persona = p.id 
                AND (aj.fecha_fin IS NULL OR aj.fecha_fin >= CURDATE())
            LEFT JOIN persona j 
                ON j.id = aj.id_jefe
            LEFT JOIN asigna_puesto ap_jefe 
                ON ap_jefe.id_persona = j.id 
                AND ap_jefe.activo = 1
            LEFT JOIN puesto pu_jefe 
                ON pu_jefe.id = ap_jefe.id_puesto
            WHERE p.estatus != 'Baja';
        """)
        personas = cursor.fetchall()

    # Construir mapa de jerarquía
    hijos = []
    pendientes = [persona_id]
    while pendientes:
        actual = pendientes.pop(0)
        hijos.append(actual)
        for p in personas:
            if p.get('id_jefe') == actual:
                pendientes.append(p['id'])

    # Filtrar solo los de la misma jerarquía
    filtrados = [p for p in personas if p['id'] in hijos]

    # Formatear como en index
    data = []
    for p in filtrados:
        data.append({
        'id': p['id'],
        'nombres': p['nombres'],
        'apellidop': p['apellidop'],
        'apellidom': p['apellidom'],
        'nombre_completo': f"{p['nombres']} {p['apellidop']} {p['apellidom']}",
        'numero_empleado': p['numero_empleado'],
        'estatus': p['estatus'],
        
        # ✅ Datos necesarios para los filtros
        'puesto_id': p['id_puesto'],               # <-- Filtro Puesto
        'puesto': p['puesto'] or '',
        'departamento_id': p['departamento_id'],   # <-- si lo necesitas
        'jefe_id': p['id_jefe'],                   # <-- Filtro Gestor / Jefe
        'departamento': p['departamento'],
        'nombre_jefe': p['nombre_jefe'],
        'puesto_jefe': p['puesto_jefe']

    })

    return jsonify(data)
#------------------------------------------
# ------------------------------------------
# ***********************************+
#   MÓDULO: Gestión de RAZÓN_AUSENCIA y AUSENCIAS
# ***********************************+
# ------------------------------------------

# Listar razones (catálogo)
@app.route('/razon_ausencia')
def listar_razon_ausencia():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, clave, nombre, descripcion, activo FROM razon_ausencia ORDER BY nombre")
        razones = cursor.fetchall()
    return render_template('razon_ausencia.html', razones=razones)

# Crear / Editar razon_ausencia
@app.route('/razon_ausencia/editar', methods=['GET','POST'])
@app.route('/razon_ausencia/editar/<int:razon_id>', methods=['GET','POST'])
def editar_razon_ausencia(razon_id=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if request.method == 'POST':
            clave = request.form.get('clave')
            nombre = request.form.get('nombre')
            descripcion = request.form.get('descripcion')
            activo = 1 if request.form.get('activo') == 'on' else 0

            if razon_id:
                cursor.execute("""
                    UPDATE razon_ausencia
                    SET clave=%s, nombre=%s, descripcion=%s, activo=%s
                    WHERE id=%s
                """, (clave, nombre, descripcion, activo, razon_id))
            else:
                cursor.execute("""
                    INSERT INTO razon_ausencia (clave, nombre, descripcion, activo)
                    VALUES (%s,%s,%s,%s)
                """, (clave, nombre, descripcion, activo))
            conn.commit()
            flash("Catálogo de razón actualizado.", "success")
            return redirect(url_for('listar_razon_ausencia'))

        razon = None
        if razon_id:
            cursor.execute("SELECT * FROM razon_ausencia WHERE id=%s", (razon_id,))
            razon = cursor.fetchone()

    return render_template('editar_razon_ausencia.html', razon=razon)

# Borrar / desactivar razón
@app.route('/razon_ausencia/eliminar/<int:razon_id>', methods=['POST'])
def eliminar_razon_ausencia(razon_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        # opción: desactivar en lugar de eliminar físicamente
        cursor.execute("UPDATE razon_ausencia SET activo=0 WHERE id=%s", (razon_id,))
        conn.commit()
    flash("Razón marcada como inactiva.", "warning")
    return redirect(url_for('listar_razon_ausencia'))

# ---------------------------
# Registrar Ausencia (form + guardar)
# ---------------------------
@app.route('/ausencia/registrar/<int:persona_id>', methods=['GET','POST'])
@app.route('/ausencia/registrar', methods=['GET','POST'])
def registrar_ausencia(persona_id=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        # traer razones activas
        cursor.execute("SELECT id, nombre FROM razon_ausencia WHERE activo=1 ORDER BY nombre")
        razones = cursor.fetchall()

        # si se pasa persona_id, cargar datos de la persona para mostrar
        persona = None
        if persona_id:
            cursor.execute("SELECT id, nombres, apellidop, apellidom, numero_empleado FROM persona WHERE id=%s", (persona_id,))
            persona = cursor.fetchone()

    if request.method == 'POST':
        id_persona = request.form.get('id_persona') or persona_id
        id_razon = request.form.get('id_razon')
        descripcion = request.form.get('descripcion')

        # El formulario tendrá campos datetime-local para fecha+hora
        fecha_inicio_raw = request.form.get('fecha_inicio')   # formato HTML: 'YYYY-MM-DDTHH:MM'
        fecha_fin_raw = request.form.get('fecha_fin')

        # Validaciones básicas
        if not id_persona or not id_razon or not fecha_inicio_raw or not fecha_fin_raw:
            flash("Faltan campos obligatorios (persona, razón, fecha inicio/fin).", "danger")
            return redirect(request.url)

        # Convertir a DATETIME compatible MySQL: 'YYYY-MM-DD HH:MM:SS'
        try:
            fecha_inicio = datetime.fromisoformat(fecha_inicio_raw)
            fecha_fin = datetime.fromisoformat(fecha_fin_raw)
        except Exception as e:
            flash("Formato de fecha/hora inválido.", "danger")
            return redirect(request.url)

        # Guardar en BD
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ausencia (id_persona, id_razon, descripcion, fecha_inicio, fecha_fin, creado_por)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (id_persona, id_razon, descripcion, fecha_inicio.strftime('%Y-%m-%d %H:%M:%S'),
                  fecha_fin.strftime('%Y-%m-%d %H:%M:%S'), (request.remote_addr or 'web')))
            conn.commit()
        flash("Ausencia registrada correctamente.", "success")
        return redirect(url_for('index'))

    # GET: render form
    return render_template('registrar_ausencia.html', persona=persona, razones=razones, persona_id=persona_id)

# Ver ausencias de una persona
@app.route('/ausencia/persona/<int:persona_id>')
def ver_ausencias_persona(persona_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.id_persona, a.id_razon, r.nombre as razon, a.descripcion,
                   a.fecha_inicio, a.fecha_fin, a.activo, a.fecha_creacion
            FROM ausencia a
            LEFT JOIN razon_ausencia r ON r.id = a.id_razon
            WHERE a.id_persona=%s
            ORDER BY a.fecha_inicio DESC
        """, (persona_id,))
        ausencias = cursor.fetchall()
    return render_template('ver_ausencias_persona.html', ausencias=ausencias, persona_id=persona_id)

# Desactivar (eliminar lógico) ausencia
@app.route('/ausencia/eliminar/<int:ausencia_id>', methods=['POST'])
def eliminar_ausencia(ausencia_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE ausencia SET activo=0 WHERE id=%s", (ausencia_id,))
        conn.commit()
    flash("Ausencia desactivada.", "warning")
    return redirect(request.referrer or url_for('index'))

# -----------------------
# 
# -----------------------
# Lista de roles
@app.route('/roles')
def listar_roles():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM roles ORDER BY nombre")
        roles = cursor.fetchall()
    return render_template('roles_list.html', roles=roles)

# Crear / editar rol
@app.route('/roles/editar', methods=['GET','POST'])
@app.route('/roles/editar/<int:rol_id>', methods=['GET','POST'])
def editar_rol(rol_id=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if request.method == 'POST':
            nombre = request.form.get('nombre')
            descripcion = request.form.get('descripcion')
            activo = 1 if request.form.get('activo') == 'on' else 0

            if rol_id:
                cursor.execute("""
                    UPDATE roles SET nombre=%s, descripcion=%s, activo=%s WHERE id=%s
                """, (nombre, descripcion, activo, rol_id))
                flash("Rol actualizado.", "success")
            else:
                cursor.execute("""
                    INSERT INTO roles (nombre, descripcion, activo) VALUES (%s,%s,%s)
                """, (nombre, descripcion, activo))
                flash("Rol creado.", "success")
            conn.commit()
            return redirect(url_for('listar_roles'))

        rol = None
        if rol_id:
            cursor.execute("SELECT * FROM roles WHERE id=%s", (rol_id,))
            rol = cursor.fetchone()

    return render_template('roles_edit.html', rol=rol)

# Eliminar/desactivar rol (soft)
@app.route('/roles/eliminar/<int:rol_id>', methods=['POST'])
def eliminar_rol(rol_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE roles SET activo=0 WHERE id=%s", (rol_id,))
        conn.commit()
    flash("Rol desactivado.", "warning")
    return redirect(url_for('listar_roles'))

# Editar permisos de un ROL (checkboxes por ruta)
@app.route('/roles/<int:rol_id>/permisos', methods=['GET','POST'])
def editar_permisos_rol(rol_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        # Obtener rol
        cursor.execute("SELECT * FROM roles WHERE id=%s", (rol_id,))
        rol = cursor.fetchone()

        # Todas las rutas/módulos
        cursor.execute("SELECT * FROM rutas WHERE activo=1 ORDER BY id")
        rutas = cursor.fetchall()

        # Permisos actuales del rol
        cursor.execute("SELECT ruta_id FROM permiso_rol WHERE rol_id=%s", (rol_id,))
        actuales = {r['ruta_id'] for r in cursor.fetchall()}

        if request.method == 'POST':
            seleccionadas = request.form.getlist('rutas')  # strings de ids
            # Normalizar a ints (seguro)
            seleccionadas = [int(x) for x in seleccionadas]

            # Eliminar permisos previos y reinsertar
            cursor.execute("DELETE FROM permiso_rol WHERE rol_id=%s", (rol_id,))
            if seleccionadas:
                args = [(rol_id, rid) for rid in seleccionadas]
                cursor.executemany("INSERT INTO permiso_rol (rol_id, ruta_id) VALUES (%s,%s)", args)
            conn.commit()
            flash("Permisos del rol actualizados.", "success")
            return redirect(url_for('editar_permisos_rol', rol_id=rol_id))

    return render_template('editar_permisos.html', rol=rol, rutas=rutas, actuales=actuales)

# Asignar roles a un usuario (multiples)
@app.route('/usuarios/<int:usuario_id>/roles', methods=['GET','POST'])
def asignar_roles_usuario(usuario_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombres, apellidop, apellidom FROM persona WHERE id=%s", (usuario_id,))
        usuario = cursor.fetchone()

        # Lista de roles activos
        cursor.execute("SELECT * FROM roles WHERE activo=1 ORDER BY nombre")
        roles = cursor.fetchall()

        # Roles actuales del usuario
        cursor.execute("SELECT rol_id FROM usuario_roles WHERE usuario_id=%s", (usuario_id,))
        actuales = {r['rol_id'] for r in cursor.fetchall()}

        if request.method == 'POST':
            seleccionados = request.form.getlist('roles')  # strings
            seleccionados = [int(x) for x in seleccionados]

            # Reemplazar asignaciones (simple estrategia)
            cursor.execute("DELETE FROM usuario_roles WHERE usuario_id=%s", (usuario_id,))
            if seleccionados:
                args = [(usuario_id, rid) for rid in seleccionados]
                cursor.executemany("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (%s,%s)", args)
            conn.commit()
            flash("Roles asignados al usuario.", "success")
            return redirect(url_for('asignar_roles_usuario', usuario_id=usuario_id))

    return render_template('asignar_roles.html', usuario=usuario, roles=roles, actuales=actuales)

# Editar permisos por USUARIO (excepciones directas)
@app.route('/usuarios/<int:usuario_id>/permisos', methods=['GET','POST'])
def editar_permisos_usuario(usuario_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombres, apellidop, apellidom FROM persona WHERE id=%s", (usuario_id,))
        usuario = cursor.fetchone()

        cursor.execute("SELECT * FROM rutas WHERE activo=1 ORDER BY nombre")
        rutas = cursor.fetchall()

        cursor.execute("SELECT ruta_id FROM permisos_usuario WHERE usuario_id=%s", (usuario_id,))
        actuales = {r['ruta_id'] for r in cursor.fetchall()}

        if request.method == 'POST':
            seleccionadas = [int(x) for x in request.form.getlist('rutas')]
            cursor.execute("DELETE FROM permisos_usuario WHERE usuario_id=%s", (usuario_id,))
            if seleccionadas:
                args = [(usuario_id, rid) for rid in seleccionadas]
                cursor.executemany("INSERT INTO permisos_usuario (usuario_id, ruta_id) VALUES (%s,%s)", args)
            conn.commit()
            flash("Permisos directos del usuario actualizados.", "success")
            return redirect(url_for('editar_permisos_usuario', usuario_id=usuario_id))

    return render_template('editar_permisos_usuario.html', usuario=usuario, rutas=rutas, actuales=actuales)


# Helper: obtener permisos efectivos de un usuario (roles + permisos usuario)
def obtener_permisos_efectivos(usuario_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        # Permisos via roles
        cursor.execute("""
            SELECT r.ruta
            FROM permiso_rol pr
            JOIN rutas r ON r.id = pr.ruta_id
            JOIN usuario_roles ur ON ur.rol_id = pr.rol_id
            WHERE ur.usuario_id = %s
        """, (usuario_id,))
        via_roles = {row['ruta'] for row in cursor.fetchall()}

        # Permisos directos usuario (añadir)
        cursor.execute("""
            SELECT r.ruta
            FROM permisos_usuario pu
            JOIN rutas r ON r.id = pu.ruta_id
            WHERE pu.usuario_id = %s
        """, (usuario_id,))
        directos = {row['ruta'] for row in cursor.fetchall()}

    # union: roles + directos
    return via_roles | directos


# -----------------------
# Run App
# -----------------------
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)


