# Susurros del Dragón v15

Aplicación web Flask con catálogo, panel administrativo, base de datos y carga de imágenes.

## Seguridad antes de desplegar

La aplicación lee los valores sensibles desde variables de entorno. Configura `SECRET_KEY`, `ADMIN_USER` y `ADMIN_PASS` en el entorno donde alojes la app. No subas `.env`, la base de datos ni imágenes de usuarios.

En producción usa HTTPS y configura `SESSION_COOKIE_SECURE=true`. La aplicación falla al iniciar si no encuentra `SECRET_KEY`; el inicio de sesión administrativo queda deshabilitado si falta `ADMIN_USER` o `ADMIN_PASS`.

## Ejecutar localmente

1. Instala Python y las dependencias con `pip install -r requirements.txt`.
2. Define las variables de entorno indicadas en `.env.example` en tu terminal.
3. Ejecuta `python app.py` y abre `http://127.0.0.1:5000`.

## Publicación

Esta app necesita un servidor Python para atender Flask y las rutas `/api/...`. GitHub Pages publica archivos estáticos HTML, CSS y JavaScript; no ejecuta este backend. Para conservar el panel, el inicio de sesión, los datos y las cargas de imágenes, despliega Flask en un servicio que admita aplicaciones Python y configura almacenamiento persistente para la base de datos y `static/uploads`.

Si publicas solo el frontend en GitHub Pages, las llamadas a `/api/...` deberán apuntar a un backend alojado por separado y configurado para aceptar solicitudes del dominio `github.io`.
