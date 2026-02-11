# Sistema de Inventario ML Producciones

Aplicación web para gestión de inventario de equipos de iluminación y producción audiovisual.

## Características

- 🔐 Sistema de autenticación (usuario: MLProducciones)
- 📦 Gestión de inventario de equipos
- 💡 Gestión individual de luminarias
- 📊 Exportación de datos a Excel
- 📝 Historial de movimientos
- 🔧 Gestión de repuestos
- 📄 Almacenamiento de manuales y documentos

## Despliegue en Render

La aplicación está configurada para desplegarse automáticamente en Render.

### Pasos para desplegar:

1. **Push al repositorio GitHub**
   ```bash
   git add .
   git commit -m "Configuración para deployment en Render"
   git push origin main
   ```

2. **Crear servicio en Render**
   - Ve a [render.com](https://render.com) y crea una cuenta
   - Click en "New +" → "Web Service"
   - Conecta tu repositorio de GitHub
   - Render detectará automáticamente el archivo `render.yaml`
   - Click en "Create Web Service"

3. **Configurar disco persistente** (importante para mantener la base de datos)
   - En el dashboard del servicio, ve a "Disks"
   - Verifica que el disco `inventario-data` esté montado en `/var/data`

4. **Acceder a la aplicación**
   - Render te proporcionará una URL como: `https://inventario-ml.onrender.com`
   - Usuario: `MLProducciones` (acepta mayúsculas/minúsculas)
   - Contraseña: `admin123`

## Desarrollo Local

### Requisitos
- Python 3.11+
- pip

### Instalación

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/AlejandroAhumada87/inventario_ML.git
   cd inventario_ML
   ```

2. Crear entorno virtual:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Ejecutar la aplicación:
   ```bash
   python app.py
   ```

5. Abrir en el navegador:
   ```
   http://localhost:5000
   ```

## Tecnologías Utilizadas

- **Backend**: Flask 3.1.2
- **Base de Datos**: SQLite con SQLAlchemy
- **Frontend**: HTML, CSS, JavaScript
- **Deployment**: Render (con Gunicorn)
- **Exportación**: Pandas, XlsxWriter

## Estructura del Proyecto

```
inventario_ML/
├── app.py                 # Aplicación principal Flask
├── inventario.db          # Base de datos SQLite
├── requirements.txt       # Dependencias Python
├── render.yaml           # Configuración de Render
├── templates/            # Plantillas HTML
├── static/              # Archivos estáticos (CSS, JS, imágenes)
├── manuales/            # Documentos y manuales subidos
└── backups/             # Backups automáticos de la BD
```

## Licencia

Proyecto privado - ML Producciones © 2026
