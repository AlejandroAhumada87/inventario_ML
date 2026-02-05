from app import app, db, Equipo, Documento
import os

def clean_data():
    with app.app_context():
        # Limpiar referencias en Equipo
        equipos = Equipo.query.all()
        for e in equipos:
            e.manual_filename = None
        
        # Eliminar todos los registros de documentos adicionales
        Documento.query.delete()
        
        db.session.commit()
        print("Base de datos actualizada: referencias a manuales y documentos eliminadas.")

if __name__ == "__main__":
    clean_data()
