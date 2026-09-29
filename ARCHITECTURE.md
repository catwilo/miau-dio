# miau-dio - Arquitectura

Documento operativo. Responde una pregunta: dado un sintoma, que archivo abro primero. Para uso del programa ver README.md.

---

## 1. Principios rectores

1. Cero dependencias de Python. Solo stdlib. Tests con unittest, servidor HTTP con http.server, abrir URL con webbrowser, persistencia en JSON, concurrencia con threading.
2. El repo es codigo, no contenido. Renders, caches, samples pesados y binarios de terceros nunca van a git. Los catalogos (metadata de unos pocos KB) si.
3. El id de todo artefacto es estable y no depende del nombre. Renombrar y duplicar nunca rompen nada.
4. Toda escritura a disco es atomica: archivo temporal y replace. Nunca se sobrescribe en sitio.
5. Motor y contenido son independientes. Project y Track no saben si su content es MIDI, patron Strudel o texto plano.
6. Cada motor externo es un adapter aislado. Ningun modulo fuera de pipeline y backends llama subprocess para audio.
7. El navegador solo sirve archivos. El servidor de live nunca ejecuta musica ni sale a la red en runtime. Toda descarga pasa por sample install.

---

## 2. Mapa de modulos

    miau_dio/
    |-- __main__.py         entrada de python -m miau_dio
    |-- cli.py              TODA la superficie de linea de comandos
    |-- abcparse/           parser ABC (subset estricto)
    |-- assignment/         insertar %%MIDI program en ABC
    |-- store/              ideas: persistencia en XDG
    |-- instruments/        biblioteca de instrumentos
    |-- project/            modelo + store + layout de proyectos
    |-- pipeline/           abc -> midi -> wav (timidity o fluidsynth)
    |-- backends/           registro de binarios externos
    |-- installer/          construir e instalar esos binarios
    |-- platform/           deteccion Termux/Debian, paths, player, open_url
    |-- config/             defaults persistentes
    |-- strudel/            REPL de Strudel local y samples
        |-- catalog.py      metadata de packs (en git)
        |-- samples.py      instalar y borrar packs (a XDG)
        |-- server.py       servidor HTTP del REPL
        |-- site/           REPL oficial vendorizado (en git)

---

## 3. Responsabilidades por archivo

### Nucleo de la CLI

**miau_dio/__main__.py** - Entrada de python -m miau_dio. Llama a cli.main. Nunca contiene logica.

**miau_dio/cli.py** - Unico lugar con argparse y subcomandos. Los handlers se llaman cmd_<grupo>_<accion>; los parsers se construyen en build_parser(). No debe contener logica de dominio: solo orquesta los otros modulos y presenta en stdout.

### Dominio musical

**miau_dio/abcparse/tokens.py** - Parser ABC. Convierte texto en Score (headers, midi_programs, notes, barlines). Subset estricto: rechaza todo lo que no necesita (acordes, ligaduras, repeticiones, voces). No toca archivos.

**miau_dio/assignment/annotate.py** - Dado texto ABC y una politica (fixed o random) devuelve nuevo texto con directivas %%MIDI program insertadas. Texto a texto, sin I/O.

**miau_dio/instruments/model.py** - Dataclass Instrument (name, program 0-127, family). Validacion en __post_init__. Sin I/O.

**miau_dio/instruments/library.py** - Persiste instrumentos en XDG_DATA_HOME/miau-dio/instruments/. Renames atomicos: escribe el nuevo, verifica, borra el viejo. Los nombres pasan por _safe_name (rechaza / \ . .. y prefijo punto).

**miau_dio/project/model.py** - Dataclasses Project y Track. Project tiene metadata (tempo 20-300, time_signature N/M, key) y lista de Track. Track tiene (name, type, instrument, content, timing, volume 0-2, pan -1 a 1, effects). content es opaco: Project nunca lo interpreta. Validacion en __post_init__.

**miau_dio/project/store.py** - Persiste proyectos en XDG_DATA_HOME/miau-dio/projects/. Toda entrada publica llama _validate_id antes de tocar el indice (evita traversal). remove borra el directorio completo.

**miau_dio/project/layout.py** - Materializa un Project como directorio autocontenido: project.json, README.md, .gitignore (ignora renders/, *.wav, *.flac, __pycache__) y subdirectorios tracks/, patterns/, samples/, renders/. Rechaza targets no vacios. read reconstruye el Project.

**miau_dio/store/store.py** - Persiste ideas en XDG_DATA_HOME/miau-dio/. El id es 8 hex de os.urandom (nunca basado en tiempo o nombre). Dos ideas con el mismo nombre en el mismo segundo tienen ids distintos.

### Audio

**miau_dio/pipeline/pipeline.py** - Renderiza .abc a .wav. Ejecuta abc2midi siempre, luego timidity (default) o fluidsynth (--engine). Expone ENGINES. Los comandos de cada motor viven en _run_timidity y _run_fluidsynth. Todo subprocess de audio vive aca.

