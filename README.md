# miau-dio

CLI para prototipar y guardar ideas musicales desde la consola.
Escribes notación ABC, la guardas con tags y notas, y la oyes al instante.

Cero dependencias de Python. Funciona en **Debian** y **Termux (Android)**.

---

## Flujo de uso

escribes ABC → se guarda como idea → abc2midi → timidity → wav → suena

Cada idea vive como texto (`.abc`, kilobytes) más metadatos. El audio se renderiza al reproducir y se cachea.

---

## Instalación

    git clone git@github.com:catwilo/miau-dio.git
    cd miau-dio
    ./install.sh

Genera el comando `miau-dio`, compila `abc2midi` desde fuentes incluidas, instala `timidity` y `sox`. No usa pip. Si el comando no aparece, añade `~/.local/bin` al PATH.

---

## Inicio rápido

    miau-dio new "mi primera idea"   # editor → guardas → suena
    miau-dio list                    # ves tus ideas
    miau-dio selftest                # verifica que todo va

---

## Comandos

**Crear**
- `new <nombre>` — plantilla en editor, al guardar la convierte en idea y suena. Acepta `--key Am --meter 3/4 --bpm 90 -t tag -n "nota" --silent`
- `save <nombre> <archivo.abc>` — guarda un `.abc` existente

**Ver y buscar**
- `list` — todas las ideas
- `list --tag bajo` — filtra por tag
- `list -s riff` — busca en nombre y notas
- `list --json` — salida JSON
- `show <id>` — detalle completo
- `tags` — todos los tags en uso

**Reproducir**
- `play-saved <id>` — renderiza/usa caché y suena
- `play-saved <id> --silent` — solo renderiza
- `play <archivo.abc>` — renderiza un `.abc` suelto a `.wav`

**Editar**
- `tag <id> --add wip --rm demo` — añade/quita tags
- `note <id> "texto"` — reemplaza notas
- `rename <id> "nombre"` — renombra (id no cambia)
- `duplicate <id> --name "v2"` — copia independiente
- `delete <id> -y` — borra idea y audio

**Configuración** (defaults persistentes para `new`)
- `config show` — defaults actuales
- `config set key Am` — cambia `key`, `meter`, `unit` o `bpm`

Precedencia: flag > config guardada > fábrica (C, 4/4, 1/8, 120).

**Mantenimiento**
- `setup --profile playback` — instala backends (`minimal`/`playback`/`full`)
- `status` — qué backends hay
- `selftest` / `selftest --full` — autoverificación (con audio el `--full`)

---

## Notación ABC (lo mínimo)

    X:1
    T:título
    M:4/4          compás
    L:1/8          duración por defecto de cada nota
    Q:1/4=120      tempo (BPM)
    K:C            tonalidad
    C E G c|       las notas

- Notas: `A B C D E F G` (mayúscula = octava base, minúscula = una arriba)
- Duración: número tras la nota la alarga → `C4` dura 4
- Acorde Cmaj7 arpegiado: `C E G B|`
- Silencio: `z` — Barra de compás: `|`

---

## Dónde se guarda

    ~/.local/share/miau-dio/
    ├── abc/<id>.abc      ideas (texto, versionable)
    ├── audio/<id>.wav    caché de audio (regenerable)
    ├── index.json        metadatos
    └── config.json       tus defaults

El `id` es estable e independiente del nombre: renombrar nunca rompe nada.

---

## Ejemplo completo

    miau-dio config set key Am
    miau-dio new "riff oscuro" -t bajo
    miau-dio list --tag bajo
    miau-dio duplicate a1b2c3d4 --name "riff oscuro v2"
    miau-dio note a1b2c3d4 "subir tempo a 140"
    miau-dio play-saved a1b2c3d4
