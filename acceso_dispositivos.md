# 📱 Guía para usar Inventario ML en múltiples dispositivos

Para que tu aplicación de inventario sea accesible desde otros computadores y teléfonos, tienes dos opciones principales:
1. **Acceder de forma remota**: La app corre en tu Chromebook y la usas desde tu teléfono u otro PC (Ideal para el día a día).
2. **Correr la app nativamente en Windows**: Instalar todo en el PC con Windows para que funcione de forma independiente.

---

## 1. Acceso Remoto desde Android, iPhone o Windows (Misma Red) 🌐

Como estás en una **Chromebook**, el sistema funciona dentro de un "contenedor" Linux, por lo que necesitamos decirle a la Chromebook que deje pasar las conexiones externas hacia la app.

### Paso A: Configurar el Puerto en Chromebook
1. Ve a la **Configuración** de tu Chromebook.
2. Busca **Avanzado** > **Desarrolladores** > **Entorno de desarrollo Linux**.
3. Haz clic en **Reenvío de puertos** (Port Forwarding).
4. Haz clic en **Agregar**.
   - **Protocolo**: TCP
   - **Puerto**: 5000
   - **Etiqueta**: APP INVENTARIO
5. Asegúrate de que el interruptor esté en **ON**.

### Paso B: Encontrar tu dirección IP
1. En tu Chromebook, haz clic en la hora (abajo a la derecha) y luego en el icono de **Wi-Fi**.
2. Haz clic en el nombre de tu red Wi-Fi actual.
3. Busca donde dice **Dirección IP** (ejemplo: `192.168.1.15`). *Anótala.*

### Paso C: Conectar desde el Celular o Windows
1. Conecta tu teléfono (Android/iPhone) o el otro PC a la **misma red Wi-Fi**.
2. Abre el navegador (Chrome, Safari, etc.).
3. En la barra de direcciones escribe la IP que anotaste seguida de `:5000`.
   - Ejemplo: `http://192.168.1.15:5000`
4. ¡Listo! Ya puedes gestionar tu inventario desde cualquier parte de la bodega.

---

## 2. Cómo instalar y correr la app en Windows (Nativo) 💻

Si quieres que la aplicación viva en el PC con Windows directamente:

### Requisitos previos
1. Descarga e instala **Python** desde [python.org](https://www.python.org/downloads/). (Marca la casilla que dice **"Add Python to PATH"** durante la instalación).
2. Copia la carpeta de tu proyecto `inventario_ML` al PC con Windows.

### Iniciar la aplicación
1. Abre la carpeta del proyecto en Windows.
2. Haz clic derecho en un espacio vacío y selecciona **"Abrir en Terminal"** (o busca `cmd` en esa carpeta).
3. Instala las librerías necesarias con este comando:
   ```cmd
   pip install flask flask-sqlalchemy pandas openpyxl xlsxwriter
   ```
4. Corre la aplicación:
   ```cmd
   python app.py
   ```
5. La app estará disponible en ese PC en `http://localhost:5000`.

---

## 💡 Tips para el Teléfono
- **Acceso Directo:** En iPhone (Safari) o Android (Chrome), puedes seleccionar "Agregar a la pantalla de inicio" para que la app se vea como una aplicación nativa en tu menú.
- **Lector de barras:** Si alguna vez decides agregar códigos de barra, al usarlo desde el teléfono podrás usar la cámara para escanear directamente desde el navegador.

---
> [!IMPORTANT]
> Para que el acceso remoto funcione, **la aplicación debe estar corriendo en la Chromebook** (el terminal donde haces `python app.py` debe estar abierto).
