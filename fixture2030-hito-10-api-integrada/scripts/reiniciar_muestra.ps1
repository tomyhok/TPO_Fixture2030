# =====================================================================
# Hito 10 - Reiniciar los datos de muestra que cambian al probar la API
# Recarga las sesiones de Redis (vencen a los 30 min) y reinicia las
# actas P-001..P-003 de IRIS. No toca las demás bases.
# Uso (desde fixture2030-hito-10-api-integrada\): .\scripts\reiniciar_muestra.ps1
# =====================================================================
docker exec fixture2030-redis sh -c "grep -v '^#' /scripts/carga_muestra.redis | redis-cli" | Out-Null
Write-Host "Redis: sesiones S-0001..S-0010 recargadas (TTL 1800 s)"

"Write ##class(Fixture.API).CargarMuestra(),!`nHalt" | docker exec -i fixture2030-iris iris session IRIS -U USER | Select-String '"ok"'
Write-Host "IRIS: actas P-001..P-003 reiniciadas"
