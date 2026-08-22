# Medición automática de gusanos

App que detecta gusanos en fotos de microscopio (objetivo 4X), mide área y
longitud en µm, y exporta todo a Excel. Corre 100% local — las fotos nunca
salen de la PC.

## Calibración actual

`393.0 px = 1mm` (2.544529 µm/píxel), confirmada con el asistente de
calibración de Motic. Está en `measure_worms.py`, línea `PX_PER_MM`.
Si en algún momento cambian de cámara/resolución/objetivo, hay que
recalibrar y actualizar ese valor (avisame y te paso el script actualizado).

## Especie y rangos esperados (referencia)

Los gusanos son *Caenorhabditis elegans*. Como referencia para detectar
mediciones sospechosas (útil si en algún momento el área o la longitud
dan valores raros):

- Adulto: ~1000-1100 µm de largo, ~65-80 µm de ancho (parte más gruesa)
- Larva L1: ~250 µm de largo, ~15 µm de ancho
- Larvas L2-L4: tamaños intermedios entre esos dos

Si una medición se va muy lejos de estos rangos, probablemente sea un
error de segmentación (ruido detectado como gusano, calibración
desactualizada, etc.) más que un gusano real de ese tamaño.

## Uso (una vez que tengas el ejecutable)

1. Descomprimí la carpeta `MedicionGusanos` completa (no muevas el .exe
   solo fuera de la carpeta, necesita los archivos de al lado).
2. Doble click en `MedicionGusanos.exe` (adentro de esa carpeta).
3. Se abre una ventana negra (dejala abierta) y el navegador solo, en
   `http://localhost:8501`.
4. Click en "Elegir carpeta" y seleccioná la carpeta con las fotos.
5. Click en "Procesar todas las fotos".
6. Revisá la tabla y las fotos anotadas (verde = medido ok, rojo = revisar
   a mano en Motic).
7. Descargá el Excel, o buscalo directo en la carpeta
   `resultados_<fecha>` que se crea adentro de la carpeta de fotos.
8. Para cerrar el programa, cerrá la ventana negra.

## Cómo generar el .exe

### Opción A — GitHub Actions (recomendado, no necesitás Windows)

1. Subí esta carpeta completa a un repositorio de GitHub.
2. Andá a la pestaña "Actions" del repo → "Compilar ejecutable Windows" →
   "Run workflow".
3. Esperá ~3-5 minutos. Al terminar, bajás la carpeta desde el artifact
   `MedicionGusanos-Windows` (es un .zip que adentro tiene toda la
   carpeta `MedicionGusanos`, con el .exe y sus archivos de soporte).

### Opción B — Compilar en una PC con Windows

```
pip install -r requirements.txt
pyinstaller worm_app.spec
```

El .exe (junto con su carpeta de soporte) queda en `dist/MedicionGusanos/`.

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
