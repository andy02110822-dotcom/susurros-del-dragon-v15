import os
import hmac
import json
import time
import uuid
import re
import hashlib
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from flask import Flask, render_template, request, jsonify, session, send_from_directory, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.utils import secure_filename

app = Flask(__name__)
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    raise RuntimeError('Define the SECRET_KEY environment variable before starting the app.')
app.config['SECRET_KEY'] = secret_key
DATA_DIR = os.path.abspath(os.environ.get('DATA_DIR', app.instance_path))
os.makedirs(DATA_DIR, exist_ok=True)

database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
if not database_url:
    database_url = f"sqlite:///{os.path.join(DATA_DIR, 'susurros_dragon.db')}"
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '').lower() in {'1', 'true', 'yes'}
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024

UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({'error': 'La imagen supera el límite de 12 MB. Reduce su tamaño e inténtalo de nuevo'}), 413

db = SQLAlchemy(app)

ADMIN_USER = os.environ.get('ADMIN_USER')
ADMIN_PASS = os.environ.get('ADMIN_PASS')
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID', '').strip()
PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET', '').strip()
PAYPAL_ENV = os.environ.get('PAYPAL_ENV', 'sandbox').strip().lower()
if PAYPAL_ENV not in {'sandbox', 'live'}:
    PAYPAL_ENV = 'sandbox'
PAYPAL_API_BASE = 'https://api-m.paypal.com' if PAYPAL_ENV == 'live' else 'https://api-m.sandbox.paypal.com'

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    imagen = db.Column(db.Text, nullable=False)
    imagen_posicion = db.Column(db.String(16), nullable=False, default='50% 50%')
    imagen_zoom = db.Column(db.Float, nullable=False, default=1.0)
    descripcion = db.Column(db.Text, nullable=True)
    variantes = db.Column(db.Text, nullable=False, default='[]')

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'categoria': self.categoria,
            'precio': self.precio,
            'imagen': self.imagen,
            'imagen_posicion': self.imagen_posicion or '50% 50%',
            'imagen_zoom': self.imagen_zoom or 1.0,
            'descripcion': self.descripcion,
            'variantes': json.loads(self.variantes or '[]')
        }

class Personalizado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50), default="Amuleto a Medida")
    precio_base = db.Column(db.Float, nullable=False)
    imagen = db.Column(db.Text, nullable=False)
    imagen_posicion = db.Column(db.String(16), nullable=False, default='50% 50%')
    imagen_zoom = db.Column(db.Float, nullable=False, default=1.0)
    descripcion = db.Column(db.Text, nullable=True)
    opciones = db.Column(db.Text, nullable=True)
    variantes = db.Column(db.Text, nullable=False, default='[]')

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'tipo': self.tipo,
            'precio_base': self.precio_base,
            'imagen': self.imagen,
            'imagen_posicion': self.imagen_posicion or '50% 50%',
            'imagen_zoom': self.imagen_zoom or 1.0,
            'descripcion': self.descripcion,
            'opciones': self.opciones,
            'variantes': json.loads(self.variantes or '[]')
        }

class Ritual(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), default="Protección")
    precio = db.Column(db.Float, nullable=False)
    imagen = db.Column(db.Text, nullable=False)
    imagen_posicion = db.Column(db.String(16), nullable=False, default='50% 50%')
    imagen_zoom = db.Column(db.Float, nullable=False, default=1.0)
    proposito = db.Column(db.Text, nullable=True)
    incluye = db.Column(db.Text, nullable=True)
    duracion = db.Column(db.String(50), default="1 Sesión Mística")
    variantes = db.Column(db.Text, nullable=False, default='[]')

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'categoria': self.categoria,
            'precio': self.precio,
            'imagen': self.imagen,
            'imagen_posicion': self.imagen_posicion or '50% 50%',
            'imagen_zoom': self.imagen_zoom or 1.0,
            'proposito': self.proposito,
            'incluye': self.incluye,
            'duracion': self.duracion,
            'variantes': json.loads(self.variantes or '[]')
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
    imagen_posicion = db.Column(db.String(16), nullable=False, default='50% 50%')
    imagen_zoom = db.Column(db.Float, nullable=False, default=1.0)
    variantes = db.Column(db.Text, nullable=False, default='[]')

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'precio': self.precio,
            'frecuencia': self.frecuencia,
            'descripcion': self.descripcion,
            'beneficios': self.beneficios,
            'imagen': self.imagen,
            'imagen_posicion': self.imagen_posicion or '50% 50%',
            'imagen_zoom': self.imagen_zoom or 1.0,
            'variantes': json.loads(self.variantes or '[]')
        }

class Remedio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), default="Infusiones")
    precio = db.Column(db.Float, nullable=False)
    imagen = db.Column(db.Text, nullable=False)
    imagen_posicion = db.Column(db.String(16), nullable=False, default='50% 50%')
    imagen_zoom = db.Column(db.Float, nullable=False, default=1.0)
    preparacion = db.Column(db.Text, nullable=True)
    propiedades = db.Column(db.Text, nullable=True)
    variantes = db.Column(db.Text, nullable=False, default='[]')

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'categoria': self.categoria,
            'precio': self.precio,
            'imagen': self.imagen,
            'imagen_posicion': self.imagen_posicion or '50% 50%',
            'imagen_zoom': self.imagen_zoom or 1.0,
            'preparacion': self.preparacion,
            'propiedades': self.propiedades,
            'variantes': json.loads(self.variantes or '[]')
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

