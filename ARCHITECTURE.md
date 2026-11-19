# miau-dio - Arquitectura

Mapa de modulos y binarios. Para uso, ver README.md.

## Mapa de modulos

    miau_dio/
    |-- __main__.py         entrada de python -m miau_dio
    |-- cli.py              superficie de linea de comandos
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
        |-- catalog.py      metadata de packs
        |-- samples.py      instalar packs y resolver vendored
        |-- server.py       servidor HTTP del REPL
        |-- site/           REPL oficial vendorizado
        |-- inject/         JS propio inyectado
        +-- vendor/         packs de samples vendorizados

## Responsabilidades por archivo

### Nucleo

**__main__.py** -- entrada de `python -m miau_dio`. Llama a `cli.main`.

**cli.py** -- unico lugar con argparse. Handlers `cmd_<grupo>_<accion>`, parsers en `build_parser()`. Sin logica de dominio.

### Dominio musical

**abcparse/tokens.py** -- parser ABC. Subset estricto: rechaza acordes, ligaduras, repeticiones, voces. Sin I/O.

**assignment/annotate.py** -- inserta `%%MIDI program` en texto ABC segun politica fija o aleatoria. Texto a texto.

**instruments/model.py** -- dataclass `Instrument` (name, program 0-127, family). Validacion en `__post_init__`.

**instruments/library.py** -- persistencia en `XDG_DATA_HOME/miau-dio/instruments/`. Nombres pasan por `_safe_name`.

**project/model.py** -- dataclasses `Project` y `Track`. `Track.content` es opaco.

**project/store.py** -- persistencia en XDG. `_validate_id` antes de tocar el indice.

**project/layout.py** -- materializa un `Project` como directorio versionable. Rechaza targets no vacios.

**store/store.py** -- ideas en XDG. Id 8 hex de `os.urandom`.

### Audio

**pipeline/pipeline.py** -- `.abc` -> `.wav`. `abc2midi` siempre, luego `timidity` (default) o `fluidsynth`. Todo subprocess de audio vive aca.

**backends/backend.py** -- registro de binarios (`abcmidi`, `timidity`, `sox`, `fluidsynth`). Cada entrada: nombre, paquete apt/termux, opcionalmente source. `PROFILES` agrupa (minimal, playback, full).

**installer/installer.py** -- obtiene cada backend. `abcmidi` se compila desde `assets/abc2midi-src/`; los demas via gestor de paquetes del sistema.

### Plataforma y config

**platform/platform.py** -- detecta Termux/Debian, resuelve gestor de paquetes, paths, player (`mpv`, `sox play`, `aplay`), `open_url` (`termux-open-url`, `webbrowser`).

**config/config.py** -- defaults para `idea new` en `XDG_DATA_HOME/miau-dio/config.json`.

### Strudel local

**strudel/catalog.py** -- catalogo de packs. Solo metadata. Agregar uno = entrada en `CATALOG`.

**strudel/samples.py** -- `install` baja manifest+assets al cache XDG; `remove` los borra. `vendored()` lista packs en `vendor/`. `available()` = `installed()` union `vendored()`. `is_installed()` es solo cache.

**strudel/server.py** -- servidor HTTP. Sirve el REPL oficial de `site/` con `inject/fetch_shim.js` y `inject/miau_bar.js` inyectados en el `<head>`. El shim reescribe URLs a hosts remotos conocidos (`SHIM_HOSTS`) a `/shim/<host>/<path>` y el servidor resuelve desde `vendor/` (via `VENDOR_MAP`) o `cache/` XDG. Si no esta en ninguno, 404: el navegador nunca sale a la red. `/samples/<file>` y `/samples/index.json` sirven wavs sueltos. Con `--at`, expone `/project/info` y `/project/pattern/<name>` (GET/POST).

**strudel/site/** -- copia estatica del REPL oficial de strudel.cc. No se edita a mano.

**strudel/inject/fetch_shim.js** -- reemplaza `window.fetch` y `XMLHttpRequest.open`. `__SHIM_HOSTS__` se sustituye con `SHIM_HOSTS` de `server.py` al servirse.

**strudel/inject/miau_bar.js** -- footer unico: toggle de animaciones + save/load de patterns (si `--at`). Idempotente, se re-instala via MutationObserver.

**strudel/vendor/** -- packs de samples en el repo (uzu, dirt, guitar, trumpet, trumpet_stac, trombone, trombone_stac). Cada uno: `.wav` + un manifest `<nombre>.json` (o `strudel.json` / `Dirt-Samples.json`).

### Otros

**bin/miau-dio** -- launcher bash. Resuelve su path (symlink), pone el repo en `PYTHONPATH`, ejecuta `python3 -m miau_dio`.

**install.sh** -- symlink `bin/miau-dio` a `PREFIX/bin` (Termux) o `~/.local/bin` (Debian). Nunca copia.

**assets/abc2midi-src/** -- fuentes C de abc2midi.

**assets/TimGM6mb.sf2** -- SoundFont por defecto (6 MB).

## Invariantes

- Ningun modulo fuera de `pipeline` e `installer` llama `subprocess` para audio.
- Ningun modulo fuera de `store`, `instruments/library.py`, `project/store.py`, `project/layout.py` y `samples.py` escribe a disco.
- Toda escritura es atomica: temp + replace.
- Ningun handler de `cli.py` hace logica de dominio.
- El id de todo artefacto es `os.urandom(4).hex()`.
- El `content` de un `Track` es opaco para `Project`.
- `sample install` es la unica via para bajar archivos del REPL.
- El navegador nunca sale a la red en `live`: shim + `SHIM_HOSTS` + `VENDOR_MAP`.

## Donde buscar cuando falla algo

| Sintoma | Empezar por |
|---|---|
| Comando no existe o no parsea | `cli.py`, parsers al final |
| Comando corre pero no hace nada | handler `cmd_*` en `cli.py` |
| No suena audio | `pipeline.py`, luego `backends/backend.py`, `installer/installer.py` |
| Audio suena mal (volumen, corte) | `pipeline._run_*` |
| Idea no se guarda o corrompe | `store/store.py` |
| Proyecto no se guarda | `project/store.py` o `project/layout.py` |
| Falla solo en Termux o solo en Debian | `platform/platform.py` |
| Binario `miau-dio` no aparece en PATH | `install.sh`, `bin/miau-dio` |
| `live` no arranca | `strudel/server.py`, luego `platform.open_url` |
| `live --at` rechaza path | `strudel/server.py:_set_project_dir` |
| Footer del REPL no aparece | `strudel/inject/miau_bar.js`, consola del navegador |
| REPL carga pero no suena | consola del navegador y `MIAU_STRUDEL_LOG` |
| Un sample no suena | `sample installed`, luego `MIAU_STRUDEL_LOG` |
| Host remoto del REPL no se resuelve | `strudel/server.py` (`SHIM_HOSTS`, `VENDOR_MAP`) |
| Pack no baja | `strudel/samples.py` o `strudel/catalog.py` |

## Tests

`python3 -m unittest discover -s tests` -- sin red ni audio real. Un archivo por modulo.
