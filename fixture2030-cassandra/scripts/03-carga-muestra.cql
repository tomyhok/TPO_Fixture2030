-- =====================================================================
-- Hito 6 - Fixture 2030 - Modulo de Comentarios Masivos
-- 03-carga-muestra.cql : dataset chico para validar el modelo (RF11)
-- =====================================================================
-- Muestra funcional de desarrollo: 3 partidos, 12 usuarios, 35 comentarios.
-- Los identificadores de partido y los codigos de equipo son los mismos que
-- usan los modulos de MongoDB (Hito 4) y Neo4j (Hito 5).
--
-- IDEMPOTENCIA (RNF7): los timeuuid estan fijados en el script en lugar de
-- generarse con now(). Son UUID v1 legitimos, derivados del instante que
-- figura en creado_en, de modo que el orden de clustering coincide con el
-- orden cronologico y las funciones minTimeuuid/maxTimeuuid funcionan sobre
-- la muestra. Como en Cassandra todo INSERT es un upsert sobre la clave
-- primaria, reejecutar el archivo reescribe las mismas 35 filas sin duplicar.
-- En produccion el id lo genera el productor con now().
--
-- shard = crc32(id_usuario) % 4, la misma formula de tools/generar_comentarios.py.
--
-- La carga de volumen (>1.000.000 de filas) NO se hace aca:
-- ver tools/generar_comentarios.py y tools/carga_masiva.sh.
-- =====================================================================

USE fixture2030;

