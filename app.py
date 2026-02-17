from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, Response, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import pandas as pd
from io import BytesIO
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import subprocess
import json
import requests


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "media_lighting_secret_key") # Usar variable de entorno en producción

# --- CONFIGURACIÓN ---
basedir = os.path.abspath(os.path.dirname(__file__))

# Configuración de base de datos: usar variable de entorno si está disponible (producción)
# De lo contrario, usar la ruta local (desarrollo)
db_path = os.environ.get('DATABASE_PATH', os.path.join(basedir, 'inventario.db'))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de archivos
upload_folder = os.environ.get('UPLOAD_FOLDER', os.path.join(basedir, 'manuales'))
app.config['UPLOAD_FOLDER'] = upload_folder
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg'}

CATEGORIAS = sorted(["Luminarias", "Grip", "Insumos", "Equipamiento Electrico", "Accesorios"])
CATEGORIAS_REPUESTOS = sorted(["General", "Electrónico", "Mecánico", "Óptico", "Cables/Conectores", "Otros"])

# Crear carpetas necesarias si no existen
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- MODELOS ---
class Equipo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    marca = db.Column(db.String(50))
    cantidad_total = db.Column(db.Integer, default=1)
    cantidad_en_uso = db.Column(db.Integer, default=0)
    fecha_ingreso = db.Column(db.String(10)) 
    observaciones = db.Column(db.Text, default="")
    danado = db.Column(db.Boolean, default=False) # Nuevo: Indicar si el equipo está dañado
    manual_filename = db.Column(db.String(200))
    gestion_individual = db.Column(db.Boolean, default=False) # True para equipos que se gestionan individualmente (ej: Luminarias)
    movimientos = db.relationship('Historial', backref='equipo', cascade="all, delete-orphan")
    documentos = db.relationship('Documento', backref='equipo', cascade="all, delete-orphan")
    stocks_por_lugar = db.relationship('StockLugar', backref='equipo', cascade="all, delete-orphan")
    
    @property
    def total_real(self):
        """Devuelve la cantidad total, ya sea del campo directo o contando unidades individuales"""
        if self.gestion_individual and self.equipos_individuales:
            return len(self.equipos_individuales)
        return self.cantidad_total or 0

        if self.gestion_individual and self.equipos_individuales:
            return sum(1 for ind in self.equipos_individuales if ind.en_uso)
        return self.cantidad_en_uso or 0

    @property
    def total_asignado(self):
        """Suma de todas las cantidades asignadas a ubicaciones fijas"""
        if not self.stocks_por_lugar:
            return 0
        return sum((s.cantidad or 0) for s in self.stocks_por_lugar)

    @property
    def cantidad_disponible(self):
        """Cantidad que realmente queda en bodega (Total Real - En Uso Real - Asignado)"""
        return self.total_real - self.uso_real - self.total_asignado
    
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'categoria': self.categoria,
            'marca': self.marca,
            'cantidad_total': self.cantidad_total,
            'cantidad_en_uso': self.cantidad_en_uso,
            'fecha_ingreso': self.fecha_ingreso,
            'observaciones': self.observaciones,
            'danado': self.danado,
            'manual_filename': self.manual_filename,
            'gestion_individual': self.gestion_individual
        }

    # Relación de compatibilidad (Muchos a Muchos)
    compatibles = db.relationship(
        'Equipo', 
        secondary='compatibilidad',
        primaryjoin='Equipo.id==compatibilidad.c.equipo_id',
        secondaryjoin='Equipo.id==compatibilidad.c.compatible_id',
        backref='es_compatible_con'
    )


# Tabla de asociación para compatibilidad
compatibilidad = db.Table('compatibilidad',
    db.Column('equipo_id', db.Integer, db.ForeignKey('equipo.id'), primary_key=True),
    db.Column('compatible_id', db.Integer, db.ForeignKey('equipo.id'), primary_key=True)
)

class Historial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipo.id'), nullable=False)
    tipo = db.Column(db.String(20)) 
    usuario = db.Column(db.String(100))
    cantidad = db.Column(db.Integer, default=1) 
    observaciones = db.Column(db.Text, default="") # Nuevo: Observaciones del movimiento
    estado_al_retorno = db.Column(db.String(50), default="Buen Estado") # Nuevo: Estado reportado (Dañado/OK)
    fecha = db.Column(db.DateTime, default=datetime.now)
    equipo_individual_id = db.Column(db.Integer, db.ForeignKey('equipo_individual.id'), nullable=True) # Vinculación opcional con equipo individual

    def to_dict(self):
        return {
            'id': self.id,
            'equipo_id': self.equipo_id,
            'tipo': self.tipo,
            'usuario': self.usuario,
            'cantidad': self.cantidad,
            'observaciones': self.observaciones,
            'estado_al_retorno': self.estado_al_retorno,
            'fecha': self.fecha.isoformat() if self.fecha else None,
            'equipo_individual_id': self.equipo_individual_id
        }


