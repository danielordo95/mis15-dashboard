# Directiva: Actualizar el dashboard de Mis 15 con un CSV nuevo

## Objetivo
Regenerar `site/data.json` y dejar `site/index.html` listo para publicarse con los datos
más recientes exportados de Meta Ads Manager, cada vez que el usuario sube un CSV nuevo.

## Entradas
- Un archivo `.csv` nuevo dentro de `Informes-de-Meta-Ads/` (exportado desde Meta Ads
  Manager: desglose diario, nivel anuncio, mismas 28 columnas del export original).
- `config/campaign-stage-map.json` (reglas de mapeo de etapa de funnel).

## Variables
- Ninguna credencial requerida para este paso — el parser corre 100% local, sin red.

## Herramientas / scripts
- `execution/build_dashboard.py` — toma el CSV más reciente por fecha de modificación
  dentro de `Informes-de-Meta-Ads/` (o el que se le indique con `--csv-file`) y escribe
  `site/data.json`.

## Pasos
1. Confirmar que el CSV nuevo ya está en `Informes-de-Meta-Ads/` (el usuario lo sube a esa
   carpeta, o se lo pasa a Cowork directamente).
2. Correr: `python3 execution/build_dashboard.py`
3. Revisar la salida en consola: cuántas filas válidas, cuántos errores/advertencias, y el
   cross-check contra la fila resumen del CSV (todo menos "Alcance" debería dar ~0% de
   diferencia — Alcance siempre difiere porque no es deduplicable sumando días, eso es
   esperado, no es un bug).
4. Si el cross-check muestra una diferencia grande (>2%) en spend, resultados, impresiones,
   clics, seguimientos o interacciones — algo cambió en el export o hay un problema real de
   parseo. Detenerse y avisar al usuario antes de publicar.
5. Si aparecen advertencias nuevas de "campaña sin etapa confirmada", decidir con el usuario
   si esa campaña debe agregarse a las reglas de `config/campaign-stage-map.json` (por
   ejemplo, un nuevo destino como "[Cartagena]").
6. Abrir `site/index.html` localmente (o levantar un server simple: `python3 -m http.server`
   desde `site/`) y verificar visualmente que el dashboard carga bien antes de avisarle al
   usuario que está listo para subir.
7. Avisar al usuario que la actualización está lista y recordarle el paso manual de Git
   (ver `README.md`) — Cowork no puede hacer push por sí solo en este entorno.

## Casos extremos
- CSV sin filas válidas → `data.json` se genera con `meta.parse_failed` o con `rows: []` y
  el dashboard muestra un banner de error explícito en vez de quedar en blanco.
- Columnas faltantes (estructura del export cambió) → se registra como advertencia tipo
  `missing_column`, el resto del pipeline sigue corriendo con lo que sí puede leer.
- Más de un CSV en la carpeta → se usa el de fecha de modificación más reciente; si eso no
  es lo que se quiere, usar `--csv-file` explícito.

## Aprendido / notas
Ver `context/learnings.md` para hallazgos técnicos acumulados (ej. limitación de red del
sandbox de Cowork hacia GitHub/Vercel, resuelta con sincronización manual — ver README.md).
