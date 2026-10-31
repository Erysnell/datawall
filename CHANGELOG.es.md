# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y el proyecto adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [1.2.0] - 2026-10-31

### Agregado

- **Notificaciones de escritorio al cruzar el límite diario.** El daemon
  dispara `notify-send` al 80% (urgencia normal) y al 100% (crítica), una
  vez por umbral por día, así el límite ya no depende de que justo corras
  un comando. Qué umbrales se dispararon se guarda en el día mismo, así que
  un reinicio no los repite y se rearman a medianoche; un fallo de entrega
  se reintenta en el ciclo siguiente. Configurable con `notify_thresholds`
  y `notifications` en `config.json`, y los cambios de límite se toman en
  menos de 60 segundos sin reiniciar. `libnotify-bin` es un `Recommends`,
  no una dependencia dura — sin él el daemon lo registra una vez y se queda
  callado.
- **`datawall status` ahora informa la salud del daemon en vez de una
  línea.** Distingue un proceso que está muestreando de uno que está vivo
  pero dejó de registrar —el modo de falla en el que un daemon muerto se ve
  bien por horas— usando el timestamp de `live.json`. Informa el pid, la
  antigüedad del último muestreo, la interfaz monitoreada, la velocidad
  actual, el uso de hoy contra el límite, y si la unidad de systemd del
  usuario está activa. Exit codes: `0` muestreando, `1` detenido, `2` vivo
  pero sin muestrear, así que sirve desde un script o un prompt de shell.
- `datawall limit` ahora informa si las notificaciones están realmente
  activas y en qué umbrales.
- Una suite de tests con `unittest` en `tests/` — 168 tests que cubren los
  parsers de tamaños y de la salida de `ss`, la migración de esquema, la
  poda por retención, el guardado condicional, todas las claves de config,
  los umbrales de notificación y la superficie de la CLI, más tests de
  integración que manejan un daemon real. Sin dependencias de test; se
  corren con `make test` o `make test-all`.

## [1.1.0] - 2026-10-31

Release de correcciones y diagnóstico. Todos los comandos de la 1.0.0 siguen
funcionando igual y los stores existentes se migran automáticamente, así que
actualizar no requiere ningún paso manual.

### Agregado

- `datawall explain [SEGUNDOS]` — mide de dónde sale el tráfico
  `unattributed` en vez de adivinarlo. Muestrea la interfaz, lo compara
  contra lo que pudo atribuir a sockets TCP, lee la mezcla TCP/UDP de
  `/proc/net/snmp` y ordena las causas probables por severidad. Avisa
  explícitamente cuando la muestra fue demasiado chica para concluir algo.
- `datawall --version`.
- Clave de config `interface`, para fijar la interfaz monitoreada cuando la
  detección automática elige la equivocada.
- Clave de config `retention_days` (90 por defecto).
- `~/.datawall/live.json`, con la velocidad actual del daemon y la interfaz
  monitoreada, para que las vistas lo consuman.

### Cambiado

- **El bucket `other` ahora se llama `unattributed`.** Los stores existentes
  se migran en la primera lectura: los contadores se fusionan, los totales se
  preservan y la migración es idempotente.
- **La selección de interfaz** ahora prefiere la ruta por defecto IPv4
  (`/proc/net/route`) en vez de la primera interfaz que el kernel listara,
  nunca elige automáticamente loopback ni interfaces virtuales (`docker*`,
  `br-*`, `virbr*`, `veth*`, `vmnet*`, `vboxnet*`), y se reevalúa cada 60
  segundos para detectar una VPN que sube o baja sin reiniciar.
- **`store.json` guarda solo el historial durable** y se escribe únicamente
  cuando los bytes acumulados realmente cambian. Las líneas base de
  contadores y las muestras de velocidad que antes persistía cada 5 segundos
  —y que nada leía nunca— se movieron a `live.json`. La línea base ahora vive
  en memoria del daemon, así que un reinicio la vuelve a sembrar en vez de
  atribuir el tráfico que pasó mientras nadie miraba.