class PedidoPayPal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    referencia = db.Column(db.String(40), nullable=False, unique=True)
    paypal_order_id = db.Column(db.String(100), nullable=False, unique=True)
    estado = db.Column(db.String(30), nullable=False, default='PENDING')
    total_cop = db.Column(db.Integer, nullable=False)
    tasa_cop_usd = db.Column(db.Numeric(12, 4), nullable=False)
    total_usd = db.Column(db.Numeric(12, 2), nullable=False)
    items_json = db.Column(db.Text, nullable=False)
    payer_email = db.Column(db.String(254), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    captured_at = db.Column(db.DateTime, nullable=True)
    shipping_name = db.Column(db.String(150), nullable=True)
    shipping_phone = db.Column(db.String(40), nullable=True)
    shipping_address = db.Column(db.String(255), nullable=True)
    shipping_address_extra = db.Column(db.String(255), nullable=True)
    shipping_city = db.Column(db.String(100), nullable=True)
    shipping_region = db.Column(db.String(100), nullable=True)
    shipping_postal_code = db.Column(db.String(30), nullable=True)
    shipping_country = db.Column(db.String(100), nullable=True)
    shipping_instructions = db.Column(db.Text, nullable=True)
    shipping_saved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'referencia': self.referencia,
            'paypal_order_id': self.paypal_order_id,
            'estado': self.estado,
            'total_cop': self.total_cop,
            'tasa_cop_usd': float(self.tasa_cop_usd),
            'total_usd': f'{self.total_usd:.2f}',
            'items': json.loads(self.items_json),
            'payer_email': self.payer_email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'captured_at': self.captured_at.isoformat() if self.captured_at else None,
            'shipping': {
                'name': self.shipping_name,
                'phone': self.shipping_phone,
                'address': self.shipping_address,
                'address_extra': self.shipping_address_extra,
                'city': self.shipping_city,
                'region': self.shipping_region,
                'postal_code': self.shipping_postal_code,
                'country': self.shipping_country,
                'instructions': self.shipping_instructions,
                'saved_at': self.shipping_saved_at.isoformat() if self.shipping_saved_at else None,
            },
        }

class VisitaDiaria(db.Model):
    """Anonymous unique browser visits, stored once per browser and Colombia date."""
    __tablename__ = 'visita_diaria'
    visitante_hash = db.Column(db.String(64), primary_key=True)
    fecha = db.Column(db.Date, primary_key=True)


def registrar_visita_publica():
    if request.method != 'GET' or request.path not in {'/', '/admin'} or session.get('logged_in'):
        return

    visitor_token = request.cookies.get('sd_visitor_id', '')
    try:
        visitor_token = str(uuid.UUID(visitor_token))
    except (ValueError, TypeError, AttributeError):
        visitor_token = str(uuid.uuid4())
        g.nuevo_cookie_visitante = True
    g.visitante_token = visitor_token

    visitor_hash = hashlib.sha256(visitor_token.encode('ascii')).hexdigest()
    fecha_local = (datetime.now(timezone.utc) + timedelta(hours=-5)).date()
    try:
        if db.session.get(VisitaDiaria, (visitor_hash, fecha_local)) is None:
            db.session.add(VisitaDiaria(visitante_hash=visitor_hash, fecha=fecha_local))
            try:
                db.session.commit()
            except IntegrityError:
                # Another concurrent request from this browser already recorded today's visit.
                db.session.rollback()
    except SQLAlchemyError as error:
        db.session.rollback()
        app.logger.warning('No se pudo registrar una visita pública: %s', type(error).__name__)


@app.before_request
def contar_entrada_publica():
    registrar_visita_publica()


@app.after_request
def guardar_cookie_visitante(response):
    if getattr(g, 'nuevo_cookie_visitante', False):
        response.set_cookie(
            'sd_visitor_id', g.visitante_token,
            max_age=60 * 60 * 24 * 365, httponly=True, secure=request.is_secure,
            samesite='Lax', path='/',
        )
    return response


PAYMENT_ITEM_MODELS = {
    'productos': (Producto, 'precio'),
    'personalizados': (Personalizado, 'precio_base'),
    'rituales': (Ritual, 'precio'),
    'remedios': (Remedio, 'precio'),
}

_trm_cache = {'value': None, 'expires_at': 0}

