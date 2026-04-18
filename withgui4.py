import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import ctkchart
import math
import struct
import serial
from datetime import datetime

# =================================================================
# 1. CONFIGURATION & THEME
# =================================================================
_PALETTE = {
    "bg": "#080c14", "card": "#111827", "accent": "#00c9a7",
    "text": "#e2e8f0", "text_sub": "#94a3b8", "border": "#1e3a5f"
}

_SENSORS = {
    "production": {
        "temperature": {"label": "Temp", "unit": "°C", "max": 100, "color": "#ef4444"},
        "courant": {"label": "Current", "unit": "A", "max": 100, "color": "#38bdf8"}
    },
    "storage": {
        "humidity": {"label": "Humidity", "unit": "%RH", "max": 100, "color": "#10b981"},
        "H2 ppm": {"label": "H2 Conc", "unit": "ppm", "max": 10000, "color": "#f59e0b"}
    }
}

# =================================================================
# 2. SERIAL COMMUNICATION
# =================================================================
class SerialManager:
    def __init__(self, port='COM5'):
        try:
            self.ser = serial.Serial(port, 115200, timeout=0.1)
        except:
            self.ser = None

    def read_data(self):
        if not self.ser or self.ser.in_waiting < 17: return None
        if self.ser.read(1) != b'\x55': return None
        try:
            d = struct.unpack('<ffff', self.ser.read(16))
            return {"temperature": d[0], "courant": d[1], "H2 ppm": d[2], "humidity": d[3]}
        except:
            return None

# =================================================================
# 3. UI COMPONENTS (Gauges & Charts)
# =================================================================
class CircularGauge(ctk.CTkFrame):
    def __init__(self, master, label, unit, color, max_val):
        super().__init__(master, fg_color="transparent")
        self.max_val, self.color = max_val, color
        ctk.CTkLabel(self, text=label, font=("Courier New", 11), text_color="#94a3b8").pack()
        self.canvas = tk.Canvas(self, width=110, height=80, bg="#162032", highlightthickness=0)
        self.canvas.pack(pady=5)
        self.set_value(0)

    def set_value(self, val):
        self.canvas.delete("all")
        self.canvas.create_arc(10, 10, 100, 100, start=0, extent=180, outline="#1e3a5f", width=12, style='arc')
        extent = (min(val, self.max_val) / self.max_val) * 180
        self.canvas.create_arc(10, 10, 100, 100, start=180, extent=-extent, outline=self.color, width=12, style='arc')
        self.canvas.create_text(55, 45, text=f"{val:.1f}", fill=self.color, font=("Courier New", 16, "bold"))

# =================================================================
# 4. MAIN APPLICATION ENGINE
# =================================================================
class HydrogenApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PFE H2 Monitoring")
        self.geometry("1200x750")
        self.configure(fg_color=_PALETTE["bg"])

        self.serial = SerialManager()
        self.ema_values = {k: 0.0 for group in _SENSORS.values() for k in group}

        self.setup_ui()
        self.update_loop()

    def setup_ui(self):
        nav = ctk.CTkFrame(self, fg_color=_PALETTE["card"], height=50, corner_radius=0)
        nav.pack(fill="x")
        ctk.CTkLabel(nav, text="H2 MONITORING SYSTEM", font=("Segoe UI", 14, "bold"),
                     text_color=_PALETTE["accent"]).pack(side="left", padx=20)

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=20)

        gauge_box = ctk.CTkFrame(self.container, fg_color=_PALETTE["card"])
        gauge_box.pack(fill="x", pady=(0, 20))
        self.ui_gauges = {}

        for group in _SENSORS.values():
            for key, conf in group.items():
                g = CircularGauge(gauge_box, conf['label'], conf['unit'], conf['color'], conf['max'])
                g.pack(side="left", expand=True, padx=10, pady=10)
                self.ui_gauges[key] = g

        self.setup_charts()

    def setup_charts(self):
        chart_card = ctk.CTkFrame(self.container, fg_color=_PALETTE["card"])
        chart_card.pack(fill="both", expand=True)

        self.ui_charts = {}
        self.ui_lines = {}

        # We change this line to create a TUPLE instead of a LIST
        # The tuple() function converts our list [0, 1, 2...] into a fixed (0, 1, 2...)
        x_values = tuple(str(i) for i in range(20))

        for i, (key, conf) in enumerate(_SENSORS['production'].items()):
            chart = ctkchart.CTkLineChart(
                chart_card,
                height=200,
                axis_color=_PALETTE["border"],
                fg_color="#0d1424",
                x_axis_values=x_values
            )
            chart.pack(fill="x", padx=10, pady=5)
            line = ctkchart.CTkLine(chart, color=conf['color'], size=2)
            self.ui_charts[key] = chart
            self.ui_lines[key] = line
    def update_loop(self):
        packet = self.serial.read_data()
        alpha = 0.2

        for key in self.ema_values:
            val = packet[key] if packet and key in packet else self.ema_values[key]
            self.ema_values[key] = (alpha * val) + ((1 - alpha) * self.ema_values[key])

            if key in self.ui_gauges:
                self.ui_gauges[key].set_value(self.ema_values[key])

            if key in self.ui_charts:
                self.ui_charts[key].show_data(line=self.ui_lines[key], data=[self.ema_values[key]])

        self.after(100, self.update_loop)

if __name__ == "__main__":
    app = HydrogenApp()
    app.mainloop()

# =================================================================
# SETTINGS & TUNING (Quick Reference)
# =================================================================
# to change dashboard colors (HMI Look) go to line 15
# to change sensor limits or units go to line 20
# to change the COM Port go to line 33
# to modify the data packet format (float count) go to line 41
# to change the gauge background color go to line 56
# to change the startup window size go to line 74
# to adjust data smoothing (Filter Intensity) go to line 111
# to change the refresh rate (Sampling speed) go to line 132
# =================================================================
#4 is better now