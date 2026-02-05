"""
Script para importar equipos individuales desde el Excel de numeración
Excluye: Bowen Projection
Alien 150c: Solo equipos indexados (con ID asignado)
"""
from app import app, db, Equipo, EquipoIndividual
import pandas as pd
from datetime import datetime

# Mapeo de hojas del Excel a nombres de equipos en la DB
MAPEO_EQUIPOS = {
    'Eastman ParLed': 'ParLed Ignite 18 Slim',
    'Eastman ParLedWP': 'ParLed Ignite 18 Slim WP',
    'Forza 500B II': 'Forza 500B II Bi-Color LED',
    'Forza720': 'Forza 720B Bi-Color LED',
    'Forza 60B': 'Forza 60B II Bi-Color LED',
    'Alien 300': 'Alien 300C RGB LED',
    'Alien 150c': 'Alien 150C RGB LED'
}

def importar_equipos():
    """Importa todos los equipos desde el Excel"""
    excel_path = 'static/Numeracion de Equipos Nuevos.xlsx'
    xls = pd.ExcelFile(excel_path)
    
    total_importados = 0
    errores = []
    
    with app.app_context():
        for sheet_name in xls.sheet_names:
            # Excluir Bowen Projection
            if sheet_name == 'Bowen Projection':
                print(f"⏭️  Saltando {sheet_name} (excluido por usuario)")
                continue
                
            if sheet_name not in MAPEO_EQUIPOS:
                print(f"⚠️  Hoja '{sheet_name}' no mapeada, saltando...")
                continue
            
            equipo_nombre = MAPEO_EQUIPOS[sheet_name]
            print(f"\n📦 Procesando: {sheet_name} → {equipo_nombre}")
            
            # Buscar el grupo en la base de datos
            equipo_grupo = Equipo.query.filter_by(nombre=equipo_nombre).first()
            
            if not equipo_grupo:
                error_msg = f"❌ Equipo '{equipo_nombre}' no encontrado en la base de datos"
                print(error_msg)
                errores.append(error_msg)
                continue
            
            # Marcar para gestión individual
            equipo_grupo.gestion_individual = True
            
            # Leer la hoja
            df = pd.read_excel(xls, sheet_name)
            
            # Procesar según la estructura de cada hoja
            try:
                if sheet_name in ['Eastman ParLed', 'Eastman ParLedWP']:
                    importados = importar_eastman(df, equipo_grupo, sheet_name)
                elif sheet_name == 'Forza 500B II':
                    importados = importar_forza_500(df, equipo_grupo)
                elif sheet_name == 'Forza720':
                    importados = importar_forza_720(df, equipo_grupo)
                elif sheet_name == 'Forza 60B':
                    importados = importar_forza_60(df, equipo_grupo)
                elif sheet_name == 'Alien 300':
                    importados = importar_alien_300(df, equipo_grupo)
                elif sheet_name == 'Alien 150c':
                    importados = importar_alien_150(df, equipo_grupo)
                else:
                    importados = 0
                
                total_importados += importados
                print(f"   ✅ {importados} equipos importados")
                
            except Exception as e:
                error_msg = f"❌ Error procesando {sheet_name}: {str(e)}"
                print(error_msg)
                errores.append(error_msg)
        
        # Commit de todos los cambios
        db.session.commit()
        
        print(f"\n{'='*60}")
        print(f"✨ IMPORTACIÓN COMPLETADA")
        print(f"{'='*60}")
        print(f"Total equipos importados: {total_importados}")
        
        if errores:
            print(f"\n⚠️  Errores encontrados ({len(errores)}):")
            for error in errores:
                print(f"   {error}")

def importar_eastman(df, equipo_grupo, tipo):
    """Importa equipos Eastman ParLed y ParLedWP"""
    count = 0
    for _, row in df.iterrows():
        fixture_num = int(row['Fixture N°'])
        serial_id = str(int(row['Serial ID']))
        
        # Verificar si ya existe
        existe = EquipoIndividual.query.filter_by(
            equipo_grupo_id=equipo_grupo.id,
            numero_serie=serial_id
        ).first()
        
        if not existe:
            nuevo = EquipoIndividual(
                equipo_grupo_id=equipo_grupo.id,
                numero_serie=serial_id,
                numero_fixture=fixture_num,
                fecha_ingreso=datetime.now().strftime("%Y-%m-%d")
            )
            db.session.add(nuevo)
            count += 1
    
    return count

