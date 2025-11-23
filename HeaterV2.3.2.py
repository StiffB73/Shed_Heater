# Shed Temperature & Humidity Monitor – v2.3.2
# Clean light theme + readable 6-hour graph labels

import Adafruit_DHT
import tkinter as tk
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import time
import threading
import subprocess
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.dates import HourLocator, DateFormatter
import matplotlib.dates as mdates

# ────────────────────── CONFIGURATION ──────────────────────
VERSION = "2.3.2"
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 16
LOW_TEMP_THRESHOLD = 11.0
HIGH_TEMP_THRESHOLD = 18.0
HUMIDITY_THRESHOLD = 75.0

MAX_MANUAL_RUNTIME = 40 * 60         # 40 minutes max for manual
HEATER_COOLDOWN = 10 * 60            # 10 min after auto-off
GRAPH_DURATION = 36 * 3600
# ───────────────────────────────────────────────────────────

class ShedMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Shed Temperature & Humidity Monitor – v{VERSION}")
        self.root.geometry("460x760")

        # State
        self.heater_on = False
        self.heater_off_sent = False
        self.heater_on_time = None
        self.manually_activated = False
        self.last_auto_off_time = None
        self.temp_data = []

        # Main frame
        self.frame = ttkb.Frame(self.root, padding="15")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)

        # Sensor display
        self.sensor_frame = ttkb.Frame(self.frame, borderwidth=2, relief="groove")
        self.sensor_frame.grid(row=0, column=0, pady=12, padx=10, sticky=tk.W+tk.E)

        self.temp_label = ttkb.Label(self.sensor_frame, text="Temperature: --.-°C", font=("Helvetica", 22, "bold"))
        self.temp_label.grid(row=0, column=0, pady=8, padx=12, sticky=tk.W)

        self.humidity_label = ttkb.Label(self.sensor_frame, text="Humidity: --.-%", font=("Helvetica", 22, "bold"))
        self.humidity_label.grid(row=1, column=0, pady=8, padx=12, sticky=tk.W)

        self.heater_status_label = ttkb.Label(self.frame, text="Heater: Off", font=("Helvetica", 18))
        self.heater_status_label.grid(row=1, column=0, pady=12, sticky=tk.W)

        self.heater_runtime_label = ttkb.Label(self.frame, text="Heater Runtime: Not running", font=("Helvetica", 16))
        self.heater_runtime_label.grid(row=2, column=0, pady=8, sticky=tk.W)

        ttkb.Separator(self.frame, orient="horizontal").grid(row=3, column=0, sticky=(tk.W, tk.E), pady=20)

        self.heater_button = ttkb.Button(self.frame, text="Toggle Heater", command=self.toggle_heater,
                                         bootstyle="success-outline", padding=12)
        self.heater_button.grid(row=4, column=0, pady=15, sticky=tk.W+tk.E)

        self.status_label = ttkb.Label(self.frame, text="Status: Waiting for data...", font=("Helvetica", 16))
        self.status_label.grid(row=5, column=0, pady=12, sticky=tk.W)

        # Graph
        plt.style.use('default')
        self.fig, self.ax = plt.subplots(figsize=(6, 3.2), facecolor='white')
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.get_tk_widget().grid(row=6, column=0, pady=20, sticky=(tk.W, tk.E))

        # Footer
        self.footer_label = ttkb.Label(self.frame, text=f"v{VERSION} – Updated: never",
                                      font=("Helvetica", 9), bootstyle="secondary", anchor="e")
        self.footer_label.grid(row=99, column=0, sticky="se", padx=15, pady=(0, 10))

        # Start sensor thread
        self.running = True
        self.sensor_thread = threading.Thread(target=self.read_sensor, daemon=True)
        self.sensor_thread.start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def send_rf(self, iq_file):
        cmd = ['sudo', '/home/pi/rpitx/sendiq', '-s', '250000', '-f', '433.9000e6', '-t', 'u8', '-i', iq_file]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except:
            return False

    def toggle_heater(self):
        if not self.heater_on:
            if self.send_rf("~/rpitx/heaton.iq"):
                self.heater_on = True
                self.heater_off_sent = False
                self.heater_on_time = time.time()
                self.manually_activated = True
                self.heater_status_label.config(text="Heater: On (Manual – 40 min max)")
                self.heater_button.configure(bootstyle="danger")
                self.status_label.config(text="Heater manually ON", bootstyle="warning")
        else:
            if self.send_rf("~/rpitx/heatoff.iq"):
                self.heater_on = False
                self.heater_off_sent = True
                self.heater_on_time = None
                self.manually_activated = False
                self.heater_status_label.config(text="Heater: Off")
                self.heater_button.configure(bootstyle="success-outline")
                self.status_label.config(text="Heater manually OFF", bootstyle="info")
        self.update_heater_runtime()

    def update_heater_runtime(self):
        if self.heater_on and self.heater_on_time:
            elapsed = int(time.time() - self.heater_on_time)
            m, s = divmod(elapsed, 60)
            txt = f"Heater Runtime: {m}m {s}s"
            if self.manually_activated:
                mins_left = max(0, 40 - m)
                txt += f"  →  {mins_left}m left" if mins_left > 0 else "  →  Time up!"
            self.heater_runtime_label.config(text=txt)
        else:
            self.heater_runtime_label.config(text="Heater Runtime: Not running")

    def read_sensor(self):
        while self.running:
            try:
                humidity, temp = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
                self.root.after(0, self.update_gui, humidity, temp)
            except Exception as e:
                self.root.after(0, self.update_gui, None, None)
            time.sleep(30)

    def update_gui(self, humidity, temperature, error=None):
        if humidity is None or temperature is None:
            self.temp_label.config(text="Temperature: --.-°C")
            self.humidity_label.config(text="Humidity: --.-%")
            self.status_label.config(text="Sensor error – check wiring", bootstyle="danger")
            return

        current_time = time.time()
        self.temp_data.append((current_time, temperature))
        self.temp_data = [d for d in self.temp_data if current_time - d[0] <= GRAPH_DURATION]

        color = "danger" if temperature < LOW_TEMP_THRESHOLD or temperature > HIGH_TEMP_THRESHOLD else "dark"
        self.temp_label.config(text=f"Temperature: {temperature:.1f}°C", bootstyle=color)
        self.humidity_label.config(text=f"Humidity: {humidity:.1f}%")

        date_str = datetime.now().strftime("%d %b %Y")
        self.footer_label.config(text=f"v{VERSION} – Updated: {date_str}")

        self.update_heater_runtime()
        self.update_graph()

        # Auto control logic
        status_msgs = []
        if temperature < LOW_TEMP_THRESHOLD:
            status_msgs.append(f"Low temp: {temperature:.1f}°C")
            if (not self.heater_on and
                (self.last_auto_off_time is None or time.time() - self.last_auto_off_time > HEATER_COOLDOWN)):
                if self.send_rf("~/rpitx/heaton.iq"):
                    self.heater_on = True
                    self.heater_off_sent = False
                    self.heater_on_time = time.time()
                    self.manually_activated = False
                    self.heater_status_label.config(text="Heater: On (Auto)")
                    self.heater_button.configure(bootstyle="danger")
                    status_msgs.append("Heater auto-ON")

        if self.heater_on and not self.heater_off_sent and not self.manually_activated:
            if temperature >= HIGH_TEMP_THRESHOLD:
                if self.send_rf("~/rpitx/heatoff.iq"):
                    self.heater_on = False
                    self.heater_off_sent = True
                    self.heater_on_time = None
                    self.last_auto_off_time = time.time()
                    self.heater_status_label.config(text="Heater: Off")
                    self.heater_button.configure(bootstyle="success-outline")
                    status_msgs.append("Heater auto-OFF")

        # Manual 40-minute cutoff
        if (self.heater_on and self.manually_activated and
            time.time() - self.heater_on_time >= MAX_MANUAL_RUNTIME):
            if self.send_rf("~/rpitx/heatoff.iq"):
                self.heater_on = False
                self.heater_off_sent = True
                self.heater_on_time = None
                self.manually_activated = False
                self.heater_status_label.config(text="Heater: Off")
                self.heater_button.configure(bootstyle="success-outline")
                status_msgs.append("Manual run ended (40 min)")

        if humidity > HUMIDITY_THRESHOLD:
            status_msgs.append(f"High humidity: {humidity:.1f}%")

        if not status_msgs:
            status_msgs.append("Status: Normal")
        self.status_label.config(text=" | ".join(status_msgs[-2:]), bootstyle="success" if "Normal" in status_msgs else "warning")

    def update_graph(self):
        self.ax.clear()
        self.fig.patch.set_facecolor('white')
        self.ax.set_facecolor('#f8f9fa')

        now = datetime.now()
        start = now - timedelta(hours=36)
        end = now + timedelta(hours=1)

        if self.temp_data:
            times, temps = zip(*self.temp_data)
            times = [datetime.fromtimestamp(t) for t in times]
            self.ax.plot(times, temps, color='#2c3e50', linewidth=2.5)
            self.ax.axhline(y=LOW_TEMP_THRESHOLD, color='#e74c3c', linestyle='--', alpha=0.7, label=f'Low: {LOW_TEMP_THRESHOLD}°C')
            self.ax.axhline(y=HIGH_TEMP_THRESHOLD, color='#f39c12', linestyle='--', alpha=0.7, label=f'High: {HIGH_TEMP_THRESHOLD}°C')

        self.ax.set_xlim(start, end)

        # Clean 6-hour labels + date at midnight
        self.ax.xaxis.set_major_locator(HourLocator(interval=6))
        self.ax.xaxis.set_minor_locator(HourLocator(interval=1))
        def format_date(x, pos):
            dt = mdates.num2date(x)
            if dt.hour == 0:
                return dt.strftime('%d %b\n00:00')
            return dt.strftime('%H:%M')
        self.ax.xaxis.set_major_formatter(plt.FuncFormatter(format_date))

        self.ax.grid(True, color='lightgray', alpha=0.5, linewidth=0.5)
        self.ax.set_title("Temperature – Last 36 Hours", fontsize=14, pad=15)
        self.ax.set_ylabel("Temperature (°C)")

        if self.temp_data:
            margin = 1.0
            self.ax.set_ylim(min(temps) - margin, max(temps) + margin)

        self.fig.tight_layout()
        self.canvas.draw()

    def on_closing(self):
        self.running = False
        if self.heater_on:
            self.send_rf("~/rpitx/heatoff.iq")
        self.root.destroy()


def main():
    root = ttkb.Window(themename="flatly")   # ← Clean, light, readable theme
    app = ShedMonitorApp(root)
    print(f"Shed Monitor v{VERSION} – Light theme + clean graph")
    root.mainloop()


if __name__ == "__main__":
    main()