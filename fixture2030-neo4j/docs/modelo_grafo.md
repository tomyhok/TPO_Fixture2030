# Modelo de Grafo - Fixture 2030

Este documento detalla el esquema lógico del subgrafo diseñado para el Fixture 2030, especificando las entidades, propiedades y relaciones.

## 1. Nodos (Etiquetas y Propiedades)

* **`:Equipo`**
  * `codigo_iso` (String - Identificador Único): Código de tres letras del país (ej. "ARG").
  * `nombre` (String): Nombre del país.
  * `confederacion` (String): Confederación a la que pertenece.
* **`:Jugador`**
  * `id_jugador` (String - Identificador Único): Código compuesto (ej. "ARG-10").
  * `nombre` (String): Nombre y apellido del jugador.
  * `posicion` (String): Rol en el campo de juego.
* **`:Sede`**
  * `codigo_sede` (String - Identificador Único): Código abreviado del estadio.
  * `nombre` (String): Nombre oficial del estadio.
  * `ciudad` (String): Ciudad donde se ubica.
* **`:Partido`**
  * `codigo_partido` (String - Identificador Único): Identificador del encuentro (ej. "P-001").
  * `fecha` (Date): Fecha programada.
  * `fase` (String): Instancia del torneo (ej. "Grupos").
* **`:Evento`**
  * `id_evento` (String - Identificador Único): Identificador del suceso.
  * `tipo` (String): Clasificación del evento (Gol, Tarjeta Amarilla, etc.).
  * `minuto` (Integer): Minuto de juego en el que ocurrió.

## 2. Relaciones y Direcciones

| Relación | Origen | Destino | Propiedades | Cardinalidad Esperada |
| :--- | :--- | :--- | :--- | :--- |
| `PERTENECE_A` | `(Jugador)` | `(Equipo)` | Ninguna | N:1 (Muchos jugadores a 1 equipo) |
| `DISPUTA` | `(Equipo)` | `(Partido)` | `condicion` (local/visitante) | 2:1 (Dos equipos por cada partido) |
| `SE_JUEGA_EN` | `(Partido)` | `(Sede)` | Ninguna | N:1 (Varios partidos en 1 sede) |
| `CORRESPONDE_A` | `(Evento)` | `(Partido)` | Ninguna | N:1 (Varios eventos en 1 partido) |
| `PROTAGONIZA` | `(Jugador)` | `(Evento)` | Ninguna | 1:N (Un jugador puede tener varios eventos) |