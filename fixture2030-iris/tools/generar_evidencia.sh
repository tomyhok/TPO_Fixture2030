#!/usr/bin/env bash
# =====================================================================
# Hito 9 - Fixture 2030 - Generar la evidencia de ejecución
# =====================================================================
# Compila las clases, corre la demo y comprueba la persistencia.
# Guarda la salida de cada paso en docs/evidencia/.
#
# Uso (desde fixture2030-iris/, con el contenedor levantado):
#   bash tools/generar_evidencia.sh
# =====================================================================

E=docs/evidencia
CONTENEDOR=fixture2030-iris

cd "$(dirname "$0")/.."

encabezado() { echo "# Fecha: $(date '+%Y-%m-%d %H:%M:%S %Z')"; echo "# $1"; }
# Ejecuta comandos ObjectScript en el Terminal de IRIS (namespace USER).
terminal() { printf '%s\nHalt\n' "$1" | docker exec -i $CONTENEDOR iris session IRIS -U USER; }

# Esperar a que IRIS esté listo (la imagen no trae healthcheck).
esperar() { until docker exec $CONTENEDOR iris qlist 2>/dev/null | grep -q '\^running'; do sleep 3; done; }
esperar

# --- 0) Ambiente ---
{
  encabezado "Ambiente"
  echo "> docker compose ps"; docker compose ps
  echo "> Version de IRIS"; terminal 'Write $ZVERSION,!'
} > $E/00_ambiente.txt 2>&1

# --- 1) Carga y compilación de las clases y la demo ---
{
  encabezado 'Do $system.OBJ.Load("/scripts/Fixture.Clases.cls","ck") y DemoOperaciones.mac'
  terminal 'Do $system.OBJ.Load("/scripts/Fixture.Clases.cls","ck")
Do $system.OBJ.Load("/scripts/DemoOperaciones.mac","ck")'
} > $E/01_compilacion.txt 2>&1

# --- 2) Demo: herencia, carga atómica, navegación, SQL y validaciones ---
{ encabezado "Do ^DemoOperaciones"; terminal 'Do ^DemoOperaciones'; } > $E/02_demo.txt 2>&1

# --- 3) Persistencia: reiniciar el contenedor y consultar por SQL ---
{
  encabezado "Persistencia: docker restart $CONTENEDOR y consultas SQL"
  docker restart $CONTENEDOR; sleep 5
  esperar
  terminal 'Do ##class(%SQL.Statement).%ExecDirect(,"SELECT ID, Sede, Estado, Arbitro->Apellido AS Arbitro FROM Fixture.Partido").%Display()
Write !
Do ##class(%SQL.Statement).%ExecDirect(,"SELECT ID, Minuto, Tipo, Partido FROM Fixture.Evento").%Display()
Write !
Do ##class(%SQL.Statement).%ExecDirect(,"SELECT ID, Nombre, Apellido, DNI FROM Fixture.Persona").%Display()'
} > $E/03_persistencia.txt 2>&1

echo "Evidencia generada en $E/"
