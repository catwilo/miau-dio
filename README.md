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
- `edit <id>` — abre el `.abc` en nvim (fallback nano), limpia caché de audio si hubo cambios
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

---

## Apendice: propuesta de proyecto — Territorios Sonoros

Contenidos digitales de creacion musical para la primera infancia,
presentado a la convocatoria "Territorios de Arte, Juego y Vida".

### La idea

Territorios Sonoros es una coleccion de canciones creadas por ninas y
ninos de 3 a 6 anos del municipio, hechas con los sonidos de su propio
territorio.

En encuentros en la biblioteca municipal, acompanados por sus familias,
los ninos componen eligiendo timbres, repitiendo patrones y decidiendo
el orden de los sonidos. No necesitan saber leer: esas decisiones ya
son musica. El material con el que juegan incluye rondas y arrullos
recuperados con los mayores del municipio, digitalizados y devueltos a
los ninos como sonidos vivos.

Todo funciona en el celular que la familia ya tiene, sin conexion ni
equipos adicionales. La inteligencia artificial que acompana la
creacion corre dentro del propio dispositivo, de modo que los datos de
los ninos nunca salen de alli.

### Que queda al final

| Entregable | Cantidad |
|---|---|
| Composiciones originales de primera infancia, catalogadas y publicadas | 120 obras |
| Rondas y arrullos del patrimonio oral local, digitalizados | 20 piezas |
| Guia pedagogica de creacion sonora 3-6 anos | 1 documento abierto |
| Biblioteca de timbres del patrimonio sonoro del municipio | 1 acervo |
| Familias participantes | 60 nucleos |
| Encuentros en la biblioteca municipal | 24 sesiones |

### Fases

1. **Recoleccion del patrimonio sonoro.** Grabacion de rondas, arrullos
   y cantos con los mayores del municipio. Construccion de la
   biblioteca de timbres locales.
2. **Adaptacion del motor a primera infancia.** Interfaz de juego sin
   texto: colores, figuras, metaforas. El nino no lee; toca.
3. **Encuentros en la biblioteca.** Sesiones con familias. Creacion
   acompanada. Cada encuentro produce obras.
4. **Catalogacion y circulacion.** Publicacion del acervo, entrega de
   la guia pedagogica, empaquetado para que otras bibliotecas puedan
   replicarlo.

### Equipo

| Rol | Perfil |
|---|---|
| Direccion tecnica | Desarrollo del motor, integracion de IA local, empaquetado |
| Direccion pedagogica | Profesional titulado en pedagogia infantil |
| Acompanamiento terapeutico | Profesional titulado en musicoterapia |
| Fundamentos musicales | Formacion teorica avanzada, diseno del contenido musical |
| Sede y convocatoria | Biblioteca municipal |

### Proteccion de la infancia

- Consentimiento informado escrito de padres o cuidadores, por
  participante y por obra publicada.
- Ningun dato personal de menores en servidores externos.
- Acompanante familiar presente en cada sesion.
- Profesionales titulados a cargo de los componentes pedagogico y
  terapeutico.
- Cumplimiento de la Ley 1581 de 2012 y de los lineamientos de
  MinCulturas y MinEducacion.

### Licenciamiento

La coleccion de canciones y la guia pedagogica quedan bajo licencia
abierta, disponibles para cualquier biblioteca publica del pais.

El motor (este repositorio) es un desarrollo previo aportado al
proyecto. Se distribuye bajo AGPL-3.0 mas CLA (Contributor License
Agreement), garantizando su uso libre y permanente para bibliotecas
publicas, instituciones educativas y comunidades. Sus autores
conservan la titularidad y los derechos de licenciamiento para usos
comerciales, lo que asegura la sostenibilidad del proyecto mas alla
del periodo de financiacion.
