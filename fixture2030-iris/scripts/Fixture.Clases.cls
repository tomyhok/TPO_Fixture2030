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

<Method name="%OnBeforeSave">
<FormalSpec>insert:%Boolean</FormalSpec>
<ReturnType>%Status</ReturnType>
<Implementation><![CDATA[
    If (..Minuto < 0) {
        Quit $$$ERROR($$$GeneralError, "El minuto del evento no puede ser negativo")
    }
    If ($ISOBJECT(..Partido)) {
        If (..Partido.Estado = "Finalizado") {
            Quit $$$ERROR($$$GeneralError, "No se pueden agregar eventos a un partido finalizado")
        }
    }
    Quit $$$OK
]]></Implementation>
</Method>
</Class>
</Export>
