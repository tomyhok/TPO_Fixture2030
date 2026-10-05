import sys
import random
import time

def generar_puntos(total_puntos=10000000, archivo_salida="data_estadisticas.lp"):
    print(f"Generando {total_puntos} puntos de estadísticas en {archivo_salida}...")
    start_time = time.time()
    
    # 127 partidos en total, con 2 equipos por partido
    # Esto es una abstracción para distribuir la cardinalidad
    num_partidos = 127
    
    # Supongamos que todos los partidos ocurren en una ventana de 1 mes (aprox 2.5 millones de segundos)
    # Comenzando desde el 1 de junio de 2030 (1906512000 epoch aprox)
    timestamp_base = 1906512000
    
    puntos_generados = 0
    
    # Usaremos un buffer para no escribir línea por línea y saturar el I/O
    buffer = []
    buffer_size = 100000
    
    with open(archivo_salida, 'w') as f:
        # Repartimos equitativamente los puntos entre las series
        # Series totales = 127 partidos * 2 equipos = 254 series
        series_totales = num_partidos * 2
        puntos_por_serie = total_puntos // series_totales
        
        for p in range(1, num_partidos + 1):
            partido_id = f"M{p:03d}"
            
            # 2 equipos por partido
            for e in range(1, 3):
                equipo_id = f"EQ{p:03d}_{e}"
                
                # Simular estado inicial para este equipo
                posesion = random.uniform(30.0, 70.0)
                pases = 0
                tiros = 0
                usuarios = random.randint(10000, 500000)
                
                # Avanzamos el timestamp para este partido en intervalos regulares
                ts_actual = timestamp_base + (p * 3600) # un partido arranca 1h despues del otro
                
                for _ in range(puntos_por_serie):
                    # Actualizar valores con pequeña variación
                    posesion = max(10.0, min(90.0, posesion + random.uniform(-1.0, 1.0)))
                    pases += random.randint(0, 2)
                    tiros += random.choices([0, 1], weights=[99, 1])[0]
                    usuarios = max(1000, usuarios + random.randint(-5000, 5000))
                    
                    # Avanzar el tiempo 1 segundo para la serie
                    ts_actual += 1
                    
                    # Formato Line Protocol: tabla,tags fields timestamp
                    linea = f"estadisticas_partido,partido_id={partido_id},equipo_id={equipo_id} posesion_pct={posesion:.2f},pases_completados={pases}i,tiros={tiros}i,usuarios_activos={usuarios}i {ts_actual}"
                    buffer.append(linea)
                    puntos_generados += 1
                    
                    if len(buffer) >= buffer_size:
                        f.write("\n".join(buffer) + "\n")
                        buffer.clear()
                        # Imprimir progreso
                        print(f"Progreso: {puntos_generados}/{total_puntos} puntos generados...", end='\r')
                        
        # Vaciar el resto
        if buffer:
            f.write("\n".join(buffer) + "\n")
            
    elapsed = time.time() - start_time
    print(f"\nSe generaron {puntos_generados} puntos en {elapsed:.2f} segundos.")
    print(f"Cardinalidad estimada: {series_totales} series únicas.")

if __name__ == "__main__":
    puntos = 10000000
    if len(sys.argv) > 1:
        puntos = int(sys.argv[1])
    
    # Permite inyectar el archivo de salida
    salida = "data_estadisticas.lp"
    if len(sys.argv) > 2:
        salida = sys.argv[2]
        
    generar_puntos(puntos, salida)
