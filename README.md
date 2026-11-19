# miau-dio

CLI para componer musica desde la terminal. Ideas en ABC, proyectos multi-pista, REPL de Strudel para live coding. Sin dependencias de Python.

## Instalacion

    git clone git@github.com:catwilo/miau-dio.git
    cd miau-dio
    ./install.sh

## Inicio rapido

    miau-dio idea new "mi primera idea"   # editor -> guardas -> suena
    miau-dio idea list                    # tus ideas
    miau-dio backend selftest             # verifica audio
    miau-dio live                         # REPL de Strudel en el navegador
    miau-dio sample list                  # packs de samples

## Comandos

### idea

- `idea new <nombre>` -- plantilla en editor, al guardar suena. Flags: `--key --meter --unit --bpm -t/--tag -n/--note --silent`.
- `idea add <nombre> <archivo.abc>` -- guarda un `.abc` existente.
- `idea list [--tag X] [-s QUERY] [--json]` -- lista / filtra / busca.
- `idea show <id>` -- detalle.
- `idea edit <id>` -- abre en `$EDITOR`. Limpia cache de audio al cambiar.
- `idea rename <id> <nuevo>` / `idea dup <id> [--name]` -- el id es estable.
- `idea tag <id> --add X --rm Y` / `idea note <id> "texto"`.
- `idea assign <id> --program N [--at K]` -- `%%MIDI program` fijo o antes de nota K.
- `idea rm <id> [-y]`.

### instr

- `instr add <nombre> <program 0-127> [--family X]`
- `instr list [--json]` / `instr show <nombre>`
- `instr dup <nombre> [--name]` / `instr rename <viejo> <nuevo>`
- `instr rm <nombre> [-y]`
- `family list`

### play

- `play file <archivo.abc> [--out out.wav] [--sf soundfont.sf2] [--engine timidity|fluidsynth]`
- `play idea <id> [--engine ...] [--sf ...] [--silent] [--random [--seed N] [--min-duration F]]`

### project

- `project new <nombre> [--tempo N] [--meter N/M] [--key X] [--track "name:type[:content]"]... [--at <ruta>]`
- `project list [--json]` / `project show <id> [--at <ruta>]` / `project rm <id> [-y]`

Con `--at`, el proyecto se materializa como directorio versionable con `project.json`, `tracks/`, `patterns/`, `samples/`, `renders/`, `README.md`, `.gitignore`.

### live

- `live [--url URL] [--host ADDR] [--port N] [--at <ruta>]`

Arranca el REPL de Strudel vendorizado en el repo y lo abre en el navegador. Defaults: `--host 0.0.0.0 --port 8765`. Con `--host 127.0.0.1` queda solo local; con `--port 0` el SO elige puerto libre.

Sin `--url`, todo es offline: cada peticion a un host remoto conocido (`raw.githubusercontent.com`, `cdn.jsdelivr.net`, etc.) se reescribe a `/shim/<host>/<path>` y el servidor la resuelve desde `miau_dio/strudel/vendor/` o el cache XDG. Nunca sale a internet.

Con `--at`, ata un proyecto al REPL: footer con save/load de patterns.

### sample

- `sample list [--json]` -- packs del catalogo.
- `sample info <nombre>` -- descripcion, tamano, manifest.
- `sample installed [--json]` -- que hay en disco.
- `sample install <nombre>...` -- baja un pack al cache XDG.
- `sample remove <nombre>... [-y]` -- borra del cache.

### config

- `config show` / `config set <campo> <valor>` -- `key`, `meter`, `unit`, `bpm`.

### backend

- `backend setup --profile <minimal|playback|full>`
- `backend status`
- `backend selftest [--full]`

## Samples en el REPL

Los packs en `miau_dio/strudel/vendor/` ya estan en disco y se sirven sin instalar nada. `sample list` los marca con `v`.

| pack | contenido |
|---|---|
| `uzu` | bateria (kick, snare, hats, claps, breaks) |
| `dirt` | percusion y texturas |
| `guitar` | guitarra acustica, cromatica A2-G#4 (37 notas) |
| `trumpet` | trompeta sostenida, multi-velocidad y round-robin |
| `trumpet_stac` | trompeta staccato, multi-velocidad y round-robin |
| `trombone` | trombon tenor sostenido, multi-velocidad |
| `trombone_stac` | trombon tenor staccato, multi-velocidad y round-robin |

