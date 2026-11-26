# =====================================================================
# Hito 10 - Reiniciar los datos de muestra que cambian al probar la API
# Recarga las sesiones de Redis (vencen a los 30 min) y deja la demo del portal
# como al principio (scripts/reiniciar_demo.py: estado de P-001/P-002 en Neo4j,
# eventos simulados, reloj y prode de esos partidos).
# Uso (desde fixture2030-hito-10-api-integrada\): .\scripts\reiniciar_muestra.ps1
# =====================================================================
docker exec fixture2030-redis sh -c "grep -v '^#' /scripts/carga_muestra.redis | redis-cli" | Out-Null
Write-Host "Redis: sesiones S-0001..S-0010 recargadas (TTL 1800 s)"

& .\.venv\Scripts\python.exe scripts\reiniciar_demo.py
