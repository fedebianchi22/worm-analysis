# C. elegans Lab

[![Compilar ejecutable Windows](https://github.com/fedebianchi22/worm-analysis/actions/workflows/build.yml/badge.svg)](https://github.com/fedebianchi22/worm-analysis/actions/workflows/build.yml)
[![Última versión](https://img.shields.io/github/v/release/fedebianchi22/worm-analysis?label=%C3%BAltima%20versi%C3%B3n)](https://github.com/fedebianchi22/worm-analysis/releases/latest)

Medición automática de nematodos (*Caenorhabditis elegans*) en fotos de
microscopio: detecta cada gusano, mide área y longitud en µm, deja corregir
a mano lo que haga falta, y exporta todo a un Excel prolijo.

Es una aplicación web propia — sin frameworks de terceros para la interfaz —
pensada para uso en laboratorio: no requiere conocimientos técnicos, corre
100% local (o en un servidor propio) y las fotos nunca salen de la
computadora donde se procesan.

## Qué hace

- **Detecta y mide automáticamente** cada gusano de una foto (área y
  longitud en µm), a partir de segmentación por umbral con corrección de
  viñeteado, esqueletización y filtros de forma.
- **Calibra por objetivo del microscopio** (0.75x a 5x), con valores medidos
  a mano contra una regla de calibración física — no una estimación.
- **Marca para revisión manual** los casos dudosos: gusanos cortados en el
  borde de la foto o posibles gusanos pegados/cruzados.
- **Corrección a mano** con un editor de contorno tipo "pluma" (Photoshop):
  agregar, mover y curvar puntos sobre la foto real, con recálculo
  inmediato del área y la longitud.
- **Separar detecciones conjuntas**: si dos gusanos pegados se detectaron
  como uno solo, se dividen en dos filas independientes para ajustar cada
  contorno por separado.
- **Selecciones y grupos**: cada tanda de fotos (una placa, una condición)
  es una selección independiente; selecciones réplica se pueden agrupar
  para promediar entre sí.
- **Exporta a Excel** con una sección por selección, promedios, y promedios
  por grupo — listo para pegar en un informe.
- **Programa de escritorio** (Windows) además de la versión web, con
  actualización automática: al abrirse, revisa solo si hay una versión
  nueva publicada y se actualiza sin pasos manuales.

## Para el laboratorio (uso sin instalar nada)

Entrá a la versión web de la app (o instalá el programa de escritorio desde
ahí — botón "Descargar para PC") y seguí las 4 etapas de la barra lateral:

1. **Cargar fotos**: subí una o más selecciones, cada una con su nombre y el
   objetivo del microscopio con el que se sacaron.
2. **Resultados**: revisá el tablero por selección (promedios, cuántos
   gusanos se midieron solos vs. cuántos hay que revisar) y las fotos
   anotadas. Los valores de la tabla se pueden editar a mano.
3. **Corregir detección**: ajustá el contorno de los gusanos marcados para
   revisar, o separá una detección que en realidad son dos gusanos pegados.
4. **Exportar**: descargá el Excel con todo, o las fotos anotadas de una
   selección puntual.

## Calibración por objetivo

Los valores están calibrados a mano con una regla de calibración Motic
(círculo de Ø1.5 mm, borde medido a nivel sub-píxel) y viven en
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

## Rangos de referencia por estadio

Como referencia para detectar mediciones sospechosas (se muestra también en
el tablero de resultados, ubicando cada gusano en una escala visual):

- Adulto: ~1000-1100 µm de largo, ~65-80 µm de ancho (parte más gruesa)
- Larva L1: ~250 µm de largo, ~15 µm de ancho
- Larvas L2-L4: tamaños intermedios entre esos dos

Si una medición se va muy lejos de estos rangos, probablemente sea un error
de segmentación (ruido detectado como gusano, objetivo mal seleccionado,
etc.) más que un gusano real de ese tamaño.

## Actualización automática del programa de escritorio

Es un programa instalado como cualquier otro: `CElegansLab-Setup.exe` abre
un asistente que deja elegir la carpeta de instalación, crea el acceso
directo en el Escritorio, y queda en "Agregar o quitar programas" para
desinstalarlo. No pide permisos de administrador (se instala para el
usuario actual). No corre en una consola: al abrirse queda un ícono
violeta en la bandeja del sistema (al lado del reloj), desde el que se
puede reabrir el navegador o cerrar el programa.

Cada apertura revisa sola si hay una versión más nueva publicada en GitHub
Releases (`updater.py`). Si la hay, muestra un aviso ("¿Querés actualizar
ahora?") y, si se acepta, descarga el instalador nuevo y lo corre en modo
silencioso: se cierra, se reinstala encima (misma carpeta) y se vuelve a
abrir solo, sin que aparezca ninguna ventana en el proceso. Requiere que la
PC tenga internet en ese momento; si no lo tiene, sigue abriendo el
programa normal sin bloquear nada.

Para publicar una versión nueva que dispare ese aviso en todas las PCs:

1. Subí el número en el archivo `VERSION` (ej. `2.0.0` → `2.1.0`) y
   commiteá ese cambio a `main`.
2. Etiquetá el commit y subí el tag:
   ```
   git tag v2.1.0
   git push origin v2.1.0
   ```
3. Eso dispara el workflow, que compila el ejecutable, arma el instalador
   (Inno Setup) y publica el Release en GitHub. A partir de ahí, cada
   instalación que se abra va a ofrecer actualizarse.

## Para desarrolladores

### Instalar y correr en local

```
pip install -r requirements.txt
uvicorn server:app --reload --port 8501
```

Y se abre `http://localhost:8501`.

### Estructura del proyecto

- `measure_worms.py` — detección y medición automática (segmentación,
  esqueleto, filtros de sombra/ruido/cruces, calibración por objetivo).
- `server.py` — servidor FastAPI: todas las rutas de la app (subir fotos,
  analizar, editar resultados, corregir, exportar).
- `state.py` — estado en memoria por sesión de navegador (sin base de
  datos: alcanza para el uso del laboratorio).
- `templates/` — páginas HTML (Jinja2), una por etapa (cargar, resultados,
  corregir, exportar) más el layout compartido con la barra lateral.
- `static/app.css` — todo el diseño visual (paleta violeta, tipografía,
  tema claro y oscuro).
- `static/pen.js` — editor de contorno tipo "pluma" (agregar/mover/curvar
  puntos con manijas Bezier), sin dependencias externas.
- `reporte_excel.py` — arma el Excel final con las secciones y colores.
- `launcher.py` — punto de entrada del ejecutable: levanta el servidor,
  abre el navegador, y queda como ícono en la bandeja del sistema (sin
  consola).
- `updater.py` — chequea y aplica actualizaciones automáticas del programa
  de escritorio.
- `VERSION` — versión instalada actual (la compara `updater.py`).
- `worm_app.spec` — configuración de PyInstaller (compila el `.exe`).
- `installer.iss` — configuración de Inno Setup (arma el instalador a
  partir de lo que compiló PyInstaller).
- `.github/workflows/build.yml` — compila el ejecutable, arma el
  instalador y publica releases en GitHub.

### Compilar el instalador de Windows

**Opción A — GitHub Actions (recomendado, no necesitás Windows):**

1. Andá a la pestaña "Actions" del repo → "Compilar ejecutable Windows" →
   "Run workflow".
2. Esperá unos minutos. Al terminar:
   - El artifact `CElegansLab-Windows` tiene la carpeta suelta (para
     probar sin instalar).
   - Si corriste el workflow desde un tag `v*.*.*`, además se publica un
     Release con `CElegansLab-Setup.exe`, el instalador de verdad.

**Opción B — Compilar en una PC con Windows:**

```
pip install -r requirements.txt
pyinstaller worm_app.spec
```

El ejecutable (junto con su carpeta de soporte) queda en
`dist/CElegansLab/`. Para armar el instalador hace falta también
[Inno Setup](https://jrsoftware.org/isinfo.php) instalado, y después:

```
iscc /DAppVersion=2.1.0 installer.iss
```

El instalador queda en `installer_output/CElegansLab-Setup.exe`.

### Desplegar la versión web

Es un servidor FastAPI estándar (no depende de Streamlit ni de ninguna
plataforma en particular), así que corre en cualquier host que acepte una
app Python con `uvicorn` — por ejemplo Render, Fly.io o un VPS propio con
Docker. El comando de arranque en producción es:

```
uvicorn server:app --host 0.0.0.0 --port $PORT
```

## Privacidad

Las fotos y las mediciones se procesan enteramente en la máquina donde
corre la app (o en el servidor propio, si se despliega uno) y no se envían
a ningún servicio de terceros.

## Licencia y uso

Este repositorio no tiene una licencia de código abierto: todos los
derechos están reservados. El código es público para que se pueda ver,
pero **no está permitido copiarlo, modificarlo, redistribuirlo ni
revenderlo sin autorización previa del autor**. Sí está permitido usar la
aplicación (la versión web o el programa de escritorio) tal como se
distribuye.

Para pedir autorización de uso o colaborar, abrí un issue en este
repositorio.