def importar_forza_500(df, equipo_grupo):
    """Importa equipos Forza 500B II"""
    count = 0
    for _, row in df.iterrows():
        fixture_id = int(row['ID'])
        serial = str(int(row['Código de Serie']))
        
        existe = EquipoIndividual.query.filter_by(
            equipo_grupo_id=equipo_grupo.id,
            numero_serie=serial
        ).first()
        
        if not existe:
            nuevo = EquipoIndividual(
                equipo_grupo_id=equipo_grupo.id,
                numero_serie=serial,
                numero_fixture=fixture_id,
                fecha_ingreso=datetime.now().strftime("%Y-%m-%d")
            )
            db.session.add(nuevo)
            count += 1
    
    return count

def importar_forza_720(df, equipo_grupo):
    """Importa equipos Forza 720"""
    count = 0
    for _, row in df.iterrows():
        fixture_num = int(row['# Forza'])
        serial = str(int(row['Número de Serie']))
        
        existe = EquipoIndividual.query.filter_by(
            equipo_grupo_id=equipo_grupo.id,
            numero_serie=serial
        ).first()
        
        if not existe:
            nuevo = EquipoIndividual(
                equipo_grupo_id=equipo_grupo.id,
                numero_serie=serial,
                numero_fixture=fixture_num,
                fecha_ingreso=datetime.now().strftime("%Y-%m-%d")
            )
            db.session.add(nuevo)
            count += 1
    
    return count

def importar_forza_60(df, equipo_grupo):
    """Importa equipos Forza 60B"""
    count = 0
    for _, row in df.iterrows():
        fixture_num = int(row['Ítem'])
        serial = str(row['Número de Identificación / Serie'])
        
        existe = EquipoIndividual.query.filter_by(
            equipo_grupo_id=equipo_grupo.id,
            numero_serie=serial
        ).first()
        
        if not existe:
            nuevo = EquipoIndividual(
                equipo_grupo_id=equipo_grupo.id,
                numero_serie=serial,
                numero_fixture=fixture_num,
                fecha_ingreso=datetime.now().strftime("%Y-%m-%d")
            )
            db.session.add(nuevo)
            count += 1
    
    return count

def importar_alien_300(df, equipo_grupo):
    """Importa equipos Alien 300"""
    count = 0
    for _, row in df.iterrows():
        fixture_id = int(row['ID de Equipo'])
        serial = str(int(row['Número de Serie']))
        
        existe = EquipoIndividual.query.filter_by(
            equipo_grupo_id=equipo_grupo.id,
            numero_serie=serial
        ).first()
        
        if not existe:
            nuevo = EquipoIndividual(
                equipo_grupo_id=equipo_grupo.id,
                numero_serie=serial,
                numero_fixture=fixture_id,
                fecha_ingreso=datetime.now().strftime("%Y-%m-%d")
            )
            db.session.add(nuevo)
            count += 1
    
    return count

def importar_alien_150(df, equipo_grupo):
    """Importa equipos Alien 150c - SOLO LOS INDEXADOS"""
    count = 0
    # Filtrar solo los que tienen ID asignado
    df_indexados = df[df['ID'].notna()]
    
    for _, row in df_indexados.iterrows():
        fixture_id = int(row['ID'])
        serial = str(int(row['Número de Serie Completo']))
        
        # Observaciones si existen
        obs = ""
        if pd.notna(row.get('Observación Técnica')):
            obs = str(row['Observación Técnica'])
        
        existe = EquipoIndividual.query.filter_by(
            equipo_grupo_id=equipo_grupo.id,
            numero_serie=serial
        ).first()
        
        if not existe:
            nuevo = EquipoIndividual(
                equipo_grupo_id=equipo_grupo.id,
                numero_serie=serial,
                numero_fixture=fixture_id,
                observaciones_individuales=obs,
                fecha_ingreso=datetime.now().strftime("%Y-%m-%d")
            )
            db.session.add(nuevo)
            count += 1
    
    return count

if __name__ == '__main__':
    print("🚀 Iniciando importación de equipos individuales...")
    print("="*60)
    importar_equipos()