Packs opcionales (se bajan con `sample install`): `piano` (8.7 MB), `mridangam` (0.2 MB).

### Claves / notas exactas

- `uzu`: `bd`, `brk`, `cb`, `cp`, `cr`, `hh`, `ht`, `lt`, `misc`, `mt`, `oh`, `rd`, `rim`, `sd`, `sh`, `tb`
- `dirt`: `casio`, `crow`, `east`, `insect`, `jazz`, `metal`, `numbers`, `space`, `wind`
- `guitar`: `A#2` `A#3` `A#4` `A2` `A3` `A4` `B2` `B3` `B4` `C#3` `C#4` `C#5` `C3` `C4` `C5` `D#2` `D#3` `D#4` `D2` `D3` `D4` `D5` `E2` `E3` `E4` `F#2` `F#3` `F#4` `F2` `F3` `F4` `G#2` `G#3` `G#4` `G2` `G3` `G4`
- `trumpet`: `A#3` `A2` `A4` `C3` `C5` `D#3` `D4` `F2` `F4` `G3`
- `trumpet_stac`: `A#3` `A2` `A4` `C3` `C5` `D#3` `D4` `F2` `F3` `F4` `G3`
- `trombone`: `A#0` `A#1` `C#1` `C#3` `C3` `D#1` `D#3` `D2` `F1` `F2` `F3`
- `trombone_stac`: `A#0` `A#1` `A#2` `D3` `F1` `F2` `F3`

### Como cargarlos en el REPL de Strudel

En `miau-dio live`, pega esto en el editor:

    // drums: s("nombre")
    samples('https://raw.githubusercontent.com/tidalcycles/uzu-drumkit/main/strudel.json')
    s("bd sd hh hh")

    // percusion y texturas de dirt: s("nombre")
    samples('https://raw.githubusercontent.com/tidalcycles/Dirt-Samples/master/Dirt-Samples.json')
    s("casio crow wind")

    // guitarra: pitched, note("...").sound("guitar")
    samples('https://raw.githubusercontent.com/nbrosowsky/tonejs-instruments/master/samples/guitar-acoustic/guitar.json')
    note("C4 E4 G4 C5").sound("guitar")

    // trompeta sostenida: note("...").sound("trumpet")
    samples('https://raw.githubusercontent.com/sgossner/VSCO-2-CE/master/Brass/Trumpet/sus/trumpet.json')
    note("C4 E4 G4").sound("trumpet")

    // trompeta staccato: note("...").sound("trumpet_stac")
    samples('https://raw.githubusercontent.com/sgossner/VSCO-2-CE/master/Brass/Trumpet/stac/trumpet_stac.json')
    note("C4 E4 G4").sound("trumpet_stac")

    // trombon tenor sostenido: note("...").sound("trombone")
    samples('https://raw.githubusercontent.com/sgossner/VSCO-2-CE/master/Brass/Tenor%20Trombone/sus/trombone.json')
    note("C2 E2 G2").sound("trombone")

    // trombon tenor staccato: note("...").sound("trombone_stac")
    samples('https://raw.githubusercontent.com/sgossner/VSCO-2-CE/master/Brass/Tenor%20Trombone/stac/trombone_stac.json')
    note("C2 E2 G2").sound("trombone_stac")

El servidor reescribe esas URLs al vendor local; el REPL no toca internet.

## Notacion ABC (subset aceptado)

    X:1
    T:titulo
    M:4/4      compas
    L:1/8      duracion por defecto
    Q:1/4=120  tempo
    K:C        tonalidad
    C E G c|   notas

- Mayuscula = octava base, minuscula = una arriba.
- `C4` dura 4 unidades de `L`.
- `z` silencio, `|` barra.
- Rechazado: acordes `[CEG]`, ligaduras `-`, repeticiones `|:`, voces `V:`.

## Donde se guarda

    ~/.local/share/miau-dio/
    |-- abc/<id>.abc
    |-- audio/<id>.wav
    |-- instruments/
    |-- projects/
    |-- strudel/
    |   |-- samples/        wavs sueltos del usuario
    |   +-- cache/          packs opt-in instalados
    |-- index.json
    +-- config.json

Vendor (en el repo): `miau_dio/strudel/vendor/<pack>/`.

Proyecto con `--at`: `project.json`, `README.md`, `.gitignore`, `tracks/`, `patterns/`, `samples/`, `renders/`.

## Arquitectura

Ver [ARCHITECTURE.md](ARCHITECTURE.md).