# Tabla de asociación para Equipo - Repuesto
equipo_repuesto = db.Table('equipo_repuesto',
    db.Column('equipo_id', db.Integer, db.ForeignKey('equipo.id'), primary_key=True),
    db.Column('repuesto_id', db.Integer, db.ForeignKey('repuesto.id'), primary_key=True)
)

class Repuesto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    marca = db.Column(db.String(50))
    categoria = db.Column(db.String(50)) 
    cantidad = db.Column(db.Integer, default=1)
    equipo_asociado_texto = db.Column(db.String(200)) # Detalle textual del equipo/serie asociado
    
    # Relación con Equipos (Luminarias u otros)
    equipos = db.relationship('Equipo', secondary=equipo_repuesto, backref=db.backref('repuestos_asociados'))

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'marca': self.marca,
            'categoria': self.categoria,
            'cantidad': self.cantidad,
            'equipo_asociado_texto': self.equipo_asociado_texto
        }


class Documento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipo.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    nombre_referencial = db.Column(db.String(100), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'equipo_id': self.equipo_id,
            'filename': self.filename,
            'nombre_referencial': self.nombre_referencial
        }


class EquipoIndividual(db.Model):
    """Modelo para gestión individual de equipos (principalmente Luminarias)"""
    id = db.Column(db.Integer, primary_key=True)
    equipo_grupo_id = db.Column(db.Integer, db.ForeignKey('equipo.id'), nullable=False)
    numero_serie = db.Column(db.String(100), nullable=False)
    numero_fixture = db.Column(db.Integer)  # Número físico del equipo (1, 2, 3...)
    danado = db.Column(db.Boolean, default=False)
    observaciones_individuales = db.Column(db.Text, default="")
    fecha_ingreso = db.Column(db.String(10))
    en_uso = db.Column(db.Boolean, default=False)
    ubicacion_actual = db.Column(db.String(200))  # Última ubicación registrada
    
    # Relación con el grupo
    equipo_grupo = db.relationship('Equipo', backref='equipos_individuales')
    # Relación con historial
    movimientos = db.relationship('Historial', backref='equipo_individual', foreign_keys='Historial.equipo_individual_id')

    def to_dict(self):
        return {
            'id': self.id,
            'equipo_grupo_id': self.equipo_grupo_id,
            'numero_serie': self.numero_serie,
            'numero_fixture': self.numero_fixture,
            'danado': self.danado,
            'observaciones_individuales': self.observaciones_individuales,
            'fecha_ingreso': self.fecha_ingreso,
            'en_uso': self.en_uso,
            'ubicacion_actual': self.ubicacion_actual
        }


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

class Lugar(db.Model):
    """Modelo para gestionar ubicaciones fijas/predefinidas"""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    stocks = db.relationship('StockLugar', backref='lugar', cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre
        }


class StockLugar(db.Model):
    """Modelo para rastrear cantidades de equipos en lugares específicos"""
    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipo.id'), nullable=False)
    lugar_id = db.Column(db.Integer, db.ForeignKey('lugar.id'), nullable=False)
    cantidad = db.Column(db.Integer, default=0)
    
    # Restricción de unicidad para evitar duplicados del mismo equipo en el mismo lugar
    __table_args__ = (db.UniqueConstraint('equipo_id', 'lugar_id', name='_equipo_lugar_uc'),)

    def to_dict(self):
        return {
            'id': self.id,
            'equipo_id': self.equipo_id,
            'lugar_id': self.lugar_id,
            'cantidad': self.cantidad
        }


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Por favor, inicia sesión para acceder.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

with app.app_context():
    db.create_all()
    # Crear usuario por defecto si no hay ninguno
    if not Usuario.query.first():
        hashed_pw = generate_password_hash("admin123")
        admin = Usuario(username="MLProducciones", password_hash=hashed_pw)
        db.session.add(admin)
        db.session.commit()
    
    # Pre-cargar lugares si está vacío
    if not Lugar.query.first():
        lugares_default = ["CASA VIP", "CASA SERVICIO", "CASA TEMÁTICA", "CASA PRECARIA"]
        for nombre in lugares_default:
            lugar = Lugar(nombre=nombre)
            db.session.add(lugar)
        db.session.commit()


# --- FUNCIONES AUXILIARES ---
import shutil
def realizar_backup():
    if not os.path.exists('backups'):
        os.makedirs('backups')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_path = os.path.join(basedir, 'inventario.db')
    backup_path = os.path.join(basedir, 'backups', f'inventario_backup_{timestamp}.db')
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)

