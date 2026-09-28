# miau-dio

CLI para prototipar, organizar y generar música desde la consola.
Se apoya en motores que ya existen (abc2midi, timidity, FluidSynth,
Strudel, FFmpeg, mpv) y aporta la capa que los coordina: ideas,
instrumentos, proyectos y sesiones de live coding.

Cero dependencias de Python (solo stdlib). Funciona en **Debian** y
**Termux (Android)** sin root.

---

## Flujo de uso

Tres modos conviven:

- **Idea** — escribes notación ABC, la guardas con tags y notas, y la oyes
  al instante: `abc → abc2midi → timidity|fluidsynth → wav → suena`.
- **Proyecto** — una canción con varias pistas, metadata (tempo, compás,
  tonalidad) y contenido desacoplado del motor. Puede vivir en el store
  global (XDG) o como directorio autocontenido versionable con git.
- **Live** — un REPL de Strudel servido localmente, sin depender de
  internet en tiempo de ejecución, con catálogo de samples que se instala
  a demanda.

---

## Instalación

    git clone git@github.com:catwilo/miau-dio.git
    cd miau-dio
    ./install.sh

`install.sh` enlaza el comando `miau-dio` (symlink, nunca copia: un
`git pull` actualiza el binario sin reinstalar), compila `abc2midi` desde
las fuentes incluidas y ofrece instalar los backends (`timidity`,
`fluidsynth`, `sox`). No usa `pip`.

Si el comando no aparece, añade `~/.local/bin` (o `$PREFIX/bin` en
Termux) al PATH.

---

## Inicio rápido

    miau-dio idea new "mi primera idea"   # editor → guardas → suena
    miau-dio idea list                    # ves tus ideas
    miau-dio backend selftest             # verifica que todo va
    miau-dio live                         # REPL de Strudel local
    miau-dio sample list                  # qué packs de samples hay
    miau-dio sample install uzu           # baja un pack al disco

---

## Comandos

La CLI tiene una jerarquía de grupos. Todos los grupos tienen `--help`.

### idea — piezas musicales en ABC

- `idea new <nombre>` — plantilla en editor, al guardar la convierte en
  idea y suena. Acepta `--key`, `--meter`, `--unit`, `--bpm`, `-t/--tag`,
  `-n/--note`, `--silent`.
- `idea add <nombre> <archivo.abc>` — guarda un `.abc` existente.
- `idea list [--tag X] [-s QUERY] [--json]` — lista / filtra / busca.
- `idea show <id>` — detalle completo.
- `idea edit <id>` — abre el `.abc` en `$EDITOR` (o nvim / nano). Si hubo
  cambios, limpia la caché de audio.
- `idea rename <id> <nuevo>` / `idea dup <id> [--name]` — el id es estable
  y no cambia.
- `idea tag <id> --add X --rm Y` / `idea note <id> "texto"`.
- `idea assign <id> --program N [--at K]` — escribe un `%%MIDI program` en
  el `.abc` (fijo, o antes de la nota K).
- `idea rm <id> [-y]`.

### instr — biblioteca de instrumentos

- `instr add <nombre> <program 0-127> [--family X]`
- `instr list [--json]` / `instr show <nombre>`
- `instr dup <nombre> [--name]` / `instr rename <viejo> <nuevo>`
- `instr rm <nombre> [-y]`
- `family list` — etiquetas de familia distintas en uso.

### play — render y reproducción

- `play file <archivo.abc> [--out out.wav] [--sf soundfont.sf2]
  [--engine timidity|fluidsynth]` — renderiza un `.abc` suelto.
- `play idea <id> [--engine ...] [--sf ...] [--silent] [--random
  [--seed N] [--min-duration F]]` — reproduce una idea guardada;
  `--random` reasigna programas al azar desde la biblioteca.

### project — proyectos musicales

- `project new <nombre> [--tempo N] [--meter N/M] [--key X]
  [--track "name:type[:content]"]... [--at <ruta>]`
  Sin `--at`, el proyecto se guarda en el store XDG. Con `--at`, se
  materializa un directorio autocontenido con `project.json`,
  `tracks/`, `patterns/`, `samples/`, `renders/`, `README.md` y
  `.gitignore`, listo para versionarse con git.
