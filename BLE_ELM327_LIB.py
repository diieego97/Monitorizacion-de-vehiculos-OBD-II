# This example finds and connects to a peripheral running the
# UART service (e.g. ble_simple_peripheral.py).

import bluetooth
import random
import struct
import time
import micropython
import binascii
from binascii import hexlify
from time import sleep
import machine, ntptime

from ble_advertising import decode_services, decode_name

from micropython import const

VERBOSITY = 0


#direcion MAC OBD2
OBD2MAC=bytes(b'f\x1e\x11\xf3E\xeb')

# Time constants (T_WAIT: ms / others: s)
_T_WAIT  = const(100)
_T_RETRY = const(10)
_T_CYCLE = const(20)





_IRQ_CENTRAL_CONNECT                = const(1)
_IRQ_CENTRAL_DISCONNECT             = const(2)
_IRQ_GATTS_WRITE                    = const(3)
_IRQ_GATTS_READ_REQUEST             = const(4)
_IRQ_SCAN_RESULT                    = const(5)
_IRQ_SCAN_DONE                      = const(6)
_IRQ_PERIPHERAL_CONNECT             = const(7)
_IRQ_PERIPHERAL_DISCONNECT          = const(8)
_IRQ_GATTC_SERVICE_RESULT           = const(9)
_IRQ_GATTC_SERVICE_DONE             = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT    = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE      = const(12)
_IRQ_GATTC_DESCRIPTOR_RESULT        = const(13)
_IRQ_GATTC_DESCRIPTOR_DONE          = const(14)
_IRQ_GATTC_READ_RESULT              = const(15)
_IRQ_GATTC_READ_DONE                = const(16)
_IRQ_GATTC_WRITE_DONE               = const(17)
_IRQ_GATTC_NOTIFY                   = const(18)
_IRQ_GATTC_INDICATE                 = const(19)
_IRQ_GATTS_INDICATE_DONE            = const(20)
_IRQ_MTU_EXCHANGED                  = const(21)
_IRQ_L2CAP_ACCEPT                   = const(22)
_IRQ_L2CAP_CONNECT                  = const(23)
_IRQ_L2CAP_DISCONNECT               = const(24)
_IRQ_L2CAP_RECV                     = const(25)
_IRQ_L2CAP_SEND_READY               = const(26)
_IRQ_CONNECTION_UPDATE              = const(27)
_IRQ_ENCRYPTION_UPDATE              = const(28)
_IRQ_GET_SECRET                     = const(29)
_IRQ_SET_SECRET                     = const(30)


_ADV_IND = const(0x00)
_ADV_DIRECT_IND = const(0x01)
_ADV_SCAN_IND = const(0x02)
_ADV_NONCONN_IND = const(0x03)

# Address types (cf. https://docs.micropython.org/en/latest/library/bluetooth.html)
ADDR_TYPE_PUBLIC = const(0x00)
ADDR_TYPE_RANDOM = const(0x01)


#OBD2 services/CHARACTERISTICS UUIDs-------------------------------------------------------------------------------------

_PRUEBA1UUID = bluetooth.UUID(0x1800)#GENERIC ACCES
_PRUEBA2UUID = bluetooth.UUID(0x1801)#GENERIC ATRIBUTE
_PRUEBA3UUID = bluetooth.UUID(0xFFF0)#UNKNOW
_PRUEBA4UUID = bluetooth.UUID(0xAE30)
_PRUEBA5UUID = bluetooth.UUID(0x1804)#TX POWER
_PRUEBA6UUID = bluetooth.UUID(0x180F)#BATERY SERVICE
_AUXREAD=bluetooth.UUID(0xFFF1)
_AUXWRITE=bluetooth.UUID(0xFFF2)
_AUX=bluetooth.UUID(0x2a00)

#value handle characteristics 

value_handle_read=0x000c #TIENE QUE SER EN HEXADECIMAL  value handle de 0xfff1 read
value_dschandle=0x000d #TIENE QUE SER EN HEXADECIMAL  value handle de descriptor0x2902 de  0xfff1 read
value_handle_write=0x000f #TIENE QUE SER EN HEXADECIMAL  value handle de 0xfff2 write

# ValORES AT OBD2 ELM327


#PIDs 


# States of state machine
S_INIT                = const(0)
S_SCAN_DONE           = const(1)
S_SERVICE_DONE        = const(2)
S_CHARACTERISTIC_DONE = const(3)
S_READ_FIRMWARE_DONE  = const(4)
S_MODE_CHANGE_DONE    = const(5)
S_READ_SENSOR_DONE    = const(6)






