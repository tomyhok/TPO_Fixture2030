# Grupo 4 — Hito 9: entidades complejas en IRIS

El modelo demuestra identidad, herencia, relación padre-hijo, guardado, navegación y proyección
SQL con los contenidos de la Clase 10. La corrección reduce los mecanismos adicionales.

## Modelo y alcance

`Persona` tiene Nombre, Apellido y DNI tipados y obligatorios. `Arbitro` hereda Persona y agrega
Rango; `Tecnico` agrega Licencia. `Partido` tiene Sede, Fecha, Estado, referencia a Arbitro y
una colección de hijos Evento. Evento tiene Minuto, Tipo, Descripcion y relación inversa al padre.
Codigo permite identificar el partido para la integración posterior; su índice único evita
duplicar ese identificador. Es opcional para conservar objetos de la demostración anterior.

Se conservan propiedades tipadas y Required. Se eliminan listas de valores, límites de rango
y el callback de guardado. No se introduce una regla distinta para cada atributo.
La **única regla de dominio** es `Partido.AgregarEvento`: rechaza agregar un evento cuando el
partido ya está Finalizado. El método encapsula creación del hijo, asociación y `%Save()`.
El ejemplo enseña a usar ese método: no pretende impedir modificaciones externas mediante SQL
o acceso directo a la colección. Una política global de autorización queda fuera del hito.

## Ejecutar

Con Docker disponible, levantar el servicio con el Compose raíz o el del módulo, usando uno
solo. El almacenamiento durable sigue en el directorio del host configurado en Compose.
No es necesario borrar datos existentes para compilar esta corrección.

```sh
docker exec -it fixture2030-iris iris session IRIS -U USER
```

En ObjectScript:

```objectscript
Do $SYSTEM.OBJ.Load("/scripts/Fixture.Clases.cls","ck")
Do $SYSTEM.OBJ.Load("/scripts/DemoOperaciones.mac","ck")
Do ^DemoOperaciones
```

La rutina crea P-009 si no existe; una segunda ejecución conserva esa muestra y avisa.
No borra ni reinicia actas ajenas. Muestra herencia, un `%Save()` del padre con sus dos hijos,
reapertura y navegación del árbitro/hijos/padre, y SELECT sobre la misma proyección mediante
`%SQL.Statement.%ExecDirect`. El guardado sin Sede demuestra Required. Finalmente guarda
Finalizado y verifica que AgregarEvento es rechazado sin cambiar la cantidad de eventos.

## Evidencia

[Compilación y demostración real](docs/revision_2026-10-19/compilacion_y_demo.txt): cinco clases
compiladas, partido guardado con dos eventos, navegación y SQL, rechazo de propiedad obligatoria
omitida y `REGLA_OK`, eventos antes=2 y después=2. Antes de compilar se exportaron las definiciones
del entorno como respaldo local. No se borraron objetos existentes.

Las capturas de `docs/evidencia/` corresponden a la implementación anterior; no prueban los
mecanismos eliminados en la versión actual. El Hito 10 consulta estas clases por SQL/DB-API y
no necesita una clase de fachada ni métodos adicionales de escritura.
