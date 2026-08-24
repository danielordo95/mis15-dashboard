# Mis 15 — Dashboard de campañas (Meta Ads)

Panel estático que lee los exports de Meta Ads Manager y muestra el estado de las
campañas sin depender de Ads Manager. Ver el spec completo del proyecto para el detalle
funcional. Este README es solo el "cómo lo actualizo".

## Estructura

```
Mis 15s/                        (raíz de este repo)
├── site/                       (esto es lo único que Vercel publica)
│   ├── index.html              (el dashboard)
│   └── data.json               (generado — no editar a mano)
├── execution/
│   └── build_dashboard.py      (parser CSV -> data.json)
├── config/
│   └── campaign-stage-map.json (reglas de mapeo de etapa de funnel)
├── directives/
│   └── actualizar-dashboard.md (SOP que sigue Cowork al actualizar)
├── Informes-de-Meta-Ads/       (sube aquí los CSV nuevos)
├── context/                    (memoria de Cowork entre sesiones — no es del sitio)
└── .env                        (nunca se sube a Git — variables locales)
```

## Setup inicial (una sola vez)

### 1. Conectar Git en esta carpeta y hacer el primer push

Cowork no tiene acceso de red a GitHub desde este entorno (limitación del sandbox, no del
token) — así que este primer push, y cada actualización futura, requieren un paso manual
tuyo de unos segundos. Abre una terminal en esta carpeta ("Mis 15s") y corre:

```
git init
git add -A
git commit -m "Primer commit — dashboard v2.0"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/mis15-dashboard.git
git push -u origin main
```

Te va a pedir usuario y contraseña — como usuario pon tu usuario de GitHub, y como
contraseña **pega el Personal Access Token** que ya generaste (no tu contraseña normal de
GitHub). Si prefieres no usar terminal, instala **GitHub Desktop**, ábrelo, "Add Local
Repository" apuntando a esta carpeta, y usa el botón "Publish repository" — te pedirá
iniciar sesión con tu cuenta de GitHub una sola vez y ya no vuelve a pedir el token.

### 2. Conectar Vercel (una sola vez, lo haces tú)

1. Entra a vercel.com, crea una cuenta o inicia sesión con tu cuenta de GitHub.
2. "Add New… → Project", selecciona el repo `mis15-dashboard`.
3. En "Configure Project", en **Root Directory** pon `site` (así Vercel solo publica el
   dashboard, no el resto del repo — el resto queda privado dentro del repo pero no
   navegable desde el link público).
4. Framework Preset: "Other" (sitio estático, sin build step).
5. Click "Deploy".

Desde ahí, cada `git push` a `main` dispara un redeploy automático — ese paso si es 100%
automático, tal como pedía el spec original.

## Actualizar el dashboard con un CSV nuevo (cada vez)

1. Sube el CSV nuevo (export completo del rango que quieras cubrir) a la carpeta
   `Informes-de-Meta-Ads/` — puede ser arrastrándolo a la carpeta en tu Mac, o subiéndolo
   en el chat de Cowork.
2. Pídele a Cowork: "actualiza el dashboard con el CSV nuevo".
3. Cowork corre el parser, revisa que los totales cuadren, regenera `site/data.json`, y
   te avisa cuando está listo — incluyendo cualquier aviso de datos rotos o campañas sin
   etapa confirmada.
4. Corre estos tres comandos en la carpeta del proyecto (o usa el botón "Push origin" en
   GitHub Desktop):

```
git add -A
git commit -m "Actualiza datos — CSV al <fecha>"
git push
```

5. Espera ~30-60 segundos — Vercel redeploya solo. El link del cliente no cambia nunca.

## Si algo se ve raro en el dashboard

El dashboard mismo te avisa: cualquier columna faltante, valor roto, o campaña sin etapa
confirmada aparece en el banner de avisos arriba del todo, con el detalle de qué y dónde.
Si el filtro que aplicaste no tiene datos, el panel te lo dice explícitamente en vez de
mostrarte un panel vacío o en ceros.

Nota sobre "Alcance": siempre se muestra como una suma diaria acumulada, que es una
aproximación — Meta no permite deduplicar personas alcanzadas entre distintos días desde
este tipo de export. Para el alcance único exacto de un periodo, hay que consultarlo
directamente en Ads Manager.
