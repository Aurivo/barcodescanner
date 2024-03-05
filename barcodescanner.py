import time
import evdev
from evdev import InputDevice, ecodes
from multiprocessing import Process, Value
import RPi.GPIO as GPIO
import requests
import aiohttp
import asyncio

G_LED_PIN = 7
R_LED_PIN = 8
B_LED_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(G_LED_PIN, GPIO.OUT)
GPIO.setup(R_LED_PIN, GPIO.OUT)
GPIO.setup(B_LED_PIN, GPIO.OUT)

BLINK_TIMER = 0.5

# Shared blink values using Value
B_BLINK = Value('b', True)  # Shared boolean value
R_BLINK = Value('b', True)
G_BLINK = Value('b', True)

# URLS
getInfoUrl = "http://api.cgold.local/api/adicomms/getstatus"
sendBarcodeUrl = "http://api.cgold.local/api/acfshipping/load_truck"
#getInfoUrl = "http://192.168.86.72:5000/processdata"
#sendBarcodeUrl = "http://192.168.86.72:5000/data"
BAY = ""
BARCODE = ""

def loop_a():
    global B_BLINK, R_BLINK, G_BLINK, BLINK_TIMER
    ledon = False
    while 1:
        if ledon:
            if B_BLINK.value:
                GPIO.output(B_LED_PIN, GPIO.HIGH)
            if R_BLINK.value:
                GPIO.output(R_LED_PIN, GPIO.HIGH)
            if G_BLINK.value:
                GPIO.output(G_LED_PIN, GPIO.HIGH)
            ledon = False
        else:
            if B_BLINK.value:
                GPIO.output(B_LED_PIN, GPIO.LOW)
            if R_BLINK.value:
                GPIO.output(R_LED_PIN, GPIO.LOW)
            if G_BLINK.value:
                GPIO.output(G_LED_PIN, GPIO.LOW)
            ledon = True
        time.sleep(BLINK_TIMER)

def keyboard_listener(BAY):
    keyboard_device = InputDevice("/dev/input/event0")
    try:
        for event in keyboard_device.read_loop():
            listen_for_key(event, BAY)
    finally:
        keyboard_device.close()  # Ensure device closure

def listen_for_key(event, BAY):
    global BARCODE
    if event.type == ecodes.EV_KEY and event.value == 1:  # Check for key press
        key_name = evdev.ecodes.KEY[event.code]  # Access key names using KEY
        if event.code == 28:
            print("Enter Pressed")
            asyncio.run(processShipment(BARCODE, BAY))
            BARCODE = ""
        else:
            BARCODE += key_name.replace("KEY_", "")

def getMyInfo():
    global getInfoUrl
    try:
        response = requests.get(getInfoUrl)
        # Check the status code

        res = {"error": False, "status_code": response.status_code, "data": response.json()}
#       data = response.json()
        writeToFile(f"Response: {response.status_code} res: {res}")
        # Access the response content
        return res
    except requests.exceptions.RequestException as e:
        print('Error sending request:', e)
        res = {"error": False, "status_code": "error", "data": {"bay": "error bay"}}
        return res
    
async def processShipmentAsync(bcode, BAY):
    global sendBarcodeUrl
    writeToFile(f"Sending Data to api: {bcode} and bay {BAY} url: {sendBarcodeUrl}")

    # Prepare data for POST request
    data = {"barcode": bcode, "bay": BAY}

    LEDState('processing')

    async with aiohttp.ClientSession() as session:
        try:
            # Make asynchronous POST request
            async with session.post(sendBarcodeUrl, json=data) as response:
                response.raise_for_status()

                print('Request successful. Status code:', response.status)
                res = await response.json()  # Await JSON response
                print('Response data:', res)
                writeToFile(f"response {res}")

                if response.status == 201:
                    writeToFile(f"Data sent successfully. Response: {res}")
                    if res['message'] == "success":
                        LEDState("barcode_ok")
                    else:
                        LEDState("barcode_error")
        except aiohttp.ClientError as e:
            print('Error sending request:', e)
            LEDState("barcode_error")

def processShipment(bcode, BAY):
    global sendBarcodeUrl

    # Data to be sent in the request body (as a dictionary)
    data = {"barcode": bcode, "bay": BAY}

    # Send the POST request and store the response object
    response = requests.post(sendBarcodeUrl, data=data)

    # Check if the request was successful
    if response.status_code == 200:
        # Print the response content
        print(response.text)
    else:
        # Print an error message
        print(f"Error: {response.status_code}")
    
def writeToFile(msg):
    with open("barcode.txt", "a") as file:
        file.write(f"{msg}\n")

def deviceIdentification():
    global B_BLINK, R_BLINK, G_BLINK
    global BAY
    LEDState('processing')
    res = getMyInfo()
    #print(res)
    #print(res['error'])
    print(res["data"])
    if not res['error']:
        BAY = res["data"]["data"][0]["bay"]
        LEDState('ready')
        Process(target=keyboard_listener(BAY)).start()
    else:
        R_BLINK.value = True
    print(f"B: {B_BLINK.value} G: {G_BLINK.value} R: {R_BLINK.value} BAY: {BAY}")

def LEDState(state):
    global B_BLINK, R_BLINK, G_BLINK
    print(f"State: {state}")
    if state == 'ready':
        B_BLINK.value = False
        R_BLINK.value = False
        G_BLINK.value = False
        GPIO.output(B_LED_PIN, GPIO.HIGH)
        GPIO.output(R_LED_PIN, GPIO.LOW)
        GPIO.output(G_LED_PIN, GPIO.LOW)
    elif state == 'processing':
        B_BLINK.value = True
        R_BLINK.value = False
        G_BLINK.value = False
        GPIO.output(R_LED_PIN, GPIO.LOW)
        GPIO.output(G_LED_PIN, GPIO.LOW)
    elif state == 'barcode_ok':
        B_BLINK.value = False
        R_BLINK.value = False
        G_BLINK.value = False
        GPIO.output(R_LED_PIN, GPIO.LOW)
        GPIO.output(B_LED_PIN, GPIO.HIGH)
        GPIO.output(G_LED_PIN, GPIO.HIGH)
    elif state == 'barcode_error':
        B_BLINK.value = False
        R_BLINK.value = False
        G_BLINK.value = False
        GPIO.output(G_LED_PIN, GPIO.LOW)
        GPIO.output(B_LED_PIN, GPIO.HIGH)
        GPIO.output(R_LED_PIN, GPIO.HIGH)
    else:
        B_BLINK.value = True
        R_BLINK.value = True
        GPIO.output(G_LED_PIN, GPIO.LOW)

if __name__ == '__main__':
    Process(target=loop_a).start()
    #Process(target=keyboard_listener).start()
    deviceIdentification()