def get_cop_usd_rate():
    """Read the current official COP/USD TRM from Colombia's open-data API."""
    now = time.time()
    if _trm_cache['value'] and now < _trm_cache['expires_at']:
        return _trm_cache['value']

    params = urlencode({'$limit': '1', '$order': 'vigenciadesde DESC'})
    req = Request(
        f'https://www.datos.gov.co/resource/32sa-8pi3.json?{params}',
        headers={'Accept': 'application/json', 'User-Agent': 'SusurrosDelDragon/1.0'},
    )
    try:
        with urlopen(req, timeout=8) as response:
            records = json.loads(response.read().decode('utf-8'))
        rate = Decimal(str(records[0]['valor']))
        if rate <= 0:
            raise ValueError('Invalid TRM')
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, IndexError, InvalidOperation, json.JSONDecodeError):
        if _trm_cache['value'] and now < _trm_cache['expires_at'] + 86400:
            return _trm_cache['value']
        raise RuntimeError('No se pudo consultar la tasa TRM vigente')

    _trm_cache.update({'value': rate, 'expires_at': now + 1800})
    return rate

def paypal_api_request(path, method='GET', payload=None, request_id=None):
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise RuntimeError('PayPal no está configurado')

    auth = (f'{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}').encode('utf-8')
    import base64
    operation = 'oauth'
    try:
        access_token = None
        for attempt in range(2):
            token_request = Request(
                f'{PAYPAL_API_BASE}/v1/oauth2/token',
                data=b'grant_type=client_credentials',
                headers={
                    'Authorization': f'Basic {base64.b64encode(auth).decode("ascii")}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                method='POST',
            )
            try:
                with urlopen(token_request, timeout=20) as response:
                    access_token = json.loads(response.read().decode('utf-8'))['access_token']
                break
            except (URLError, TimeoutError):
                if attempt == 1:
                    raise
                # Token creation is safe to retry; no order or payment is made here.
                time.sleep(0.5)
        operation = 'api'
        body = json.dumps(payload).encode('utf-8') if payload is not None else None
        api_request = Request(
            f'{PAYPAL_API_BASE}{path}',
            data=body,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'PayPal-Request-Id': request_id or str(uuid.uuid4()),
            },
            method=method,
        )
        with urlopen(api_request, timeout=20) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        # Log only allowlisted PayPal diagnostics, never credentials or the response body.
        provider_code = 'unknown'
        debug_id = 'unavailable'
        try:
            provider_error = json.loads(error.read().decode('utf-8'))
            provider_code = str(provider_error.get('error') or provider_error.get('name') or 'unknown')[:80]
            debug_id = str(provider_error.get('debug_id') or 'unavailable')[:80]
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            pass
        app.logger.warning(
            'PayPal %s request rejected: status=%s code=%s debug_id=%s',
            operation, error.code, provider_code, debug_id,
        )
        raise RuntimeError('No se pudo completar la solicitud a PayPal') from error
    except (URLError, TimeoutError, KeyError, json.JSONDecodeError) as error:
        app.logger.warning('PayPal %s request failed: %s', operation, type(error).__name__)
        raise RuntimeError('No se pudo completar la solicitud a PayPal') from error

def resolve_payment_items(raw_items):
    if not isinstance(raw_items, list) or not raw_items or len(raw_items) > 30:
        raise ValueError('El caldero no contiene productos válidos')

    items = []
    total_cop = 0
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValueError('Actualiza el caldero e inténtalo de nuevo')
        item_type = raw.get('tipo')
        try:
            item_id = int(raw.get('id'))
        except (TypeError, ValueError):
            raise ValueError('Actualiza el caldero e inténtalo de nuevo')

        config = PAYMENT_ITEM_MODELS.get(item_type)
        if not config:
            if item_type == 'suscripciones':
                raise ValueError('Las suscripciones se gestionan por WhatsApp; el cobro recurrente de PayPal no está configurado')
            raise ValueError('Hay un artículo que no se puede pagar con PayPal')
        model, price_field = config
        item = db.session.get(model, item_id)
        if not item:
            raise ValueError('Uno de los artículos ya no está disponible')
        price = Decimal(str(getattr(item, price_field))).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        selected_variant = None
        if item_type in {'productos', 'personalizados', 'rituales', 'remedios'}:
            variants = json.loads(item.variantes or '[]')
            requested_variant = str(raw.get('variante') or '').strip()
            if variants:
                selected_variant = next((variant for variant in variants if variant['nombre'] == requested_variant), None)
                if not selected_variant:
                    raise ValueError('Selecciona un tipo disponible para cada producto')
                price = Decimal(str(product_variant_price(selected_variant, price))).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            elif requested_variant:
                raise ValueError('Actualiza el caldero e inténtalo de nuevo')
        if price <= 0:
            raise ValueError('El precio de un artículo no es válido')

        name = item.nombre
        if item_type == 'rituales':
            name = f'Ritual: {name}'
        elif item_type == 'personalizados':
            name = f'Personalizado: {name}'

        details = raw.get('personalizacion') if item_type == 'personalizados' else None
        if selected_variant:
            name = f"{name} · {selected_variant['nombre']}"
        snapshot = {'tipo': item_type, 'id': item_id, 'nombre': name, 'precio_cop': int(price)}
        if details and isinstance(details, dict):
            # Keep customer customization for fulfillment, but never send these fields to PayPal.
            snapshot['personalizacion'] = {
                key: str(details.get(key, '')).strip()[:300]
                for key in ('cliente', 'fecha_nac', 'intencion', 'detalles')
            }
        items.append(snapshot)
        total_cop += int(price)

    return items, total_cop

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

