import uasyncio as asyncio
import network
import time
import machine
import bluetooth
import _thread
from math import radians, sin, cos, sqrt, atan2
from ble_advertising import decode_services, decode_name
from uthingsboard.client import TBDeviceMqttClient
from GPS_NEO6M_LIB import GPS_Neo6m
from BLE_ELM327_LIB import BLE_ELM327
import math

#INICIALIZAMOS LAS DISTINTAS CLASES
gps=GPS_Neo6m()
value_handle_write=0x000f #TIENE QUE SER EN HEXADECIMAL  value handle de 0xfff2 write
wf=network.WLAN(network.STA_IF)
#Definimos las variables globales.
CHAT_ID='xxxxx'
TOKEN_TELEGRAM='xxxxx'
SSID = 'xxx'
PASSWORD = 'xxxx'
TOKEN_THINGSBOARD='xxxx'

lat=None
lon=None
distancia=0
rpm=None
speed=None
temp_cool=None
presion=None
pos_acelerador=None
nivel_combustible=None
Error_lat=0.00003507348632812500
Error_lon=0.00003517292785644531
ble = bluetooth.BLE()
central = BLE_ELM327(ble)
central.MAC=b'f\x1e\x11\xf3E\xeb' #Dirección MAC de ELM327

def main():
    global lat,lon,rpm,velocidad,temp_cool,presion,pos_acelerador,nivel_combustible,distancia
    
    while True:
        #-------LECTURA-GPS -----------------------------
        if coche_en_movimiento():
            print("Coche en movimiento")
            #--------CONEXION WIFI-----------------------------
            print("Buscando conexión a internet...")
            if red_on():
                client = TBDeviceMqttClient('demo.thingsboard.io', access_token=TOKEN_THINGSBOARD)
                client.connect()
                print("Enviando mensaje a Telegram")
                mensaje=True  #Aviso de Thinsgboard en Telegram
                _thread.start_new_thread(Mensaje_telegram, (client,mensaje,distancia))
                #-------------Activo dispositivo ELM327-------------
                if inic_BLE():
               
                    lat1,lon1,speed_gps1= gps.leer_gps()
                    inicio = time.time()#tiempo inicio calcular distancia entre puntos cada cierto tiempo
                    
                    monitorizacion=True
                    while monitorizacion:
                        # Ejecutar las tareas
                        
                        loop = asyncio.get_event_loop()
                        loop.run_until_complete(ejecutar_tareas())
                        central.notify_data=bytearray()
                        #print("--------------------------------------------------")
                        #print("latitud =",lat,"Longitud =",lon,"RPM =",rpm,"velocidad =",velocidad,"temp refrigerante =",temp_cool,"Presion =",presion,"Posición acelerador =",pos_acelerador,"Nivel del combustible =",nivel_combustible
                        _thread.start_new_thread(telemetria, (client,))
                
                        #print("localizacion",lat1,lon1)
                        calcular_distancia_gps(lat1,lon1)
                        #print("Distancia recorrida",distancia)
                        lat1,lon1,speed_gps1= gps.leer_gps()
                        
                        if rpm is None or rpm ==0:#Esperar 30 segundos para confirmar que el coche esta apagado
                            #print("Esperando...")
                            monitorizacion=comprobacion_RPM()
                            #print("salindo de espera")
                        
                        
            #----------El coche se ha apagado ----------------------
                    mensaje=False
                    print("Fin trayecto Telegram")
                    print("Distancia",distancia)
                    Mensaje_telegram(client,mensaje,distancia)
                    wf.disconnect() #quitamos conexion wifi
                    central.disconnect()
                    distancia=0
                else:
                    print("No se puede conectar a ELM327")
            
            else:
                print("No se ha encontrado conexión a internet")
        else:        
            print("Coche detenido")        
            #time.sleep_ms(3000)
            machine.deepsleep(30000)#30 segundos en modo deepsleep

            
    
async def obtener_rpm():
    
    #print("Obteniendo RPM...")
    rpm=central.get_engine_rpm()
    central.notify_data=bytearray()
    return rpm
        
       
async def obtener_velocidad():
    
    #print("Obteniendo VELOCIDAD...")
    speed=central.get_speed()
    central.notify_data=bytearray()
    return speed

async def obtener_temp_refrigerante():
    
    #print("Obteniendo temperatura refrigerante...")
    temp_cool=central.get_engine_coolant_temperature()
    central.notify_data=bytearray()
    return temp_cool
   
async def obtener_presion():
    
    #print("Obteniendo presion...")
    presion=central.get_intake_manifold_pressure()
    central.notify_data=bytearray()
    return presion

async def obtener_pos_acelerador():
    
    #print("Obteniendo posicion del acelerador...")
    pos_acelerador=central.get_pedal_accelerator_position()
    central.notify_data=bytearray()
    return pos_acelerador
    

async def obtener_nivel_combustible():
    
    #print("Obteniendo nivel del combustible...")
    nivel_combustible=central.get_fuel_tank_level()
    central.notify_data=bytearray()
    return nivel_combustible


async def lectura_gps():
    await asyncio.sleep(0.2)      #se ejecuta cada segundo 
    latitud,longitud,velocidad=gps.leer_gps()
    return latitud,longitud
  
def telemetria(client):
    global lat,lon,rpm,velocidad,temp_cool,presion,pos_acelerador,nivel_combustible
    #client = TBDeviceMqttClient('demo.thingsboard.io', access_token=TOKEN_THINGSBOARD)
    #client.connect()
    telemetry = {'latitude': lat, 'longitude': lon,'RPM':rpm,'velocidad':velocidad,'temp_refrigetante':temp_cool,
                'pres_Admision':presion,'pos_acelerador':pos_acelerador,'nivel_combustible':nivel_combustible}                           
    client.send_telemetry(telemetry)
    #discnonet
    #espera=true
    #hacerlo por argumentos el def telemetria(client):
    _thread.exit() #Se libera el thread
    
