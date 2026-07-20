# datawall — Monitor de consumo de red por programa

Monitor de tráfico de red por proceso para Linux. Muestra en una tabla
con barras visuales cuántos datos envió y recibió cada programa en el día,
junto con la velocidad actual.

```
╭─────────────────────────── DataWall — 2026-07-13 ────────────────────────────╮
│                                                                              │
│  ┏━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓           │
│  ┃ Program  ┃    Sent ┃ Received ┃    Total ┃ %                 ┃           │
│  ┣━━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━━╋━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━┫           │
│  ┃ firefox  ┃ 15.2 MB ┃  82.1 MB ┃  97.3 MB ┃ ████████░░  62.2% ┃           │
│  ┃ discord  ┃  2.1 MB ┃  12.8 MB ┃  14.9 MB ┃ ██░░░░░░░░   9.6% ┃           │
│  ┃ other    ┃  8.7 MB ┃  35.3 MB ┃  44.0 MB ┃ ███░░░░░░░  28.2% ┃           │
│  ┃ TOTAL    ┃ 26.0 MB ┃ 140.2 MB ┃ 166.2 MB ┃                   ┃           │
│  ┗━━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━━┻━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━┛           │
│                                                                              │
╰──────────────────── Speed:  ↑ 1.2 MB/s  ↓ 3.8 MB/s   [wlo1] ────────────────╯
  Daemon: running
```

## Requisitos

| Paquete | Propósito |
|---|---|
| `python3` | Entorno de ejecución |
| `python3-psutil` | Lectura de contadores de red del kernel |
| `python3-rich` | Tablas y barras en terminal |
| `iproute2` | Comando `ss` para datos exactos por socket (viene instalado en todo Linux) |

## Instalación

### Desde el .deb

```bash
sudo apt install ./datawall_1.0.0_all.deb
```

O con dpkg (las dependencias deben resolverse manualmente):

```bash
sudo dpkg -i datawall_1.0.0_all.deb
sudo apt install -f
```

### Manual

```bash
pip install psutil rich
chmod +x datawall
ln -sf "$PWD/datawall" ~/.local/bin/datawall
```

## Uso

| Comando | Descripción |
|---|---|
| `datawall` | Muestra el reporte del día |
| `datawall start` | Inicia el daemon en background |
| `datawall stop` | Detiene el daemon |
| `datawall restart` | Reinicia el daemon |
| `datawall status` | Muestra si el daemon está corriendo |
| `datawall reset` | Resetea los datos acumulados de hoy |
| `datawall watch` | Monitor de ancho de banda en tiempo real (top/htop) |
| `datawall days N` | Reporte agregado de los últimos N días |
| `datawall limit` | Muestra el límite diario y el uso actual |
| `datawall limit SIZE` | Establece límite diario (ej. 5GB, 500MB) |
| `datawall limit off` | Elimina el límite diario |
| `datawall connections` | Muestra conexiones TCP activas por IP remota |

## Auto-inicio con systemd

```bash
systemctl --user enable --now datawall.service
```

## Cómo funciona

### 1. Daemon de muestreo

El daemon corre en background y cada 5 segundos:

1. Lee los contadores totales de red desde el kernel (`psutil.net_io_counters`)
2. Toma una foto de todos los sockets TCP abiertos con sus bytes exactos
3. Compara contra la foto anterior y calcula cuántos bytes movió cada socket
4. Acumula esos bytes por nombre de proceso en `~/.datawall/store.json`

### 2. Seguimiento exacto por proceso (SOCK_DIAG)

Usa `ss -tpin` para leer del kernel, vía netlink, los contadores exactos
por socket TCP: `bytes_acked` (enviados) y `bytes_received` (recibidos).

Cada socket se identifica por `(pid, fd)`. El daemon guarda el último valor
visto de cada socket y calcula el delta en el próximo muestreo.

Si `ss` no está disponible, cae automáticamente al método de atribución
proporcional por cantidad de conexiones.

### 3. Reporte

Al ejecutar `datawall` sin argumentos, lee `~/.datawall/store.json` y
muestra una tabla con Rich con:

