import os
import hmac
from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.utils import secure_filename

app = Flask(__name__)
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    raise RuntimeError('Define the SECRET_KEY environment variable before starting the app.')
app.config['SECRET_KEY'] = secret_key
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
if not database_url:
    database_url = f"sqlite:///{os.path.join(app.instance_path, 'susurros_dragon.db')}"
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '').lower() in {'1', 'true', 'yes'}

os.makedirs(app.instance_path, exist_ok=True)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

ADMIN_USER = os.environ.get('ADMIN_USER')
ADMIN_PASS = os.environ.get('ADMIN_PASS')

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    imagen = db.Column(db.Text, nullable=False)
    descripcion = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'categoria': self.categoria,
            'precio': self.precio,
            'imagen': self.imagen,
            'descripcion': self.descripcion
        }

class Personalizado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50), default="Amuleto a Medida")
    precio_base = db.Column(db.Float, nullable=False)
    imagen = db.Column(db.Text, nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    opciones = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'tipo': self.tipo,
            'precio_base': self.precio_base,
            'imagen': self.imagen,
            'descripcion': self.descripcion,
            'opciones': self.opciones
        }

class Ritual(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), default="Protección")
    precio = db.Column(db.Float, nullable=False)
    imagen = db.Column(db.Text, nullable=False)
    proposito = db.Column(db.Text, nullable=True)
    incluye = db.Column(db.Text, nullable=True)
    duracion = db.Column(db.String(50), default="1 Sesión Mística")

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'categoria': self.categoria,
            'precio': self.precio,
            'imagen': self.imagen,
            'proposito': self.proposito,
            'incluye': self.incluye,
            'duracion': self.duracion
        }

class Cita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_cliente = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(50), nullable=False)
    tipo_servicio = db.Column(db.String(100), nullable=False)
    modalidad = db.Column(db.String(50), default="Virtual")
    fecha = db.Column(db.String(50), nullable=False)
    hora = db.Column(db.String(50), nullable=False)
    notas = db.Column(db.Text, nullable=True)
    estado = db.Column(db.String(50), default="Pendiente")

    def to_dict(self):
        return {
            'id': self.id,
            'nombre_cliente': self.nombre_cliente,
            'telefono': self.telefono,
            'tipo_servicio': self.tipo_servicio,
            'modalidad': self.modalidad,
            'fecha': self.fecha,
            'hora': self.hora,
            'notas': self.notas,
            'estado': self.estado
        }

class Suscripcion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    frecuencia = db.Column(db.String(50), default="Mensual")
    descripcion = db.Column(db.Text, nullable=True)
    beneficios = db.Column(db.Text, nullable=True)
    imagen = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'precio': self.precio,
            'frecuencia': self.frecuencia,
            'descripcion': self.descripcion,
            'beneficios': self.beneficios,
            'imagen': self.imagen
        }

class Remedio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), default="Infusiones")
    precio = db.Column(db.Float, nullable=False)
    imagen = db.Column(db.Text, nullable=False)
    preparacion = db.Column(db.Text, nullable=True)
    propiedades = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'categoria': self.categoria,
            'precio': self.precio,
            'imagen': self.imagen,
            'preparacion': self.preparacion,
            'propiedades': self.propiedades
        }