ADMIN_EDIT_FIELDS = {
    'personalizados': (Personalizado, ('nombre', 'tipo', 'precio_base', 'descripcion', 'opciones', 'variantes', 'imagen', 'imagen_posicion', 'imagen_zoom'), {'precio_base'}),
    'citas': (Cita, ('nombre_cliente', 'telefono', 'tipo_servicio', 'modalidad', 'fecha', 'hora', 'notas'), set()),
    'productos': (Producto, ('nombre', 'categoria', 'precio', 'descripcion', 'variantes', 'imagen', 'imagen_posicion', 'imagen_zoom'), {'precio'}),
    'rituales': (Ritual, ('nombre', 'categoria', 'precio', 'duracion', 'proposito', 'incluye', 'variantes', 'imagen', 'imagen_posicion', 'imagen_zoom'), {'precio'}),
    'suscripciones': (Suscripcion, ('nombre', 'precio', 'frecuencia', 'descripcion', 'beneficios', 'variantes', 'imagen', 'imagen_posicion', 'imagen_zoom'), {'precio'}),
    'remedios': (Remedio, ('nombre', 'categoria', 'precio', 'preparacion', 'propiedades', 'variantes', 'imagen', 'imagen_posicion', 'imagen_zoom'), {'precio'}),
    'foro': (ForoTema, ('titulo', 'semana', 'contenido', 'imagen'), set()),
}

def save_updated_image(current_image):
    uploaded = request.files.get('imagen_archivo')
    if uploaded and uploaded.filename:
        if not allowed_file(uploaded.filename):
            return None, 'Tipo de imagen no permitido'
        import uuid
        filename = secure_filename(uploaded.filename)
        filename = f"{uuid.uuid4().hex}_{filename}"
        uploaded.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return f"/static/uploads/{filename}", None

    image_url = request.form.get('imagen_url', '').strip()
    return image_url or current_image, None

def normalize_image_position(value):
    """Keep image cropping controls to two safe percentage values."""
    match = re.fullmatch(r'\s*(\d{1,3})%\s+(\d{1,3})%\s*', str(value or ''))
    if not match:
        return '50% 50%'
    x, y = (int(part) for part in match.groups())
    if not (0 <= x <= 100 and 0 <= y <= 100):
        return '50% 50%'
    return f'{x}% {y}%'

def normalize_image_zoom(value):
    """Keep the image scale between 50% and 150%."""
    try:
        zoom = float(value)
    except (TypeError, ValueError):
        return 1.0
    return round(min(1.5, max(0.5, zoom)), 2)

def normalize_product_variants(value):
    """Parse one option per line: Name, Name|price, or legacy Name/price in COP."""
    if isinstance(value, list):
        raw_variants = value
    else:
        raw_variants = []
        for line in str(value or '').splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split('|', 1)
            raw_variants.append({'nombre': parts[0].strip(), 'precio': parts[1].strip() if len(parts) > 1 else ''})

    variants = []
    seen = set()
    if len(raw_variants) > 20:
        raise ValueError('Un producto puede tener hasta 20 tipos')
    for raw_variant in raw_variants:
        if not isinstance(raw_variant, dict):
            raise ValueError('Revisa los tipos del producto')
        name = str(raw_variant.get('nombre') or '').strip()
        raw_price = str(raw_variant.get('precio') or '').strip()
        if not raw_price:
            legacy_price = re.fullmatch(r'(.+?)/\s*([\d.,]+)\s*', name)
            if legacy_price:
                name, raw_price = legacy_price.group(1).strip(), legacy_price.group(2).strip()
        if not name or len(name) > 80 or name.lower() in seen:
            raise ValueError('Cada tipo necesita un nombre único de hasta 80 caracteres')
        seen.add(name.lower())
        variant = {'nombre': name, 'precio': None}
        if raw_price:
            try:
                price_text = raw_price.replace('.', '').replace(',', '') if re.fullmatch(r'\d+(?:[.,]\d{3})+', raw_price) else raw_price
                price = Decimal(price_text).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            except (InvalidOperation, TypeError, ValueError):
                raise ValueError('El precio de cada tipo debe ser un número válido')
            if not price.is_finite() or price <= 0:
                raise ValueError('El precio de cada tipo debe ser mayor a cero')
            variant['precio'] = int(price)
        variants.append(variant)
    return json.dumps(variants, ensure_ascii=False)

