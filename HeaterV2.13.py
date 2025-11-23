# Shed Temperature & Humidity Monitor v2.13 – FINAL
# • Countdown only on manual activation
# • Auto runtime now shows days if >24h
# • Button text shows correct action

import Adafruit_DHT
import tkinter as tk
import time
import threading
import os
import logging
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque

# === LOGGING ===
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
handler = TimedRotatingFileHandler(
    os.path.join(LOG_DIR, f"shed_monitor_{datetime.now():%Y-%m-%d}.log"),
    when="midnight", interval=1, backupCount=30
)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", handlers=[handler])

# === CONFIG ===
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 16
LOW_TEMP_THRESHOLD = 12.0
HIGH_TEMP_THRESHOLD = 18.0
HUMIDITY_THRESHOLD = 75.0
MAX_MANUAL_RUNTIME = 40 * 60
HEATER_COOLDOWN = 10 * 60
GRAPH_HOURS = 36
FUTURE_HOURS = 1
VERSION = "2.13"

class ShedMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Shed Monitor – v{VERSION}")
        self.root.geometry("640x780")
        self.root.configure(bg="#000080")

        self.heater_on = False
        self.heater_off_sent = False
        self.heater_on_time = None
        self.manually_activated = False
        self.last_auto_off_time = None
        self.last_log_time = 0

        self.times = deque(maxlen=GRAPH_HOURS * 120)
        self.temps = deque(maxlen=GRAPH_HOURS * 120)

        frame = tk.Frame(root, bg="#000080")
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        big = ("Arial", 24, "bold")
        med = ("Arial", 18)

        self.temp_lbl = tk.Label(frame, text="Temperature: --.-°C", font=big, bg="#000080", fg="white")
        self.temp_lbl.grid(row=0, column=0, pady=12, sticky="w")

        self.hum_lbl = tk.Label(frame, text="Humidity: --.-%", font=big, bg="#000080", fg="white")
        self.hum_lbl.grid(row=1, column=0, pady=12, sticky="w")

        self.status_lbl = tk.Label(frame, text="Heater: Off", font=med, bg="#000080", fg="lightgreen")
        self.status_lbl.grid(row=2, column=0, pady=8, sticky="w")

        self.runtime_lbl = tk.Label(frame, text="Runtime: Not running", font=med, bg="#000080", fg="white")
        self.runtime_lbl.grid(row=3, column=0, pady=8, sticky="w")

        self.btn = tk.Button(frame, text="Heater ON", command=self.toggle_heater,
                            bg="green", fg="white", font=("Arial", 18, "bold"), width=18, height=2)
        self.btn.grid(row=4, column=0, pady=20)

        self.msg_lbl = tk.Label(frame, text="Status: Starting...", font=("Arial", 16), bg="#000080", fg="white", justify="left")
        self.msg_lbl.grid(row=5, column=0, pady=15, sticky="w")

        # Graph
        self.fig, self.ax = plt.subplots(figsize=(8, 4.5), facecolor='#000080')
        self.ax.set_facecolor('#000033')
        (self.line,) = self.ax.plot([], [], color='cyan', linewidth=3)
        self.ax.axhline(LOW_TEMP_THRESHOLD, color='red', linestyle='--', alpha=0.7)
        self.ax.axhline(HIGH_TEMP_THRESHOLD, color='orange', linestyle='--', alpha=0.7)
        self.ax.set_ylim(0, 35)
        self.ax.set_title("Temperature – Last 36 Hours", color='white', fontsize=16, pad=20)
        self.ax.set_ylabel("°C", color='white', fontsize=12)
        self.ax.grid(True, color='gray', alpha=0.3)
        self.ax.tick_params(colors='white', labelsize=11)

        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.get_tk_widget().grid(row=6, column=0, pady=20, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        tk.Label(root, text=f"v{VERSION}", font=("Arial", 10), bg="#000080", fg="lightgray").place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        threading.Thread(target=self.sensor_loop, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        logging.info("=== Shed Monitor v2.13 STARTED ===")

    def send(self, state): 
        os.system(f"sudo ~/rpitx/sendiq -s 250000 -f 433.9000e6 -t u8 -i ~/rpitx/heat{state}.iq")

    def toggle_heater(self):
        if not self.heater_on:
            self.send("on")
            self.heater_on = True
            self.heater_off_sent = False
            self.heater_on_time = time.time()
            self.manually_activated = True
            self.status_lbl.config(text="Heater: ON (Manual)", fg="yellow")
            self.btn.config(text="Heater OFF", bg="red")
            logging.info("MANUAL → Heater ON (40 min max)")
        else:
            self.send("off")
            self.heater_on = self.heater_off_sent = self.manually_activated = False
            self.heater_on_time = None
            self.status_lbl.config(text="Heater: Off", fg="lightgreen")
            self.btn.config(text="Heater ON", bg="green")
            logging.info("MANUAL → Heater OFF")
        self.update_runtime()

    def update_runtime(self):
        if not self.heater_on:
            self.runtime_lbl.config(text="Runtime: Not running")
            return

        elapsed = int(time.time() - self.heater_on_time)
        days = elapsed // 86400
        remaining = elapsed % 86400
        hours = remaining // 3600
        remaining %= 3600
        minutes = remaining // 60
        seconds = remaining % 60

        if self.manually_activated:
            mins_elapsed = elapsed // 60
            remaining_manual = max(0, 40 - mins_elapsed)
            if remaining_manual > 0:
                self.runtime_lbl.config(text=f"Runtime: {minutes}m {seconds}s | {remaining_manual}m left (manual)")
            else:
                self.runtime_lbl.config(text=f"Runtime: {minutes}m {seconds}s | FORCED OFF")
        else:
            # Auto mode – pretty long-duration display
            if days:
                time_str = f"{days}d {hours}h {minutes}m {seconds}s"
            elif hours:
                time_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes:
                time_str = f"{minutes}m {seconds}s"
            else:
                time_str = f"{seconds}s"
            self.runtime_lbl.config(text=f"Runtime: {time_str} (auto)")

    def sensor_loop(self):
        while True:
            try:
                h, t = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
                now = time.time()
                self.root.after(0, self.update_gui, t, h, now)
            except: pass
            time.sleep(30)

    def update_gui(self, temp, hum, now):
        if now - self.last_log_time >= (60 if self.heater_on else 300):
            logging.info(f"Temp: {temp:.1f}°C | Hum: {hum:.1f}% | Heater: {'ON' if self.heater_on else 'OFF'}")
            self.last_log_time = now

        self.times.append(datetime.fromtimestamp(now))
        self.temps.append(temp)
        self.line.set_data(self.times, self.temps)

        if len(self.times) > 1:
            end = self.times[-1] + timedelta(hours=FUTURE_HOURS)
            start = end - timedelta(hours=GRAPH_HOURS)
            self.ax.set_xlim(start, end)
            self.ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
            self.ax.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
            def fmt(x, pos):
                dt = mdates.num2date(x)
                if dt.hour == 0:
                    return dt.strftime("%d %b")
                return dt.strftime("%H:%M")
            self.ax.xaxis.set_major_formatter(plt.FuncFormatter(fmt))

        self.ax.set_ylim(max(0, min(self.temps)-2), max(self.temps)+3)
        self.canvas.draw()

        color = "red" if temp < LOW_TEMP_THRESHOLD else "orange" if temp > HIGH_TEMP_THRESHOLD else "white"
        self.temp_lbl.config(text=f"Temperature: {temp:.1f}°C", fg=color)
        self.hum_lbl.config(text=f"Humidity: {hum:.1f}%")

        self.update_runtime()

        msgs = []
        if temp < LOW_TEMP_THRESHOLD and not self.heater_on:
            if not self.last_auto_off_time or (now - self.last_auto_off_time > HEATER_COOLDOWN):
                self.send("on")
                self.heater_on = True
                self.heater_off_sent = False
                self.heater_on_time = now
                self.manually_activated = False
                self.status_lbl.config(text="Heater: ON (Auto)", fg="yellow")
                self.btn.config(text="Heater OFF", bg="red")
                msgs.append("AUTO-ON (cold)")
                logging.info("AUTO → Heater ON")

        if self.heater_on and not self.heater_off_sent and not self.manually_activated:
            if temp >= HIGH_TEMP_THRESHOLD:
                self.send("off")
                self.heater_on = False
                self.heater_off_sent = True
                self.heater_on_time = None
                self.last_auto_off_time = now
                self.status_lbl.config(text="Heater: Off", fg="lightgreen")
                self.btn.config(text="Heater ON", bg="green")
                msgs.append("AUTO-OFF (warm)")
                logging.info("AUTO → Heater OFF")

        if self.heater_on and self.manually_activated and (now - self.heater_on_time >= MAX_MANUAL_RUNTIME):
            self.send("off")
            self.heater_on = False
            self.heater_off_sent = True
            self.heater_on_time = None
            self.manually_activated = False
            self.status_lbl.config(text="Heater: Off", fg="lightgreen")
            self.btn.config(text="Heater ON", bg="green")
            msgs.append("Manual 40 min → OFF")
            logging.info("MANUAL → 40 min limit → OFF")

        if hum > HUMIDITY_THRESHOLD:
            msgs.append(f"High humidity {hum:.0f}%")

        self.msg_lbl.config(text="\n".join(msgs) if msgs else "Status: Normal",
                           fg="red" if any("cold" in m.lower() or "high humidity" in m.lower() for m in msgs) else "white")

    def shutdown(self):
        if self.heater_on: 
            self.send("off")
        logging.info("=== Shed Monitor STOPPED ===")
        self.root.destroy()

if __name__ == "__main__":
    tk.Tk().withdraw()
    app = ShedMonitorApp(tk.Tk())
    app.root.mainloop()