- `project list [--json]` / `project show <id> [--at <ruta>]` /
  `project rm <id> [-y]`.

### live — REPL de Strudel local

- `live [--url URL] [--port N]` — arranca un servidor HTTP local que
  sirve el **REPL oficial de Strudel** vendorizado en el repo, abre el
  navegador y bloquea hasta Ctrl+C. Todo el motor corre en el navegador
  (Web Audio), el servidor solo reparte archivos. Sin `--url`, la sesión
  es offline: las peticiones a hosts remotos (samples, hydra) se
  reescriben a `/shim/<host>/<path>` y se resuelven desde el cache local
  en `XDG_DATA_HOME/miau-dio/strudel/cache/`.

### sample — gestión del catálogo de samples

- `sample list [--json]` — packs disponibles en el catálogo.
- `sample info <nombre>` — descripción, licencia, tamaño aproximado,
  URL del manifest.
- `sample installed [--json]` — qué hay en disco y cuánto ocupa.
- `sample install <nombre>...` — descarga un pack al cache local
  (`XDG_DATA_HOME/miau-dio/strudel/cache/<host>/<path>`), con todos sus
  archivos y su manifest.
- `sample remove <nombre>... [-y]` — borra un pack del cache.

Los packs se guardan **fuera del repositorio**, en el directorio XDG del
usuario. El repo solo contiene el catálogo (metadata, unos pocos KB).

### config — defaults persistentes para `idea new`

- `config show` — valores actuales.
- `config set <campo> <valor>` — `key`, `meter`, `unit` o `bpm`.

Precedencia: flag > config guardada > fábrica (`C`, `4/4`, `1/8`, `120`).

### backend — dependencias externas

- `backend setup --profile <minimal|playback|full>` — instala el set.
- `backend status` — qué binarios hay.
- `backend selftest [--full]` — autoverificación (con audio en `--full`).

---

## Notación ABC (lo mínimo)

    X:1
    T:título
    M:4/4          compás
    L:1/8          duración por defecto de cada nota
    Q:1/4=120      tempo (BPM)
    K:C            tonalidad
    C E G c|       las notas

- Notas: `A B C D E F G` (mayúscula = octava base, minúscula = una arriba).
- Duración: número tras la nota la alarga → `C4` dura 4.
- Acorde Cmaj7 arpegiado: `C E G B|`.
- Silencio: `z` — Barra de compás: `|`.

El parser solo acepta el subset listado arriba; todo lo demás (corchetes
de acorde `[CEG]`, ligaduras `-`, repeticiones `|:`, voces `V:`) se
rechaza con un mensaje claro.

---

## Dónde se guarda

**Estado global** (store XDG, por usuario):

    ~/.local/share/miau-dio/
    ├── abc/<id>.abc                  ideas
    ├── audio/<id>.wav                caché de audio de ideas
    ├── instruments/                  biblioteca de instrumentos
    │   ├── index.json
    │   └── <nombre>.json
    ├── projects/                     proyectos (store XDG)
    │   ├── index.json
    │   └── <id>/project.json
    ├── strudel/
    │   ├── samples/                  wavs sueltos del usuario
    │   └── cache/                    packs instalados
    ├── index.json                    índice de ideas
    └── config.json                   defaults de `idea new`

**Proyecto autocontenido** (con `--at <ruta>`):

    <ruta>/
    ├── project.json
    ├── README.md
    ├── .gitignore
    ├── tracks/
    ├── patterns/
    ├── samples/
    └── renders/

Los renders y caches quedan fuera de git (por `.gitignore`).

En todos los casos el `id` (8 hex derivado de `os.urandom`) es estable e
independiente del nombre: renombrar nunca rompe artefactos.

---

## Ejemplo completo

    miau-dio config set key Am
    miau-dio idea new "riff oscuro" -t bajo
    miau-dio idea list --tag bajo
    miau-dio idea duplicate a1b2c3d4 --name "riff oscuro v2"
    miau-dio idea note a1b2c3d4 "subir tempo a 140"
    miau-dio play idea a1b2c3d4 --engine fluidsynth

    miau-dio project new "mi canción" --tempo 95 --meter 3/4 --key Am \
      --track "bass:midi:C E G" --track "drum:pattern:bd sd" \
      --at ~/musica/mi-cancion
    cd ~/musica/mi-cancion && git init && git add . && git commit -m "inicio"

    miau-dio sample list
    miau-dio sample install uzu dirt
    miau-dio live --port 8765

