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
<Parameter name="VALUELIST" value=",FIFA,Nacional"/>
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
<Parameter name="VALUELIST" value=",Programado,En Juego,Finalizado"/>
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
</Class>

<Class name="Fixture.Evento">
<Super>%Persistent</Super>
<Property name="Minuto">
<Type>%Integer</Type>
<Required>1</Required>
<Parameter name="MINVAL" value="1"/>
<Parameter name="MAXVAL" value="130"/>
</Property>
<Property name="Tipo">
<Type>%String</Type>
<Required>1</Required>
<Parameter name="VALUELIST" value=",Gol,Tarjeta Amarilla,Tarjeta Roja,Cambio"/>
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

<Method name="%OnBeforeSave">
<FormalSpec>insert:%Boolean</FormalSpec>
<Private>1</Private>
<ReturnType>%Status</ReturnType>
<ServerOnly>1</ServerOnly>
<Implementation><![CDATA[
    // Regla de estado: un partido Finalizado no admite eventos nuevos.
    // (El rango del minuto lo controlan MINVAL/MAXVAL de la propiedad.)
    If (insert && $ISOBJECT(..Partido)) {
        If (..Partido.Estado = "Finalizado") {
            Quit $$$ERROR($$$GeneralError, "No se pueden agregar eventos a un partido finalizado")
        }
    }
    Quit $$$OK
]]></Implementation>
</Method>
</Class>
</Export>
