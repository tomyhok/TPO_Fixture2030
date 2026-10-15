/// Hito 10 - Fachada de objetos que consume la API REST.
/// <p>Cada método trabaja con el modelo de objetos del Hito 9 (apertura por índice,
/// navegación de referencias y relaciones, %Save con sus validaciones) y devuelve
/// un JSON con un resultado de negocio:</p>
/// <ul>
/// <li><code>{"ok":1, ...}</code> cuando la operación se realizó.</li>
/// <li><code>{"ok":0, "error":"NO_ENCONTRADO" | "TRANSICION_INVALIDA" | "PARTIDO_FINALIZADO" | "VALIDACION"}</code>
/// cuando la regla de dominio la rechazó.</li>
/// </ul>
/// <p>El %ID interno, el DNI del árbitro y los mensajes de %Status no forman parte
/// de la respuesta: el detalle técnico queda en <code>detalle_interno</code>, que la
/// API registra en el log y nunca devuelve al consumidor.</p>
Class Fixture.API Extends %RegisteredObject
{

/// Acta oficial del partido: datos, árbitro y eventos ordenados por minuto.
ClassMethod ObtenerActa(codigo As %String) As %String
{
    Set partido = ##class(Fixture.Partido).CodigoIndexOpen(codigo, 0)
    If '$IsObject(partido) Quit ..Error("NO_ENCONTRADO")
    Quit {"ok":1, "acta":(..Acta(partido))}.%ToJSON()
}

/// Máquina de estados del partido: Programado -> En Juego -> Finalizado.
/// Pedir el estado actual no modifica nada (idempotente).
ClassMethod CambiarEstado(codigo As %String, nuevo As %String) As %String
{
    // Concurrencia 4: bloqueo exclusivo mientras se valida y se guarda.
    Set partido = ##class(Fixture.Partido).CodigoIndexOpen(codigo, 4, .sc)
    If '$IsObject(partido) {
        // Si el código existe pero no se pudo abrir, falló el bloqueo, no la búsqueda.
        If ##class(Fixture.Partido).CodigoIndexExists(codigo) {
            Quit ..Error("ERROR_INTERNO", $System.Status.GetErrorText(sc))
        }
        Quit ..Error("NO_ENCONTRADO")
    }
    Set actual = partido.Estado
    If actual = nuevo {
        Quit {"ok":1, "cambiado":0, "acta":(..Acta(partido))}.%ToJSON()
    }
    If '..TransicionValida(actual, nuevo) {
        Quit {"ok":0, "error":"TRANSICION_INVALIDA", "estado_actual":(actual)}.%ToJSON()
    }
    Set partido.Estado = nuevo
    Set sc = partido.%Save()
    If $$$ISERR(sc) Quit ..Error("VALIDACION", $System.Status.GetErrorText(sc))
    Quit {"ok":1, "cambiado":1, "acta":(..Acta(partido))}.%ToJSON()
}

/// Registra un evento en el acta. La regla "un partido Finalizado no admite
/// eventos" la aplica Fixture.Evento:%OnBeforeSave (Hito 9); el rango del minuto
/// y el tipo los validan MINVAL/MAXVAL y VALUELIST.
ClassMethod RegistrarEvento(codigo As %String, minuto As %Integer, tipo As %String, descripcion As %String = "") As %String
{
    Set partido = ##class(Fixture.Partido).CodigoIndexOpen(codigo, 0)
    If '$IsObject(partido) Quit ..Error("NO_ENCONTRADO")

    Set evento = ##class(Fixture.Evento).%New()
    Set evento.Minuto = minuto
    Set evento.Tipo = tipo
    Set evento.Descripcion = descripcion
    Set evento.Partido = partido
    Set sc = evento.%Save()
    If $$$ISERR(sc) {
        If partido.Estado = "Finalizado" {
            Quit {"ok":0, "error":"PARTIDO_FINALIZADO", "estado_actual":"Finalizado", "detalle_interno":($System.Status.GetErrorText(sc))}.%ToJSON()
        }
        Quit ..Error("VALIDACION", $System.Status.GetErrorText(sc))
    }
    Quit {"ok":1, "evento":(..Evento(evento)), "acta":(..Acta(partido))}.%ToJSON()
}

