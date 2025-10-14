#   Added button to manually toggle heater on and off
import Adafruit_DHT
import tkinter as tk
from tkinter import ttk
import time
import threading
import os

# Sensor configuration
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 16  # GPIO Pin 16
LOW_TEMP_THRESHOLD = 13.0  # Low temperature threshold in Celsius
HIGH_TEMP_THRESHOLD = 20.0  # High temperature threshold in Celsius
HUMIDITY_THRESHOLD = 75.0  # High humidity threshold in percentage
HEATER_DURATION = 40 * 60  # 40 minutes in seconds

class ShedMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shed Temperature & Humidity Monitor")
        
        # Configure window
        self.root.geometry("400x450")  # Height accommodates all widgets
        self.root.configure(bg="#0000ff")  # Blue background
        
        # Initialize heater states and counters
        self.low_temp_warning_count = 0
        self.heater_on = False
        self.heater_off_sent = False
        self.heater_on_time = None  # Track when heater was turned on
        self.manually_activated = False  # Track if heater was turned on manually
        
        # Create and configure main frame
        self.frame = ttk.Frame(self.root, padding="10")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.frame.configure(style="Blue.TFrame")
        
        # Configure style for frame background
        style = ttk.Style()
        style.configure("Blue.TFrame", background="#0000ff")
        
        # Labels for temperature, humidity, warnings, status, and runtime
        self.temp_label = ttk.Label(self.frame, text="Temperature: --.-°C", font=("Arial", 21), 
                                  foreground="white", background="#0000ff")
        self.temp_label.grid(row=0, column=0, pady=10, sticky=tk.W)
        
        self.humidity_label = ttk.Label(self.frame, text="Humidity: --.-%", font=("Arial", 21), 
                                      foreground="white", background="#0000ff")
        self.humidity_label.grid(row=1, column=0, pady=10, sticky=tk.W)
        
        self.low_temp_count_label = ttk.Label(self.frame, text="Low Temp Warnings: 0", font=("Arial", 18), 
                                            foreground="white", background="#0000ff")
        self.low_temp_count_label.grid(row=2, column=0, pady=10, sticky=tk.W)
        
        self.heater_status_label = ttk.Label(self.frame, text="Heater: Off", font=("Arial", 18), 
                                           foreground="white", background="#0000ff")
        self.heater_status_label.grid(row=3, column=0, pady=10, sticky=tk.W)
        
        self.heater_runtime_label = ttk.Label(self.frame, text="Heater Runtime: Not running", font=("Arial", 18), 
                                            foreground="white", background="#0000ff")
        self.heater_runtime_label.grid(row=4, column=0, pady=10, sticky=tk.W)
        
        # Button to manually toggle heater (green when off, red when on)
        self.heater_button = tk.Button(self.frame, text="Toggle Heater", command=self.toggle_heater,
                                      bg="green", fg="white", font=("Arial", 14))
        self.heater_button.grid(row=5, column=0, pady=10, sticky=tk.W)
        
        self.status_label = ttk.Label(self.frame, text="Status: Waiting for data...", 
                                    font=("Arial", 18), foreground="white", background="#0000ff")
        self.status_label.grid(row=6, column=0, pady=10, sticky=tk.W)
        
        # Start sensor reading thread
        self.running = True
        self.sensor_thread = threading.Thread(target=self.read_sensor)
        self.sensor_thread.daemon = True
        self.sensor_thread.start()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def toggle_heater(self):
        """Manually toggle heater on or off, update button color."""
        status_messages = []
        if not self.heater_on:
            # Turn heater on
            os.system('sudo ~/rpitx/./sendiq -s 250000 -f 433.9000e6 -t u8 -i ~/rpitx/heaton.iq')
            self.heater_on = True
            self.heater_off_sent = False  # Reset to allow future off signal
            self.heater_on_time = time.time()  # Record heater on time
            self.manually_activated = True  # Mark as manually activated
            self.heater_status_label.config(text="Heater: On")
            self.heater_button.config(bg="red")  # Red when heater is on
            status_messages.append("Heater manually turned on")
        elif self.heater_on and not self.heater_off_sent:
            # Turn heater off
            os.system('sudo ~/rpitx/./sendiq -s 250000 -f 433.9000e6 -t u8 -i ~/rpitx/heatoff.iq')
            self.heater_on = False
            self.heater_off_sent = True  # Prevent further off signals
            self.heater_on_time = None  # Reset heater on time
            self.manually_activated = False  # Clear manual activation
            self.heater_status_label.config(text="Heater: Off")
            self.heater_button.config(bg="green")  # Green when heater is off
            status_messages.append("Heater manually turned off")
        
        # Update status label
        current_status = self.status_label.cget("text").split("\n")
        if "Status: Normal" in current_status:
            current_status = []
        current_status.extend(status_messages)
        status_color = "red" if any("WARNING" in msg or "ALERT" in msg for msg in current_status) else "white"
        self.status_label.config(text="\n".join(current_status), foreground=status_color)
        
        # Update runtime label
        if self.heater_on and self.heater_on_time:
            elapsed_time = time.time() - self.heater_on_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            self.heater_runtime_label.config(text=f"Heater Runtime: {minutes} min {seconds} sec")
        else:
            self.heater_runtime_label.config(text="Heater Runtime: Not running")
    
    def read_sensor(self):
        while self.running:
            try:
                humidity, temperature = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
                self.root.after(0, self.update_gui, humidity, temperature)
            except Exception as e:
                self.root.after(0, self.update_gui, None, None, f"Error reading sensor: {e}")
            time.sleep(30)  # Read every 30 seconds
    
    def update_gui(self, humidity, temperature, error=None):
        if error:
            self.temp_label.config(text="Temperature: --.-°C", foreground="white")
            self.humidity_label.config(text="Humidity: --.-%", foreground="white")
            self.heater_status_label.config(text="Heater: Off")
            self.heater_runtime_label.config(text="Heater Runtime: Not running")
            self.heater_button.config(bg="green")  # Green when heater is off
            self.status_label.config(text=f"Status: {error}", foreground="red", background="#0000ff")
            self.heater_on = False
            self.heater_off_sent = False
            self.heater_on_time = None
            self.manually_activated = False
            return
            
        if humidity is not None and temperature is not None:
            # Temperature label color
            temp_color = "red" if temperature > HIGH_TEMP_THRESHOLD or temperature < LOW_TEMP_THRESHOLD else "white"
            self.temp_label.config(text=f"Temperature: {temperature:.1f}°C", foreground=temp_color)
            self.humidity_label.config(text=f"Humidity: {humidity:.1f}%", foreground="white")
            
            # Update heater runtime
            if self.heater_on and self.heater_on_time:
                elapsed_time = time.time() - self.heater_on_time
                minutes = int(elapsed_time // 60)
                seconds = int(elapsed_time % 60)
                self.heater_runtime_label.config(text=f"Heater Runtime: {minutes} min {seconds} sec")
            else:
                self.heater_runtime_label.config(text="Heater Runtime: Not running")
            
            # Update button color
            self.heater_button.config(bg="red" if self.heater_on else "green")
            
            # Check thresholds and update status
            status_messages = []
            status_color = "white"
            
            if temperature < LOW_TEMP_THRESHOLD:
                self.low_temp_warning_count += 1
                status_messages.append(f"WARNING: Temperature below {LOW_TEMP_THRESHOLD}°C!")
                status_color = "red"
                if not self.heater_on:
                    # Turn on heater automatically
                    os.system('sudo ~/rpitx/./sendiq -s 250000 -f 433.9000e6 -t u8 -i ~/rpitx/heaton.iq')
                    self.heater_on = True
                    self.heater_off_sent = False
                    self.heater_on_time = time.time()
                    self.manually_activated = False  # Automatic activation
                    self.heater_status_label.config(text="Heater: On")
                    self.heater_button.config(bg="red")  # Red when heater is on
                    status_messages.append("Heater turned on")
            elif self.heater_on and not self.heater_off_sent:
                # Check for heater off conditions
                elapsed_time = time.time() - self.heater_on_time if self.heater_on_time else 0
                # Skip temperature threshold check if manually activated
                if (not self.manually_activated and temperature >= HIGH_TEMP_THRESHOLD) or elapsed_time >= HEATER_DURATION:
                    os.system('sudo ~/rpitx/./sendiq -s 250000 -f 433.9000e6 -t u8 -i ~/rpitx/heatoff.iq')
                    self.heater_on = False
                    self.heater_off_sent = True
                    self.heater_on_time = None
                    self.manually_activated = False
                    self.heater_status_label.config(text="Heater: Off")
                    self.heater_button.config(bg="green")  # Green when heater is off
                    status_messages.append("Heater turned off")
                
            if humidity > HUMIDITY_THRESHOLD:
                status_messages.append(f"ALERT: Humidity exceeds {HUMIDITY_THRESHOLD}%!")
                status_color = "red"
                
            if not status_messages:
                status_messages.append("Status: Normal")
                
            self.low_temp_count_label.config(text=f"Low Temp Warnings: {self.low_temp_warning_count}")
            self.status_label.config(text="\n".join(status_messages), foreground=status_color, background="#0000ff")
        else:
            self.temp_label.config(text="Temperature: --.-°C", foreground="white")
            self.humidity_label.config(text="Humidity: --.-%", foreground="white")
            self.heater_status_label.config(text="Heater: Off")
            self.heater_runtime_label.config(text="Heater Runtime: Not running")
            self.heater_button.config(bg="green")  # Green when heater is off
            self.status_label.config(text="Status: Failed to retrieve data", foreground="red", background="#0000ff")
            self.heater_on = False
            self.heater_off_sent = False
            self.heater_on_time = None
            self.manually_activated = False
    
    def on_closing(self):
        self.running = False
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ShedMonitorApp(root)
    print("Starting shed temperature and humidity monitoring with GUI...")
    root.mainloop()

if __name__ == "__main__":
    main()

