# Example for the first lab of IIoT-Cloud
import time
from sense_hat import SenseHat, ACTION_PRESSED, ACTION_HELD, ACTION_RELEASED
import RPi.GPIO as GPIO
import json
import threading
import sys
from digi.xbee.devices import XBeeDevice
from digi.xbee.io import IOLine, IOMode
import paho.mqtt.client as mqtt

from azure.iot.device import IoTHubDeviceClient, Message

AUX_CONNECTION_STRING = 'HostName=icaiiotlabgroup01Lio.azure-devices.net;DeviceId=rpy;SharedAccessKey=e19eryiT6hpocWrCCUIr05Inog0RpnMktgw3TSE0MN4='
DEVICE_NAME = AUX_CONNECTION_STRING.split(";")[1].split("=")[1]

MAX_TEMP = 28
MAX_HUM = 50
MIN_LUX = 100

LUXPIN = 7
BUZZERPIN = 36


SERIALPORT = "/dev/ttyUSB0"
BAUDS = 9600
IOLINE_IN = IOLine.DIO1_AD1

sound_db = 0


def get_network_n_nodes(coordinator):

    xnet = coordinator.get_network()
    xnet.start_discovery_process(deep=True, n_deep_scans=1)
    while xnet.is_discovery_running():
        time.sleep(0.5)

    nodes = xnet.get_devices()

    return xnet, nodes


def aux_validate_connection_string():
    if not AUX_CONNECTION_STRING.startswith('HostName='):
        print("ERROR  - YOUR IoT HUB CONNECTION STRING IS NOT VALID")
        print("FORMAT - HostName=your_iot_hub_name.azure-devices.net;DeviceId=your_device_name;SharedAccessKey=your_shared_access_key")
        sys.exit()


def aux_iothub_client_init():
    client = IoTHubDeviceClient.create_from_connection_string(
        AUX_CONNECTION_STRING)
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
    print(diff)
    return diff


def calib_rpy_lux_sensor():
    slope = []
    n = []
    input("Cover the rpy sensor and press intro:")
    min_diff = get_lux_diff()
    input("Apply max light to the sensor and press intro:")
    max_diff = get_lux_diff()
    slope.append(-1023.0/(min_diff-max_diff))
    n.append(1023-max_diff*slope[-1])
    return slope, n


def calibrate_zigbee_sensors(nodes, pend, n):
    for remote_num in range(len(nodes)):
        input("Dar maxima luz al sensor {} y pulsar intro".format(remote_num))
        max_val = nodes[remote_num].get_adc_value(IOLINE_IN)
        pend.append(-1023.0/(1023-max_val))
        n.append(1023.0-(max_val*pend[-1]))
    return pend, n


def calib_sensors(nodes):
    slope, n = calib_rpy_lux_sensor()
    slope, n = calibrate_zigbee_sensors(nodes, slope, n)
    return slope, n


def get_lux(nodes, slope, n):
    measures = {}
    diff = get_lux_diff()
    measures['0'] = slope[0]*diff+n[0]

    for remote_num in range(len(nodes)):
        measure = nodes[remote_num].get_adc_value(IOLINE_IN)
        measures[str(remote_num+1)] = measure * \
            slope[remote_num+1]+n[remote_num+1]
    for key in dict.keys(measures):
        if measures[key] < 0:
            measures[key] = 0
        elif measures[key] > 1023:
            measures[key] = 1023
    return measures


def message_listener(client):
    while True:
        message = client.receive_message()
        #GPIO.output(BUZZERPIN, GPIO.HIGH)
        print("Message received")
        print("    Data: {}".format(message.data.decode("utf-8")))
        print("    Properties: {}".format(message.custom_properties))
        if 'Lux_cmd' in message.custom_properties:
            lux_event(message.custom_properties['Lux_cmd'])
        if 'Tmp_cmd' in message.custom_properties:
            tmp_event(message.custom_properties['Tmp_cmd'])
        #GPIO.output(BUZZERPIN, GPIO.LOW)


