"""Configuración de la API (RF16, RNF6).

Todos los valores de conexión se leen de variables de entorno o de un archivo
`.env` local excluido del repositorio. El código no tiene hosts, puertos,
usuarios ni contraseñas fijos: los valores por defecto corresponden a la
ejecución desde la notebook contra el `docker-compose.yml` de la raíz y no
incluyen secretos.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_HITO = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_HITO / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- API ---
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"

    # --- Límites de espera comunes (RNF8) ---
    timeout_conexion_s: float = Field(2.0, gt=0)
    timeout_operacion_s: float = Field(5.0, gt=0)

    # --- MongoDB (Hito 4) ---
    mongo_host: str = "127.0.0.1"
    mongo_port: int = 27017
    mongo_user: str = ""
    mongo_password: SecretStr = SecretStr("")
    mongo_auth_db: str = "admin"
    mongo_database: str = "fixture2030"

    # --- Neo4j (Hito 5) ---
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("")
    neo4j_database: str = "neo4j"

    # --- Cassandra (Hito 6) ---
    cassandra_hosts: str = "127.0.0.1"
    cassandra_port: int = 9042
    cassandra_keyspace: str = "fixture2030"
    cassandra_dc: str = "datacenter1"

    # --- Redis (Hito 7) ---
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: SecretStr = SecretStr("")
    redis_db: int = 0

    # --- InfluxDB 3 Core (Hito 8) ---
    influx_url: str = "http://127.0.0.1:8181"
    influx_database: str = "fixture2030"
    influx_token: SecretStr = SecretStr("")
    # Si no se define INFLUX_TOKEN se usa el archivo que genera
    # fixture2030-influxDB/scripts/inicializacion.sh (excluido del repositorio).
    influx_token_file: Path = RAIZ_HITO.parent / "fixture2030-influxDB" / ".influxdb3-token"

    # --- InterSystems IRIS (Hito 9) ---
    iris_host: str = "127.0.0.1"
    iris_port: int = 1972
    iris_namespace: str = "USER"
    iris_user: str = "fixture_api"
    iris_password: SecretStr = SecretStr("")

    # --- Reglas de negocio configurables ---
    cache_partido_ttl_s: int = 300
    idempotencia_ttl_s: int = 86400

    def token_influx(self) -> str:
        token = self.influx_token.get_secret_value()
        if token:
            return token
        try:
            return self.influx_token_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def lista_hosts_cassandra(self) -> list[str]:
        return [h.strip() for h in self.cassandra_hosts.split(",") if h.strip()]


@lru_cache
def obtener_settings() -> Settings:
    return Settings()