def Mensaje_telegram(client,mensaje,distancia):
    #client = TBDeviceMqttClient('demo.thingsboard.io', access_token=TOKEN_THINGSBOARD)
    #client.connect()
    telemetry={'Mensaje':mensaje,'Distancia':distancia}                          
    client.send_telemetry(telemetry)
    _thread.exit() #Se libera el thread
     
 
# Función principal para ejecutar las tareas
async def ejecutar_tareas():
    global rpm,velocidad,temp_cool,presion,pos_acelerador,nivel_combustible,lat,lon
    tarea_GPS=asyncio.create_task(lectura_gps())
    rpm=await obtener_rpm()
    velocidad=await obtener_velocidad()
    temp_cool=await obtener_temp_refrigerante()
    presion=await obtener_presion()
    pos_acelerador=await obtener_pos_acelerador()
    nivel_combustible=await obtener_nivel_combustible()
    if lectura_gps():
        resultados = await tarea_GPS
        lat=resultados[0]
        lon=resultados[1]
    #tarea_telemetria=asyncio.create_task(telemetria())
    


def calcular_distancia_gps(latitud,longitud,Error_lat=0.00003507348632812500,Error_lon=0.00003517292785644531): #se hara en un thread
    global distancia
    #print("Calculando distancia GPS...")
    lat2,lon2,speed_gps2= gps.leer_gps()
    #print("localizacion 2",lat2,lon2)
    
    if latitud and longitud and lat2 and lon2:
        result_lat=abs(latitud-lat2)   
        result_lon=abs(longitud-lon2)
    
    if (result_lat > Error_lat or result_lon > Error_lon): #Evitar sumar metros de error de gps cuando el coche esta detenido
        distancia=calcular_distancia(latitud,longitud,lat2,lon2)+distancia
    #_thread.exit()
    
#----------------------------------------------------------------------------------------------------------------------
   
def inic_BLE():
    
    not_found=False

    def on_scan(addr_type, addr, name):
        if addr_type is not None:
            print("Found peripheral:", addr_type, bytes(addr), name)
            central.connect()
        else:
            nonlocal not_found
            not_found = True
            print("No peripheral found.")
    
    central.scan(callback=on_scan)

    
 # Wait for connection...
    while not central.is_connected():
        time.sleep_ms(100)
        if not_found:
            return False
            
    time.sleep_ms(1000)
    # a veces se conecta pero falla al encontrar caracteristicas
    if not central.fallo_characteristic: 
        central.inicELM327()
        return True
    else:
        return False


def red_on():
    espera=0
    wf.active(True)
    wf.connect(SSID,PASSWORD)
    while not wf.isconnected() and espera < 60:
        #print(".")
        espera=espera+1 #tiempo para conexion a internet
        time.sleep(1)
        
    return wf.isconnected()

def Telegram_inic():
    inicio=time.ticks_ms()
    bot = utelegram.ubot(TOKEN_TELEGRAM)
    #bot= ubot(TOKEN_TELEGRAM)
    bot.send(CHAT_ID, 'INICIO DE TRAYECTO')
    fin = time.ticks_ms()
    tiempo_transcurrido = time.ticks_diff(fin, inicio)
    print("Tiempo transcurrido: {} ms".format(tiempo_transcurrido))
    

def calcular_distancia(latitud1,longitud1,latitud2, longitud2):
  
    R = 6371  # Radio medio de la Tierra en kilómetros
    latitud1_rad = math.radians(latitud1)
    longitud1_rad = math.radians(longitud1)  
    latitud2_rad = math.radians(latitud2)
    longitud2_rad = math.radians(longitud2)
    dlat = latitud2_rad - latitud1_rad
    dlon = longitud2_rad - longitud1_rad
    a = math.sin(dlat/2) ** 2 + math.cos(latitud1_rad) * math.cos(latitud2_rad) * math.sin(dlon/2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distancia = R * c
    return distancia

def coche_en_movimiento(Error_lat=0.00004507348632812500,Error_lon=0.00004517292785644531):
    
    lat_ant,lon_ant,speed_ant= gps.leer_gps()
    time.sleep(2)
    lat_act,lon_act,speed_act=gps.leer_gps()
    
    if lat_ant and lon_ant and lat_act and lon_act:
        result_lat=abs(lat_ant-lat_act)   
        result_lon=abs(lon_ant-lon_act)
        if (result_lat > Error_lat or result_lon > Error_lon):
            return True
        else:
            return False
    else:
        return False

def comprobacion_RPM():
    for i in range(30):
        central.write_data(value_handle_write,b'010C\r\n') #rpm
        time.sleep(1)
        string=central.bytearraytostring(central.notify_data)
        central.notify_data=bytearray()
        if (central.es_hexadecimal(string[-4:]) and string):
            rpm= int(string[-4:],16)/4
        else:
            rpm= None
        if rpm and rpm > 0 :
            result= True
            break
        else:
            result= False
    return result
#-------------------------------------------------------------------------------------------------------------------------------

while True:
    try:
        main()
    except OSError:
        # Manejo de errores de red
        print("Se produjo un error de red")
        
    except Exception as e:
        print("Se produjo algún fallo")
        mensaje=False
        Mensaje_telegram(client,mensaje,distancia)
        wf.disconnect() #quitamos conexion wifi
        time.sleep(5)  # Espera unos segundos antes de reiniciar
        machine.reset() 