-- ---------------------------------------------------------------------
-- 1) Tabla principal: muro en vivo por partido
-- ---------------------------------------------------------------------
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152015', 1, f03a7a01-e505-11f5-8001-00000005f1c7, 'U-1002', 'verdeamarelo10', 'BRA', 'El arbitro cobro mal ese offside', 'pt', 'publicado', 12, '2030-06-15 20:15:00+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152015', 0, f6c8f182-e505-11f5-8002-00000005f1c7, 'U-1004', 'carioca_futbol', 'BRA', 'Golazo de media distancia, imposible para el arquero', 'pt', 'publicado', 14, '2030-06-15 20:15:11+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152015', 1, fd576903-e505-11f5-8003-00000005f1c7, 'U-1002', 'verdeamarelo10', 'BRA', 'Cambio necesario, el mediocampo esta perdido', 'pt', 'publicado', 16, '2030-06-15 20:15:22+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152015', 0, 03e5e084-e506-11f5-8004-00000005f1c7, 'U-1004', 'carioca_futbol', 'BRA', 'Que atajada tremenda, salvo el partido', 'pt', 'publicado', 18, '2030-06-15 20:15:33+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152015', 1, 0a745805-e506-11f5-8005-00000005f1c7, 'U-1002', 'verdeamarelo10', 'BRA', 'Penal clarisimo que no cobraron', 'pt', 'publicado', 20, '2030-06-15 20:15:44+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152016', 3, 13fdc006-e506-11f5-8006-00000005f1c7, 'U-1003', 'tribuna_sur', 'ARG', 'El VAR tarda demasiado en revisar', 'es', 'publicado', 22, '2030-06-15 20:16:00+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152016', 3, 1a8c3787-e506-11f5-8007-00000005f1c7, 'U-1001', 'hincha_albiceleste', 'ARG', 'Se viene el gol, presionan alto', 'es', 'publicado', 24, '2030-06-15 20:16:11+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152016', 3, 211aaf08-e506-11f5-8008-00000005f1c7, 'U-1003', 'tribuna_sur', 'ARG', 'Partidazo, no se puede dejar de mirar', 'es', 'publicado', 26, '2030-06-15 20:16:22+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152016', 3, 27a92689-e506-11f5-8009-00000005f1c7, 'U-1001', 'hincha_albiceleste', 'ARG', 'Tres amarillas en diez minutos, se descontrolo', 'es', 'publicado', 28, '2030-06-15 20:16:33+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152016', 3, 2e379e0a-e506-11f5-800a-00000005f1c7, 'U-1003', 'tribuna_sur', 'ARG', 'Que jugada de contraataque, casi gol', 'es', 'publicado', 30, '2030-06-15 20:16:44+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152017', 0, 37c1060b-e506-11f5-800b-00000005f1c7, 'U-1004', 'carioca_futbol', 'BRA', 'El arbitro cobro mal ese offside', 'pt', 'en_revision', 32, '2030-06-15 20:17:00+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152017', 1, 3e4f7d8c-e506-11f5-800c-00000005f1c7, 'U-1002', 'verdeamarelo10', 'BRA', 'Golazo de media distancia, imposible para el arquero', 'pt', 'publicado', 34, '2030-06-15 20:17:11+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152017', 0, 44ddf50d-e506-11f5-800d-00000005f1c7, 'U-1004', 'carioca_futbol', 'BRA', 'Cambio necesario, el mediocampo esta perdido', 'pt', 'publicado', 36, '2030-06-15 20:17:22+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152017', 1, 4b6c6c8e-e506-11f5-800e-00000005f1c7, 'U-1002', 'verdeamarelo10', 'BRA', 'Que atajada tremenda, salvo el partido', 'pt', 'publicado', 38, '2030-06-15 20:17:33+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-001', '203006152017', 0, 51fae40f-e506-11f5-800f-00000005f1c7, 'U-1004', 'carioca_futbol', 'BRA', 'Penal clarisimo que no cobraron', 'pt', 'publicado', 40, '2030-06-15 20:17:44+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-002', '203006152245', 2, e4a57e10-e51a-11f5-8010-00000005f1c7, 'U-1005', 'la_roja_fan', 'ESP', 'El VAR tarda demasiado en revisar', 'es', 'publicado', 42, '2030-06-15 22:45:00+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-002', '203006152245', 2, eb33f591-e51a-11f5-8011-00000005f1c7, 'U-1007', 'madrid_norte', 'ESP', 'Se viene el gol, presionan alto', 'es', 'rechazado', 44, '2030-06-15 22:45:11+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-002', '203006152245', 2, f1c26d12-e51a-11f5-8012-00000005f1c7, 'U-1005', 'la_roja_fan', 'ESP', 'Partidazo, no se puede dejar de mirar', 'es', 'publicado', 46, '2030-06-15 22:45:22+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-002', '203006152245', 2, f850e493-e51a-11f5-8013-00000005f1c7, 'U-1007', 'madrid_norte', 'ESP', 'Tres amarillas en diez minutos, se descontrolo', 'es', 'publicado', 48, '2030-06-15 22:45:33+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-002', '203006152245', 2, fedf5c14-e51a-11f5-8014-00000005f1c7, 'U-1005', 'la_roja_fan', 'ESP', 'Que jugada de contraataque, casi gol', 'es', 'publicado', 50, '2030-06-15 22:45:44+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-002', '203006152246', 0, 0868c415-e51b-11f5-8015-00000005f1c7, 'U-1006', 'paris_bleu', 'FRA', 'El arbitro cobro mal ese offside', 'en', 'publicado', 52, '2030-06-15 22:46:00+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-002', '203006152246', 3, 0ef73b96-e51b-11f5-8016-00000005f1c7, 'U-1008', 'lyon_ultras', 'FRA', 'Golazo de media distancia, imposible para el arquero', 'en', 'en_revision', 54, '2030-06-15 22:46:11+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-002', '203006152246', 0, 1585b317-e51b-11f5-8017-00000005f1c7, 'U-1006', 'paris_bleu', 'FRA', 'Cambio necesario, el mediocampo esta perdido', 'en', 'publicado', 56, '2030-06-15 22:46:22+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-002', '203006152246', 3, 1c142a98-e51b-11f5-8018-00000005f1c7, 'U-1008', 'lyon_ultras', 'FRA', 'Que atajada tremenda, salvo el partido', 'en', 'publicado', 58, '2030-06-15 22:46:33+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-002', '203006152246', 0, 22a2a219-e51b-11f5-8019-00000005f1c7, 'U-1006', 'paris_bleu', 'FRA', 'Penal clarisimo que no cobraron', 'en', 'publicado', 60, '2030-06-15 22:46:44+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-003', '203006161830', 2, 6f8c841a-e5c0-11f5-801a-00000005f1c7, 'U-1011', 'penarol_1891', 'URU', 'El VAR tarda demasiado en revisar', 'es', 'publicado', 62, '2030-06-16 18:30:00+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-003', '203006161830', 1, 761afb9b-e5c0-11f5-801b-00000005f1c7, 'U-1009', 'celeste_charrua', 'URU', 'Se viene el gol, presionan alto', 'es', 'publicado', 64, '2030-06-16 18:30:11+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-003', '203006161830', 2, 7ca9731c-e5c0-11f5-801c-00000005f1c7, 'U-1011', 'penarol_1891', 'URU', 'Partidazo, no se puede dejar de mirar', 'es', 'publicado', 66, '2030-06-16 18:30:22+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-003', '203006161830', 1, 8337ea9d-e5c0-11f5-801d-00000005f1c7, 'U-1009', 'celeste_charrua', 'URU', 'Tres amarillas en diez minutos, se descontrolo', 'es', 'publicado', 68, '2030-06-16 18:30:33+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-003', '203006161830', 2, 89c6621e-e5c0-11f5-801e-00000005f1c7, 'U-1011', 'penarol_1891', 'URU', 'Que jugada de contraataque, casi gol', 'es', 'publicado', 70, '2030-06-16 18:30:44+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-003', '203006161831', 0, 934fca1f-e5c0-11f5-801f-00000005f1c7, 'U-1012', 'chilango_gol', 'MEX', 'El arbitro cobro mal ese offside', 'es', 'publicado', 72, '2030-06-16 18:31:00+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-003', '203006161831', 0, 99de41a0-e5c0-11f5-8020-00000005f1c7, 'U-1010', 'azteca_verde', 'MEX', 'Golazo de media distancia, imposible para el arquero', 'es', 'publicado', 74, '2030-06-16 18:31:11+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-003', '203006161831', 0, a06cb921-e5c0-11f5-8021-00000005f1c7, 'U-1012', 'chilango_gol', 'MEX', 'Cambio necesario, el mediocampo esta perdido', 'es', 'en_revision', 76, '2030-06-16 18:31:22+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-003', '203006161831', 0, a6fb30a2-e5c0-11f5-8022-00000005f1c7, 'U-1010', 'azteca_verde', 'MEX', 'Que atajada tremenda, salvo el partido', 'es', 'rechazado', 78, '2030-06-16 18:31:33+0000');
INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
VALUES ('P-003', '203006161831', 0, ad89a823-e5c0-11f5-8023-00000005f1c7, 'U-1012', 'chilango_gol', 'MEX', 'Penal clarisimo que no cobraron', 'es', 'publicado', 80, '2030-06-16 18:31:44+0000');

