from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import pandas as pd
from io import BytesIO
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "media_lighting_secret_key" # Necesario para mensajes Flash

# --- CONFIGURACIÓN ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'inventario.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'manuales')
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg'}

CATEGORIAS = ["Luminarias", "Grip", "Insumos", "Equipamiento Electrico"]

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
    manual_filename = db.Column(db.String(200))
    movimientos = db.relationship('Historial', backref='equipo', cascade="all, delete-orphan")

class Historial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipo.id'), nullable=False)
    tipo = db.Column(db.String(20)) 
    usuario = db.Column(db.String(100))
    cantidad = db.Column(db.Integer, default=1) 
    fecha = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    equipos = Equipo.query.order_by(Equipo.id.desc()).all()
    return render_template('index.html', equipos=equipos, categorias=CATEGORIAS)

@app.route('/equipo/<int:id>')
def detalle_equipo(id):
    e = Equipo.query.get_or_404(id)
    return render_template('detalle.html', e=e)

@app.route('/equipo/<int:id>/update', methods=['POST'])
def update_equipo(id):
    e = Equipo.query.get_or_404(id)
    e.observaciones = request.form.get('observaciones')
    if 'manual' in request.files:
        file = request.files['manual']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"manual_{e.id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            e.manual_filename = filename
    db.session.commit()
    flash(f"Ficha de {e.nombre} actualizada correctamente.", "success")
    return redirect(url_for('detalle_equipo', id=id))

@app.route('/download/<filename>')
def download_manual(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/movimiento/<int:id>/<tipo>', methods=['POST'])
def movimiento(id, tipo):
    e = Equipo.query.get(id)
    nombre_usuario = request.form.get('usuario') or "Sin Nombre"
    try:
        cant_lote = int(request.form.get('cant_lote') or 1)
    except ValueError:
        cant_lote = 1
    
    if tipo == 'prestar':
        disponible = e.cantidad_total - e.cantidad_en_uso
        if cant_lote <= disponible: 
            e.cantidad_en_uso += cant_lote
            db.session.add(Historial(equipo_id=id, tipo='SALIDA', usuario=nombre_usuario, cantidad=cant_lote))
            flash(f"Salida registrada: {cant_lote} x {e.nombre}", "warning")
        else:
            flash("Error: Stock insuficiente para esta salida.", "error")
    elif tipo == 'devolver':
        if cant_lote <= e.cantidad_en_uso: 
            e.cantidad_en_uso -= cant_lote
            db.session.add(Historial(equipo_id=id, tipo='RETORNO', usuario=nombre_usuario, cantidad=cant_lote))
            flash(f"Retorno registrado: {cant_lote} x {e.nombre}", "success")
        else:
            flash("Error: No puedes retornar más de lo que está en uso.", "error")
    db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/add', methods=['POST'])
def add():
    nuevo = Equipo(
        nombre=request.form.get('nom'),
        marca=request.form.get('mar'),
        categoria=request.form.get('cat'),
        cantidad_total=int(request.form.get('can') or 1),
        fecha_ingreso=datetime.now().strftime("%Y-%m-%d")
    )
    db.session.add(nuevo)
    db.session.commit()
    flash(f"Equipo {nuevo.nombre} añadido al inventario.", "success")
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    equipo = Equipo.query.get(id)
    if equipo:
        nombre = equipo.nombre
        db.session.delete(equipo)
        db.session.commit()
        flash(f"Equipo {nombre} eliminado.", "error")
    return redirect(url_for('index'))

@app.route('/exportar')
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
            "Disponible": e.cantidad_total - e.cantidad_en_uso,
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

@app.route('/historial')
def mostrar_historial():
    registros = Historial.query.order_by(Historial.id.desc()).all()
    return render_template('historial.html', registros=registros)

@app.route('/buscar')
def buscar():
    equipos = Equipo.query.all()
    return render_template('buscar.html', equipos=equipos)

if __name__ == '__main__':
    app.run(debug=True, port=5001)