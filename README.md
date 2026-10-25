# Susurros del Dragón v15

Aplicación web Flask con catálogo, panel administrativo, base de datos y carga de imágenes.

## Seguridad antes de desplegar

La aplicación lee los valores sensibles desde variables de entorno. Configura `SECRET_KEY`, `ADMIN_USER` y `ADMIN_PASS` en el entorno donde alojes la app. No subas `.env`, la base de datos ni imágenes de usuarios.

En producción usa HTTPS y configura `SESSION_COOKIE_SECURE=true`. La aplicación falla al iniciar si no encuentra `SECRET_KEY`; el inicio de sesión administrativo queda deshabilitado si falta `ADMIN_USER` o `ADMIN_PASS`.

## Ejecutar localmente

1. Instala Python y las dependencias con `pip install -r requirements.txt`.
2. Define las variables de entorno indicadas en `.env.example` en tu terminal.
3. Ejecuta `python app.py` y abre `http://127.0.0.1:5000`.

## Publicar una vista previa en Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/andy02110822-dotcom/susurros-del-dragon-v15)

1. Abre el botón **Deploy to Render** y conecta GitHub con Render si te lo solicita.
2. Revisa el servicio definido en `render.yaml`; el plan configurado es gratuito.
3. Cuando Render lo pida, define `ADMIN_USER` y `ADMIN_PASS` con valores nuevos y únicos. Nunca uses credenciales antiguas ni las publiques en el repositorio.
4. Crea el servicio y espera a que termine el primer deploy. Render mostrará una dirección pública `onrender.com`.

La primera visita puede tardar aproximadamente un minuto si el servicio gratuito se ha detenido por inactividad. En el plan gratuito el sistema de archivos es temporal: los cambios en SQLite y los archivos de imagen cargados pueden perderse al reiniciarse o redeplegarse. Usa almacenamiento persistente antes de utilizar la app con datos reales.

## Publicación

Esta app necesita un servidor Python para atender Flask y las rutas `/api/...`. GitHub Pages publica archivos estáticos HTML, CSS y JavaScript; no ejecuta este backend. Para un uso estable, despliega Flask en un servicio que admita aplicaciones Python y configura almacenamiento persistente para la base de datos y `static/uploads`.

Si publicas solo el frontend en GitHub Pages, las llamadas a `/api/...` deberán apuntar a un backend alojado por separado y configurado para aceptar solicitudes del dominio `github.io`.