-- ---------------------------------------------------------------------
-- 2) Vista duplicada: historial por usuario (misma informacion, otra clave)
-- ---------------------------------------------------------------------
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1002', '203006', f03a7a01-e505-11f5-8001-00000005f1c7, 'P-001', 'El arbitro cobro mal ese offside', 'publicado', '2030-06-15 20:15:00+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1004', '203006', f6c8f182-e505-11f5-8002-00000005f1c7, 'P-001', 'Golazo de media distancia, imposible para el arquero', 'publicado', '2030-06-15 20:15:11+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1002', '203006', fd576903-e505-11f5-8003-00000005f1c7, 'P-001', 'Cambio necesario, el mediocampo esta perdido', 'publicado', '2030-06-15 20:15:22+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1004', '203006', 03e5e084-e506-11f5-8004-00000005f1c7, 'P-001', 'Que atajada tremenda, salvo el partido', 'publicado', '2030-06-15 20:15:33+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1002', '203006', 0a745805-e506-11f5-8005-00000005f1c7, 'P-001', 'Penal clarisimo que no cobraron', 'publicado', '2030-06-15 20:15:44+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1003', '203006', 13fdc006-e506-11f5-8006-00000005f1c7, 'P-001', 'El VAR tarda demasiado en revisar', 'publicado', '2030-06-15 20:16:00+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1001', '203006', 1a8c3787-e506-11f5-8007-00000005f1c7, 'P-001', 'Se viene el gol, presionan alto', 'publicado', '2030-06-15 20:16:11+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1003', '203006', 211aaf08-e506-11f5-8008-00000005f1c7, 'P-001', 'Partidazo, no se puede dejar de mirar', 'publicado', '2030-06-15 20:16:22+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1001', '203006', 27a92689-e506-11f5-8009-00000005f1c7, 'P-001', 'Tres amarillas en diez minutos, se descontrolo', 'publicado', '2030-06-15 20:16:33+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1003', '203006', 2e379e0a-e506-11f5-800a-00000005f1c7, 'P-001', 'Que jugada de contraataque, casi gol', 'publicado', '2030-06-15 20:16:44+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1004', '203006', 37c1060b-e506-11f5-800b-00000005f1c7, 'P-001', 'El arbitro cobro mal ese offside', 'en_revision', '2030-06-15 20:17:00+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1002', '203006', 3e4f7d8c-e506-11f5-800c-00000005f1c7, 'P-001', 'Golazo de media distancia, imposible para el arquero', 'publicado', '2030-06-15 20:17:11+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1004', '203006', 44ddf50d-e506-11f5-800d-00000005f1c7, 'P-001', 'Cambio necesario, el mediocampo esta perdido', 'publicado', '2030-06-15 20:17:22+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1002', '203006', 4b6c6c8e-e506-11f5-800e-00000005f1c7, 'P-001', 'Que atajada tremenda, salvo el partido', 'publicado', '2030-06-15 20:17:33+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1004', '203006', 51fae40f-e506-11f5-800f-00000005f1c7, 'P-001', 'Penal clarisimo que no cobraron', 'publicado', '2030-06-15 20:17:44+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1005', '203006', e4a57e10-e51a-11f5-8010-00000005f1c7, 'P-002', 'El VAR tarda demasiado en revisar', 'publicado', '2030-06-15 22:45:00+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1007', '203006', eb33f591-e51a-11f5-8011-00000005f1c7, 'P-002', 'Se viene el gol, presionan alto', 'rechazado', '2030-06-15 22:45:11+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1005', '203006', f1c26d12-e51a-11f5-8012-00000005f1c7, 'P-002', 'Partidazo, no se puede dejar de mirar', 'publicado', '2030-06-15 22:45:22+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1007', '203006', f850e493-e51a-11f5-8013-00000005f1c7, 'P-002', 'Tres amarillas en diez minutos, se descontrolo', 'publicado', '2030-06-15 22:45:33+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1005', '203006', fedf5c14-e51a-11f5-8014-00000005f1c7, 'P-002', 'Que jugada de contraataque, casi gol', 'publicado', '2030-06-15 22:45:44+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1006', '203006', 0868c415-e51b-11f5-8015-00000005f1c7, 'P-002', 'El arbitro cobro mal ese offside', 'publicado', '2030-06-15 22:46:00+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1008', '203006', 0ef73b96-e51b-11f5-8016-00000005f1c7, 'P-002', 'Golazo de media distancia, imposible para el arquero', 'en_revision', '2030-06-15 22:46:11+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1006', '203006', 1585b317-e51b-11f5-8017-00000005f1c7, 'P-002', 'Cambio necesario, el mediocampo esta perdido', 'publicado', '2030-06-15 22:46:22+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1008', '203006', 1c142a98-e51b-11f5-8018-00000005f1c7, 'P-002', 'Que atajada tremenda, salvo el partido', 'publicado', '2030-06-15 22:46:33+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1006', '203006', 22a2a219-e51b-11f5-8019-00000005f1c7, 'P-002', 'Penal clarisimo que no cobraron', 'publicado', '2030-06-15 22:46:44+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1011', '203006', 6f8c841a-e5c0-11f5-801a-00000005f1c7, 'P-003', 'El VAR tarda demasiado en revisar', 'publicado', '2030-06-16 18:30:00+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1009', '203006', 761afb9b-e5c0-11f5-801b-00000005f1c7, 'P-003', 'Se viene el gol, presionan alto', 'publicado', '2030-06-16 18:30:11+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1011', '203006', 7ca9731c-e5c0-11f5-801c-00000005f1c7, 'P-003', 'Partidazo, no se puede dejar de mirar', 'publicado', '2030-06-16 18:30:22+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1009', '203006', 8337ea9d-e5c0-11f5-801d-00000005f1c7, 'P-003', 'Tres amarillas en diez minutos, se descontrolo', 'publicado', '2030-06-16 18:30:33+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1011', '203006', 89c6621e-e5c0-11f5-801e-00000005f1c7, 'P-003', 'Que jugada de contraataque, casi gol', 'publicado', '2030-06-16 18:30:44+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1012', '203006', 934fca1f-e5c0-11f5-801f-00000005f1c7, 'P-003', 'El arbitro cobro mal ese offside', 'publicado', '2030-06-16 18:31:00+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1010', '203006', 99de41a0-e5c0-11f5-8020-00000005f1c7, 'P-003', 'Golazo de media distancia, imposible para el arquero', 'publicado', '2030-06-16 18:31:11+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1012', '203006', a06cb921-e5c0-11f5-8021-00000005f1c7, 'P-003', 'Cambio necesario, el mediocampo esta perdido', 'en_revision', '2030-06-16 18:31:22+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1010', '203006', a6fb30a2-e5c0-11f5-8022-00000005f1c7, 'P-003', 'Que atajada tremenda, salvo el partido', 'rechazado', '2030-06-16 18:31:33+0000');
INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
VALUES ('U-1012', '203006', ad89a823-e5c0-11f5-8023-00000005f1c7, 'P-003', 'Penal clarisimo que no cobraron', 'publicado', '2030-06-16 18:31:44+0000');

