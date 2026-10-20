<?xml version="1.0" encoding="UTF-8"?>
<Export generator="IRIS" version="26">
<Class name="Fixture.Persona">
<Super>%Persistent</Super>
<Property name="Nombre">
<Type>%String</Type>
<Required>1</Required>
</Property>
<Property name="Apellido">
<Type>%String</Type>
<Required>1</Required>
</Property>
<Property name="DNI">
<Type>%String</Type>
<Required>1</Required>
</Property>
</Class>

<Class name="Fixture.Arbitro">
<Super>Fixture.Persona</Super>
<Property name="Rango">
<Type>%String</Type>
<Required>1</Required>
</Property>
</Class>

<Class name="Fixture.Tecnico">
<Super>Fixture.Persona</Super>
<Property name="Licencia">
<Type>%String</Type>
<Required>1</Required>
</Property>
</Class>

<Class name="Fixture.Partido">
<Super>%Persistent</Super>
<Property name="Sede">
<Type>%String</Type>
<Required>1</Required>
</Property>
<Property name="Fecha">
<Type>%Date</Type>
<Required>1</Required>
</Property>
<Property name="Estado">
<Type>%String</Type>
<Required>1</Required>
</Property>
<Property name="Arbitro">
<Type>Fixture.Arbitro</Type>
<Required>1</Required>
</Property>
<Property name="Eventos">
<Type>Fixture.Evento</Type>
<Cardinality>children</Cardinality>
<Inverse>Partido</Inverse>
<Relationship>1</Relationship>
</Property>
<Property name="Codigo">
<Description>
Codigo de negocio del partido (ej. P-001), homologado con Neo4j, Cassandra, Redis
e InfluxDB. Identificador de negocio legible. Es opcional para conservar los objetos del laboratorio anterior.</Description>
<Type>%String</Type>
</Property>

<Index name="CodigoIndex">
<Properties>Codigo</Properties>
<Unique>1</Unique>
</Index>

<Method name="AgregarEvento">
<FormalSpec>minuto:%Integer,tipo:%String,descripcion:%String=""</FormalSpec>
<ReturnType>%Status</ReturnType>
<Implementation><![CDATA[
    // Única regla de dominio: un partido finalizado no admite eventos nuevos.
    If ..Estado = "Finalizado" {
        Quit $SYSTEM.Status.Error(5001, "No se pueden agregar eventos a un partido finalizado")
    }
    Set evento = ##class(Fixture.Evento).%New()
    Set evento.Minuto = minuto
    Set evento.Tipo = tipo
    Set evento.Descripcion = descripcion
    Do ..Eventos.Insert(evento)
    Quit ..%Save()
]]></Implementation>
</Method>
</Class>

<Class name="Fixture.Evento">
<Super>%Persistent</Super>
<Property name="Minuto">
<Type>%Integer</Type>
<Required>1</Required>
</Property>
<Property name="Tipo">
<Type>%String</Type>
<Required>1</Required>
</Property>
<Property name="Descripcion">
<Type>%String</Type>
</Property>
<Property name="Partido">
<Type>Fixture.Partido</Type>
<Cardinality>parent</Cardinality>
<Inverse>Eventos</Inverse>
<Relationship>1</Relationship>
</Property>

<Index name="PartidoIndex">
<Properties>Partido</Properties>
</Index>

</Class>
</Export>