def prettify(mac_string):
    return ':'.join('{:02x}'.format(b) for b in mac_string)

class BLE_ELM327:

    def __init__(self, ble):
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)

        self._reset()

    def _reset(self):
    
     # Init public members.
        self.state       = S_INIT
        self.search_addr = None
        self.addr_found  = False
        self.name        = None
        self.rssi        = 0
        self.version     = None
        self.battery     = None
        self.rpm        = None
        self.tempcoolant     = None
        
        # Cached name and address from a successful scan.
    
        self._name = None
        self._addr_type = None
        self._addr = None
        # Cached value (if we have one).
        self._value      = None

        # Callbacks for completion of various operations.
        # These reset back to None after being invoked.
        self._scan_callback      = None
        self._conn_callback      = None
        self._serv_done_callback = None
        self._char_done_callback = None
        self._read_callback      = None
        self._write_callback     = None
        # Persistent callback for when new data is notified from the device.
        self._notify_callback = None

        # Connected device.
        self._conn_handle = None
        self._start_handle = None
        self._end_handle = None
        self._ca_handle=None
        self._dsc_handle=None
        self.char_data = bytearray(30)
        self.read_flag = None
        self.write_flag = None
        self.notify = None
        self.connected = False
        self.notify_data=bytearray()
        self.MAC=bytearray()
        
    
        
        
    

    def _irq(self, event, data):
        
        """
        Interrupt request handler.
        See https://docs.micropython.org/en/latest/library/ubluetooth.html for description.
        Parameters:
            event (int):  interrupt request ID
            data (tuple): event specific data as tuple  
        """
        
        if event == _IRQ_SCAN_RESULT:
            
            addr_type, addr, adv_type, rssi, adv_data = data
            
        
            #if bytes(addr)== b'f\x1e\x11\xf3E\xeb':
            if bytes(addr)== self.MAC:
            # Found a potential device, remember it and stop scanning
            
                self._addr_type = addr_type
                self.rssi = rssi
                self.addr_found = True
                self._addr = addr
                _adv_data = bytes(adv_data)
                _name = decode_name(_adv_data) or "?"
                if _name!='?':
                    self._name=_name
                
                
                print("DISPOSITIVO CONECTADO:",prettify(self._addr),"nombre:",self._name)    
            
                self._ble.gap_scan(None)
                
            
        

        elif event == _IRQ_SCAN_DONE:
            if self._scan_callback:
                if self._addr:
                    # Found a device during the scan (and the scan was explicitly stopped).
                    self._scan_callback(self._addr_type, self._addr, self._name)
                    self._scan_callback = None
                else:
                    # Scan timed out.
                    self._scan_callback(None, None, None)
                    

        elif event == _IRQ_PERIPHERAL_CONNECT:
            # Connect successful.
            # gap_connect() successful.
            conn_handle, addr_type, addr = data
            if addr_type == self._addr_type and addr == self._addr:
                self._conn_handle = conn_handle
                self._ble.gattc_discover_services(self._conn_handle)

        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            # Disconnect (either initiated by us or the remote end).
            conn_handle, _, _ = data
            if conn_handle == self._conn_handle:
                # If it was initiated by us, it'll already be reset.
                self._reset()
                
#-----------------------SERVICE-------------------------------------------------------------------------------------

        elif event == _IRQ_GATTC_SERVICE_RESULT:
            # Connected device returned a service.
            
            conn_handle, start_handle, end_handle, uuid = data
            
            print("services", data)
            if conn_handle == self._conn_handle and uuid == _PRUEBA3UUID:
                
                self._start_handle, self._end_handle = start_handle, end_handle
        

        elif event == _IRQ_GATTC_SERVICE_DONE:
            # Service query complete.
            
            self.state = S_SERVICE_DONE
            ###obtengo characteristics de services especifico
            if self._start_handle and self._end_handle:
                self._ble.gattc_discover_characteristics(
                    self._conn_handle, self._start_handle, self._end_handle
                )
            else:
                print("fallo en self._ble.gattc_discover_characteristics() ")
                
