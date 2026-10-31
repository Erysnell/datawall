# datawall — Monitor de consumo de red por programa

> **English:** Also available in [English](README.md).

Las notas de cada release están en [CHANGELOG.es.md](CHANGELOG.es.md).

Monitor de tráfico de red por proceso para Linux. Muestra en una tabla
con barras visuales cuántos datos envió y recibió cada programa en el día,
junto con la velocidad actual.

```
╭─────────────────────────── DataWall — 2026-07-13 ────────────────────────────╮
│                                                                              │
│  ┏━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓        │
│  ┃ Program      ┃    Sent ┃ Received ┃    Total ┃ %                 ┃        │
│  ┣━━━━━━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━━╋━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━┫        │
│  ┃ firefox      ┃ 15.2 MB ┃  82.1 MB ┃  97.3 MB ┃ ██████░░░░  62.3% ┃        │
│  ┃ unattributed ┃  8.7 MB ┃  35.3 MB ┃  44.0 MB ┃ ██░░░░░░░░  28.2% ┃        │
│  ┃ discord      ┃  2.1 MB ┃  12.8 MB ┃  14.9 MB ┃ █░░░░░░░░░   9.5% ┃        │
│  ┃ TOTAL        ┃ 26.0 MB ┃ 130.2 MB ┃ 156.2 MB ┃                   ┃        │
│  ┗━━━━━━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━━┻━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━┛        │
│                                                                              │
╰────────────────── Speed:  ↑ 1.2 MB/s  ↓ 3.8 MB/s   [wlo1] ───────────────────╯
  'unattributed' is 28% — run datawall explain for the breakdown
  Daemon: running
```

## Requisitos

| Paquete | Propósito |
|---|---|
| `python3` | Entorno de ejecución |
| `python3-psutil` | Lectura de contadores de red del kernel |
| `python3-rich` | Tablas y barras en terminal |
| `iproute2` | Comando `ss` para datos exactos por socket (viene instalado en todo Linux) |
| `libnotify-bin` | *Opcional* — `notify-send` para las notificaciones de límite |

## Instalación

### Desde el .deb

```bash
sudo apt install ./datawall_1.2.0_all.deb
```

O con dpkg (las dependencias deben resolverse manualmente):

