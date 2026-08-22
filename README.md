# Medición automática de gusanos

App que detecta gusanos en fotos de microscopio (objetivo 4X), mide área y
longitud en µm, y exporta todo a Excel. Corre 100% local — las fotos nunca
salen de la PC.

## Calibración actual

`393.0 px = 1mm` (2.544529 µm/píxel), confirmada con el asistente de
calibración de Motic. Está en `measure_worms.py`, línea `PX_PER_MM`.
Si en algún momento cambian de cámara/resolución/objetivo, hay que
recalibrar y actualizar ese valor (avisame y te paso el script actualizado).

## Uso (una vez que tengas el .exe)

1. Doble click en `MedicionGusanos.exe`.
2. Se abre el navegador solo, en `http://localhost:8501`.
3. Click en "Elegir carpeta" y seleccioná la carpeta con las fotos.
4. Click en "Procesar todas las fotos".
5. Revisá la tabla y las fotos anotadas (verde = medido ok, rojo = revisar
   a mano en Motic).
6. Descargá el Excel, o buscalo directo en la carpeta
   `resultados_<fecha>` que se crea adentro de la carpeta de fotos.

## Cómo generar el .exe

### Opción A — GitHub Actions (recomendado, no necesitás Windows)

1. Subí esta carpeta completa a un repositorio de GitHub.
2. Andá a la pestaña "Actions" del repo → "Compilar ejecutable Windows" →
   "Run workflow".
3. Esperá ~3-5 minutos. Al terminar, bajás el .exe desde el artifact
   `MedicionGusanos-Windows`.

### Opción B — Compilar en una PC con Windows

```
pip install -r requirements.txt
pyinstaller worm_app.spec
```

El .exe queda en `dist/MedicionGusanos.exe`.

## Desarrollo / probar sin compilar

```
pip install -r requirements.txt
streamlit run app.py
```

## Estructura

- `measure_worms.py` — lógica de detección y medición (segmentación,
  esqueleto, filtros de sombra/ruido/cruces).
- `app.py` — interfaz Streamlit.
- `launcher.py` — punto de entrada del .exe (abre el navegador solo).
- `worm_app.spec` — configuración de PyInstaller.
- `.github/workflows/build.yml` — compila el .exe automáticamente en GitHub.
# worm-analysis