def product_variant_price(variant, base_price):
    """Use a variant's explicit COP price or read a legacy trailing /price suffix."""
    raw_price = str(variant.get('precio') or '').strip()
    if not raw_price:
        match = re.fullmatch(r'.+?/\s*([\d.,]+)\s*', str(variant.get('nombre') or '').strip())
        raw_price = match.group(1) if match else ''
    if raw_price:
        if re.fullmatch(r'\d+(?:[.,]\d{3})+', raw_price):
            raw_price = raw_price.replace('.', '').replace(',', '')
        try:
            return Decimal(raw_price).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            pass
    return Decimal(str(base_price)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

def normalize_cop_price(value):
    """Accept COP prices typed with or without Colombian thousands separators."""
    raw = str(value or '').strip().replace('\u00a0', '').replace(' ', '')
    raw = re.sub(r'(?i)COP', '', raw).replace('$', '')
    if not raw or not re.fullmatch(r'\d+(?:[.,]\d+)*', raw):
        raise ValueError('Escribe un precio válido en pesos, por ejemplo 75000')

    if '.' in raw and ',' in raw:
        if raw.rfind(',') > raw.rfind('.'):
            raw = raw.replace('.', '').replace(',', '.')
        else:
            raw = raw.replace(',', '')
    elif re.fullmatch(r'\d{1,3}(?:[.,]\d{3})+', raw):
        raw = raw.replace('.', '').replace(',', '')
    else:
        raw = raw.replace(',', '.')

    try:
        price = Decimal(raw)
    except InvalidOperation as error:
        raise ValueError('Escribe un precio válido en pesos, por ejemplo 75000') from error
    if not price.is_finite() or price <= 0 or price > Decimal('1000000000000'):
        raise ValueError('El precio debe ser mayor que cero y menor a un billón de pesos')
    return float(price.quantize(Decimal('1'), rounding=ROUND_HALF_UP))

@app.route('/api/<string:modulo>/<int:registro_id>', methods=['PUT'])
def update_admin_item(modulo, registro_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403

    config = ADMIN_EDIT_FIELDS.get(modulo)
    if not config:
        return jsonify({'error': 'Sección no válida'}), 404

    model, fields, numeric_fields = config
    item = db.session.get(model, registro_id)
    if not item:
        return jsonify({'error': 'No encontrado'}), 404

    values = request.form if request.form else (request.get_json(silent=True) or {})
    saved_image_path = None
    try:
        for field in fields:
            if field == 'imagen' or field not in values:
                continue
            value = values.get(field)
            if field == 'variantes':
                try:
                    value = normalize_product_variants(value)
                except ValueError as error:
                    raise ValueError(f'Revisa los tipos del artículo: {error}') from error
            elif field == 'imagen_posicion':
                value = normalize_image_position(value)
            elif field == 'imagen_zoom':
                value = normalize_image_zoom(value)
            elif field in numeric_fields:
                try:
                    value = normalize_cop_price(value)
                except ValueError as error:
                    raise ValueError(f'Revisa el campo {field}: {error}') from error
            setattr(item, field, value)

        if 'imagen' in fields:
            uploaded = request.files.get('imagen_archivo')
            if uploaded and uploaded.filename:
                if not allowed_file(uploaded.filename):
                    raise ValueError('La imagen debe ser JPG, PNG, WEBP o GIF')
                filename = secure_filename(uploaded.filename)
                filename = f"{uuid.uuid4().hex}_{filename}"
                saved_image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                uploaded.save(saved_image_path)
                image = f"/static/uploads/{filename}"
                error = None
            else:
                image, error = save_updated_image(item.imagen)
            if error:
                db.session.rollback()
                return jsonify({'error': error}), 400
            item.imagen = image
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        if saved_image_path:
            try:
                os.remove(saved_image_path)
            except OSError:
                app.logger.warning('No se pudo limpiar una imagen de edición fallida')
        return jsonify({'error': str(error)}), 400
    except (TypeError, OSError, SQLAlchemyError):
        db.session.rollback()
        if saved_image_path:
            try:
                os.remove(saved_image_path)
            except OSError:
                app.logger.warning('No se pudo limpiar una imagen de edición fallida')
        app.logger.exception('No se pudo guardar la edición de un artículo')
        return jsonify({'error': 'No se pudieron guardar los cambios. Inténtalo de nuevo'}), 500

    return jsonify(item.to_dict())

def init_db():
    with app.app_context():
        db.create_all()

        def columns_for(model):
            inspector = inspect(db.engine)
            if not inspector.has_table(model.__tablename__):
                # A second create_all handles a transient schema race during
                # simultaneous worker startup before attempting an ALTER.
                db.create_all()
                inspector = inspect(db.engine)
            if not inspector.has_table(model.__tablename__):
                raise RuntimeError(f"No se pudo crear la tabla {model.__tablename__}")
            return {column['name'] for column in inspector.get_columns(model.__tablename__)}

        def add_column_if_missing(model, column_name, column_type):
            if column_name in columns_for(model):
                return
            try:
                with db.engine.begin() as connection:
                    connection.execute(text(
                        f'ALTER TABLE {model.__tablename__} ADD COLUMN {column_name} {column_type}'
                    ))
            except SQLAlchemyError:
                # Another worker may have completed the same additive
                # migration between inspection and ALTER.
                if column_name not in columns_for(model):
                    raise

        shipping_columns = {
            'shipping_name': 'VARCHAR(150)',
            'shipping_phone': 'VARCHAR(40)',
            'shipping_address': 'VARCHAR(255)',
            'shipping_address_extra': 'VARCHAR(255)',
            'shipping_city': 'VARCHAR(100)',
            'shipping_region': 'VARCHAR(100)',
            'shipping_postal_code': 'VARCHAR(30)',
            'shipping_country': 'VARCHAR(100)',
            'shipping_instructions': 'TEXT',
            'shipping_saved_at': 'TIMESTAMP',
        }
        for column_name, column_type in shipping_columns.items():
            add_column_if_missing(PedidoPayPal, column_name, column_type)

        add_column_if_missing(Suscripcion, 'imagen', 'TEXT')
        for model in (Producto, Personalizado, Ritual, Remedio, Suscripcion):
            add_column_if_missing(model, 'imagen_posicion', "VARCHAR(16) NOT NULL DEFAULT '50% 50%'")
            add_column_if_missing(model, 'imagen_zoom', 'FLOAT NOT NULL DEFAULT 1.0')
            add_column_if_missing(model, 'variantes', "TEXT NOT NULL DEFAULT '[]'")
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

@app.route('/api/admin/visitas', methods=['GET'])
def admin_visitas():
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403

    hoy = (datetime.now(timezone.utc) + timedelta(hours=-5)).date()
    total = db.session.query(func.count(func.distinct(VisitaDiaria.visitante_hash))).scalar() or 0
    hoy_unicos = VisitaDiaria.query.filter_by(fecha=hoy).count()
    return jsonify({'visitantes_unicos_total': total, 'visitantes_unicos_hoy': hoy_unicos})

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
    usuario_valido = (
        isinstance(usuario, str) and credenciales_configuradas
        and hmac.compare_digest(usuario.encode('utf-8'), ADMIN_USER.encode('utf-8'))
    )
    password_valida = (
        isinstance(password, str) and credenciales_configuradas
        and hmac.compare_digest(password.encode('utf-8'), ADMIN_PASS.encode('utf-8'))
    )
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

@app.route('/api/tasa-cambio', methods=['GET'])
def tasa_cambio():
    try:
        return jsonify({
            'cop_por_usd': str(get_cop_usd_rate()),
            'moneda': 'USD',
            'fuente': 'TRM oficial · Superintendencia Financiera de Colombia',
        })
    except RuntimeError:
        return jsonify({'error': 'La tasa de cambio no está disponible en este momento'}), 503

def paypal_is_configured():
    return bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)

def paypal_order_amount(total_cop, rate):
    return (Decimal(total_cop) / rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

@app.route('/api/paypal/client-token', methods=['GET'])
def paypal_client_token():
    """Return a short-lived PayPal client token for PayPal-hosted card fields."""
    if not paypal_is_configured():
        return jsonify({'error': 'PayPal aún no está configurado'}), 503
    try:
        token_data = paypal_api_request('/v1/identity/generate-token', 'POST')
        client_token = token_data.get('client_token')
        if not client_token:
            raise RuntimeError('PayPal no devolvió un token de cliente')
        response = jsonify({'client_token': client_token})
        response.headers['Cache-Control'] = 'no-store'
        return response
    except RuntimeError:
        return jsonify({'error': 'No se pudieron habilitar los campos de tarjeta'}), 502

@app.route('/api/paypal/config', methods=['GET'])
def paypal_config():
    return jsonify({
        'enabled': paypal_is_configured(),
        'client_id': PAYPAL_CLIENT_ID if paypal_is_configured() else None,
        'environment': PAYPAL_ENV,
        'currency': 'USD',
    })

@app.route('/api/paypal/quote', methods=['POST'])
def paypal_quote():
    data = request.get_json(silent=True) or {}
    try:
        _, total_cop = resolve_payment_items(data.get('items'))
        rate = get_cop_usd_rate()
        total_usd = paypal_order_amount(total_cop, rate)
        if total_usd <= 0:
            raise ValueError('El total es demasiado bajo para convertirlo a USD')
        return jsonify({
            'total_cop': total_cop,
            'total_usd': f'{total_usd:.2f}',
            'cop_por_usd': str(rate),
            'moneda': 'USD',
            'fuente': 'TRM oficial · Superintendencia Financiera de Colombia',
        })
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    except RuntimeError:
        return jsonify({'error': 'No se pudo consultar la TRM vigente'}), 503

@app.route('/api/paypal/orders', methods=['POST'])
def crear_pedido_paypal():
    if not paypal_is_configured():
        return jsonify({'error': 'PayPal aún no está configurado'}), 503
    data = request.get_json(silent=True) or {}
    try:
        items, total_cop = resolve_payment_items(data.get('items'))
        rate = get_cop_usd_rate()
        total_usd = paypal_order_amount(total_cop, rate)
        if total_usd <= 0:
            raise ValueError('El total es demasiado bajo para convertirlo a USD')
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    except RuntimeError:
        return jsonify({'error': 'No se pudo consultar la TRM vigente'}), 503

    reference = f'SDR-{uuid.uuid4().hex[:20].upper()}'
    payload = {
        'intent': 'CAPTURE',
        'purchase_units': [{
            'reference_id': reference,
            'custom_id': reference,
            'invoice_id': reference,
            'description': f'Pedido Susurros del Dragón {reference}',
            'amount': {'currency_code': 'USD', 'value': f'{total_usd:.2f}'},
        }],
        'application_context': {
            'brand_name': 'Susurros del Dragón',
            'user_action': 'PAY_NOW',
            'shipping_preference': 'NO_SHIPPING',
        },
    }
    try:
        paypal_order = paypal_api_request('/v2/checkout/orders', 'POST', payload, request_id=reference)
        order_id = paypal_order.get('id')
        if not order_id:
            raise RuntimeError('PayPal no devolvió el ID del pedido')
        order = PedidoPayPal(
            referencia=reference,
            paypal_order_id=order_id,
            estado=paypal_order.get('status', 'CREATED'),
            total_cop=total_cop,
            tasa_cop_usd=rate,
            total_usd=total_usd,
            items_json=json.dumps(items, ensure_ascii=False),
        )
        db.session.add(order)
        db.session.commit()
        return jsonify({'id': order_id, 'reference': reference})
    except RuntimeError:
        db.session.rollback()
        return jsonify({'error': 'PayPal no pudo iniciar el pago. Inténtalo de nuevo.'}), 502
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'No se pudo guardar el pedido de pago.'}), 500