- El daemon poda los días fuera de la ventana de retención al arrancar y en
  cada cambio de fecha, así el store ya no puede crecer indefinidamente.
- El reporte diario lee la velocidad actual de `live.json` cuando está fresca,
  en vez de gastar un segundo volviéndola a medir (1.21s a 0.21s medido acá).
- El reporte imprime una línea que apunta a `datawall explain` cuando
  `unattributed` supera el 15% del total.
- El modo watch acota su tabla a lo que cabe en el terminal y pliega el resto
  en una sola fila `… +N more` que conserva la velocidad y los totales
  combinados. Las filas se ordenan por bytes usados hoy, con la velocidad
  actual como desempate.
- `prerm` ahora detiene los daemons con un barrido por pid file que verifica
  el proceso antes de señalarlo, y usa `pkill` como respaldo en vez de como
  mecanismo principal.
- El `Makefile` deriva la versión del paquete de la constante `VERSION` del
  script y la inyecta en los metadatos al construir, así la versión vive en un
  solo lugar. `make version` la reporta y falla si no la puede leer.
- El paquete declara `iproute2` como dependencia; `ss` es necesario para el
  seguimiento por proceso.
- La URL de documentación de `datawall.service` ahora apunta a este proyecto y
  no a un repositorio ajeno.

### Corregido

- **`datawall reset` se revertía solo en menos de 5 segundos.** El daemon
  mantenía una única copia del store en memoria durante toda su vida y
  reescribía el día viejo encima del reset. Ahora relee el store cuando otro
  proceso lo escribió.
- **`datawall days N` crasheaba** con `ZeroDivisionError` cuando ningún día de
  la ventana tenía datos.
- **Un pico fantasma de gigabytes** podía quedar registrado cuando una
  interfaz desaparecía y volvía: la lectura fallida guardaba una línea base en
  cero, que el siguiente muestreo leía como el contador acumulado completo.
- La tabla del modo watch crecía todo el día y la pantalla alternativa la
  recortaba en silencio, sin forma de hacer scroll.
- La clave de ordenamiento del modo watch comparaba porcentajes contra bytes
  por segundo, así que un proceso con tráfico actual saltaba por encima de
  todo lo demás.
- El modo watch mostraba el estado del daemon calculado una sola vez al
  arrancar, así que el subtítulo quedaba mal el resto de la sesión.
- El nombre de la interfaz monitoreada nunca aparecía en el subtítulo del
  reporte: Rich parseaba `[wlo1]` como tag de estilo y lo descartaba.
- El patrón `pkill` del `prerm` estaba anclado a `^python3 `, que nunca
  matcheaba el daemon empaquetado — un shebang produce la línea de comando
  `/usr/bin/python3 /usr/bin/datawall run`.

## [1.0.0] - 2026-07-20

Primer release empaquetado.

### Agregado

- Daemon de muestreo que lee los contadores de red del kernel cada 5 segundos
  y atribuye el delta a los procesos con contadores exactos por socket de
  `ss -tpin` (SOCK_DIAG), con respaldo a atribución proporcional por cantidad
  de conexiones cuando `ss` no está disponible.
- Reporte diario con enviado/recibido/total por programa, barras de uso y
  velocidad de transferencia actual.
- `datawall watch` — monitor de ancho de banda por proceso en tiempo real.
- `datawall days N` — reporte agregado de los últimos N días con promedio
  diario.
- `datawall limit` — límite de tráfico diario con avisos visuales al 80% y al
  100%.
- `datawall connections` — conexiones TCP activas agrupadas por programa y
  dirección remota.
- Comandos de ciclo de vida del daemon (`start`, `run`, `stop`, `restart`,
  `status`) y `reset`.
- Empaquetado Debian y unidad systemd de usuario.

[1.2.0]: https://github.com/Erysnell/datawall/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Erysnell/datawall/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Erysnell/datawall/releases/tag/v1.0.0