#-----------------------CHARACTERISTIC-------------------------------------------------------------------------------------

        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            # Connected device returned a characteristic.
            
            conn_handle, def_handle, value_handle, properties, uuid = data
            print("characteristic",data)
            print('Value handle {:02x}'.format(value_handle))
            
            if conn_handle == self._conn_handle and uuid == _AUXREAD:
                self._ca_handle = value_handle
                
            
        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            # Characteristic query complete.
            self.state = S_CHARACTERISTIC_DONE
            if self._ca_handle is not None :
                self._ble.gattc_discover_descriptors(self._conn_handle, self._start_handle, self._end_handle)
                # We've finished connecting and discovering device, fire the connect callback.
                if self._conn_callback:
                    self._conn_callback()
                    
            else:
                print("Failed to find  characteristic.")
                
#--------------------DESCRIPTORS---------------------------------------------------------------

        elif event == _IRQ_GATTC_DESCRIPTOR_RESULT:
        # Called for each descriptor found by gattc_discover_descriptors().
            conn_handle, dsc_handle, uuid = data
            print("DESCRIPTOR",data)
           
            print('Value handle description {:02x}'.format(dsc_handle))
            self._dsc_handle=dsc_handle
                
            
        elif event == _IRQ_GATTC_DESCRIPTOR_DONE:
        # Called once service discovery is complete.
        # Note: Status will be zero on success, implementation-specific value otherwise.
            conn_handle, status = data
        
#--------------------------------------------------------------------------------------------
       
      
        elif event == _IRQ_GATTS_WRITE:
            # A central has written to this characteristic or descriptor.
            self._conn_handle, attr_handle = data
            print ('A central has written to this characteristic or descriptor.', self._conn_handle, attr_handle)

        elif event == _IRQ_GATTC_WRITE_DONE:
            # A gattc_write() has completed.
            self._conn_handle, value_handle, status = data
            #print('A gattc_write() has completed - status.', self._conn_handle, value_handle, status)
            self.write_flag = True
            
            
        elif event == _IRQ_GATTC_READ_RESULT:
            # A read completed successfully.
            conn_handle, value_handle, char_data = data
           
            for b in range(len(char_data)):
                self.char_data[b] = char_data[b]
            print("leer dato read=",self.char_data)
                
            self.read_flag = True
     
        elif event == _IRQ_GATTC_READ_DONE:
            # Read completed (no-op).
            conn_handle, value_handle, status = data
            self.read_flag = True
            
            
        elif event == _IRQ_GATTC_NOTIFY:
         # A server has sent a notify request
            conn_handle, value_handle, notify_data = data
            
            for i in range(len(notify_data)-1):
                if notify_data[i] == 13 and notify_data[i+1] == 13 :#13=salto de linea en codigo ASCII
                    break
                self.notify_data.append(notify_data[i])
                
            #print("leer notify =",self.notify_data)
            
    
            self.notify = True
           
            
##------------------------------------------------------------------------------------------------------------------------------------
    
    # Returns true if we've successfully connected and discovered characteristics.
    def is_connected(self):
        return (
            self._conn_handle is not None
            and self._ca_handle is not None
        )

    # Find a device advertising the environmental sensor service.
    def scan(self, callback=None):
        self._addr_type = None
        self._addr = None
        self._scan_callback = callback
        self._ble.gap_scan(2000, 30000, 30000,True)
        
        
        
    # Connect to the specified device (otherwise use cached address from a scan).
    def connect(self, addr_type=None, addr=None, callback=None):
        self._addr_type = addr_type or self._addr_type
        self._addr = addr or self._addr
        self._conn_callback = callback
        if self._addr_type is None or self._addr is None:
            return False
        self._ble.gap_connect(self._addr_type, self._addr)
        return True
        
       
    # Disconnect from current device.
    def disconnect(self):
        try:
            conn = self._ble.gap_disconnect(self.conn_handle)
            self._reset()
        except Exception as e:
            return False
            

        # returns false on timeout
        timer = 0
        while self.is_connected:
            print ('.',end='')
            sleep(1)
            timer += 1
            if timer > 60:
                return False
        return True



        
        
    def read_data(self, value_handle):
        #self.read_flag = False
       
        print('Reading Data')
        try:
            self._ble.gattc_read(self._conn_handle, value_handle)
        except Exception as e:
            debug('Error: Read ' + str(e))
            return False
       
        return True

        
        
    def write_data(self, value_handle, data):
        
        try:
            self._ble.gattc_write(self._conn_handle, value_handle, data, 1)
        except Exception as e:
            
            return False
        
        return True

