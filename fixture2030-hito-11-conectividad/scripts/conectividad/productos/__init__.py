"""Un módulo por producto, con la misma firma: evaluar(cfg, registro, capas, sondas)."""

from conectividad.productos import cassandra, influxdb, iris, mongodb, neo4j, redis_kv

PRODUCTOS = {
    "mongodb": mongodb,
    "neo4j": neo4j,
    "cassandra": cassandra,
    "redis": redis_kv,
    "influxdb": influxdb,
    "iris": iris,
}