**miau_dio/backends/backend.py** - Registro de binarios externos (abcmidi, timidity, sox, fluidsynth). Cada entrada declara name (comando en PATH), apt_pkg, termux_pkg y opcionalmente un Source (build desde fuente). PROFILES agrupa subconjuntos (minimal, playback, full). Para agregar un binario, se agrega aca y, si necesita build, tambien en installer.

**miau_dio/installer/installer.py** - Sabe como obtener cada backend. abcmidi se compila desde assets/abc2midi-src/; los demas se instalan con el gestor de paquetes del sistema (pkg en Termux, apt en Debian). Copia el SoundFont al XDG la primera vez. ensure es la entrada: dada una lista de nombres, instala lo que falte.

### Plataforma

**miau_dio/platform/platform.py** - Detecta Termux vs Debian (is_termux), resuelve el comando de instalacion (pkg_install_cmd), define rutas (assets_dir, bin_dir, soundfont_path), elige reproductor (audio_player: mpv, luego sox play, luego aplay) y abre URLs (open_url: termux-open-url, luego webbrowser). Si algo solo funciona en una plataforma, es aca.

### Configuracion

**miau_dio/config/config.py** - Defaults persistentes para idea new (key, meter, unit, bpm) en XDG_DATA_HOME/miau-dio/config.json. Precedencia: flag, config, fabrica.

### Strudel local

**miau_dio/strudel/catalog.py** - Catalogo de packs (uzu, piano, dirt, mridangam). Solo metadata: descripcion, licencia, URL del manifest, tamano aproximado, tags. Agregar un pack es agregar una entrada Pack al diccionario CATALOG.

**miau_dio/strudel/samples.py** - Instala y borra packs. install baja el manifest y cada asset y los guarda en XDG_DATA_HOME/miau-dio/strudel/cache/<host>/<path>. El registro .packs/<nombre>.json guarda que archivos pertenecen a cada pack. remove borra esos archivos y poda directorios vacios. Si falla la red a mitad, borra lo ya bajado.

**miau_dio/strudel/server.py** - Servidor HTTP local que sirve el REPL oficial vendorizado. Sirve el HTML del sitio con dos <script> externos inyectados en el head (nunca JS embebido en Python, para no romper la sintaxis por escapes): /miau/fetch_shim.js y /miau/miau_bar.js. El shim reescribe cualquier URL a un host remoto conocido (la tupla SHIM_HOSTS: raw.githubusercontent.com, cdn.jsdelivr.net, unpkg.com, felixroos.github.io, shabda.ndre.gr) a /shim/<host>/<path>, resuelto desde el cache XDG. Si no esta en cache, 404: el navegador nunca sale a la red. Tambien sirve /samples/<file> y /samples/index.json. Con `live --at <dir>` activa el project bridge: GET /project/info (nombre + patterns del proyecto), GET/POST /project/pattern/<name> (leer/escribir en <dir>/patterns/). Path traversal rechazado, nombre de pattern validado (_safe_pattern_name), body acotado a MAX_PATTERN_BYTES. Logging opcional via MIAU_STRUDEL_LOG.