##--------------------DISPOSITIVO ELM327----------------------------------------------------------------------------------------------------------------   
       
    def inicELM327(self):
        
        self.write_data(value_dschandle,b'\x01\x00')
        print("Notificaciones activas")
        time.sleep_ms(100)
        self.write_data(value_handle_write,b'ATZ\r\n')
        print("Reinicio de dispositivo con ATZ")
        time.sleep_ms(100)
        self.write_data(value_handle_write,b'ATSP0\r\n')
        print("Comunicación OBD-II en modo automático ATSP0")
        time.sleep_ms(100)
        self.write_data(value_handle_write,b'ATE0\r\n')
        print("Modo eco desactivado con ATE0")
        time.sleep_ms(100)
        self.notify_data=bytearray()
        #self.write_data(value_handle_write,b'010C\r\n')
        #print("primer comando para obtener RPM")
        #time.sleep_ms(100)
        #inic tambien rpm por ejemplo porque en la primera sale searching en el bytearray
        #ver tiempo que tarda cada respuesta
        
        return True
    
    def es_hexadecimal(self,string):
        last = string
        return all(char in '0123456789ABCDEFabcdef' for char in last)

    def bytearraytostring(self,data):
        data=self.notify_data.decode()
        line = data.replace('\r', '').replace('>', '').replace(' ', '')
        return line
        
        
    def read_battery_voltage(self):
        self.write_data(value_handle_write,b'ATRV\r\n')
        time.sleep_ms(500)
        string=self.bytearraytostring(self.notify_data)
        return string

   
    def get_engine_coolant_temperature(self):
        self.write_data(value_handle_write,b'0105\r\n') #temperatura refrigerante
        string=self.bytearraytostring(self.notify_data)
        while (string[-2:]=="..") or not string :       #espera hasta que recibe datos
            string=self.bytearraytostring(self.notify_data) # Leer respuesta
        if self.es_hexadecimal(string[-2:]):
            return int(string[-2:],16)-40

    def get_intake_manifold_pressure(self):
        self.write_data(value_handle_write,b'010B\r\n') #presion del colector de admision
        string=self.bytearraytostring(self.notify_data)
        while (string[-2:]=="..") or not string :       #espera hasta que recibe datos
            string=self.bytearraytostring(self.notify_data) # Leer respuesta
            #print("notificacion ELM327 bucle ",central.notify_data)
            #print("Notificacion pasado  String bucle",string)
        if self.es_hexadecimal(string[-2:]):
            return int(string[-2:],16)

    def get_engine_rpm(self):
        self.write_data(value_handle_write,b'010C\r\n') #rpm
        string=self.bytearraytostring(self.notify_data)
        while (string[-2:]=="..") or not string :       #espera hasta que recibe datos
            string=self.bytearraytostring(self.notify_data) # Leer respuesta
            #print("notificacion ELM327 bucle ",central.notify_data)
            #print("Notificacion pasado  String bucle",string)
        if (self.es_hexadecimal(string[-4:])):
            return int(string[-4:],16)/4
        else:
            return None

    def get_speed(self):
        self.write_data(value_handle_write,b'010D\r\n') #velocidad
        string=self.bytearraytostring(self.notify_data)
        while (string[-2:]=="..") or not string :       #espera hasta que recibe datos
            string=self.bytearraytostring(self.notify_data) # Leer respuesta
        if self.es_hexadecimal(string[-2:]):
            return int(string[-2:],16)

    def get_engine_oil_temperature(self):
        self.write_data(value_handle_write,b'015C\r\n')
        while (string[-2:]=="..") or not string :       #espera hasta que recibe datos
            string=self.bytearraytostring(self.notify_data) # Leer respuesta
        if self.es_hexadecimal(string[-2:]):
            temp=string[-2:]
            return int(temp,16)-40
    
    def get_pedal_accelerator_position(self):
        self.write_data(value_handle_write,b'0149\r\n') #POSICION DEL PEDAL DEL ACELERADOR
        string=self.bytearraytostring(self.notify_data)
        while (string[-2:]=="..") or not string :       #espera hasta que recibe datos
            string=self.bytearraytostring(self.notify_data) # Leer respuesta
        if self.es_hexadecimal(string[-2:]):
            pos=string[-2:]
            return int(pos,16)/2.55
        
    def get_fuel_tank_level(self):
        self.write_data(value_handle_write,b'012F\r\n') #NIVEL DE COMBUSTIBLE
        string=self.bytearraytostring(self.notify_data)
        while (string[-2:]=="..") or not string :       #espera hasta que recibe datos
            string=self.bytearraytostring(self.notify_data) # Leer respuesta
        if self.es_hexadecimal(string[-2:]):
            fuel=string[-2:]
            return int(fuel,16)/2.55