class ForoTema(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    semana = db.Column(db.String(50), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    imagen = db.Column(db.Text, nullable=True)
    fecha = db.Column(db.String(50), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'titulo': self.titulo,
            'semana': self.semana,
            'contenido': self.contenido,
            'imagen': self.imagen,
            'fecha': self.fecha
        }

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    with app.app_context():
        db.create_all()
        suscripcion_columns = {column['name'] for column in inspect(db.engine).get_columns(Suscripcion.__tablename__)}
        if 'imagen' not in suscripcion_columns:
            try:
                with db.engine.begin() as connection:
                    connection.execute(text(f'ALTER TABLE {Suscripcion.__tablename__} ADD COLUMN imagen TEXT'))
            except Exception:
                updated_columns = {column['name'] for column in inspect(db.engine).get_columns(Suscripcion.__tablename__)}
                if 'imagen' not in updated_columns:
                    raise
        if Producto.query.count() == 0:
            prods = [
                Producto(nombre="TALISMAN DE VIDA", categoria="amuletos", precio=45000, imagen="https://images.unsplash.com/photo-1567653418876-5bb0e566e1c2?auto=format&fit=crop&w=600&q=80", descripcion="Artículo ritual consagrado."),
                Producto(nombre="TAROT ARCANA CELESTIAL", categoria="tarot", precio=48000, imagen="https://images.unsplash.com/photo-1601314002592-b8734bca6604?auto=format&fit=crop&w=600&q=80", descripcion="Mazo completo de 78 cartas arcanas con bordes dorados e ilustraciones en tinta."),
                Producto(nombre="DRUSA DE AMATISTA", categoria="cristales", precio=35000, imagen="https://images.unsplash.com/photo-1535585209827-a15fcdbc4c2d?auto=format&fit=crop&w=600&q=80", descripcion="Cristal natural transmutador de energías densas."),
                Producto(nombre="SAHUMERIO DE SALVIA", categoria="inciensos", precio=15000, imagen="https://images.unsplash.com/photo-1608571423902-eed4a5ad8108?auto=format&fit=crop&w=600&q=80", descripcion="Atado ritualizado para sahumar ambientes.")
            ]
            db.session.bulk_save_objects(prods)

        if Personalizado.query.count() == 0:
            pers = [
                Personalizado(
                    nombre="TALISMÁN O AMULETO CONSAGRADO A MEDIDA",
                    tipo="Amuleto Personalizado",
                    precio_base=60000,
                    imagen="https://images.unsplash.com/photo-1535585209827-a15fcdbc4c2d?auto=format&fit=crop&w=600&q=80",
                    descripcion="Amuleto forjado y cargado energéticamente con tu fecha de nacimiento, nombre y la intención específica que requieras.",
                    opciones="Piedra Principal: Amatista / Cuarzo Rosa / Ojo de Tigre / Obsidiana | Intención: Protección, Prosperidad, Amor, Salud"
                ),
                Personalizado(
                    nombre="VELÓN RITUALIZADO CON INTENCIÓN NOMBRE Y FECHA",
                    tipo="Vela Personalizada",
                    precio_base=40000,
                    imagen="https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=600&q=80",
                    descripcion="Velón tallado a mano con tus siglas, consagrado con óleos místicos e hierbas rituales según tu propósito.",
                    opciones="Color: Morado (Transformación), Dorado (Abundancia), Rojo (Pasión), Blanco (Limpia) | Hierbas: Romera, Salvia, Lavanda, Canela"
                )
            ]
            db.session.bulk_save_objects(pers)

        if Ritual.query.count() == 0:
            rits = [
                Ritual(nombre="RITUAL DE LIMPIEZA & ABRECAMINOS", categoria="Purificación", precio=75000, imagen="https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=600&q=80", proposito="Desbloquear bloqueos energéticos, limpiar aura y atraer prosperidad.", incluye="Lectura diagnóstica previa, velón ritualizado, canalización y reporte de cierre.", duracion="1 Sesión (Ritual Individual)"),
                Ritual(nombre="CONSAGRACIÓN Y PROTECCIÓN DEL HOGAR", categoria="Protección", precio=95000, imagen="https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=600&q=80", proposito="Blindar el espacio personal o negocio contra malas influencias y envidias.", incluye="Sellado de esquinas, sahumado sagrado, amuleto de protección consagrado.", duracion="Sesión Completa Presencial / Distancia")
            ]
            db.session.bulk_save_objects(rits)

        if Suscripcion.query.count() == 0:
            subs = [
                Suscripcion(nombre="MEMBRESÍA DRAGÓN MÍSTICO", precio=50000, frecuencia="Mensual", descripcion="Recibe cada mes una caja de rituales seleccionada y lecturas privadas.", beneficios="1 Caja Mística Mensual, Acceso al Foro Exclusivo, 10% Descuento en Tienda"),
                Suscripcion(nombre="CIRCULO SAGRADO ANCESTRAL", precio=120000, frecuencia="Trimestral", descripcion="Acceso VIP a rituales de Luna Llena, oráculo semanal personalizado y caja ritual.", beneficios="3 Cajas Sagradas, Lectura de Tarot de 30 min, Acceso VIP a Foros Directos")
            ]
            db.session.bulk_save_objects(subs)

        if Remedio.query.count() == 0:
            rems = [
                Remedio(nombre="ELIXIR DE SUEÑO DULCE DE MANZANILLA & LAVANDA", categoria="Infusiones", precio=25000, imagen="https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=600&q=80", preparacion="Infusionar 1 cucharada en agua hirviendo durante 7 minutos.", propiedades="Relajante nervioso, alivia insomnio y disminuye ansiedad."),
                Remedio(nombre="TÓNICO PROTECTOR DE JENGIBRE & ROMERO", categoria="Tónicos", precio=32000, imagen="https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=600&q=80", preparacion="Hervir a fuego lento durante 10 minutos y endulzar con miel silvestre.", propiedades="Eleva las defensas, limpia el tracto respiratorio y revitaliza la mente.")
            ]
            db.session.bulk_save_objects(rems)

        if ForoTema.query.count() == 0:
            foros = [
                ForoTema(titulo="El Poder Revelador de la Luna Creciente en la Mente", semana="Semana 42 - Octubre", contenido="Bienvenidos a nuestro encuentro semanal. Esta semana exploraremos cómo los ciclos lunares afectan nuestras emociones y cómo canalizar la energía de la Luna Creciente para decretos y manifestación de proyectos...", imagen="https://images.unsplash.com/photo-1532693322450-2cb5c511067d?auto=format&fit=crop&w=600&q=80", fecha="19 Oct 2026")
            ]
            db.session.bulk_save_objects(foros)

        db.session.commit()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('index.html')

@app.route('/service-worker.js')
def service_worker():
    response = send_from_directory(app.static_folder, 'service-worker.js', mimetype='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache'
    return response

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# AUTH
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    usuario = data.get('usuario')
    password = data.get('password')
    credenciales_configuradas = bool(ADMIN_USER and ADMIN_PASS)
    usuario_valido = isinstance(usuario, str) and credenciales_configuradas and hmac.compare_digest(usuario, ADMIN_USER)
    password_valida = isinstance(password, str) and credenciales_configuradas and hmac.compare_digest(password, ADMIN_PASS)
    if usuario_valido and password_valida:
        session['logged_in'] = True
        return jsonify({'success': True})
    return jsonify({'success': False}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return jsonify({'success': True})

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    return jsonify({'authenticated': session.get('logged_in', False)})

# PERSONALIZADOS
@app.route('/api/personalizados', methods=['GET'])
def get_personalizados():
    return jsonify([p.to_dict() for p in Personalizado.query.all()])

@app.route('/api/personalizados', methods=['POST'])
def add_personalizado():
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403

    nombre = request.form.get('nombre')
    tipo = request.form.get('tipo', 'Amuleto Personalizado')
    precio_base = float(request.form.get('precio_base', 0))
    descripcion = request.form.get('descripcion', '')
    opciones = request.form.get('opciones', '')
    imagen_final = request.form.get('imagen_url', '')

    if 'imagen_archivo' in request.files:
        file = request.files['imagen_archivo']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            base, ext = os.path.splitext(filename)
            import time
            filename = f"{base}_{int(time.time())}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            imagen_final = f"/static/uploads/{filename}"

    if not imagen_final:
        imagen_final = "https://images.unsplash.com/photo-1535585209827-a15fcdbc4c2d?auto=format&fit=crop&w=600&q=80"

    nuevo = Personalizado(nombre=nombre, tipo=tipo, precio_base=precio_base, imagen=imagen_final, descripcion=descripcion, opciones=opciones)
    db.session.add(nuevo)
    db.session.commit()
    return jsonify(nuevo.to_dict()), 201

@app.route('/api/personalizados/<int:item_id>', methods=['DELETE'])
def delete_personalizado(item_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403
    p = Personalizado.query.get(item_id)
    if p:
        db.session.delete(p)
        db.session.commit()
        return jsonify({'message': 'Eliminado'})
    return jsonify({'error': 'No encontrado'}), 404

# CITAS & ASESORÍAS
@app.route('/api/citas', methods=['GET'])
def get_citas():
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403
    return jsonify([c.to_dict() for c in Cita.query.order_by(Cita.id.desc()).all()])

@app.route('/api/citas', methods=['POST'])
def add_cita():
    data = request.get_json() or {}
    nueva = Cita(
        nombre_cliente=data.get('nombre_cliente'),
        telefono=data.get('telefono'),
        tipo_servicio=data.get('tipo_servicio', 'Asesoría Mística General'),
        modalidad=data.get('modalidad', 'Virtual'),
        fecha=data.get('fecha'),
        hora=data.get('hora'),
        notas=data.get('notas', '')
    )
    db.session.add(nueva)
    db.session.commit()
    return jsonify(nueva.to_dict()), 201

@app.route('/api/citas/<int:cita_id>', methods=['DELETE'])
def delete_cita(cita_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403
    c = Cita.query.get(cita_id)
    if c:
        db.session.delete(c)
        db.session.commit()
        return jsonify({'message': 'Cita eliminada'})
    return jsonify({'error': 'No encontrada'}), 404

# PRODUCTOS
@app.route('/api/productos', methods=['GET'])
def get_productos():
    return jsonify([p.to_dict() for p in Producto.query.all()])

@app.route('/api/productos', methods=['POST'])
def add_producto():
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403

    nombre = request.form.get('nombre')
    categoria = request.form.get('categoria', 'amuletos')
    precio = float(request.form.get('precio', 0))
    descripcion = request.form.get('descripcion', '')
    imagen_final = request.form.get('imagen_url', '')

    if 'imagen_archivo' in request.files:
        file = request.files['imagen_archivo']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            base, ext = os.path.splitext(filename)
            import time
            filename = f"{base}_{int(time.time())}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            imagen_final = f"/static/uploads/{filename}"

    if not imagen_final:
        imagen_final = "https://images.unsplash.com/photo-1567653418876-5bb0e566e1c2?auto=format&fit=crop&w=600&q=80"

    nuevo = Producto(nombre=nombre, categoria=categoria, precio=precio, imagen=imagen_final, descripcion=descripcion)
    db.session.add(nuevo)
    db.session.commit()
    return jsonify(nuevo.to_dict()), 201

@app.route('/api/productos/<int:prod_id>', methods=['DELETE'])
def delete_producto(prod_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403
    p = Producto.query.get(prod_id)
    if p:
        db.session.delete(p)
        db.session.commit()
        return jsonify({'message': 'Eliminado'})
    return jsonify({'error': 'No encontrado'}), 404

# RITUALES
@app.route('/api/rituales', methods=['GET'])
def get_rituales():
    return jsonify([r.to_dict() for r in Ritual.query.all()])

@app.route('/api/rituales', methods=['POST'])
def add_ritual():
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403

    nombre = request.form.get('nombre')
    categoria = request.form.get('categoria', 'Protección')
    precio = float(request.form.get('precio', 0))
    proposito = request.form.get('proposito', '')
    incluye = request.form.get('incluye', '')
    duracion = request.form.get('duracion', '1 Sesión Mística')
    imagen_final = request.form.get('imagen_url', '')

    if 'imagen_archivo' in request.files:
        file = request.files['imagen_archivo']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            base, ext = os.path.splitext(filename)
            import time
            filename = f"{base}_{int(time.time())}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            imagen_final = f"/static/uploads/{filename}"

    if not imagen_final:
        imagen_final = "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=600&q=80"

    nuevo = Ritual(nombre=nombre, categoria=categoria, precio=precio, imagen=imagen_final, proposito=proposito, incluye=incluye, duracion=duracion)
    db.session.add(nuevo)
    db.session.commit()
    return jsonify(nuevo.to_dict()), 201

@app.route('/api/rituales/<int:rit_id>', methods=['DELETE'])
def delete_ritual(rit_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403
    r = Ritual.query.get(rit_id)
    if r:
        db.session.delete(r)
        db.session.commit()
        return jsonify({'message': 'Eliminado'})
    return jsonify({'error': 'No encontrado'}), 404

# SUSCRIPCIONES
@app.route('/api/suscripciones', methods=['GET'])
def get_suscripciones():
    return jsonify([s.to_dict() for s in Suscripcion.query.all()])

@app.route('/api/suscripciones', methods=['POST'])
def add_suscripcion():
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403

    imagen_final = request.form.get('imagen_url', '').strip()
    if 'imagen_archivo' in request.files:
        file = request.files['imagen_archivo']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            base, ext = os.path.splitext(filename)
            import time
            filename = f"{base}_{int(time.time())}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            imagen_final = f"/static/uploads/{filename}"

    nueva = Suscripcion(
        nombre=request.form.get('nombre'),
        precio=float(request.form.get('precio', 0)),
        frecuencia=request.form.get('frecuencia', 'Mensual'),
        descripcion=request.form.get('descripcion', ''),
        beneficios=request.form.get('beneficios', ''),
        imagen=imagen_final or None
    )
    db.session.add(nueva)
    db.session.commit()
    return jsonify(nueva.to_dict()), 201

@app.route('/api/suscripciones/<int:sub_id>', methods=['DELETE'])
def delete_suscripcion(sub_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403
    s = Suscripcion.query.get(sub_id)
    if s:
        db.session.delete(s)
        db.session.commit()
        return jsonify({'message': 'Eliminada'})
    return jsonify({'error': 'No encontrada'}), 404

# REMEDIOS
@app.route('/api/remedios', methods=['GET'])
def get_remedios():
    return jsonify([r.to_dict() for r in Remedio.query.all()])

@app.route('/api/remedios', methods=['POST'])
def add_remedio():
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403

    nombre = request.form.get('nombre')
    categoria = request.form.get('categoria', 'Infusiones')
    precio = float(request.form.get('precio', 0))
    preparacion = request.form.get('preparacion', '')
    propiedades = request.form.get('propiedades', '')
    imagen_final = request.form.get('imagen_url', '')

    if 'imagen_archivo' in request.files:
        file = request.files['imagen_archivo']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            base, ext = os.path.splitext(filename)
            import time
            filename = f"{base}_{int(time.time())}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            imagen_final = f"/static/uploads/{filename}"

    if not imagen_final:
        imagen_final = "https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=600&q=80"

    nuevo = Remedio(nombre=nombre, categoria=categoria, precio=precio, imagen=imagen_final, preparacion=preparacion, propiedades=propiedades)
    db.session.add(nuevo)
    db.session.commit()
    return jsonify(nuevo.to_dict()), 201

@app.route('/api/remedios/<int:rem_id>', methods=['DELETE'])
def delete_remedio(rem_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403
    r = Remedio.query.get(rem_id)
    if r:
        db.session.delete(r)
        db.session.commit()
        return jsonify({'message': 'Eliminado'})
    return jsonify({'error': 'No encontrado'}), 404

# FORO
@app.route('/api/foro', methods=['GET'])
def get_foro():
    return jsonify([f.to_dict() for f in ForoTema.query.order_by(ForoTema.id.desc()).all()])

@app.route('/api/foro', methods=['POST'])
def add_foro():
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403

    titulo = request.form.get('titulo')
    semana = request.form.get('semana', 'Semana Actual')
    contenido = request.form.get('contenido')
    imagen_final = request.form.get('imagen_url', '')

    if 'imagen_archivo' in request.files:
        file = request.files['imagen_archivo']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            base, ext = os.path.splitext(filename)
            import time
            filename = f"{base}_{int(time.time())}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            imagen_final = f"/static/uploads/{filename}"

    import datetime
    fecha_str = datetime.datetime.now().strftime("%d %b %Y")
    nuevo = ForoTema(
        titulo=titulo,
        semana=semana,
        contenido=contenido,
        imagen=imagen_final,
        fecha=fecha_str
    )
    db.session.add(nuevo)
    db.session.commit()
    return jsonify(nuevo.to_dict()), 201

@app.route('/api/foro/<int:foro_id>', methods=['DELETE'])
def delete_foro(foro_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403
    f = ForoTema.query.get(foro_id)
    if f:
        db.session.delete(f)
        db.session.commit()
        return jsonify({'message': 'Eliminado'})
    return jsonify({'error': 'No encontrado'}), 404

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5000')), debug=False)

