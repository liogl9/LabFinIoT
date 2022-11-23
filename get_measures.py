# Example for the first lab of IIoT-Cloud 
import time
from sense_hat import SenseHat
import RPi.GPIO as GPIO
import json
import threading

from azure.iot.device import IoTHubDeviceClient, Message

AUX_CONNECTION_STRING = 'HostName=icaiiotlabgroup01Lio.azure-devices.net;DeviceId=rpy;SharedAccessKey=e19eryiT6hpocWrCCUIr05Inog0RpnMktgw3TSE0MN4='
DEVICE_NAME=AUX_CONNECTION_STRING.split(";")[1].split("=")[1]

MAX_TEMP = 28
MAX_HUM = 50
MIN_LUX = 100

LUXPIN = 7

def aux_validate_connection_string():
    if not AUX_CONNECTION_STRING.startswith( 'HostName=' ):
        print ("ERROR  - YOUR IoT HUB CONNECTION STRING IS NOT VALID")
        print ("FORMAT - HostName=your_iot_hub_name.azure-devices.net;DeviceId=your_device_name;SharedAccessKey=your_shared_access_key")
        sys.exit()
        
def aux_iothub_client_init():
    client = IoTHubDeviceClient.create_from_connection_string(AUX_CONNECTION_STRING)
    return client

def get_lux_diff():
   # Charge the capacitor
   GPIO.setup(LUXPIN, GPIO.OUT)
   GPIO.output(LUXPIN, GPIO.LOW)
   time.sleep(0.1)
   GPIO.setup(LUXPIN, GPIO.IN)
   currentTime = time.time()
   diff = 0
   # Measure time until discharge
   while(GPIO.input(LUXPIN) == GPIO.LOW):
       diff = time.time() - currentTime
   
   #time in miliseconds
   diff = diff*1000
   return diff

def get_lux(slope, n):
   diff = get_lux_diff()
   lux_v = slope*diff+n
   if lux_v < 0:
       lx_v = 0
   print(lux_v)
   return lux_v



def calib_lux_sensor():
    input("Cover the sensor and press intro:")
    min_diff = get_lux_diff()
    input("Apply max light to the sensor and press intro:")
    max_diff = get_lux_diff()
    slope = -1023.0/(min_diff-max_diff)
    n = 1023-max_diff*slope
    return slope, n
    
def message_listener(client):
    while True:
        message = client.receive_message()
        print("Message received")
        print( "    Data: {}".format( message.data.decode("utf-8")  ) )
        print( "    Properties: {}".format(message.custom_properties))
   
   

if __name__ == "__main__":
    
    dict_data = {}
    
    # Configure pins for lux read
    GPIO.setmode(GPIO.BOARD)
    
    # Instantieate the senseHat
    sense = SenseHat()
    aux_validate_connection_string()
    client = aux_iothub_client_init()
    
    #ENABLE THE RECEPTION THREAD, DEFINING THE TARGET METHOD
    message_listener_thread = threading.Thread(target=message_listener, args=(client,))
    message_listener_thread.daemon = True
    message_listener_thread.start()
    
    slope, n = calib_lux_sensor()
    
    while True:
       # get the temperature 
       temp = sense.get_temperature()
       temp = round(temp, 2)
       # Get humidity
       humid = sense.get_humidity()
       humid = round(humid,2)
       
       lux_v = get_lux(slope,n)
       
       
       # Collection of data in data structure
       dict_data['device_name'] = DEVICE_NAME
       dict_data['temperature'] = temp
       dict_data['humidity'] = humid
       dict_data['luminosity'] = lux_v
       # Transforming in to json
       json_dict_data = json.dumps(dict_data)
       #Creating an azure iot message object
       azure_iot_message = Message(json_dict_data)
       #Sending alarms
       if temp > MAX_TEMP:
           azure_iot_message.custom_properties['temperature_alert'] = 'true'
       else:
           azure_iot_message.custom_properties['temperature_alert'] = 'false'
       
       if humid > MAX_HUM:
           azure_iot_message.custom_properties['humidity_alert'] = 'true'
       else:
           azure_iot_message.custom_properties['humidity_alert'] = 'false'
           
       if lux_v < MIN_LUX:
           azure_iot_message.custom_properties['luminosity_alert'] = 'true'
       else:
           azure_iot_message.custom_properties['luminosity_alert'] = 'false'
       #Message encoding
       azure_iot_message.content_encoding='utf-8'
       azure_iot_message.content_type='application/json'
       #Sending the message
       print( "Sending azure_iot_message: {}".format(azure_iot_message) )
       client.send_message(azure_iot_message)
       print ( "Message successfully sent" )
       
       #msg = "Temp: {}; Humid: {}; Lux: {}".format(temp, humid, round(lux_v,2)) 
       
       
       #sense.show_letter('a', [0,0,0],[0,0,0])
     
     # sleep 5 seconds
       time.sleep(5)