def respaldar_en_github():
    """Ejecuta los comandos de git para respaldar la base de datos"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Git Add
        subprocess.run(["git", "add", "inventario.db"], check=True, cwd=basedir)
        
        # 2. Git Commit
        subprocess.run(["git", "commit", "-m", f"Sync auto: {timestamp}"], check=True, cwd=basedir)
        
        # 3. Git Push
        subprocess.run(["git", "push", "origin", "main"], check=True, cwd=basedir)
        
        print(f"✅ Respaldo en GitHub completado: {timestamp}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al respaldar en GitHub: {e}")
        return False


@app.route('/')
def welcome():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('welcome.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        # Búsqueda case-insensitive del usuario
        usuario = Usuario.query.filter(db.func.lower(Usuario.username) == user.lower()).first()
        
        if usuario and check_password_hash(usuario.password_hash, pw):
            session['user_id'] = usuario.id
            session['username'] = usuario.username
            flash(f"Bienvenido de nuevo, {usuario.username}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Usuario o contraseña incorrectos.", "error")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for('welcome'))

@app.route('/inventario')
@login_required
def index():
    equipos = Equipo.query.filter(Equipo.categoria != 'Luminarias').order_by(Equipo.id.desc()).all()
    # Obtener lista de lugares de la tabla Lugar
    lugares = Lugar.query.order_by(Lugar.nombre).all()
    ubicaciones = [l.nombre for l in lugares]
    return render_template('index.html', equipos=equipos, categorias=CATEGORIAS, ubicaciones=ubicaciones)

@app.route('/equipo/<int:id>')
@login_required
def detalle_equipo(id):
    e = Equipo.query.get_or_404(id)
    # Solo necesitamos las luminarias para el selector de compatibilidad si es un repuesto
    luminarias = []
    if e.categoria == "Repuestos/Spare":
        luminarias = Equipo.query.filter_by(categoria="Luminarias").order_by(Equipo.nombre).all()
    
    return render_template('detalle.html', e=e, categorias=CATEGORIAS, luminarias=luminarias, lugares=Lugar.query.order_by(Lugar.nombre).all())

@app.route('/equipo/<int:id>/update', methods=['POST'])
@login_required
def update_equipo(id):
    e = Equipo.query.get_or_404(id)
    
    # Actualizar campos básicos
    e.nombre = request.form.get('nombre', e.nombre)
    e.marca = request.form.get('marca', e.marca)
    e.categoria = request.form.get('categoria', e.categoria)
    if e.categoria == 'Luminarias':
        e.gestion_individual = True
    e.observaciones = request.form.get('observaciones', '')
    e.fecha_ingreso = request.form.get('fecha_ingreso', e.fecha_ingreso)
    e.danado = 'danado' in request.form # Nuevo: Checkbox de dañado
    
    try:
        e.cantidad_total = int(request.form.get('cantidad_total', e.cantidad_total))
    except ValueError:
        pass # Mantener valor anterior si hay error

    if 'manual' in request.files:
        file = request.files['manual']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"manual_{e.id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            e.manual_filename = filename
            
    db.session.commit()
    flash(f"Ficha de {e.nombre} actualizada correctamente.", "success")
    
    # Redireccionar usando el parámetro 'next' si existe
    next_url = request.form.get('next')
    if next_url:
        return redirect(next_url)
        
    return redirect(url_for('detalle_equipo', id=id))

@app.route('/download/<filename>')
@login_required
def download_manual(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/movimiento/<int:id>/<tipo>', methods=['POST'])
@login_required
def movimiento(id, tipo):
    e = Equipo.query.get_or_404(id)
    # Cambiado de 'usuario' a 'donde' (ubicación física)
    ubicacion = request.form.get('donde', 'Sin Destino').strip() or "Sin Destino"
    
    # Ya no agregamos lugares automáticamente
    # Si la ubicación no existe en la tabla Lugar, simplemente la usamos para el historial
    # pero no la guardamos como una opción para el futuro.
    # Esto evita que errores de tipeo se guarden permanentemente.
            
    obs_movimiento = request.form.get('observaciones_movimiento', '').strip()
    
    try:
        cant_lote = int(request.form.get('cant_lote') or 1)
        if cant_lote < 1:
            flash("La cantidad debe ser al menos 1.", "warning")
            return redirect(request.referrer or url_for('index'))
    except ValueError:
        cant_lote = 1
    
    if tipo == 'prestar':
        disponible = e.cantidad_disponible
        if cant_lote <= disponible: 
            ind_id = request.form.get('ind_id', type=int)
            e.cantidad_en_uso += cant_lote
            
            nuevo_h = Historial(
                equipo_id=id, 
                tipo='SALIDA', 
                usuario=ubicacion, 
                cantidad=cant_lote,
                observaciones=obs_movimiento,
                equipo_individual_id=ind_id
            )
            
            # Si se especificó un equipo individual
            if ind_id:
                ind = EquipoIndividual.query.get(ind_id)
                if ind:
                    ind.en_uso = True
                    ind.ubicacion_actual = ubicacion
            
            db.session.add(nuevo_h)
            flash(f"Salida registrada: {cant_lote} x {e.nombre} para {ubicacion}", "warning")
        else:
            flash(f"Error: Solo quedan {disponible} disponibles.", "error")
    elif tipo == 'devolver':
        if cant_lote <= e.cantidad_en_uso: 
            estado = request.form.get('estado_retorno', 'Buen Estado')
            ind_id = request.form.get('ind_id', type=int)
            
            e.cantidad_en_uso -= cant_lote
            
            # Si se marca como dañado a nivel de grupo (solo para equipos sin gestión individual)
            if estado == 'Dañado' and not e.gestion_individual:
                e.danado = True
            
            nuevo_h = Historial(
                equipo_id=id, 
                tipo='RETORNO', 
                usuario=ubicacion, 
                cantidad=cant_lote,
                observaciones=obs_movimiento, 
                estado_al_retorno=estado,
                equipo_individual_id=ind_id
            )
            
            # Si se especificó un equipo individual
            if ind_id:
                ind = EquipoIndividual.query.get(ind_id)
                if ind:
                    ind.en_uso = False
                    ind.ubicacion_actual = "Bodega"
                    if estado == 'Dañado':
                        ind.danado = True
            
            db.session.add(nuevo_h)
            flash(f"Retorno registrado: {cant_lote} x {e.nombre} ({estado})", "success")
        else:
            flash(f"Error: Solo hay {e.cantidad_en_uso} en uso actualmente.", "error")
    
    db.session.commit()
    realizar_backup() # Sistema de Backup Automático
    return redirect(request.referrer or url_for('index'))

@app.route('/movimiento/<int:id>/transferir', methods=['POST'])
@login_required
def transferir(id):
    e = Equipo.query.get_or_404(id)
    nueva_ubicacion = request.form.get('donde', 'Sin Destino').strip() or "Sin Destino"
    ind_id = request.form.get('ind_id', type=int)
    
    # Ya no agregamos lugares automáticamente
    
    # Obtener el historial más reciente para saber de dónde viene
    if ind_id:
        # Para equipo individual
        ind = EquipoIndividual.query.get(ind_id)
        if not ind or not ind.en_uso:
            flash("El equipo no está en uso.", "error")
            return redirect(request.referrer or url_for('index'))
        
        antigua_ubicacion = ind.ubicacion_actual
        ind.ubicacion_actual = nueva_ubicacion
        
        nuevo_h = Historial(
            equipo_id=id,
            tipo='TRANSFERENCIA',
            usuario=nueva_ubicacion,
            cantidad=1,
            observaciones=f"Transferido desde {antigua_ubicacion}. " + request.form.get('observaciones_movimiento', ''),
            equipo_individual_id=ind_id
        )
        db.session.add(nuevo_h)
    else:
        # Para equipo por lote
        try:
            cant = int(request.form.get('cant_lote') or 1)
        except ValueError:
            cant = 1
            
        if cant > e.cantidad_en_uso:
            flash(f"Error: Solo hay {e.cantidad_en_uso} en terreno.", "error")
            return redirect(request.referrer or url_for('index'))
            
        nuevo_h = Historial(
            equipo_id=id,
            tipo='TRANSFERENCIA',
            usuario=nueva_ubicacion,
            cantidad=cant,
            observaciones=f"Transferencia de lote. " + request.form.get('observaciones_movimiento', '')
        )
        db.session.add(nuevo_h)
        
    db.session.commit()
    flash(f"Transferencia a {nueva_ubicacion} registrada.", "info")
    return redirect(request.referrer or url_for('index'))

@app.route('/equipo/<int:id>/add_documento', methods=['POST'])
@login_required
def add_documento(id):
    e = Equipo.query.get_or_404(id)
    referencia = request.form.get('referencia', 'Documento sin nombre').strip()
    if not referencia:
        referencia = 'Documento sin nombre'
    
    if 'documento' in request.files:
        file = request.files['documento']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"doc_{e.id}_{int(datetime.now().timestamp())}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            nuevo_doc = Documento(equipo_id=id, filename=filename, nombre_referencial=referencia)
            db.session.add(nuevo_doc)
            db.session.commit()
            flash(f"Documento '{referencia}' agregado correctamente.", "success")
        else:
            flash("Archivo no válido o no seleccionado.", "error")
    
    return redirect(url_for('detalle_equipo', id=id))

@app.route('/documento/delete/<int:doc_id>', methods=['POST'])
@login_required
def delete_documento(doc_id):
    doc = Documento.query.get_or_404(doc_id)
    equipo_id = doc.equipo_id
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], doc.filename))
    except (FileNotFoundError, TypeError):
        pass # Si el archivo no existe, solo lo borramos de la DB
    
    db.session.delete(doc)
    db.session.commit()
    flash("Documento eliminado.", "success")
    return redirect(url_for('detalle_equipo', id=equipo_id))

@app.route('/equipo/<int:id>/add_compatibilidad', methods=['POST'])
@login_required
def add_compatibilidad(id):
    e = Equipo.query.get_or_404(id)
    compatible_id = request.form.get('compatible_id')
    if compatible_id:
        compatible_item = Equipo.query.get(compatible_id)
        if compatible_item and compatible_item not in e.compatibles:
            e.compatibles.append(compatible_item)
            db.session.commit()
            flash(f"Compatibilidad con {compatible_item.nombre} agregada.", "success")
    return redirect(url_for('detalle_equipo', id=id))

@app.route('/equipo/<int:id>/remove_compatibilidad/<int:comp_id>', methods=['POST'])
@login_required
def remove_compatibilidad(id, comp_id):
    e = Equipo.query.get_or_404(id)
    compatible_item = Equipo.query.get(comp_id)
    if compatible_item and compatible_item in e.compatibles:
        e.compatibles.remove(compatible_item)
        db.session.commit()
        flash(f"Compatibilidad con {compatible_item.nombre} eliminada.", "success")
    return redirect(url_for('detalle_equipo', id=id))

@app.route('/add', methods=['POST'])
@login_required
def add():
    nuevo = Equipo(
        nombre=request.form.get('nom'),
        marca=request.form.get('mar'),
        categoria=request.form.get('cat'),
        cantidad_total=int(request.form.get('can') or 1),
        fecha_ingreso=datetime.now().strftime("%Y-%m-%d")
    )
    db.session.add(nuevo)
    if nuevo.categoria == "Luminarias":
        nuevo.gestion_individual = True
    db.session.commit()
    flash(f"Equipo {nuevo.nombre} añadido al inventario.", "success")
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    equipo = Equipo.query.get(id)
    if equipo:
        nombre = equipo.nombre
        db.session.delete(equipo)
        db.session.commit()
        flash(f"Equipo {nombre} eliminado.", "error")
    return redirect(url_for('index'))

@app.route('/exportar')
@login_required
def exportar_excel():
    equipos = Equipo.query.all()
    data = []
    for e in equipos:
        data.append({
            "ID": e.id,
            "Nombre": e.nombre,
            "Marca": e.marca,
            "Categoría": e.categoria,
            "Total": e.cantidad_total,
            "En Uso": e.cantidad_en_uso,
            "Disponible": e.cantidad_disponible,
            "Fecha Ingreso": e.fecha_ingreso
        })
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario')
    output.seek(0)
    
    return Response(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-disposition": "attachment; filename=Inventario_Bodega.xlsx"}
    )

@app.route('/exportar_movimientos')
@login_required
def exportar_movimientos():
    ahora = datetime.now()
    # Historial del mes actual
    registros = Historial.query.filter(
        db.extract('month', Historial.fecha) == ahora.month,
        db.extract('year', Historial.fecha) == ahora.year
    ).all()
    
    data = []
    for h in registros:
        data.append({
            "Fecha": h.fecha.strftime("%Y-%m-%d %H:%M"),
            "Equipo": h.equipo.nombre if h.equipo else "Unknown",
            "Tipo": h.tipo,
            "Cantidad": h.cantidad,
            "Usuario": h.usuario,
            "Estado Retorno": h.estado_al_retorno if h.tipo == 'RETORNO' else "-",
            "Observaciones": h.observaciones
        })
    
    df = pd.DataFrame(data)
    csv_data = df.to_csv(index=False, encoding='utf-8-sig')
    
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=Movimientos_{ahora.strftime('%Y_%m')}.csv"}
    )

@app.route('/historial')
@login_required
def mostrar_historial():
    registros = Historial.query.order_by(Historial.id.desc()).all()
    return render_template('historial.html', registros=registros)

@app.route('/buscar')
@login_required
def buscar():
    equipos = Equipo.query.order_by(Equipo.nombre.asc()).all()
    # Obtener lista de lugares de la tabla Lugar
    lugares = Lugar.query.order_by(Lugar.nombre).all()
    ubicaciones = [l.nombre for l in lugares]
    return render_template('buscar.html', equipos=equipos, categorias=CATEGORIAS, ubicaciones=ubicaciones)


@app.route('/luminarias')
@login_required
def luminarias():
    equipos = Equipo.query.filter_by(categoria='Luminarias').order_by(Equipo.nombre.asc()).all()
    return render_template('luminarias.html', equipos=equipos)

# --- RUTAS DE REPUESTOS ---

@app.route('/repuestos')
@login_required
def repuestos():
    lista_repuestos = Repuesto.query.order_by(Repuesto.nombre.asc()).all()
    return render_template('repuestos.html', repuestos=lista_repuestos, categorias=CATEGORIAS_REPUESTOS)

@app.route('/repuesto/<int:id>')
@login_required
def detalle_repuesto(id):
    r = Repuesto.query.get_or_404(id)
    # Lista de equipos para vincular (excluyendo los ya vinculados)
    equipos_disponibles = Equipo.query.order_by(Equipo.nombre).all()
    # En producción real, filtraríamos mejor, pero por ahora mostramos todos para seleccionar
    return render_template('detalle_repuesto.html', r=r, categorias=CATEGORIAS_REPUESTOS, equipos=equipos_disponibles)

@app.route('/repuesto/add', methods=['POST'])
@login_required
def add_repuesto():
    nuevo = Repuesto(
        nombre=request.form.get('nombre'),
        categoria=request.form.get('categoria'),
        cantidad=int(request.form.get('cantidad') or 1),
        equipo_asociado_texto=request.form.get('equipo_asociado_texto')
    )
    db.session.add(nuevo)
    db.session.commit()
    flash(f"Repuesto {nuevo.nombre} agregado.", "success")
    return redirect(url_for('repuestos'))

@app.route('/repuesto/<int:id>/update', methods=['POST'])
@login_required
def update_repuesto(id):
    r = Repuesto.query.get_or_404(id)
    r.nombre = request.form.get('nombre', r.nombre)
    r.categoria = request.form.get('categoria', r.categoria)
    r.equipo_asociado_texto = request.form.get('equipo_asociado_texto', r.equipo_asociado_texto)
    try:
        r.cantidad = int(request.form.get('cantidad', r.cantidad))
    except ValueError:
        pass
    
    db.session.commit()
    flash(f"Repuesto {r.nombre} actualizado.", "success")
    return redirect(url_for('detalle_repuesto', id=id))

@app.route('/repuesto/delete/<int:id>')
@login_required
def delete_repuesto(id):
    r = Repuesto.query.get_or_404(id)
    nombre = r.nombre
    db.session.delete(r)
    db.session.commit()
    flash(f"Repuesto {nombre} eliminado.", "warning")
    return redirect(url_for('repuestos'))

@app.route('/repuesto/<int:id>/link_equipo', methods=['POST'])
@login_required
def link_equipo_repuesto(id):
    r = Repuesto.query.get_or_404(id)
    equipo_id = request.form.get('equipo_id')
    if equipo_id:
        equipo = Equipo.query.get(equipo_id)
        if equipo and equipo not in r.equipos:
            r.equipos.append(equipo)
            db.session.commit()
            flash(f"Vinculado con {equipo.nombre}.", "success")
    return redirect(url_for('detalle_repuesto', id=id))

@app.route('/repuesto/<int:id>/unlink_equipo/<int:equipo_id>', methods=['POST'])
@login_required
def unlink_equipo_repuesto(id, equipo_id):
    r = Repuesto.query.get_or_404(id)
    equipo = Equipo.query.get(equipo_id)
    if equipo and equipo in r.equipos:
        r.equipos.remove(equipo)
        db.session.commit()
        flash(f"Desvinculado de {equipo.nombre}.", "success")
    return redirect(url_for('detalle_repuesto', id=id))

# --- RUTAS DE GESTIÓN INDIVIDUAL ---

@app.route('/equipo/<int:id>/individuales')
@login_required
def gestion_individual(id):
    """Vista principal de gestión de equipos individuales"""
    equipo_grupo = Equipo.query.get_or_404(id)
    
    if not equipo_grupo.gestion_individual:
        flash("Este equipo no requiere gestión individual.", "warning")
        return redirect(url_for('detalle_equipo', id=id))
    
    # Obtener filtros
    filtro = request.args.get('filtro', 'todos')
    
    # Query base
    query = EquipoIndividual.query.filter_by(equipo_grupo_id=id)
    
    # Aplicar filtros
    if filtro == 'disponibles':
        query = query.filter_by(en_uso=False, danado=False)
    elif filtro == 'en_uso':
        query = query.filter_by(en_uso=True)
    elif filtro == 'danados':
        query = query.filter_by(danado=True)
    
    equipos_ind = query.order_by(EquipoIndividual.numero_fixture).all()
    
    # Estadísticas
    total = len(equipo_grupo.equipos_individuales)
    disponibles = sum(1 for e in equipo_grupo.equipos_individuales if not e.en_uso and not e.danado)
    en_uso = sum(1 for e in equipo_grupo.equipos_individuales if e.en_uso)
    danados = sum(1 for e in equipo_grupo.equipos_individuales if e.danado)
    
    # Obtener lugares para el datalist
    lugares = Lugar.query.order_by(Lugar.nombre).all()
    ubicaciones = [l.nombre for l in lugares]

    return render_template('gestion_individual.html', 
                         equipo_grupo=equipo_grupo,
                         equipos_ind=equipos_ind,
                         filtro=filtro,
                         stats={'total': total, 'disponibles': disponibles, 'en_uso': en_uso, 'danados': danados},
                         ubicaciones=ubicaciones)

@app.route('/equipo/<int:id>/individual/add', methods=['POST'])
@login_required
def add_individual(id):
    """Agregar un equipo individual manualmente"""
    equipo_grupo = Equipo.query.get_or_404(id)
    
    numero_serie = request.form.get('numero_serie', '').strip()
    numero_fixture = request.form.get('numero_fixture', type=int)
    
    if not numero_serie:
        flash("El número de serie es obligatorio.", "error")
        return redirect(url_for('gestion_individual', id=id))
    
    # Verificar que no exista
    existe = EquipoIndividual.query.filter_by(
        equipo_grupo_id=id,
        numero_serie=numero_serie
    ).first()
    
    if existe:
        flash(f"Ya existe un equipo con el número de serie {numero_serie}.", "error")
        return redirect(url_for('gestion_individual', id=id))
    
    nuevo = EquipoIndividual(
        equipo_grupo_id=id,
        numero_serie=numero_serie,
        numero_fixture=numero_fixture,
        fecha_ingreso=datetime.now().strftime("%Y-%m-%d")
    )
    
    db.session.add(nuevo)
    db.session.commit()
    flash(f"Equipo #{numero_fixture} agregado correctamente.", "success")
    return redirect(url_for('gestion_individual', id=id))

@app.route('/equipo/<int:id>/individual/<int:ind_id>/update', methods=['POST'])
@login_required
def update_individual(id, ind_id):
    """Actualizar un equipo individual"""
    equipo_ind = EquipoIndividual.query.get_or_404(ind_id)
    
    if equipo_ind.equipo_grupo_id != id:
        flash("Equipo no encontrado.", "error")
        return redirect(url_for('gestion_individual', id=id))
    
    equipo_ind.observaciones_individuales = request.form.get('observaciones', '')
    
    db.session.commit()
    flash(f"Equipo #{equipo_ind.numero_fixture} actualizado.", "success")
    return redirect(url_for('gestion_individual', id=id))

@app.route('/equipo/<int:id>/individual/<int:ind_id>/toggle_danado', methods=['POST'])
@login_required
def toggle_danado_individual(id, ind_id):
    """Marcar/desmarcar equipo individual como dañado"""
    equipo_ind = EquipoIndividual.query.get_or_404(ind_id)
    
    if equipo_ind.equipo_grupo_id != id:
        flash("Equipo no encontrado.", "error")
        return redirect(url_for('gestion_individual', id=id))
    
    equipo_ind.danado = not equipo_ind.danado
    db.session.commit()
    
    estado = "DAÑADO" if equipo_ind.danado else "OPERATIVO"
    
# --- RUTAS DE SINCRONIZACIÓN ---

@app.route('/exportar_sync', methods=['GET'])
def exportar_sync():
    """Exporta toda la base de datos en formato JSON"""
    try:
        data = {
            'equipos': [e.to_dict() for e in Equipo.query.all()],
            'equipos_individuales': [ei.to_dict() for ei in EquipoIndividual.query.all()],
            'historial': [h.to_dict() for h in Historial.query.all()],
            'lugares': [l.to_dict() for l in Lugar.query.all()],
            'stock_lugares': [s.to_dict() for s in StockLugar.query.all()],
            'repuestos': [r.to_dict() for r in Repuesto.query.all()],
            'documentos': [d.to_dict() for d in Documento.query.all()]
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

from flask import jsonify 

@app.route('/import_sync', methods=['POST'])
def import_sync():
    """Importa datos JSON y los fusiona con la base de datos local"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # 1. Lugares (Prioridad baja, pero necesario para StockLugar)
        for item in data.get('lugares', []):
            l = Lugar.query.get(item['id'])
            if not l:
                l = Lugar(id=item['id'])
            l.nombre = item['nombre']
            db.session.merge(l)
            
        # 2. Equipos (Prioridad Alta)
        for item in data.get('equipos', []):
            e = Equipo.query.get(item['id'])
            if not e:
                e = Equipo(id=item['id'])
            
            e.nombre = item.get('nombre')
            e.categoria = item.get('categoria')
            e.marca = item.get('marca')
            e.cantidad_total = item.get('cantidad_total')
            e.cantidad_en_uso = item.get('cantidad_en_uso')
            e.fecha_ingreso = item.get('fecha_ingreso')
            e.observaciones = item.get('observaciones')
            e.danado = item.get('danado')
            e.manual_filename = item.get('manual_filename')
            e.gestion_individual = item.get('gestion_individual')

            
            db.session.merge(e)
        
        # 3. Equipos Individuales
        for item in data.get('equipos_individuales', []):
            ei = EquipoIndividual.query.get(item['id'])
            if not ei:
                ei = EquipoIndividual(id=item['id'])
            
            ei.equipo_grupo_id = item.get('equipo_grupo_id')
            ei.numero_serie = item.get('numero_serie')
            ei.numero_fixture = item.get('numero_fixture')
            ei.danado = item.get('danado')
            ei.observaciones_individuales = item.get('observaciones_individuales')
            ei.fecha_ingreso = item.get('fecha_ingreso')
            ei.en_uso = item.get('en_uso')
            ei.ubicacion_actual = item.get('ubicacion_actual')

            
            db.session.merge(ei)

        # 4. Historial
        for item in data.get('historial', []):
            h = Historial.query.get(item['id'])
            if not h:
                h = Historial(id=item['id'])
            
            h.equipo_id = item.get('equipo_id')
            h.tipo = item.get('tipo')
            h.usuario = item.get('usuario')
            h.cantidad = item.get('cantidad')
            h.observaciones = item.get('observaciones')
            h.estado_al_retorno = item.get('estado_al_retorno')
            # Convertir string ISO a datetime si es necesario, 
            # pero SQLite suele manejar strings. Si 'fecha' es DateTime en modelo 
            # y recibimos ISO string, hay que parsear.
            if item.get('fecha'):
                try:
                    h.fecha = datetime.fromisoformat(item.get('fecha'))

                except ValueError:
                    pass # Keep original or handle error if needed
            
            h.equipo_individual_id = item.get('equipo_individual_id')

            
            db.session.merge(h)
            
        # 5. Repuestos
        for item in data.get('repuestos', []):
            r = Repuesto.query.get(item['id'])
            if not r:
                r = Repuesto(id=item['id'])
            
            r.nombre = item.get('nombre')
            r.marca = item.get('marca')
            r.categoria = item.get('categoria')
            r.cantidad = item.get('cantidad')
            r.equipo_asociado_texto = item.get('equipo_asociado_texto')

            
            db.session.merge(r)

        # 6. Documentos
        for item in data.get('documentos', []):
            d = Documento.query.get(item['id'])
            if not d:
                d = Documento(id=item['id'])
            
            d.equipo_id = item.get('equipo_id')
            d.filename = item.get('filename')
            d.nombre_referencial = item.get('nombre_referencial')

            
            db.session.merge(d)

        # 7. StockLugar
        for item in data.get('stock_lugares', []):
            s = StockLugar.query.get(item['id'])
            if not s:
                s = StockLugar(id=item['id'])
                
            s.equipo_id = item.get('equipo_id')
            s.lugar_id = item.get('lugar_id')
            s.cantidad = item.get('cantidad')

            
            db.session.merge(s)
            
        db.session.commit()
        
        # Trigger Backup
        try:
            respaldar_en_github()
        except Exception as e:
            print(f"Backup warning: {e}")
            
        return jsonify({'status': 'success', 'message': 'Sincronización completada y respaldo iniciado.'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/sincronizar')
@login_required
def sincronizar_ui():
    """Interfaz gráfica para la sincronización"""
    return render_template('sincronizar.html')

    flash(f"Equipo #{equipo_ind.numero_fixture} marcado como {estado}.", "success")
    return redirect(url_for('gestion_individual', id=id))

@app.route('/equipo/<int:id>/individual/<int:ind_id>/delete', methods=['POST'])
@login_required
def delete_individual(id, ind_id):
    """Eliminar un equipo individual"""
    equipo_ind = EquipoIndividual.query.get_or_404(ind_id)
    
    if equipo_ind.equipo_grupo_id != id:
        flash("Equipo no encontrado.", "error")
        return redirect(url_for('gestion_individual', id=id))
    
    numero = equipo_ind.numero_fixture
    db.session.delete(equipo_ind)
    db.session.commit()
    flash(f"Equipo #{numero} eliminado.", "warning")
    return redirect(url_for('gestion_individual', id=id))

# --- RUTAS DE LUGARES ---

@app.route('/lugares', methods=['GET', 'POST'])
@login_required
def gestionar_lugares():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        if nombre:
            # Verificar si ya existe
            existe = Lugar.query.filter(db.func.lower(Lugar.nombre) == nombre.lower()).first()
            if not existe:
                nuevo = Lugar(nombre=nombre)
                db.session.add(nuevo)
                db.session.commit()
                flash(f"Lugar '{nombre}' agregado correctamente.", "success")
            else:
                flash(f"El lugar '{nombre}' ya existe.", "warning")
        return redirect(url_for('gestionar_lugares'))

    lugares = Lugar.query.order_by(Lugar.nombre).all()
    return render_template('lugares.html', lugares=lugares)

@app.route('/lugar/delete/<int:id>', methods=['POST'])
@login_required
def delete_lugar(id):
    lugar = Lugar.query.get_or_404(id)
    nombre = lugar.nombre
    
    # Opcional: Verificar si hay equipos en este lugar antes de borrar?
    # El usuario pidió borrar "CASA TEMATICA" porque no tiene contenido.
    
    db.session.delete(lugar)
    db.session.commit()
    flash(f"Lugar '{nombre}' eliminado correctamente.", "success")
    return redirect(url_for('gestionar_lugares'))

@app.route('/equipo/<int:id>/asignar_stock', methods=['POST'])
@login_required
def asignar_stock_lugar(id):
    equipo = Equipo.query.get_or_404(id)
    lugar_id = request.form.get('lugar_id', type=int)
    try:
        cantidad = int(request.form.get('cantidad', 0))
    except ValueError:
        cantidad = 0
        
    if not lugar_id:
        flash("Debe seleccionar un lugar.", "error")
        return redirect(url_for('detalle_equipo', id=id))

    # Buscar si ya existe asignación para este equipo en este lugar
    stock = StockLugar.query.filter_by(equipo_id=id, lugar_id=lugar_id).first()
    
    if stock:
        stock.cantidad = cantidad
    else:
        stock = StockLugar(equipo_id=id, lugar_id=lugar_id, cantidad=cantidad)
        db.session.add(stock)
        
    db.session.commit()
    flash(f"Stock actualizado para el lugar seleccionado.", "success")
    return redirect(url_for('detalle_equipo', id=id))

@app.route('/equipo/<int:id>/eliminar_stock/<int:stock_id>', methods=['POST'])
@login_required
def eliminar_stock_lugar(id, stock_id):
    stock = StockLugar.query.get_or_404(stock_id)
    if stock.equipo_id == id:
        db.session.delete(stock)
        db.session.commit()
        flash("Asignación de stock eliminada.", "success")
    return redirect(url_for('detalle_equipo', id=id))


if __name__ == '__main__':
    # Configuración para permitir acceso desde la red local
    app.run(debug=True, host='0.0.0.0', port=5000)
