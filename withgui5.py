import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import ctkchart
import struct
import serial
from datetime import datetime

# =================================================================
# 1. DESIGN TOKENS (Industry Standard Palette)
# =================================================================
_PALETTE = {
    "bg": "#0f172a",  # Slate 900
    "card": "#1e293b",  # Slate 800
    "accent": "#38bdf8",  # Sky Blue
    "danger": "#f43f5e",  # Rose
    "safe": "#10b981",  # Emerald
    "text": "#f8fafc"
}

_SENSORS = {
    "production": {
        "temperature": {"label": "REACTOR TEMP", "unit": "°C", "max": 100, "color": "#f43f5e"},
        "courant": {"label": "ELECTROLYZER I", "unit": "A", "max": 100, "color": "#38bdf8"}
    },
    "storage": {
        "humidity": {"label": "SYSTEM HUMIDITY", "unit": "%RH", "max": 100, "color": "#10b981"},
        "H2 ppm": {"label": "H2 CONCENTRATION", "unit": "ppm", "max": 10000, "color": "#fbbf24"}
    }
}


# =================================================================
# 2. HARDWARE ENGINE
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
# 3. PROFESSIONAL COMPONENTS
# =================================================================
class CircularGauge(ctk.CTkFrame):
    def __init__(self, master, label, unit, color, max_val):
        super().__init__(master, fg_color=_PALETTE["card"], corner_radius=12, border_width=1, border_color="#334155")
        self.max_val, self.color = max_val, color
        ctk.CTkLabel(self, text=label, font=("Inter", 11, "bold"), text_color="#94a3b8").pack(pady=(10, 0))
        self.canvas = tk.Canvas(self, width=120, height=80, bg=_PALETTE["card"], highlightthickness=0)
        self.canvas.pack(pady=5)
        self.set_value(0)

    def set_value(self, val):
        self.canvas.delete("all")
        # Track
        self.canvas.create_arc(15, 15, 105, 105, start=0, extent=180, outline="#334155", width=8, style='arc')
        # Value Arc
        extent = (min(val, self.max_val) / self.max_val) * 180
        self.canvas.create_arc(15, 15, 105, 105, start=180, extent=-extent, outline=self.color, width=8, style='arc')
        self.canvas.create_text(60, 50, text=f"{val:.1f}", fill=_PALETTE["text"], font=("Inter", 16, "bold"))


# =================================================================
# 4. MASTER INTERFACE
# =================================================================
class HydrogenApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("H2 PRO-CONTROL v1.0")
        self.geometry("1280x800")
        self.configure(fg_color=_PALETTE["bg"])

        self.serial = SerialManager()
        self.ema_values = {k: 0.0 for group in _SENSORS.values() for k in group}

        self.setup_layout()
        self.update_loop()

    def setup_layout(self):
        # Top Bar
        self.top_bar = ctk.CTkFrame(self, fg_color=_PALETTE["card"], height=60, corner_radius=0)
        self.top_bar.pack(fill="x", side="top")
        ctk.CTkLabel(self.top_bar, text="HYDROGEN PRODUCTION UNIT 01", font=("Inter", 18, "bold")).pack(side="left",
                                                                                                        padx=25)

        # Status Bar (Bottom)
        self.status_bar = ctk.CTkFrame(self, fg_color="#020617", height=30, corner_radius=0)
        self.status_bar.pack(fill="x", side="bottom")
        self.st_label = ctk.CTkLabel(self.status_bar, text="● SYSTEM READY", text_color=_PALETTE["safe"],
                                     font=("Inter", 11))
        self.st_label.pack(side="left", padx=20)

        # Main Dashboard Area
        self.main_grid = ctk.CTkFrame(self, fg_color="transparent")
        self.main_grid.pack(fill="both", expand=True, padx=25, pady=25)

        # Gauge Row
        self.gauge_frame = ctk.CTkFrame(self.main_grid, fg_color="transparent")
        self.gauge_frame.pack(fill="x", pady=(0, 20))
        self.ui_gauges = {}

        for group in _SENSORS.values():
            for key, conf in group.items():
                g = CircularGauge(self.gauge_frame, conf['label'], conf['unit'], conf['color'], conf['max'])
                g.pack(side="left", expand=True, padx=8)
                self.ui_gauges[key] = g

        # Chart Section
        self.chart_frame = ctk.CTkFrame(self.main_grid, fg_color=_PALETTE["card"], corner_radius=12, border_width=1,
                                        border_color="#334155")
        self.chart_frame.pack(fill="both", expand=True)

        self.ui_charts = {}
        self.ui_lines = {}

        # We only chart the two most critical production values to keep UI clean
        for key in ["temperature", "courant"]:
            conf = _SENSORS["production"][key]
            chart = ctkchart.CTkLineChart(self.chart_frame, height=220, axis_color="#475569", fg_color="transparent")
            chart.pack(fill="x", padx=15, pady=15)
            self.ui_charts[key] = chart
            self.ui_lines[key] = ctkchart.CTkLine(chart, color=conf['color'], size=2)

    def update_loop(self):
        packet = self.serial.read_data()
        alpha = 0.15

        # Update Connection Status
        if packet:
            self.st_label.configure(text=f"● LIVE DATA: {datetime.now().strftime('%H:%M:%S')}",
                                    text_color=_PALETTE["safe"])
        else:
            self.st_label.configure(text="○ WAITING FOR HARDWARE...", text_color=_PALETTE["danger"])

        for key in self.ema_values:
            val = packet[key] if packet and key in packet else self.ema_values[key]
            self.ema_values[key] = (alpha * val) + ((1 - alpha) * self.ema_values[key])

            if key in self.ui_gauges: self.ui_gauges[key].set_value(self.ema_values[key])
            if key in self.ui_charts: self.ui_charts[key].show_data(line=self.ui_lines[key],
                                                                    data=[self.ema_values[key]])

        self.after(100, self.update_loop)


if __name__ == "__main__":
    app = HydrogenApp()
    app.mainloop()

# =================================================================
# SETTINGS & TUNING (Quick Reference)
# =================================================================
# to change dashboard colors (HMI Look) go to line 14
# to change sensor limits or units go to line 22
# to change the COM Port go to line 38
# to change gauge border/roundness go to line 54
# to change the smoothing filter (Alpha) go to line 111
# =================================================================