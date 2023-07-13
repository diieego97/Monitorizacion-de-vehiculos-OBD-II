import machine
from machine import UART

class GPS_Neo6m:
    def __init__(self, tx_pin=17, rx_pin=16):
        self.uart = UART(1, baudrate=9600, tx=tx_pin, rx=rx_pin)
        

    def leer_gps(self):
        while True:
            if self.uart.any():  # Verifica si hay datos en el buffer de recepción
                gps = self.uart.readline()# Lee los datos del GPS
                if gps[0:6] == b'$GPRMC':  # Verifica si los datos son de tipo GPRMC
                    trama = gps.split(b',')# Divide los campos de los datos
                    if trama[2] == b'A':   # Verifica si hay una posición válida
                        lat = float(trama[3][0:2]) + float(trama[3][2:])/60.0   
                        # Convierte la latitud a grados decimales
                        if trama[4]== b'S':
                            lat=-lat
                        lon = float(trama[5][0:3]) + float(trama[5][3:])/60.0  
                        # Convierte la longitud a grados decimales
                        if trama[6]== b'W':
                            lon=-lon
                        speed = float(trama[7]) *  1.852  
                        # Convierte la velocidad de nudos a metros por segundo
                        return lat,lon,speed
                    else:
                        lat=None
                        lon=None
                        speed=None
                        return lat,lon,speed                