def lux_event(cmd_str):
    # Construccion del cliente
    clientM = mqtt.Client("SONOFF_pub")
    # Conexion con el broker
    clientM.connect("broker.hivemq.com", 1883)
    # Mantener el trafico de red con el broker
    clientM.loop_start()
    for item in cmd_str.split(';'):
        cmd = item.split(' ')[0]
        dev = item.split(' ')[1]
        msg = "%s" % (cmd)
        clientM.publish("IIoT/{}/relay/0/set".format(dev), msg)
        time.sleep(2)

    clientM.disconnect()


def tmp_event(cmd_str):
    # Construccion del cliente
    clientM = mqtt.Client("SONOFF_pub")
    # Conexion con el broker
    clientM.connect("broker.hivemq.com", 1883)
    # Mantener el trafico de red con el broker
    clientM.loop_start()
    msg = "%s" % (cmd_str)
    clientM.publish("IIoT/0/Temp", msg)
    time.sleep(2)
    clientM.disconnect()


def pushed_up(event):
    global sound_db
    if event.action != ACTION_RELEASED:
        sound_db = sound_db+1


def pushed_down(event):
    global sound_db
    if event.action != ACTION_RELEASED:
        sound_db = sound_db-1


if _name_ == "_main_":

    dict_data = {}

    # Configure pins for lux read
    GPIO.setmode(GPIO.BOARD)
    #GPIO.setup(BUZZERPIN, GPIO.OUT)

    # Instantieate the senseHat
    sense = SenseHat()
    sense.stick.direction_up = pushed_up
    sense.stick.direction_down = pushed_down

    # Validate Azure connection
    aux_validate_connection_string()
    client = aux_iothub_client_init()

    # ENABLE THE RECEPTION THREAD, DEFINING THE TARGET METHOD
    message_listener_thread = threading.Thread(
        target=message_listener, args=(client,))
    message_listener_thread.daemon = True
    message_listener_thread.start()

    # Create zigbee object and get the network
    coordinator = XBeeDevice(SERIALPORT, BAUDS)
    coordinator.open()
    xnet, nodes = get_network_n_nodes(coordinator)

    # Config nodes
    for remote in nodes:
        remote.set_io_configuration(IOLINE_IN, IOMode.ADC)
    del remote
    print("Red zigbee detectada: ")
    for remote in nodes:
        print(remote)

    # Calibrate Raspberry lux sensor
    slope, n = calib_sensors(nodes)

    while True:
        # get the temperature
        temp = sense.get_temperature()
        temp = round(temp, 2)
        # Get humidity
        humid = sense.get_humidity()
        humid = round(humid, 2)

        lux_measures = get_lux(nodes, slope, n)

        # Collection of data in data structure
        dict_data['device_name'] = DEVICE_NAME
        dict_data['temperature'] = temp
        dict_data['humidity'] = humid
        dict_data['luminosity'] = lux_measures
        dict_data['soud_db'] = sound_db
        # Transforming in to json
        json_dict_data = json.dumps(dict_data)
        # Creating an azure iot message object
        azure_iot_message = Message(json_dict_data)
        # Sending alarms
        if temp > MAX_TEMP:
            azure_iot_message.custom_properties['temperature_alert'] = 'true'
        else:
            azure_iot_message.custom_properties['temperature_alert'] = 'false'

        if humid > MAX_HUM:
            azure_iot_message.custom_properties['humidity_alert'] = 'true'
        else:
            azure_iot_message.custom_properties['humidity_alert'] = 'false'

#        if lux_v < MIN_LUX:
#            azure_iot_message.custom_properties['luminosity_alert'] = 'true'
#        else:
#            azure_iot_message.custom_properties['luminosity_alert'] = 'false'
        # Message encoding
        azure_iot_message.content_encoding = 'utf-8'
        azure_iot_message.content_type = 'application/json'
        # Sending the message
        print("Sending azure_iot_message: {}".format(azure_iot_message))
        client.send_message(azure_iot_message)
        print("Message successfully sent")

#        msg = "Temp: {}; Humid: {}; Lux: {}".format(temp, humid, round(lux_measures['0'],2))
#        sense.show_message(msg)

        #sense.show_letter('a', [0,0,0],[0,0,0])

      # sleep 5 seconds
        time.sleep(5)
