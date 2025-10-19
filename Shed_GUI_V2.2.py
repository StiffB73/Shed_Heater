import Adafruit_DHT
import tkinter as tk
from tkinter import ttk
import time
import threading
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime, timedelta

# Sensor configuration
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 16  # GPIO Pin 16
LOW_TEMP_THRESHOLD = 13.0  # Low temperature threshold in Celsius
HIGH_TEMP_THRESHOLD = 19.0  # High temperature threshold in Celsius
HUMIDITY_THRESHOLD = 75.0  # High humidity threshold in percentage
HEATER_DURATION = 40 * 60  # 40 minutes in seconds
GRAPH_DURATION = 36 * 3600  # 36 hours in seconds

class ShedMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shed Temperature & Humidity Monitor")
        
        # Configure window
        self.root.geometry("400x650")  # Increased height for graph
        self.root.configure(bg="#0000ff")  # Blue background
        
        # Initialize heater states and temperature data
        self.heater_on = False
        self.heater_off_sent = False
        self.heater_on_time = None
        self.manually_activated = False
        self.temp_data = []  # List of (timestamp, temperature) tuples
        
        # Create and configure main frame
        self.frame = ttk.Frame(self.root, padding="10")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.frame.configure(style="Blue.TFrame")
        
        # Configure style for frame background
        style = ttk.Style()
        style.configure("Blue.TFrame", background="#0000ff")
        
        # Labels for temperature, humidity, status, and runtime
        self.temp_label = ttk.Label(self.frame, text="Temperature: --.-°C", font=("Arial", 21), 
                                  foreground="white", background="#0000ff")
        self.temp_label.grid(row=0, column=0, pady=10, sticky=tk.W)
        
        self.humidity_label = ttk.Label(self.frame, text="Humidity: --.-%", font=("Arial", 21), 
                                      foreground="white", background="#0000ff")
        self.humidity_label.grid(row=1, column=0, pady=10, sticky=tk.W)
        
        self.heater_status_label = ttk.Label(self.frame, text="Heater: Off", font=("Arial", 18), 
                                           foreground="white", background="#0000ff")
        self.heater_status_label.grid(row=2, column=0, pady=10, sticky=tk.W)
        
        self.heater_runtime_label = ttk.Label(self.frame, text="Heater Runtime: Not running", font=("Arial", 18), 
                                            foreground="white", background="#0000ff")
        self.heater_runtime_label.grid(row=3, column=0, pady=10, sticky=tk.W)
        
        # Button to manually toggle heater
        self.heater_button = tk.Button(self.frame, text="Toggle Heater", command=self.toggle_heater,
                                      bg="green", fg="white", font=("Arial", 14))
        self.heater_button.grid(row=4, column=0, pady=10, sticky=tk.W)
        
        self.status_label = ttk.Label(self.frame, text="Status: Waiting for data...", 
                                    font=("Arial", 18), foreground="white", background="#0000ff")
        self.status_label.grid(row=5, column=0, pady=10, sticky=tk.W)
        
        # Set up matplotlib figure for temperature graph
        self.fig, self.ax = plt.subplots(figsize=(5, 2.5))  # Compact size for GUI
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.get_tk_widget().grid(row=6, column=0, pady=10, sticky=tk.W)
        
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
            os.system('sudo ~/rpitx/./sendiq -s 250000 -f 433.9000e6 -t u8 -i ~/rpitx/heaton.iq')
            self.heater_on = True
            self.heater_off_sent = False
            self.heater_on_time = time.time()
            self.manually_activated = True
            self.heater_status_label.config(text="Heater: On")
            self.heater_button.config(bg="red")
            status_messages.append("Heater manually turned on")
        elif self.heater_on and not self.heater_off_sent:
            os.system('sudo ~/rpitx/./sendiq -s 250000 -f 433.9000e6 -t u8 -i ~/rpitx/heatoff.iq')
            self.heater_on = False
            self.heater_off_sent = True
            self.heater_on_time = None
            self.manually_activated = False
            self.heater_status_label.config(text="Heater: Off")
            self.heater_button.config(bg="green")
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
            time.sleep(30)
    
    def update_gui(self, humidity, temperature, error=None):
        if error:
            self.temp_label.config(text="Temperature: --.-°C", foreground="white")
            self.humidity_label.config(text="Humidity: --.-%", foreground="white")
            self.heater_status_label.config(text="Heater: Off")
            self.heater_runtime_label.config(text="Heater Runtime: Not running")
            self.heater_button.config(bg="green")
            self.status_label.config(text=f"Status: {error}", foreground="red", background="#0000ff")
            self.heater_on = False
            self.heater_off_sent = False
            self.heater_on_time = None
            self.manually_activated = False
            return
            
        if humidity is not None and temperature is not None:
            # Update temperature data
            current_time = time.time()
            self.temp_data.append((current_time, temperature))
            # Remove data older than 36 hours
            self.temp_data = [(t, temp) for t, temp in self.temp_data if current_time - t <= GRAPH_DURATION]
            
            # Update temperature label color
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
            
            # Update temperature graph
            self.update_graph()
            
            # Check thresholds and update status
            status_messages = []
            status_color = "white"
            
            if temperature < LOW_TEMP_THRESHOLD:
                status_messages.append(f"WARNING: Temperature below {LOW_TEMP_THRESHOLD}°C!")
                status_color = "red"
                if not self.heater_on:
                    os.system('sudo ~/rpitx/./sendiq -s 250000 -f 433.9000e6 -t u8 -i ~/rpitx/heaton.iq')
                    self.heater_on = True
                    self.heater_off_sent = False
                    self.heater_on_time = time.time()
                    self.manually_activated = False
                    self.heater_status_label.config(text="Heater: On")
                    self.heater_button.config(bg="red")
                    status_messages.append("Heater turned on")
            elif self.heater_on and not self.heater_off_sent:
                elapsed_time = time.time() - self.heater_on_time if self.heater_on_time else 0
                if (not self.manually_activated and temperature >= HIGH_TEMP_THRESHOLD) or elapsed_time >= HEATER_DURATION:
                    os.system('sudo ~/rpitx/./sendiq -s 250000 -f 433.9000e6 -t u8 -i ~/rpitx/heatoff.iq')
                    self.heater_on = False
                    self.heater_off_sent = True
                    self.heater_on_time = None
                    self.manually_activated = False
                    self.heater_status_label.config(text="Heater: Off")
                    self.heater_button.config(bg="green")
                    status_messages.append("Heater turned off")
                
            if humidity > HUMIDITY_THRESHOLD:
                status_messages.append(f"ALERT: Humidity exceeds {HUMIDITY_THRESHOLD}%!")
                status_color = "red"
                
            if not status_messages:
                status_messages.append("Status: Normal")
                
            self.status_label.config(text="\n".join(status_messages), foreground=status_color, background="#0000ff")
        else:
            self.temp_label.config(text="Temperature: --.-°C