-- ---------------------------------------------------------------------
-- 3) Cola de moderacion: SOLO los comentarios no publicados
-- ---------------------------------------------------------------------
INSERT INTO comentarios_en_revision (id_partido, estado_moderacion, id_comentario, id_usuario, texto, motivo, creado_en)
VALUES ('P-001', 'en_revision', 37c1060b-e506-11f5-800b-00000005f1c7, 'U-1004', 'El arbitro cobro mal ese offside', 'reporte_usuario', '2030-06-15 20:17:00+0000');
INSERT INTO comentarios_en_revision (id_partido, estado_moderacion, id_comentario, id_usuario, texto, motivo, creado_en)
VALUES ('P-002', 'rechazado', eb33f591-e51a-11f5-8011-00000005f1c7, 'U-1007', 'Se viene el gol, presionan alto', 'filtro_automatico', '2030-06-15 22:45:11+0000');
INSERT INTO comentarios_en_revision (id_partido, estado_moderacion, id_comentario, id_usuario, texto, motivo, creado_en)
VALUES ('P-002', 'en_revision', 0ef73b96-e51b-11f5-8016-00000005f1c7, 'U-1008', 'Golazo de media distancia, imposible para el arquero', 'reporte_usuario', '2030-06-15 22:46:11+0000');
INSERT INTO comentarios_en_revision (id_partido, estado_moderacion, id_comentario, id_usuario, texto, motivo, creado_en)
VALUES ('P-003', 'en_revision', a06cb921-e5c0-11f5-8021-00000005f1c7, 'U-1012', 'Cambio necesario, el mediocampo esta perdido', 'reporte_usuario', '2030-06-16 18:31:22+0000');
INSERT INTO comentarios_en_revision (id_partido, estado_moderacion, id_comentario, id_usuario, texto, motivo, creado_en)
VALUES ('P-003', 'rechazado', a6fb30a2-e5c0-11f5-8022-00000005f1c7, 'U-1010', 'Que atajada tremenda, salvo el partido', 'filtro_automatico', '2030-06-16 18:31:33+0000');