- Bytes enviados, recibidos y total por programa
- Barra visual de uso relativo
- Velocidad actual (medición en vivo de 1 segundo)
- Estado del daemon

### 4. Reportes históricos

`datawall days 7` (o 30, 90, etc.) agrega datos de múltiples días
desde `store.json`, sumando los totales por programa y mostrando un
promedio por día.

### 5. Modo watch

`datawall watch` abre una interfaz en tiempo real (pantalla alternativa,
como `top`/`htop`) que se actualiza cada 2 segundos mostrando:

- **Velocidad de subida/bajada por proceso** — muestreando `ss -tpin`
  con caché de sockets y corrección de timing
- **Totales acumulados del día** — leídos en vivo desde `store.json`
  (recargado en cada ciclo, los cambios del daemon aparecen solos)
- **Tráfico residual "other"** — tráfico de interfaz no capturado por `ss`
- **Velocidad total de interfaz** — desde `psutil.net_io_counters()`

Presione `Ctrl+C` para salir.

### 6. Límite diario

`datawall limit 5GB` establece un límite de tráfico diario guardado en
`~/.datawall/config.json`. El reporte y el modo watch muestran
automáticamente una advertencia en el subtítulo cuando el uso se acerca
o supera el límite:

- **≥80%**: advertencia amarilla `⚠ Near limit: 4.5 GB / 5.0 GB (90%)`
- **≥100%**: advertencia roja `⚠ EXCEEDED: 6.2 GB / 5.0 GB (124%)`

El daemon no aplica el límite — es solo una alerta visual en la UI.
Use `datawall limit off` para eliminarlo.

### 7. Visor de conexiones

`datawall connections` toma una foto de todos los sockets TCP activos
vía `ss -tpin` y los agrupa por `(programa, IP_remota:puerto)`,
mostrando bytes enviados/recibidos por endpoint remoto con barra de
porcentaje relativa al total del programa.

## Precisión

| Componente | Fuente | Precisión |
|---|---|---|
| Total del día | `net_io_counters()` | **100%** |
| Por programa (TCP) | `ss -tpin` delta por socket | **~99%** |
| "other" | Tráfico no atribuido (UDP, conexiones fugaces entre muestreos, retransmisiones) | Variable |

## Formato del store

Los datos se guardan en `~/.datawall/store.json`:

```json
{
  "days": {
    "2026-07-13": {
      "total_sent": 26000000,
      "total_recv": 140200000,
      "processes": {
        "firefox": { "sent": 15200000, "recv": 82100000 },
        "discord": { "sent": 2100000,  "recv": 12800000 },
        "other":   { "sent": 8700000,  "recv": 35300000 }
      }
    }
  }
}
```

## Solución de problemas

**El daemon no encuentra la interfaz:** Asegurate de tener una interfaz de
red activa (WiFi o ethernet). El loopback (`lo`) se ignora automáticamente.

**El reporte muestra 0 bytes:** El daemon necesita al menos 5 segundos para
acumular datos después de iniciar. `datawall days N` mostrará 0 para
fechas futuras sin datos.

**"other" tiene un % alto:** Es normal en los primeros muestreos. Con el
paso de los minutos el porcentaje se estabiliza. Un % alto sostenido
indica tráfico UDP o conexiones muy cortas (API calls, DNS).

**Reiniciar datos:** `datawall reset` borra los datos del día actual.

## Desarrollo

### Estructura del proyecto

```
datawall/
├── datawall                  # Script principal (Python, ejecutable)
├── datawall.service          # Unidad de systemd user
├── Makefile                  # Build helper
├── README.md                 # Documentación en inglés
├── README.es.md              # Documentación en español (este archivo)
├── .gitignore
├── pkg/
│   └── debian/
│       ├── control           # Metadatos del paquete Debian
│       ├── postinst          # Post-instalación
│       └── prerm             # Pre-eliminación
```

### Construir el .deb

```bash
make deb
```

Genera `datawall_1.0.0_all.deb`.

### Limpiar

```bash
make clean
```

## Licencia

MIT
