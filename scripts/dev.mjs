// Levanta los motores (docker compose) y la API del Hito 10, que sirve el portal.
// Hace lo mismo que fixture2030-hito-10-api-integrada/scripts/iniciar_api.(ps1|sh): crea el .venv
// si falta, instala requirements.txt, toma host/puerto del .env y guarda la salida en logs/api.log.
// Uso: npm run dev   |   npm run api (sin docker compose)
import { spawnSync, spawn } from "node:child_process";
import { createServer } from "node:net";
import { createWriteStream, existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const hito = join(raiz, "fixture2030-hito-10-api-integrada");
const windows = process.platform === "win32";

function salir(mensaje, codigo = 1) {
  console.error(mensaje);
  process.exit(codigo);
}

function correr(cmd, args, opciones = {}) {
  const r = spawnSync(cmd, args, { cwd: hito, stdio: "inherit", ...opciones });
  return r.status === 0;
}

function leerEnv(clave, porDefecto) {
  const linea = readFileSync(join(hito, ".env"), "utf8").split(/\r?\n/).find((l) => l.startsWith(`${clave}=`));
  return linea?.slice(clave.length + 1).trim() || porDefecto;
}

function puertoLibre(host, puerto) {
  return new Promise((resolver) => {
    const s = createServer()
      .once("error", () => resolver(false))
      .once("listening", () => s.close(() => resolver(true)))
      .listen(puerto, host);
  });
}

// 1. Motores
if (!process.argv.includes("--sin-docker")) {
  console.log("> docker compose up -d");
  if (!correr("docker", ["compose", "up", "-d"], { cwd: raiz })) {
    salir("No se pudieron levantar los motores. ¿Está abierto Docker Desktop?");
  }
}

// 2. Configuración y entorno Python
if (!existsSync(join(hito, ".env"))) {
  salir("Falta fixture2030-hito-10-api-integrada/.env: copiar .env.example a .env y completar las contraseñas.");
}
const py = join(hito, ".venv", windows ? "Scripts/python.exe" : "bin/python");
if (!existsSync(py)) {
  console.log("> Creando entorno virtual con Python 3.12...");
  const ok = windows
    ? correr("py", ["-3.12", "-m", "venv", ".venv"])
    : correr("python3.12", ["-m", "venv", ".venv"]);
  if (!ok) salir("No se pudo crear el .venv: hace falta Python 3.12 instalado.");
}
if (!correr(py, ["-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", "requirements.txt"])) {
  salir("Falló pip install -r requirements.txt.");
}

// 3. API
const host = leerEnv("API_HOST", "127.0.0.1");
const puerto = Number(leerEnv("API_PORT", "8000"));
if (!(await puertoLibre(host, puerto))) {
  salir(
    `El puerto ${puerto} ya está en uso: probablemente la API ya está corriendo en otra terminal.\n` +
      `Abrí http://${host}:${puerto}/ o cerrá ese proceso y volvé a correr el comando.`
  );
}

mkdirSync(join(hito, "logs"), { recursive: true });
const log = createWriteStream(join(hito, "logs", "api.log"), { flags: "a" });
console.log(`> Portal: http://${host}:${puerto}/   Swagger: http://${host}:${puerto}/docs   (Ctrl+C para detener)`);

const api = spawn(py, ["-m", "uvicorn", "app.main:app", "--host", host, "--port", String(puerto), "--no-access-log"], {
  cwd: hito,
  stdio: ["inherit", "pipe", "pipe"],
});
for (const [origen, destino] of [[api.stdout, process.stdout], [api.stderr, process.stderr]]) {
  origen.on("data", (d) => {
    destino.write(d);
    log.write(d);
  });
}
api.on("exit", (codigo) => log.end(() => process.exit(codigo ?? 0)));