/// Reinicia los partidos de muestra del Hito 10 a un estado conocido.
/// Se puede ejecutar las veces que haga falta: borra y vuelve a crear solo
/// los partidos con código P-001, P-002 y P-003 (sus eventos se borran en
/// cascada por la relación parent/children).
ClassMethod CargarMuestra() As %String
{
    Set arbitro = ..ArbitroMuestra()
    If '$IsObject(arbitro) Quit ..Error("ERROR_INTERNO", "No se pudo crear el arbitro de muestra")

    Set eventos = []
    Do eventos.%Push({"minuto":23, "tipo":"Gol", "descripcion":"Gol de ARG-10"})
    Set sc = ..ReiniciarPartido("P-001", "Estadio Monumental", "2030-06-10", "En Juego", arbitro, eventos)
    If $$$ISERR(sc) Quit ..Error("ERROR_INTERNO", $System.Status.GetErrorText(sc))

    Set sc = ..ReiniciarPartido("P-002", "Estadio Centenario", "2030-06-12", "Programado", arbitro, [])
    If $$$ISERR(sc) Quit ..Error("ERROR_INTERNO", $System.Status.GetErrorText(sc))

    Set eventos = []
    Do eventos.%Push({"minuto":10, "tipo":"Gol", "descripcion":"Gol de URU-9"})
    Do eventos.%Push({"minuto":80, "tipo":"Tarjeta Amarilla", "descripcion":"Falta en mitad de cancha"})
    Set sc = ..ReiniciarPartido("P-003", "Estadio Santiago Bernabeu", "2030-06-16", "Finalizado", arbitro, eventos)
    If $$$ISERR(sc) Quit ..Error("ERROR_INTERNO", $System.Status.GetErrorText(sc))

    Quit {"ok":1, "partidos":["P-001","P-002","P-003"]}.%ToJSON()
}

ClassMethod TransicionValida(actual As %String, nuevo As %String) As %Boolean [ Private ]
{
    Quit ((actual = "Programado") && (nuevo = "En Juego")) || ((actual = "En Juego") && (nuevo = "Finalizado"))
}

ClassMethod Acta(partido As Fixture.Partido) As %DynamicObject [ Private ]
{
    Set acta = {
        "codigo_partido":(partido.Codigo),
        "sede":(partido.Sede),
        "fecha":($ZDate(partido.Fecha, 3)),
        "estado":(partido.Estado)
    }
    Set arbitro = partido.Arbitro
    Set acta.arbitro = {"nombre":(arbitro.Nombre), "apellido":(arbitro.Apellido), "rango":(arbitro.Rango)}

    // Ordenar los eventos por minuto (y por orden de carga dentro del mismo minuto).
    Set clave = ""
    For {
        Set evento = partido.Eventos.GetNext(.clave)
        Quit:clave=""
        Set orden(evento.Minuto, $Increment(n)) = evento
    }
    Set eventos = []
    Set minuto = ""
    For {
        Set minuto = $Order(orden(minuto))
        Quit:minuto=""
        Set i = ""
        For {
            Set i = $Order(orden(minuto, i), 1, evento)
            Quit:i=""
            Do eventos.%Push(..Evento(evento))
        }
    }
    Set acta.eventos = eventos
    Quit acta
}

ClassMethod Evento(evento As Fixture.Evento) As %DynamicObject [ Private ]
{
    Quit {"minuto":(+evento.Minuto), "tipo":(evento.Tipo), "descripcion":(evento.Descripcion)}
}

ClassMethod Error(codigo As %String, detalle As %String = "") As %String [ Private ]
{
    Set r = {"ok":0, "error":(codigo)}
    If detalle '= "" Set r."detalle_interno" = detalle
    Quit r.%ToJSON()
}

ClassMethod ArbitroMuestra() As Fixture.Arbitro [ Private ]
{
    &sql(SELECT TOP 1 ID INTO :id FROM Fixture.Arbitro WHERE DNI = '30111222' ORDER BY ID)
    If SQLCODE = 0 Quit ##class(Fixture.Arbitro).%OpenId(id)
    Set arbitro = ##class(Fixture.Arbitro).%New()
    Set arbitro.Nombre = "Facundo"
    Set arbitro.Apellido = "Tello"
    Set arbitro.DNI = "30111222"
    Set arbitro.Rango = "FIFA"
    If $$$ISERR(arbitro.%Save()) Quit ""
    Quit arbitro
}

ClassMethod ReiniciarPartido(codigo As %String, sede As %String, fecha As %String, estado As %String, arbitro As Fixture.Arbitro, eventos As %DynamicArray) As %Status [ Private ]
{
    Set existente = ##class(Fixture.Partido).CodigoIndexOpen(codigo, 0)
    If $IsObject(existente) {
        Set id = existente.%Id()
        Kill existente
        Set sc = ##class(Fixture.Partido).%DeleteId(id)
        If $$$ISERR(sc) Quit sc
    }

    Set partido = ##class(Fixture.Partido).%New()
    Set partido.Codigo = codigo
    Set partido.Sede = sede
    Set partido.Fecha = $ZDateH(fecha, 3)
    Set partido.Arbitro = arbitro
    // Los eventos se cargan con el partido abierto; si el estado final es
    // Finalizado se aplica después, igual que en el flujo real del acta.
    Set partido.Estado = $Select(estado = "Finalizado":"En Juego", 1:estado)
    Set iter = eventos.%GetIterator()
    While iter.%GetNext(.k, .datos) {
        Set evento = ##class(Fixture.Evento).%New()
        Set evento.Minuto = datos.minuto
        Set evento.Tipo = datos.tipo
        Set evento.Descripcion = datos.descripcion
        Do partido.Eventos.Insert(evento)
    }
    Set sc = partido.%Save()
    If $$$ISERR(sc) Quit sc
    If estado '= partido.Estado {
        Set partido.Estado = estado
        Set sc = partido.%Save()
    }
    Quit sc
}

}
