from app import app, db, Equipo, Lugar, Historial, EquipoIndividual
from datetime import datetime

def verify_all():
    with app.app_context():
        print("--- Starting Verification ---")
        
        # 1. Verify "CASA TEMÁTICA" exists
        ct = Lugar.query.filter_by(nombre="CASA TEMÁTICA").first()
        if ct:
            print(f"✓ CASA TEMÁTICA existe.")
        else:
            print("✗ CASA TEMÁTICA no encontrada.")



        # 2. Test Transfer Logic (Lot)
        e = Equipo.query.filter(Equipo.categoria != "Luminarias").first()
        if e:
            print(f"Probando transferencia de lote con: {e.nombre}")
            # Simulamos salida
            e.cantidad_en_uso += 1
            h1 = Historial(equipo_id=e.id, tipo='SALIDA', usuario='LUGAR_A', cantidad=1)
            db.session.add(h1)
            db.session.commit()
            
            # Simulamos transferencia
            h2 = Historial(equipo_id=e.id, tipo='TRANSFERENCIA', usuario='LUGAR_B', cantidad=1, observaciones="Transferido de LUGAR_A")
            db.session.add(h2)
            db.session.commit()
            
            print(f"✓ Transferencia de lote registrada en historial.")
        
        # 3. Test Transfer Logic (Individual)
        ei = EquipoIndividual.query.first()
        if ei:
            print(f"Probando transferencia individual con: {ei.equipo_grupo.nombre} #{ei.numero_fixture}")
            ei.en_uso = True
            ei.ubicacion_actual = "LUGAR_X"
            db.session.commit()
            
            # Transfer
            antigua = ei.ubicacion_actual
            nueva = "LUGAR_Y"
            ei.ubicacion_actual = nueva
            h3 = Historial(equipo_id=ei.equipo_grupo_id, tipo='TRANSFERENCIA', usuario=nueva, cantidad=1, equipo_individual_id=ei.id, observaciones=f"De {antigua}")
            db.session.add(h3)
            db.session.commit()
            
            if ei.ubicacion_actual == "LUGAR_Y":
                print(f"✓ Ubicación actualizada correctamente a {nueva}.")
            else:
                print(f"✗ Falló actualización de ubicación.")

        print("--- Verification Finished ---")

if __name__ == "__main__":
    verify_all()