def paypal_shipping_token(order):
    message = f'envio:{order.paypal_order_id}:{order.referencia}'.encode('utf-8')
    return hmac.new(app.config['SECRET_KEY'].encode('utf-8'), message, 'sha256').hexdigest()

@app.route('/api/paypal/orders/<string:paypal_order_id>/capture', methods=['POST'])
def capturar_pedido_paypal(paypal_order_id):
    if not paypal_is_configured() or not re.fullmatch(r'[A-Z0-9-]{8,100}', paypal_order_id):
        return jsonify({'error': 'Pedido PayPal inválido'}), 400
    order = PedidoPayPal.query.filter_by(paypal_order_id=paypal_order_id).first()
    if not order:
        return jsonify({'error': 'No se encontró el pedido de pago'}), 404
    if order.estado == 'COMPLETED':
        return jsonify({
            'success': True,
            'status': order.estado,
            'reference': order.referencia,
            'shipping_token': paypal_shipping_token(order),
        })

    try:
        result = paypal_api_request(
            f'/v2/checkout/orders/{paypal_order_id}/capture',
            'POST', {}, request_id=f'capture-{paypal_order_id}'[:38],
        )
    except RuntimeError:
        return jsonify({'error': 'PayPal no pudo confirmar el pago. Revisa tu cuenta antes de reintentar.'}), 502

    status = result.get('status', 'UNKNOWN')
    capture = (((result.get('purchase_units') or [{}])[0].get('payments') or {}).get('captures') or [{}])[0]
    captured_amount = capture.get('amount') or {}
    if status == 'COMPLETED':
        try:
            amount_matches = (
                captured_amount.get('currency_code') == 'USD'
                and Decimal(captured_amount.get('value', '0')) == Decimal(order.total_usd)
            )
        except InvalidOperation:
            amount_matches = False
        if not amount_matches:
            order.estado = 'REVIEW'
            db.session.commit()
            return jsonify({'error': 'El importe confirmado requiere revisión del comercio'}), 409
        order.estado = 'COMPLETED'
        order.payer_email = (result.get('payer') or {}).get('email_address')
        order.captured_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({
            'success': True,
            'status': order.estado,
            'reference': order.referencia,
            'shipping_token': paypal_shipping_token(order),
        })

    order.estado = status
    db.session.commit()
    return jsonify({'success': False, 'status': status, 'error': 'El pago no quedó completado'}), 402

