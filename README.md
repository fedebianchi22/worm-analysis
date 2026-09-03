# C. elegans Lab

App que detecta gusanos (*Caenorhabditis elegans*) en fotos de microscopio,
mide área y longitud en µm, permite corregir a mano lo que haga falta, y
exporta todo a un Excel prolijo. Corre 100% local (o en Streamlit Cloud) —
las fotos nunca salen de donde se procesan.

## Calibración por objetivo

Cada selección de fotos elige su objetivo (zoom digital de Motic) en un
desplegable. Los valores están calibrados a mano con la regla de calibración
Motic (círculo de Ø1.5mm, borde medido a nivel sub-píxel) y viven en
`measure_worms.py`, diccionario `OBJETIVOS_CALIBRADOS`:

| Objetivo | px / mm |
|----------|---------|
| 0.75x    | 72.1    |
| 1x       | 96.1    |
| 2x       | 192.1   |
| 3x       | 288.2   |
| 4x       | 384.3   |
| 5x       | 480.3   |

La relación es lineal (`px/mm ≈ 96.07 × zoom`, con un error menor al 1.1% en
los 6 puntos medidos). Si se usa un zoom no listado, hay que calibrarlo con
la regla y agregarlo al diccionario.

## Especie y rangos esperados (referencia)

Como referencia para detectar mediciones sospechosas:

- Adulto: ~1000-1100 µm de largo, ~65-80 µm de ancho (parte más gruesa)
- Larva L1: ~250 µm de largo, ~15 µm de ancho
- Larvas L2-L4: tamaños intermedios entre esos dos

Si una medición se va muy lejos de estos rangos, probablemente sea un error
de segmentación (ruido detectado como gusano, objetivo mal seleccionado,
etc.) más que un gusano real de ese tamaño.

## Uso

1. **Fotos a analizar**: subí una o más selecciones de fotos, cada una con
   su nombre y el objetivo con el que se sacaron.
2. **Promediar entre selecciones** (opcional): si dos o más selecciones son
   réplicas de la misma condición, armá un grupo para promediarlas.
3. Click en **"Analizar fotos"**.
4. Revisá la tabla y las fotos anotadas por selección (verde = medido ok,
   rojo = revisar a mano). Podés editar los valores directo en la tabla.
5. **Corregir una detección**: elegí un gusano y ajustá su contorno a mano
   con el editor tipo "pluma" (agregar/mover/curvar puntos). Si una
   detección son en realidad 2 gusanos pegados, separala en 2 primero.
6. Descargá el Excel con todo, o las fotos analizadas de una selección en ZIP.

## Actualización automática del .exe

Cada .exe instalado revisa solo, al abrirse, si hay una versión más nueva
publicada en GitHub Releases (`updater.py`). Si la hay, muestra un aviso
("¿Querés actualizar ahora?") y, si el usuario acepta, la descarga y
reemplaza la instalación sola, sin pasos manuales. Requiere que la PC
tenga internet en ese momento; si no lo tiene, sigue abriendo la app
normal sin bloquear nada.

Para publicar una versión nueva que dispare ese aviso en todas las PCs:

1. Subí el número en el archivo `VERSION` (ej. `1.0.0` → `1.1.0`) y
   commiteá ese cambio a `main`.
2. Etiquetá el commit y subí el tag:
   ```
   git tag v1.1.0
   git push origin v1.1.0
   ```
3. Eso dispara el workflow, que compila, arma el `.zip` y publica el
   Release en GitHub automáticamente. A partir de ahí, cada .exe que se
   abra en el laboratorio va a ofrecer actualizarse.

## Cómo generar el .exe

### Opción A — GitHub Actions (recomendado, no necesitás Windows)

1. Subí esta carpeta completa a un repositorio de GitHub.
2. Andá a la pestaña "Actions" del repo → "Compilar ejecutable Windows" →
   "Run workflow".
3. Esperá unos minutos. Al terminar, bajás la carpeta desde el artifact
   `CElegansLab-Windows` (es un .zip que adentro tiene toda la carpeta
   `CElegansLab`, con el .exe y sus archivos de soporte).

### Opción B — Compilar en una PC con Windows

```
pip install -r requirements.txt
pyinstaller worm_app.spec
```

El .exe (junto con su carpeta de soporte) queda en `dist/CElegansLab/`.

## Desarrollo / probar sin compilar

```
pip install -r requirements.txt
streamlit run app.py
```

## Estructura

- `measure_worms.py` — detección y medición automática (segmentación,
  esqueleto, filtros de sombra/ruido/cruces, calibración por objetivo).
- `app.py` — interfaz Streamlit.
- `pen_editor.py` / `pen_editor/index.html` — editor de contorno tipo
  "pluma" (componente propio, sin dependencias externas).
- `reporte_excel.py` — arma el Excel final con las secciones y colores.
- `.streamlit/config.toml` — tema visual (paleta violeta).
- `launcher.py` — punto de entrada del .exe (abre el navegador solo).
- `updater.py` — chequea y aplica actualizaciones automáticas del .exe.
- `VERSION` — versión instalada actual (la compara `updater.py`).
- `worm_app.spec` — configuración de PyInstaller.
- `.github/workflows/build.yml` — compila el .exe y publica releases en GitHub.
