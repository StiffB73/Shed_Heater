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

# ────────────────────── CONFIGURATION ──────────────────────
VERSION = "2.3.1"                    # ← Now 2.3.1
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 16
LOW_TEMP_THRESHOLD = 11.0
HIGH_TEMP_THRESHOLD = 18.0
HUMIDITY_THRESHOLD = 75.0

MAX_MANUAL_RUNTIME = 40 * 60         # 40 minutes max for manual activation
HEATER_COOLDOWN = 10 * 60            # 10 min cooldown after auto-off
GRAPH_DURATION = 36 * 3600
# ───────────────────────────────────────────────────────────

class ShedMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Shed Temperature & Humidity Monitor – v{VERSION}")
        self.root.geometry("420x720")
        self.root.configure(bg="#1E3A8A")

        # State variables
        self.heater_on = False
        self.heater_off_sent = False
        self.heater_on_time = None
        self.manually_activated = False
        self.last_auto_off_time = None
        self.temp_data = []

        # Main frame
        self.frame = ttkb.Frame(self.root, padding="10", bootstyle="primary")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)

        # Sensor display
        self.sensor_frame = ttkb.Frame(self.frame, borderwidth=2, relief="groove", bootstyle="primary")
        self.sensor_frame.grid(row=0, column=0, pady=10, padx=10, sticky=tk.W+tk.E)

        self.temp_label = ttkb.Label(self.sensor_frame, text="Temperature: --.-°C", font=("DejaVu Sans", 20, "bold"), bootstyle="light")
        self.temp_label.grid(row=0, column=0, pady=5, padx=10, sticky=tk.W)

        self.humidity_label = ttkb.Label(self.sensor_frame, text="Humidity: --.-%", font=("DejaVu Sans", 20, "bold"), bootstyle="light")
        self.humidity_label.grid(row=1, column=0, pady=5, padx=10, sticky=tk.W)

        self.heater_status_label = ttkb.Label(self.frame, text="Heater: Off", font=("DejaVu Sans", 16), bootstyle="light")
        self.heater_status_label.grid(row=1, column=0, pady=10, padx=10, sticky=tk.W)

        self.heater_runtime_label = ttkb.Label(self.frame, text="Heater Runtime: Not running", font=("DejaVu Sans", 16), bootstyle="light")
        self.heater_runtime_label.grid(row=2, column=0, pady=10, padx=10, sticky=tk.W)

        ttkb.Separator(self.frame, orient="horizontal").grid(row=3, column=0, sticky=(tk.W, tk.E), pady=15)

        self.heater_button = ttkb.Button(self.frame, text="Toggle Heater", command=self.toggle_heater,
                                         style="success.TButton", padding=10)
        self.heater_button.grid(row=4, column=0, pady=10, padx=10, sticky=tk.W+tk.E)

        self.status_label = ttkb.Label(self.frame, text="Status: Waiting for data...", font=("DejaVu Sans", 16), bootstyle="light")
        self.status_label.grid(row=5, column=0, pady=10, padx=10, sticky=tk.W)

        # Graph
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(5.5, 2.8))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.get_tk_widget().grid(row=6, column=0, pady=15, sticky=(tk.W, tk.E))

        # Footer - version + date
        self.footer_label = ttkb.Label(self.frame, text=f"v{VERSION} – Updated: never",
                                      font=("DejaVu Sans", 9), bootstyle="secondary", anchor="e")
        self.footer_label.grid(row=99, column=0, sticky="se", padx=12, pady=(0, 8))

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
        except Exception as e:
            print(f"RF transmit error: {e}")
            return False

    def toggle_heater(self):
        if not self.heater_on:
            if self.send_rf("~/rpitx/heaton.iq"):
                self.heater_on = True
                self.heater_off_sent = False
                self.heater_on_time = time.time()
                self.manually_activated = True
                self.heater_status_label.config(text="Heater: On (Manual)")
                self.heater_button.configure(style="danger.TButton")
                self.status_label.config(text="Heater manually ON (40 min max)", bootstyle="warning")
        else:
            if self.send_rf("~/rpitx/heatoff.iq"):
                self.heater_on = False
                self.heater_off_sent = True
                self.heater_on_time = None
                self.manually_activated = False
                self.heater_status_label.config(text="Heater: Off")
                self.heater_button.configure(style="success.TButton")
                self.status_label.config(text="Heater manually turned OFF", bootstyle="info")
        self.update_heater_runtime()

    def update_heater_runtime(self):
        if self.heater_on and self.heater_on_time:
            elapsed = int(time.time() - self.heater_on_time)
            m, s = divmod(elapsed, 60)
            remaining = ""
            if self.manually_activated:
                mins_left = max(0, 40 - m)
                remaining = f" ({mins_left}m left)" if mins_left > 0 else " (time up!)"
            self.heater_runtime_label.config(text=f"Heater Runtime: {m}m {s}s{remaining}")
        else:
            self.heater_runtime_label.config(text="Heater Runtime: Not running")

    def read_sensor(self):
        while self.running:
            try:
                humidity, temp = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
                self.root.after(0, self.update_gui, humidity, temp)
            except Exception as e:
                self.root.after(0, self.update_gui, None, None, str(e))
            time.sleep(30)

    def update_gui(self, humidity, temperature, error=None):
        if error or humidity is None or temperature is None:
            self.temp_label.config(text="Temperature: --.-°C", bootstyle="light")
            self.humidity_label.config(text="Humidity: --.-%", bootstyle="light")
            self.status_label.config(text=f"Sensor error: {error or 'No data'}", bootstyle="danger")
            return

        current_time = time.time()
        self.temp_data.append((current_time, temperature))
        self.temp_data = [d for d in self.temp_data if current_time - d[0] <= GRAPH_DURATION]

        temp_color = "danger" if temperature < LOW_TEMP_THRESHOLD or temperature > HIGH_TEMP_THRESHOLD else "light"
        self.temp_label.config(text=f"Temperature: {temperature:.1f}°C", bootstyle=temp_color)
        self.humidity_label.config(text=f"Humidity: {humidity:.1f}%", bootstyle="light")

        # Update footer date
        date_str = datetime.now().strftime("%d %b %Y")
        self.footer_label.config(text=f"v{VERSION} – Updated: {date_str}")

        self.update_heater_runtime()
        self.update_graph()

        status_msgs = []
        status_style = "light"

        # Auto activation (no time limit)
        if temperature < LOW_TEMP_THRESHOLD:
            status_msgs.append(f"Low temp: {temperature:.1f}°C")
            status_style = "danger"
            if (not self.heater_on and
                (self.last_auto_off_time is None or time.time() - self.last_auto_off_time > HEATER_COOLDOWN)):
                if self.send_rf("~/rpitx/heaton.iq"):
                    self.heater_on = True
                    self.heater_off_sent = False
                    self.heater_on_time = time.time()
                    self.manually_activated = False
                    self.heater_status_label.config(text="Heater: On (Auto)")
                    self.heater_button.configure(style="danger.TButton")
                    status_msgs.append("Heater auto-ON")

        # Auto shut-off when warm enough
        if self.heater_on and not self.heater_off_sent and not self.manually_activated:
            if temperature >= HIGH_TEMP_THRESHOLD:
                if self.send_rf("~/rpitx/heatoff.iq"):
                    self.heater_on = False
                    self.heater_off_sent = True
                    self.heater_on_time = None
                    self.last_auto_off_time = time.time()
                    self.heater_status_label.config(text="Heater: Off")
                    self.heater_button.configure(style="success.TButton")
                    status_msgs.append("Heater auto-OFF (warm)")

        # Manual 40-minute safety cutoff
        if (self.heater_on and self.manually_activated and
            time.time() - self.heater_on_time >= MAX_MANUAL_RUNTIME):
            if self.send_rf("~/rpitx/heatoff.iq"):
                self.heater_on = False
                self.heater_off_sent = True
                self.heater_on_time = None
                self.manually_activated = False
                self.heater_status_label.config(text="Heater: Off")
                self.heater_button.configure(style="success.TButton")
                status_msgs.append("Manual run ended (40 min limit)")

        if humidity > HUMIDITY_THRESHOLD:
            status_msgs.append(f"High humidity: {humidity:.1f}%")
            status_style = "danger"

        if not status_msgs:
            status_msgs.append("Status: Normal")
            status_style = "success"

        self.status_label.config(text="\n".join(status_msgs[-2:]), bootstyle=status_style)

    def update_graph(self):
        self.ax.clear()
        self.ax.set_facecolor("#1E3A8A")
        self.fig.set_facecolor("#1E3A8A")
        for spine in self.ax.spines.values():
            spine.set_color('#E5E7EB')
        self.ax.tick_params(colors='#E5E7EB', labelsize=9)
        self.ax.xaxis.label.set_color('#E5E7EB')
        self.ax.yaxis.label.set_color('#E5E7EB')
        self.ax.title.set_color('#E5E7EB')

        now = datetime.now()
        start = now - timedelta(hours=36)
        end = now + timedelta(hours=1)

        if self.temp_data:
            times, temps = zip(*self.temp_data)
            times = [datetime.fromtimestamp(t) for t in times]
            self.ax.plot(times, temps, color='#E5E7EB', linewidth=2.5)
            self.ax.axhline(y=LOW_TEMP_THRESHOLD, color='#F87171', linestyle='--', alpha=0.8, label=f'Low: {LOW_TEMP_THRESHOLD}°C')
            self.ax.axhline(y=HIGH_TEMP_THRESHOLD, color='#FBBF24', linestyle='--', alpha=0.8, label=f'High: {HIGH_TEMP_THRESHOLD}°C')
            if self.heater_on and self.heater_on_time:
                self.ax.axvline(datetime.fromtimestamp(self.heater_on_time), color='#FBBF24', linestyle=':', linewidth=1.5)

        self.ax.set_xlim(start, end)
        self.ax.xaxis.set_major_locator(HourLocator(interval=3))
        self.ax.xaxis.set_minor_locator(HourLocator(interval=1))
        self.ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))
        self.fig.autofmt_xdate(bottom=0.18, rotation=0, ha='center')

        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Temperature (°C)")
        self.ax.set_title("Temperature – Last 36 Hours")
        self.ax.grid(True, color='gray', alpha=0.3, linestyle='-', linewidth=0.5)

        if self.temp_data:
            temps = [t[1] for t in self.temp_data]
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
    root = ttkb.Window(themename="darkly")
    app = ShedMonitorApp(root)
    print(f"Shed Monitor v{VERSION} started – Manual max 40 min | Auto unlimited")
    root.mainloop()


if __name__ == "__main__":
    main()