@app.route('/api/paypal/orders/<string:paypal_order_id>/shipping', methods=['POST'])
def guardar_envio_pedido_paypal(paypal_order_id):
    order = PedidoPayPal.query.filter_by(paypal_order_id=paypal_order_id).first()
    if not order:
        return jsonify({'error': 'No se encontró el pedido'}), 404
    if order.estado != 'COMPLETED' or not order.captured_at:
        return jsonify({'error': 'Solo se aceptan datos para pagos confirmados'}), 409

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Datos de envío inválidos'}), 400
    token = data.get('token', '')
    if not isinstance(token, str) or not hmac.compare_digest(token, paypal_shipping_token(order)):
        return jsonify({'error': 'No se pudo validar este pedido'}), 403

    fields = {
        'nombre': ('shipping_name', 150),
        'telefono': ('shipping_phone', 40),
        'direccion': ('shipping_address', 255),
        'complemento': ('shipping_address_extra', 255),
        'ciudad': ('shipping_city', 100),
        'departamento': ('shipping_region', 100),
        'codigo_postal': ('shipping_postal_code', 30),
        'pais': ('shipping_country', 100),
        'instrucciones': ('shipping_instructions', 1000),
    }
    values = {}
    for key, (attribute, limit) in fields.items():
        value = data.get(key, '')
        if not isinstance(value, str):
            return jsonify({'error': 'Revisa los datos de envío'}), 400
        values[attribute] = value.strip()[:limit]

    required = ('shipping_name', 'shipping_phone', 'shipping_address', 'shipping_city', 'shipping_region', 'shipping_country')
    if any(not values[field] for field in required):
        return jsonify({'error': 'Completa los datos obligatorios de envío'}), 400

    for field, value in values.items():
        setattr(order, field, value or None)
    order.shipping_saved_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'success': True, 'reference': order.referencia})


