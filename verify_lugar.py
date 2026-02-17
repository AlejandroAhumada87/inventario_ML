from app import app, db, Lugar
import os

def test_lugar_management():
    with app.app_context():
        # Ensure the DB is initialized and seeded
        db.create_all()
        
        # Check if default locations are seeded
        lugares = Lugar.query.all()
        nombres = [l.nombre for l in lugares]
        print(f"Lugares en la DB: {nombres}")
        
        expected = ["CASA VIP", "CASA SERVICIO", "CASA TEMÁTICA", "CASA PRECARIA"]
        for e in expected:
            if e in nombres:
                print(f"✓ {e} encontrado.")
            else:
                print(f"✗ {e} NO encontrado.")

                
        # Test adding a new location
        new_name = "TEST LOCATION"
        if new_name not in nombres:
            nl = Lugar(nombre=new_name)
            db.session.add(nl)
            db.session.commit()
            print(f"✓ Agregado: {new_name}")
            
        # Verify it's there
        if Lugar.query.filter_by(nombre=new_name).first():
            print(f"✓ Verificado: {new_name} está en la DB.")
            
if __name__ == "__main__":
    test_lugar_management()
