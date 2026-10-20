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

    # --- Diagnóstico de salud (Hito 11) ---
    # El chequeo profundo de /health/ready y /health/dependencias se reutiliza
    # durante este tiempo para no consultar las seis bases en cada llamada.
    health_cache_ttl_s: float = Field(10.0, ge=0)
    # Un ping exitoso que tarda más que esto marca la fuente como "degraded".
    health_umbral_lento_ms: float = Field(1000.0, gt=0)

    def configuracion_faltante(self) -> dict[str, list[str]]:
        """Variables imprescindibles sin valor, por fuente (solo nombres, nunca valores).

        Una fuente con faltantes se informa como `not_configured` y no se consulta.
        Cassandra y Redis no tienen credenciales en el laboratorio.
        """

        def vacias(*pares: tuple[str, str]) -> list[str]:
            return [nombre for nombre, valor in pares if not valor.strip() or valor.strip() == "<completar>"]

        mongo = vacias(("MONGO_HOST", self.mongo_host), ("MONGO_DATABASE", self.mongo_database))
        if self.mongo_user:
            mongo += vacias(("MONGO_PASSWORD", self.mongo_password.get_secret_value()))
        return {
            "mongodb": mongo,
            "neo4j": vacias(
                ("NEO4J_URI", self.neo4j_uri),
                ("NEO4J_USER", self.neo4j_user),
                ("NEO4J_PASSWORD", self.neo4j_password.get_secret_value()),
            ),
            "cassandra": vacias(("CASSANDRA_HOSTS", self.cassandra_hosts), ("CASSANDRA_KEYSPACE", self.cassandra_keyspace)),
            "redis": vacias(("REDIS_HOST", self.redis_host)),
            "influxdb": vacias(
                ("INFLUX_URL", self.influx_url),
                ("INFLUX_DATABASE", self.influx_database),
                ("INFLUX_TOKEN", self.token_influx()),
            ),
            "iris": vacias(
                ("IRIS_HOST", self.iris_host),
                ("IRIS_NAMESPACE", self.iris_namespace),
                ("IRIS_USER", self.iris_user),
                ("IRIS_PASSWORD", self.iris_password.get_secret_value()),
            ),
        }

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