---

## Arquitectura

Ver [ARCHITECTURE.md](ARCHITECTURE.md): mapa de módulos, responsabilidades
por archivo, invariantes y dónde buscar cuando algo falla.

---

## Licencia

AGPL-3.0 + CLA. Ver la sección de licenciamiento en el apéndice.

---

## Apéndice: propuesta de proyecto — Territorios Sonoros

Contenidos digitales de creación musical para la primera infancia,
presentado a la convocatoria "Territorios de Arte, Juego y Vida".

### La idea

Territorios Sonoros es una colección de canciones creadas por niñas y
niños de 3 a 6 años del municipio, hechas con los sonidos de su propio
territorio.

En encuentros en la biblioteca municipal, acompañados por sus familias,
los niños componen eligiendo timbres, repitiendo patrones y decidiendo
el orden de los sonidos. No necesitan saber leer: esas decisiones ya
son música. El material con el que juegan incluye rondas y arrullos
recuperados con los mayores del municipio, digitalizados y devueltos a
los niños como sonidos vivos.

Todo funciona en el celular que la familia ya tiene, sin conexión ni
equipos adicionales. La inteligencia artificial que acompaña la
creación corre dentro del propio dispositivo, de modo que los datos de
los niños nunca salen de allí.

### Qué queda al final

| Entregable | Cantidad |
|---|---|
| Composiciones originales de primera infancia, catalogadas y publicadas | 120 obras |
| Rondas y arrullos del patrimonio oral local, digitalizados | 20 piezas |
| Guía pedagógica de creación sonora 3-6 años | 1 documento abierto |
| Biblioteca de timbres del patrimonio sonoro del municipio | 1 acervo |
| Familias participantes | 60 núcleos |
| Encuentros en la biblioteca municipal | 24 sesiones |

### Fases

1. **Recolección del patrimonio sonoro.** Grabación de rondas, arrullos
   y cantos con los mayores del municipio. Construcción de la
   biblioteca de timbres locales.
2. **Adaptación del motor a primera infancia.** Interfaz de juego sin
   texto: colores, figuras, metáforas. El niño no lee; toca.
3. **Encuentros en la biblioteca.** Sesiones con familias. Creación
   acompañada. Cada encuentro produce obras.
4. **Catalogación y circulación.** Publicación del acervo, entrega de
   la guía pedagógica, empaquetado para que otras bibliotecas puedan
   replicarlo.

### Equipo

| Rol | Perfil |
|---|---|
| Dirección técnica | Desarrollo del motor, integración de IA local, empaquetado |
| Dirección pedagógica | Profesional titulado en pedagogía infantil |
| Acompañamiento terapéutico | Profesional titulado en musicoterapia |
| Fundamentos musicales | Formación teórica avanzada, diseño del contenido musical |
| Sede y convocatoria | Biblioteca municipal |

### Protección de la infancia

- Consentimiento informado escrito de padres o cuidadores, por
  participante y por obra publicada.
- Ningún dato personal de menores en servidores externos.
- Acompañante familiar presente en cada sesión.
- Profesionales titulados a cargo de los componentes pedagógico y
  terapéutico.
- Cumplimiento de la Ley 1581 de 2012 y de los lineamientos de
  MinCulturas y MinEducación.

### Licenciamiento

La colección de canciones y la guía pedagógica quedan bajo licencia
abierta, disponibles para cualquier biblioteca pública del país.

El motor (este repositorio) es un desarrollo previo aportado al
proyecto. Se distribuye bajo AGPL-3.0 más CLA (Contributor License
Agreement), garantizando su uso libre y permanente para bibliotecas
públicas, instituciones educativas y comunidades. Sus autores
conservan la titularidad y los derechos de licenciamiento para usos
comerciales, lo que asegura la sostenibilidad del proyecto más allá
del periodo de financiación.
