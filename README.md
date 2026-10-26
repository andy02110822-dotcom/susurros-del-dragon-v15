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
2. Revisa el servicio definido en `render.yaml`; el plan configurado es gratuito y la clave de sesión la genera Render.
3. Crea el servicio y espera a que termine el primer deploy. Render mostrará una dirección pública `onrender.com`.
4. El inicio del panel administrativo queda deshabilitado en esta vista previa. Si necesitas administrarlo, añade `ADMIN_USER` y `ADMIN_PASS` como variables secretas en Render, con valores nuevos y únicos.

## PayPal Checkout

El catálogo guarda los precios en COP y muestra su equivalente aproximado en USD con la TRM publicada por la Superintendencia Financiera. PayPal cobra en USD; el servidor vuelve a calcular el total con la TRM vigente al iniciar el pago. El envío se coordina por WhatsApp y no está incluido en el pago web. Las suscripciones recurrentes continúan por WhatsApp; aún no se cobra su renovación automática con PayPal.

Para configurar PayPal primero crea una aplicación REST de prueba en PayPal Developer y agrega estas variables en Render: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` y `PAYPAL_ENV=sandbox`. El botón aparecerá cuando estén las credenciales de prueba. Tras validar el flujo y confirmar que la cuenta Business puede recibir pagos en USD, cambia `PAYPAL_ENV` a `live` y agrega las credenciales de producción de esa aplicación. Nunca guardes el Client Secret en el repositorio ni lo compartas por chat. `.env.example` enumera estas variables para el entorno local.

La configuración de Render usa un disco persistente montado en `/var/data` para guardar la base SQLite y las imágenes que se suben desde el panel. Render no permite discos persistentes en el plan gratuito; esta configuración usa el plan Starter y un disco de 1 GB, por lo que el servicio y el almacenamiento tienen un costo según las tarifas vigentes de Render. Revisa el costo en Render antes de sincronizar o desplegar el Blueprint. En instalaciones propias, define `DATA_DIR` como una carpeta persistente y con permisos de escritura. `DATABASE_URL` puede sustituir a SQLite para la base de datos; las imágenes siguen guardándose en `DATA_DIR/uploads`.

Los cambios hechos desde el panel que ya se perdieron cuando el servidor gratuito se detuvo no se pueden reconstruir desde el disco efímero. La versión del sitio y del panel del 25 de octubre sí está en el código del repositorio; se recuperará al desplegar esa revisión.

## Publicación

Esta app necesita un servidor Python para atender Flask y las rutas `/api/...`. GitHub Pages publica archivos estáticos HTML, CSS y JavaScript; no ejecuta este backend. Para un uso estable, despliega Flask en un servicio que admita aplicaciones Python y configura almacenamiento persistente para la base de datos y `static/uploads`.

Si publicas solo el frontend en GitHub Pages, las llamadas a `/api/...` deberán apuntar a un backend alojado por separado y configurado para aceptar solicitudes del dominio `github.io`.