@app.route('/api/admin/paypal-orders', methods=['GET'])
def listar_pedidos_paypal():
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403
    orders = PedidoPayPal.query.filter(PedidoPayPal.estado == 'COMPLETED', PedidoPayPal.captured_at.isnot(None)).order_by(PedidoPayPal.id.desc()).limit(100).all()
    return jsonify([order.to_dict() for order in orders])

@app.route('/api/admin/envios', methods=['GET'])
def listar_envios():
    if not session.get('logged_in'):
        return jsonify({'error': 'No autorizado'}), 403
    orders = PedidoPayPal.query.filter(
        PedidoPayPal.estado == 'COMPLETED',
        PedidoPayPal.captured_at.isnot(None)
    ).order_by(PedidoPayPal.id.desc()).limit(200).all()
    response = jsonify([order.to_dict() for order in orders])
    response.headers['Cache-Control'] = 'no-store'
    return response

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
    try:
        variantes = normalize_product_variants(request.form.get('variantes', ''))
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
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

    nuevo = Personalizado(nombre=nombre, tipo=tipo, precio_base=precio_base, imagen=imagen_final,
                          imagen_posicion=normalize_image_position(request.form.get('imagen_posicion')),
                          imagen_zoom=normalize_image_zoom(request.form.get('imagen_zoom')),
                          descripcion=descripcion, opciones=opciones, variantes=variantes)
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

    nombre = request.form.get('nombre', '').strip()
    categoria = request.form.get('categoria', 'amuletos').strip() or 'amuletos'
    descripcion = request.form.get('descripcion', '').strip()
    if not nombre or len(nombre) > 100:
        return jsonify({'error': 'Escribe un nombre de hasta 100 caracteres'}), 400
    if len(categoria) > 50:
        return jsonify({'error': 'La sección debe tener hasta 50 caracteres'}), 400
    try:
        precio_decimal = Decimal(request.form.get('precio', '').strip())
        if not precio_decimal.is_finite() or precio_decimal <= 0 or precio_decimal > Decimal('1000000000000'):
            raise InvalidOperation
        precio = float(precio_decimal)
        variantes = normalize_product_variants(request.form.get('variantes', ''))
    except (InvalidOperation, TypeError, ValueError) as error:
        if isinstance(error, ValueError) and str(error):
            return jsonify({'error': str(error)}), 400
        return jsonify({'error': 'Escribe un precio en pesos mayor que cero'}), 400

    imagen_final = request.form.get('imagen_url', '').strip()
    uploaded = request.files.get('imagen_archivo')
    saved_image_path = None
    if uploaded and uploaded.filename:
        if not allowed_file(uploaded.filename):
            return jsonify({'error': 'La imagen debe ser JPG, PNG, WEBP o GIF'}), 400
        extension = os.path.splitext(secure_filename(uploaded.filename))[1].lower()
        filename = f"{uuid.uuid4().hex}{extension}"
        saved_image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            uploaded.save(saved_image_path)
        except OSError:
            app.logger.exception('No se pudo guardar la imagen del producto')
            return jsonify({'error': 'No se pudo guardar la imagen. Inténtalo de nuevo'}), 500
        imagen_final = f"/static/uploads/{filename}"

    if not imagen_final:
        imagen_final = "https://images.unsplash.com/photo-1567653418876-5bb0e566e1c2?auto=format&fit=crop&w=600&q=80"

    nuevo = Producto(nombre=nombre, categoria=categoria, precio=precio, imagen=imagen_final,
                     imagen_posicion=normalize_image_position(request.form.get('imagen_posicion')),
                     imagen_zoom=normalize_image_zoom(request.form.get('imagen_zoom')),
                     descripcion=descripcion, variantes=variantes)
    try:
        db.session.add(nuevo)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        if saved_image_path:
            try:
                os.remove(saved_image_path)
            except OSError:
                app.logger.warning('No se pudo limpiar una imagen de producto sin publicar')
        app.logger.exception('No se pudo publicar el producto')
        return jsonify({'error': 'No se pudo guardar el producto. Revisa los datos e inténtalo de nuevo'}), 500
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
    try:
        variantes = normalize_product_variants(request.form.get('variantes', ''))
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
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

    nuevo = Ritual(nombre=nombre, categoria=categoria, precio=precio, imagen=imagen_final,
                   imagen_posicion=normalize_image_position(request.form.get('imagen_posicion')),
                   imagen_zoom=normalize_image_zoom(request.form.get('imagen_zoom')),
                   proposito=proposito, incluye=incluye, duracion=duracion, variantes=variantes)
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
    try:
        variantes = normalize_product_variants(request.form.get('variantes', ''))
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
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
        imagen=imagen_final or None,
        imagen_posicion=normalize_image_position(request.form.get('imagen_posicion')),
        imagen_zoom=normalize_image_zoom(request.form.get('imagen_zoom')),
        variantes=variantes
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
    try:
        variantes = normalize_product_variants(request.form.get('variantes', ''))
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
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

    nuevo = Remedio(nombre=nombre, categoria=categoria, precio=precio, imagen=imagen_final,
                    imagen_posicion=normalize_image_position(request.form.get('imagen_posicion')),
                    imagen_zoom=normalize_image_zoom(request.form.get('imagen_zoom')),
                    preparacion=preparacion, propiedades=propiedades, variantes=variantes)
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