-- ---------------------------------------------------------------------
-- 4) Metricas de interaccion (counter: siempre UPDATE, nunca INSERT)
-- ---------------------------------------------------------------------
-- ATENCION: los counter NO son idempotentes. Reejecutar este bloque vuelve
-- a sumar. Es el unico tramo del script que hay que correr una sola vez, o
-- borrar antes las filas (DELETE FROM metricas_comentario WHERE ...).
-- ---------------------------------------------------------------------
UPDATE metricas_comentario SET likes = likes + 89, reportes = reportes + 1, respuestas = respuestas + 5 WHERE id_comentario = f03a7a01-e505-11f5-8001-00000005f1c7;
UPDATE metricas_comentario SET likes = likes + 8, reportes = reportes + 0, respuestas = respuestas + 1 WHERE id_comentario = f6c8f182-e505-11f5-8002-00000005f1c7;
UPDATE metricas_comentario SET likes = likes + 22, reportes = reportes + 2, respuestas = respuestas + 1 WHERE id_comentario = fd576903-e505-11f5-8003-00000005f1c7;
UPDATE metricas_comentario SET likes = likes + 36, reportes = reportes + 0, respuestas = respuestas + 1 WHERE id_comentario = 03e5e084-e506-11f5-8004-00000005f1c7;
UPDATE metricas_comentario SET likes = likes + 50, reportes = reportes + 2, respuestas = respuestas + 1 WHERE id_comentario = 0a745805-e506-11f5-8005-00000005f1c7;
UPDATE metricas_comentario SET likes = likes + 64, reportes = reportes + 0, respuestas = respuestas + 1 WHERE id_comentario = 13fdc006-e506-11f5-8006-00000005f1c7;
UPDATE metricas_comentario SET likes = likes + 78, reportes = reportes + 2, respuestas = respuestas + 1 WHERE id_comentario = 1a8c3787-e506-11f5-8007-00000005f1c7;
UPDATE metricas_comentario SET likes = likes + 92, reportes = reportes + 0, respuestas = respuestas + 1 WHERE id_comentario = 211aaf08-e506-11f5-8008-00000005f1c7;
UPDATE metricas_comentario SET likes = likes + 11, reportes = reportes + 3, respuestas = respuestas + 4 WHERE id_comentario = 27a92689-e506-11f5-8009-00000005f1c7;
UPDATE metricas_comentario SET likes = likes + 25, reportes = reportes + 1, respuestas = respuestas + 4 WHERE id_comentario = 2e379e0a-e506-11f5-800a-00000005f1c7;

-- ---------------------------------------------------------------------
-- Verificacion de la carga de muestra
-- ---------------------------------------------------------------------
SELECT COUNT(*) AS comentarios_muestra FROM comentarios_por_partido;   -- esperado: 35
SELECT COUNT(*) AS historial_usuarios  FROM comentarios_por_usuario;   -- esperado: 35
SELECT COUNT(*) AS cola_moderacion     FROM comentarios_en_revision;   -- esperado: 5