**miau_dio/strudel/site/** - Copia estatica del REPL oficial de strudel.cc (HTML, chunks Astro, fuentes). No se edita a mano. Se regenera con el crawler de vendorizado. Solo se toca para actualizar la version del REPL.

**Actualizar el sitio vendorizado** - El sitio oficial cambia con cada release de strudel.cc: los hashes de chunks (`index.BF19ZmMS.js`) son distintos en cada version. Para actualizar:
  1. Correr el crawler recursivo contra `https://strudel.cc/` (recorre el grafo de imports de Astro, no solo el HTML).
  2. Reemplazar `miau_dio/strudel/site/` con lo descargado.
  3. Revisar `SHIM_HOSTS` en `strudel/server.py`: la version nueva puede pedir hosts distintos.
  4. Probar en el navegador con `MIAU_STRUDEL_LOG` para ver que no se escape ningun recurso a internet.
  5. Actualizar `tests/test_strudel_server.py` si aparecen nuevos chunks con hash distinto en los tests.

**`_local_ipv4_addresses()` (en `strudel/server.py`)** - Devuelve las IPs no-loopback del host. Usa tres sondas en orden: `tailscale ip -4`, `ifconfig` (parsea las lineas `inet ...`; funciona en Termux sin root con warning benigno de netlink), `hostname -I` (ultimo recurso). Se usa solo en el mensaje informativo al arrancar `live --host 0.0.0.0`. Tests en `tests/test_local_ip.py`.

**miau_dio/strudel/inject/** - Assets propios inyectados en el REPL vendoreado. `fetch_shim.js` (reemplaza __SHIM_HOSTS__ con la tupla de server.py al servirse) corta cualquier peticion a hosts remotos. `miau_bar.js` es la unica barra de controles: un footer full-width abajo con el toggle de animaciones (siempre) y save/load/estado del proyecto (solo si la sesion arranco con --at). El script es idempotente y se re-instala via MutationObserver si una pasada del DOM (hidratacion React) lo quita. Se sirven via /miau/<file>.

### Otros

**bin/miau-dio** - Launcher bash. Resuelve su propio path (soporta symlink), pone el repo en PYTHONPATH y ejecuta python3 -m miau_dio.

**install.sh** - Symlinkea bin/miau-dio a PREFIX/bin (Termux) o ~/.local/bin (Debian). Nunca copia, siempre symlink: git pull actualiza el binario sin reinstalar. Modo verify: solo chequea el symlink sin tocar nada.

**assets/abc2midi-src/** - Fuentes C de abc2midi. Solo se toca al subir de version abc2midi.

**assets/TimGM6mb.sf2** - SoundFont por defecto (6 MB). Lo usa pipeline cuando no se pasa --sf.

**pyproject.toml** - Metadata del paquete. Declara cero dependencias.

---

## 4. Invariantes globales

- Ningun modulo fuera de pipeline y installer llama subprocess para audio.
- Ningun modulo fuera de store, instruments/library.py, project/store.py, project/layout.py y samples.py escribe a disco.
- Toda escritura es atomica: archivo temporal y replace. Si aparece open(w).write sin temp, es bug.
- Ningun handler de cli.py hace logica de dominio.
- El id de todo artefacto es os.urandom(4).hex() (8 hex). No basado en tiempo ni en nombre.
- El content de un Track es opaco para Project.
- sample install es la UNICA via para bajar archivos del REPL. Si el navegador sale a la red (verificar con MIAU_STRUDEL_LOG), es bug del shim.

---

## 5. Donde buscar cuando falla algo

| Sintoma | Empezar por |
|---|---|
| Un comando no existe o no parsea | cli.py, seccion de parsers al final |
| Un comando corre pero no hace nada | el handler cmd_* en cli.py; de ahi al modulo que llama |
| No suena audio | pipeline.py, luego backends/backend.py, luego installer/installer.py |
| El audio suena mal (volumen, corte) | pipeline._run_* (parametros del motor) |
| Una idea no se guarda o se corrompe | store/store.py |
| Un proyecto no se guarda | project/store.py o project/layout.py |
| Algo falla solo en Termux o solo en Debian | platform/platform.py |
| El binario miau-dio no aparece en PATH | install.sh (symlink), bin/miau-dio (launcher) |
| miau-dio live no arranca | strudel/server.py, luego platform.open_url |
| live --at rechaza el path | strudel/server.py:_set_project_dir (requiere project.json) |
| El footer del REPL no aparece o no responde | strudel/inject/miau_bar.js, luego el DOM del navegador (consola) |
| El REPL carga pero no suena | consola del navegador y MIAU_STRUDEL_LOG |
| Un sample no suena | sample installed, luego MIAU_STRUDEL_LOG |
| Un host remoto del REPL no se resuelve | strudel/server.py, lista SHIM_HOSTS |
| Un pack no baja | strudel/samples.py o strudel/catalog.py |
| Un test falla | tests/, un archivo por modulo |

---

## 6. Tests

Todos usan unittest de stdlib en tests/, un archivo por modulo (test_<modulo>.py).

    python3 -m unittest discover -s tests

No deben requerir red ni audio real. Para motores externos se mockea subprocess.run. Para XDG se usa tempfile.TemporaryDirectory y se cambia la variable de entorno. Para el servidor Strudel, se levanta en un puerto efimero y se consulta con urllib.

Cuando un modulo cambia su contrato publico, el test del modulo correspondiente se actualiza en el mismo commit.

---

## 7. Como agregar cosas

**Nuevo subcomando de la CLI** - Handler cmd_<grupo>_<accion> en cli.py. Subparser dentro de build_parser(). Tests en tests/test_cli.py, agregando el nombre al set de subcomandos del grupo.

**Nuevo motor de audio** - Entrada en BACKENDS (backends/backend.py). Si requiere build, receta en installer/installer.py. Rama nueva en pipeline.render con su _run_<motor>. Actualizar --engine choices y _engine_backends en cli.py.

**Nuevo pack de samples** - Entrada Pack en strudel/catalog.py. Solo metadata. No hace falta tocar samples.py ni server.py.

**Cambiar la UI inyectada en el REPL** - Editar el archivo correspondiente en strudel/inject/. `miau_bar.js` es el unico punto de entrada para botones y estado. Nunca embeber JS en server.py: si un cambio requiere logica nueva, va en inject/*.js y se referencia desde _render_index().

**Actualizar la version del REPL vendorizado** - Correr el crawler contra https://strudel.cc/ que recorra el grafo de chunks Astro. Reemplazar miau_dio/strudel/site/. Revisar SHIM_HOSTS en server.py: puede haber hosts nuevos. Probar con MIAU_STRUDEL_LOG.

**Nuevo modulo de dominio** - Carpeta con __init__.py, model.py (dataclasses y validacion) y store.py (persistencia). tests/test_<modulo>_model.py y tests/test_<modulo>_store.py. Nunca mezclar I/O y validacion en el mismo archivo.
