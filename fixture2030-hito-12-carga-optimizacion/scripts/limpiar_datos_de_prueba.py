"""
Hito 12 - LIMPIEZA OPCIONAL. Solo borra lo que crea este hito:
  - keyspace fixture2030_carga en Cassandra (no toca fixture2030 del Hito 6)
  - claves muro:* y lock:muro:* en Redis (no toca sesiones ni cache del Hito 7)
No borra volumenes ni la carpeta de evidencia.

Uso:
    python scripts/limpiar_datos_de_prueba.py --confirmar
"""

import sys

import comun

if "--confirmar" not in sys.argv:
    sys.exit("Agregar --confirmar para borrar el keyspace %s y las claves muro:* de Redis" % comun.KEYSPACE)

cluster, session = comun.conectar_cassandra("system")
session.execute("DROP KEYSPACE IF EXISTS %s" % comun.KEYSPACE, timeout=60)
cluster.shutdown()

r = comun.conectar_redis()
claves = list(r.scan_iter("muro:*")) + list(r.scan_iter("lock:muro:*"))
if claves:
    r.delete(*claves)
print("Keyspace %s eliminado, %d claves de Redis eliminadas" % (comun.KEYSPACE, len(claves)))
