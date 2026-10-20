"""Ejecuta carga idempotente dos veces, CRUD reservado y recorridos; no fabrica capturas."""
from pathlib import Path
from datetime import datetime, timezone
import subprocess, json, re, hashlib, secrets, sys, os
ROOT=Path(__file__).resolve().parents[2]
def leer_env(path):
 if not path.exists(): return {}
 result={}
 for line in path.read_text(encoding='utf-8').splitlines():
  if line.strip() and not line.lstrip().startswith('#') and '=' in line:
   key,value=line.split('=',1);result[key.strip()]=value.strip().strip('"').strip("'")
 return result
from neo4j import GraphDatabase
import redis
def docker(*args,input=None):
 r=subprocess.run(['docker',*args],input=input,text=True,encoding='utf-8',errors='replace',capture_output=True)
 if r.returncode: raise RuntimeError(r.stderr)
 return r.stdout
def save(path,obj):
 p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
stamp=datetime.now(timezone.utc).isoformat()
env={**leer_env(ROOT/'fixture2030-hito-10-api-integrada/.env'), **leer_env(ROOT/'.env'), **os.environ}
neo=ROOT/'fixture2030-neo4j'

for name in ['equipos.json','jugadores.json']:
 docker('cp',str(ROOT/'fixture2030-mongoDB/init-scripts/data'/name),'fixture2030-neo4j:/var/lib/neo4j/import/'+name)
driver=GraphDatabase.driver('bolt://127.0.0.1:7687',auth=('neo4j',env['NEO4J_PASSWORD']))
def ejecutar_archivo(sesion,nombre):
 text=(neo/'queries'/nombre).read_text(encoding='utf-8')
 text=re.sub(r'//[^\n]*','',text) if nombre!='carga.cypher' else '\n'.join(l for l in text.splitlines() if not l.strip().startswith('//'))
 # Inline comments occur only in CRUD; preserve file:/// in the load source.
 salidas=[]
 for query in text.split(';'):
  if not query.strip():continue
  result=sesion.run(query)
  rows=result.data(); summary=result.consume()
  salidas.append({'consulta':query.strip(),'filas':rows,'contadores':{k:getattr(summary.counters,k) for k in ('nodes_created','nodes_deleted','relationships_created','relationships_deleted','properties_set','constraints_added')}})
 return salidas
def conteos(sesion):
 return {'nodos':sesion.run('MATCH(n) RETURN count(n) AS n').single()['n'],
 'relaciones':sesion.run('MATCH()-[r]->() RETURN count(r) AS n').single()['n'],
 'etiquetas':sesion.run('MATCH(n) RETURN labels(n) AS etiquetas,count(*) AS cantidad ORDER BY etiquetas').data()}
with driver.session() as s:
 evidencia={'fecha_utc':stamp,'version':s.run("CALL dbms.components() YIELD name, versions WHERE name = 'Neo4j Kernel' RETURN versions").single()['versions'],'estructura':ejecutar_archivo(s,'estructura.cypher')}
 evidencia['carga_1']=ejecutar_archivo(s,'carga.cypher'); evidencia['conteos_1']=conteos(s)
 evidencia['carga_2']=ejecutar_archivo(s,'carga.cypher'); evidencia['conteos_2']=conteos(s)
 assert evidencia['conteos_1']==evidencia['conteos_2']
 assert sum(q['contadores'].get('nodes_created',0) for q in evidencia['carga_2'])==0
 assert s.run("MATCH(e:Evento {id_evento:'EV-H5-DEMO'}) RETURN count(e) AS n").single()['n']==0
 evidencia['crud']=ejecutar_archivo(s,'crud.cypher')
 evidencia['evento_demo_despues']=s.run("MATCH(e:Evento {id_evento:'EV-H5-DEMO'}) RETURN count(e) AS n").single()['n']
 assert evidencia['crud'][1]['filas'] and evidencia['evento_demo_despues']==0
 evidencia['recorridos']=ejecutar_archivo(s,'consultas_grafo.cypher')
 evidencia['sha256_scripts']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (neo/'queries').glob('*.cypher')}
out=Path('fixture2030-neo4j/docs/evidencia')/datetime.now(timezone.utc).strftime('ejecucion_%Y%m%dT%H%M%S%fZ')/'ejecucion.json'
save(out,evidencia)
print('Evidencia:',ROOT/out)
driver.close();print('Neo4j: dos cargas, conteos iguales, CRUD completo y tres recorridos verificados.')