```bash
sudo dpkg -i datawall_1.2.0_all.deb
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
| `datawall explain` | Diagnostica de dónde sale el tráfico `unattributed` |
| `datawall explain N` | Igual, muestreando N segundos (default 4) |
| `datawall --version` | Muestra la versión |

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
- **Tráfico residual `unattributed`** — tráfico de interfaz que `ss`
  no capturó
- **Velocidad total de interfaz** — desde `psutil.net_io_counters()`

La tabla se acota a lo que cabe en el terminal — la pantalla alternativa
no puede hacer scroll — y los procesos restantes se plegan en una sola
fila `… +N more` que conserva su velocidad y totales combinados. Las
filas se ordenan por bytes usados hoy, con la velocidad actual como
desempate.

Presione `Ctrl+C` para salir.

### 6. Selección de interfaz

datawall monitorea una sola interfaz, elegida en este orden:

1. `"interface"` en `~/.datawall/config.json`, si está definida
2. La interfaz con la ruta por defecto IPv4 (`/proc/net/route`)
3. La primera interfaz no virtual con tráfico
4. La primera interfaz no virtual que esté activa

Nunca se eligen automáticamente loopback, `docker*`, `br-*`, `virbr*`,
`veth*`, `vmnet*` ni `vboxnet*`. El daemon reevalúa la elección cada 60
segundos, así que una VPN que sube o baja se detecta sin reiniciar.

Para fijarla a mano, agregala a la config:

```json
{ "interface": "wlo1" }
```

Monitorear la placa física en vez del túnel VPN mide lo que realmente
te cobra el proveedor, pero infla `unattributed` con el overhead del túnel.

### 7. Límite diario

`datawall limit 5GB` establece un límite de tráfico diario guardado en
`~/.datawall/config.json`. El reporte y el modo watch muestran
automáticamente una advertencia en el subtítulo cuando el uso se acerca
o supera el límite:

- **≥80%**: advertencia amarilla `⚠ Near limit: 4.5 GB / 5.0 GB (90%)`
- **≥100%**: advertencia roja `⚠ EXCEEDED: 6.2 GB / 5.0 GB (124%)`

El daemon no aplica el límite — no se limita ni bloquea nada.

**Notificaciones de escritorio.** El daemon además dispara una
notificación con `notify-send` cuando el uso cruza un umbral, una vez por
umbral por día, así te enterás sin tener que correr ningún comando. El 80%
se manda con urgencia normal y el 100% con urgencia crítica, para que
quede en pantalla.

Qué umbrales ya se dispararon se guarda en el día mismo, así que un
reinicio del daemon no los repite, y se rearman solos a medianoche (o
después de un `datawall reset`). Si la entrega falla —por ejemplo porque
al arrancar todavía no hay bus de sesión— se reintenta en el ciclo
siguiente en vez de perderse.

`datawall limit` informa si las notificaciones están realmente activas:

```
datawall: daily limit: 200.0 MB  (734.3 MB used — 367.2%)
datawall: notifications: on at 80%, 100%
```

Los umbrales y la funcionalidad misma se configuran en
`~/.datawall/config.json`:

```json
{
  "daily_limit": 209715200,
  "notify_thresholds": [50, 80, 100],
  "notifications": false
}
```

Las notificaciones necesitan `notify-send` (paquete `libnotify-bin` en
Debian y Ubuntu). Sin él, el daemon lo registra una vez al arrancar y se
queda callado. Los cambios de límite se toman en menos de 60 segundos,
sin reiniciar.

Use `datawall limit off` para eliminar el límite.

### 8. Diagnóstico del tráfico no atribuido

`datawall explain` responde "¿por qué `unattributed` es tan grande?" con
mediciones, no con suposiciones. Muestrea unos segundos y reporta:

- **A dónde fueron los bytes** — bytes de la interfaz contra los que pudo
  atribuir a sockets TCP, y el residuo.
- **Mezcla de protocolos** — tasa de segmentos TCP y datagramas UDP, más
  una estimación de los bytes de cabecera TCP/IP que los contadores de
  payload nunca pueden ver.
- **Causas probables, ordenadas** — derivadas de lo que realmente observó:
  un túnel por debajo de la interfaz monitoreada, una ruta por defecto en
  otra interfaz, UDP superando a TCP, overhead de cabeceras, sockets sin
  dueño visible.

Muestreá más tiempo y con algo descargando para obtener una lectura útil:

```bash
datawall explain 30
```

Unos segundos con el enlace en reposo no miden casi nada, y el comando lo
dice en vez de reportar un 100% sin sentido.

### 9. Visor de conexiones

`datawall connections` toma una foto de todos los sockets TCP activos
vía `ss -tpin` y los agrupa por `(programa, IP_remota:puerto)`,
mostrando bytes enviados/recibidos por endpoint remoto con barra de
porcentaje relativa al total del programa.

## Precisión

| Componente | Fuente | Precisión |
|---|---|---|
| Total del día | `net_io_counters()` | **100%** |
| Por programa (TCP) | `ss -tpin` delta por socket | **~99%** |
| `unattributed` | Tráfico que ningún socket TCP explicó — ver abajo | Variable |

### Qué es `unattributed`

`unattributed` (se llamaba `other` antes de la 1.1.0) no es un programa.
Es la diferencia entre lo que contó la interfaz y lo que los sockets TCP
visibles pudieron explicar, en orden de impacto típico:

1. **Una VPN por debajo de la interfaz monitoreada.** Si la ruta por
   defecto es un túnel pero se monitorea una placa física, `ss` reporta
   el payload del túnel mientras la placa cuenta ese mismo tráfico
   encapsulado y cifrado. Toda la diferencia es inatribuible. datawall
   monitorea la interfaz de la ruta por defecto justamente para evitarlo.
2. **UDP no se mide.** `ss -tpin` es solo TCP, así que QUIC/HTTP3 (como
   los navegadores transmiten video hoy), DNS, DHCP, WireGuard y las
   videollamadas caen todas acá.
3. **Overhead de cabeceras.** `net_io_counters()` cuenta tramas
   completas; `bytes_acked` cuenta solo payload. ~5-10% estructural.
4. **Procesos de otros usuarios o de root.** Sin privilegios `ss` no
   puede asociar sus sockets a un PID, así que el tráfico de `apt`,
   `systemd-resolved` y `NetworkManager` queda sin atribuir.
5. **Sockets efímeros** que nacen y mueren entre dos muestreos.
6. Retransmisiones, ICMP, ARP, multicast.

## Retención

El daemon conserva los últimos 90 días y descarta los más viejos, así el
store no crece indefinidamente. La ventana se cambia en
`~/.datawall/config.json`:

```json
{ "retention_days": 365 }
```

La poda corre al arrancar el daemon y de nuevo en cada cambio de fecha.

## Formato del store

`~/.datawall/store.json` guarda solo el historial durable, y se escribe
únicamente cuando los bytes acumulados realmente cambian:

```json
{
  "days": {
    "2026-07-13": {
      "total_sent": 26000000,
      "total_recv": 130200000,
      "notified": [80, 100],
      "processes": {
        "firefox":      { "sent": 15200000, "recv": 82100000 },
        "discord":      { "sent": 2100000,  "recv": 12800000 },
        "unattributed": { "sent": 8700000,  "recv": 35300000 }
      }
    }
  }
}
```

`notified` registra qué umbrales del límite ya se dispararon hoy, para
que un reinicio del daemon no los repita. Es el único estado por día que
vive acá y no en `live.json`, justamente porque tiene que sobrevivir a un
reinicio.

El bucket `unattributed` se llamaba `other` antes de la 1.1.0. Los stores
existentes se migran automáticamente en la primera lectura, y las líneas
base de contadores y las muestras de velocidad que antes se persistían
acá ahora viven en `~/.datawall/live.json`, que el reporte lee para
mostrar la velocidad actual sin volver a medirla.

## Solución de problemas

**El daemon no encuentra la interfaz:** Asegurate de tener una interfaz de
red activa (WiFi o ethernet). El loopback y las interfaces virtuales
(`docker*`, `br-*`, `virbr*`, `veth*`, `vmnet*`, `vboxnet*`) nunca se
eligen automáticamente; si la detección falla, fijá una con
`{"interface": "..."}` en `~/.datawall/config.json`.

**El reporte muestra 0 bytes:** El daemon necesita al menos 5 segundos para
acumular datos después de iniciar. `datawall days N` mostrará 0 para
fechas futuras sin datos.

**`unattributed` tiene un % alto:** Corré `datawall explain 30` con algo
descargando — mide la causa real en vez de adivinarla. La más común por
lejos es un túnel VPN por debajo de la interfaz monitoreada; ver
"Selección de interfaz".

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
├── CHANGELOG.md              # Notas de release
├── CHANGELOG.es.md           # Notas de release en español
├── tests/                    # suite de unittest (ver tests/README.md)
├── .gitignore
├── pkg/
│   └── debian/
│       ├── control           # Metadatos del paquete Debian
│       ├── postinst          # Post-instalación
│       └── prerm             # Pre-eliminación
```

### Tests

```bash
make test        # suite rápida: sin red, sin daemon (~7s)
make test-all    # agrega los de integración (~4min, necesita red)
```

Usa `unittest` de la biblioteca estándar, así que no hay dependencias de
test. `test_daemon.py` arranca un daemon real contra un `HOME` descartable
y se saltea salvo que definas `DATAWALL_SLOW_TESTS=1`. Ver
[tests/README.md](tests/README.md).

### Construir el .deb

```bash
make deb
```

Genera `datawall_1.2.0_all.deb`.

### Limpiar

```bash
make clean
```

## Licencia

MIT
