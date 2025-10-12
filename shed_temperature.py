import Adafruit_DHT
import time

# Sensor configuration
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 16  # GPIO Pin 16
LOW_TEMP_THRESHOLD = 12.0  # Low temperature threshold in Celsius
HIGH_TEMP_THRESHOLD = 18.0  # High temperature threshold in Celsius

def read_temperature():
    try:
        # Read from DHT11 sensor
        humidity, temperature = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
        
        if humidity is not None and temperature is not None:
            print(f"Temperature: {temperature:.1f}°C  Humidity: {humidity:.1f}%")
            if temperature < LOW_TEMP_THRESHOLD:
                print(f"WARNING: Temperature dropped below {LOW_TEMP_THRESHOLD}°C!")
                os.system('sudo ~/rpitx/./sendiq -s 250000 -f 433.9000e6 -t u8 -i ~/rpitx/heaton.iq')
            elif temperature > HIGH_TEMP_THRESHOLD:
                print(f"WARNING: Temperature rose above {HIGH_TEMP_THRESHOLD}°C!")
                os.system('sudo ~/rpitx/./sendiq -s 250000 -f 433.9000e6 -t u8 -i ~/rpitx/heatoff.iq')
        else:
            print("Failed to retrieve data from sensor")
            
    except Exception as e:
        print(f"Error reading sensor: {e}")

def main():
    print("Starting shed temperature monitoring...")
    while True:
        read_temperature()
        time.sleep(30)  # Read every 30 seconds

if __name__ == "__main__":
    main()
