"""
PFE H₂ Monitoring System
========================
Industrial-grade real-time monitoring dashboard.
Dark-first SCADA/HMI aesthetic: deep navy, electric teal accent,
monospaced instrument values, live status bar.
"""

from __future__ import annotations

import csv
import math
import os
import random
import tkinter as tk
import tkinter.ttk as ttk
from datetime import datetime
from typing import Any

import ctkchart
import customtkinter as ctk
import serial

# ── Serial port setup ──────────────────────────────────────────────────────────
try:
    _ser = serial.Serial(
        port='COM5',
        baudrate=115200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.05          # non-blocking — GUI won't freeze
    )
except Exception as e:
    print(f"Serial not connected: {e}")
    _ser = None

# ═══════════════════════════════════════════════════════════════════════════════
# DESIGN TOKENS
# ═══════════════════════════════════════════════════════════════════════════════

# Fonts
_F_MONO  = "Courier New"   # instrument / data values
_F_UI    = "Segoe UI"      # labels, navigation, headings

# Dark palette  (primary — control room standard)
_D: dict[str, str] = {
    "bg":          "#080c14",
    "surface":     "#0d1424",
    "card":        "#111827",
    "card2":       "#162032",
    "border":      "#1e3a5f",
    "border_sub":  "#1a2d47",
    "accent":      "#00c9a7",
    "accent_dim":  "#00967d",
    "accent_glow": "#00ffd0",
    "danger":      "#ef4444",
    "info":        "#38bdf8",
    "success":     "#10b981",
    "warning":     "#f59e0b",
    "text":        "#e2e8f0",
    "text_sub":    "#94a3b8",
    "text_dim":    "#475569",
    "axis":        "#1e3a5f",
    "tick":        "#334155",
    "gauge_track": "#1e3a5f",
    "tbl_bg":      "#0d1424",
    "tbl_alt":     "#111827",
    "tbl_head":    "#162032",
    "tbl_sel":     "#1e3a5f",
    "btn":         "#162032",
    "btn_hover":   "#1e3a5f",
    "btn_text":    "#94a3b8",
    "inactive":    "#162032",
}

# Light palette
_L: dict[str, str] = {
    "bg":          "#f1f5f9",
    "surface":     "#f8fafc",
    "card":        "#ffffff",
    "card2":       "#f0f7ff",
    "border":      "#cbd5e1",
    "border_sub":  "#e2e8f0",
    "accent":      "#0d9488",
    "accent_dim":  "#0f766e",
    "accent_glow": "#14b8a6",
    "danger":      "#dc2626",
    "info":        "#0284c7",
    "success":     "#059669",
    "warning":     "#b45309",
    "text":        "#0f172a",
    "text_sub":    "#334155",
    "text_dim":    "#64748b",
    "axis":        "#e2e8f0",
    "tick":        "#94a3b8",
    "gauge_track": "#e2e8f0",
    "tbl_bg":      "#ffffff",
    "tbl_alt":     "#f8fafc",
    "tbl_head":    "#f1f5f9",
    "tbl_sel":     "#e0f2fe",
    "btn":         "#e2e8f0",
    "btn_hover":   "#cbd5e1",
    "btn_text":    "#334155",
    "inactive":    "#e2e8f0",
}

# Sensor accent colors — consistent across both themes
_SENSOR_COLORS = {
    "dark": {
        "temperature": "#ef4444",
        "courant":     "#38bdf8",
        "humidity":    "#10b981",
        "H2 ppm":      "#f59e0b",
    },
    "light": {
        "temperature": "#dc2626",
        "courant":     "#0284c7",
        "humidity":    "#059669",
        "H2 ppm":      "#b45309",
    },
}

_ALL_DARK  = frozenset({"#080c14","#0d1424","#111827","#162032","#1e3a5f",
                         "#1a2d47","#1e2d45","#0d1117","#161b22","#0b0f1a",
                         "#1a1f2e","#1f2630","#0d1420","black","#000000"})
_ALL_LIGHT = frozenset({"#f1f5f9","#f8fafc","#ffffff","#f0f7ff","#e2e8f0",
                         "#cbd5e1","#f0f0f0","#dde1e7","#f7f7f7","#e8e8e8",
                         "#d8dce2","#f5f5f5"})
_ACCENT_SET = frozenset({"#00c9a7","#00967d","#00ffd0","#0d9488","#0f766e",
                          "#14b8a6","#ef4444","#dc2626","#38bdf8","#0284c7",
                          "#10b981","#059669","#f59e0b","#b45309"})


# ═══════════════════════════════════════════════════════════════════════════════
# CIRCULAR GAUGE
# ═══════════════════════════════════════════════════════════════════════════════

class CircularGauge(ctk.CTkFrame):
    """Original semicircular gauge — simple, reliable, no background issues."""

    def __init__(
        self,
        master: Any,
        label: str = "value",
        unit: str = "",
        size: int = 110,
        color: str = "#5dffb6",
        max_val: float = 100,
        palette: dict | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.size   = size
        self._max   = max_val
        self.color  = color
        self._unit  = unit
        self._p     = palette or _D

        ctk.CTkLabel(
            self, text=label,
            font=(_F_MONO, 11), text_color=self._p["text_sub"],
        ).pack()

        self.canvas = tk.Canvas(
            self,
            width=size, height=size // 2 + 20,
            bg=self._p["card2"], highlightthickness=0,
        )
        self.canvas.pack()
        self._draw_gauge(0)

    def _draw_gauge(self, value: float) -> None:
        self.canvas.configure(bg=self._p["card2"])
        self.canvas.delete("all")
        cx, cy = self.size // 2, self.size // 2
        r_outer = self.size // 2 - 6
        r_inner = r_outer - 14

        # Background arc
        self._draw_arc(cx, cy, r_outer, r_inner, 180, 360, self._p["gauge_track"])

        # Value arc
        pct = max(0, min(1, value / self._max))
        if pct > 0:
            self._draw_arc(cx, cy, r_outer, r_inner, 180, 180 + pct * 180, self.color)

        # Value text
        self.canvas.create_text(
            cx, cy - 4,
            text=str(int(value)),
            fill=self.color,
            font=(_F_MONO, 16, "bold"),
        )
        # Unit text
        if self._unit:
            self.canvas.create_text(
                cx, cy + 12,
                text=self._unit,
                fill=self._p["text_dim"],
                font=(_F_UI, 8),
            )

    def _draw_arc(
        self, cx: float, cy: float,
        r_out: float, r_in: float,
        start_deg: float, end_deg: float,
        color: str,
    ) -> None:
        steps = max(2, int(abs(end_deg - start_deg)))
        outer, inner = [], []
        for i in range(steps + 1):
            a = math.radians(start_deg + (end_deg - start_deg) * i / steps)
            outer.append((cx + r_out * math.cos(a), cy + r_out * math.sin(a)))
            inner.append((cx + r_in  * math.cos(a), cy + r_in  * math.sin(a)))
        pts  = outer + list(reversed(inner))
        flat = [coord for pt in pts for coord in pt]
        if len(flat) >= 6:
            self.canvas.create_polygon(flat, fill=color, outline="")

    def set_value(self, value: float) -> None:
        self._draw_gauge(value)

    def set_palette(self, p: dict, canvas_bg: str | None = None) -> None:
        self._p = p
        self._draw_gauge(0)


# ═══════════════════════════════════════════════════════════════════════════════
# SCALE CONTROL
# ═══════════════════════════════════════════════════════════════════════════════

class ScaleControl(ctk.CTkFrame):
    """
    Compact Y-axis range control bar.
    [−] zoom out  [+] zoom in  Min[__] Max[__]  [Apply] [Reset]
    """

    def __init__(
        self,
        master: Any,
        default_min: float,
        default_max: float,
        on_scale: Any,
        palette: dict,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color=palette["surface"],
                         corner_radius=6, **kwargs)
        self._dmin     = default_min
        self._dmax     = default_max
        self._on_scale = on_scale
        self._p        = palette

        self._min_var = tk.StringVar(value=str(int(default_min)))
        self._max_var = tk.StringVar(value=str(int(default_max)))
        self._build(palette)

    def _build(self, p: dict) -> None:
        # Zoom
        zoom = ctk.CTkFrame(self, fg_color="transparent")
        zoom.pack(side="left", padx=(6, 0), pady=2)

        ctk.CTkLabel(zoom, text="ZOOM", font=(_F_UI, 8, "bold"),
                     text_color=p["text_dim"]).pack(side="left", padx=(0, 3))

        for sym, cmd in [("−", self._zoom_out), ("+", self._zoom_in)]:
            ctk.CTkButton(
                zoom, text=sym, width=22, height=20,
                font=(_F_MONO, 11, "bold"),
                fg_color=p["btn"], hover_color=p["btn_hover"],
                text_color=p["accent"], corner_radius=4,
                command=cmd,
            ).pack(side="left", padx=1)

        # Divider
        tk.Frame(self, bg=p["border"], width=1).pack(
            side="left", fill="y", padx=6, pady=4)

        # Entries
        entries = ctk.CTkFrame(self, fg_color="transparent")
        entries.pack(side="left", pady=2)

        for lbl, var in [("MIN", self._min_var), ("MAX", self._max_var)]:
            ctk.CTkLabel(entries, text=lbl, width=26,
                         font=(_F_UI, 8, "bold"),
                         text_color=p["text_dim"]).pack(side="left")
            ctk.CTkEntry(
                entries, textvariable=var, width=56, height=20,
                font=(_F_MONO, 9),
                fg_color=p["btn"], text_color=p["text"],
                border_color=p["border"], border_width=1,
            ).pack(side="left", padx=(0, 6))

        # Apply / Reset
        ctk.CTkButton(
            self, text="APPLY", width=48, height=20,
            font=(_F_UI, 8, "bold"),
            fg_color=p["accent"], hover_color=p["accent_dim"],
            text_color=p["bg"], corner_radius=4,
            command=self._apply,
        ).pack(side="left", padx=2, pady=2)

        ctk.CTkButton(
            self, text="RESET", width=44, height=20,
            font=(_F_UI, 8),
            fg_color=p["btn"], hover_color=p["btn_hover"],
            text_color=p["btn_text"], corner_radius=4,
            command=self._reset,
        ).pack(side="left", padx=2, pady=2)

    # ------------------------------------------------------------------
    def _range(self) -> tuple[float, float]:
        try:
            lo, hi = float(self._min_var.get()), float(self._max_var.get())
            if hi <= lo:
                raise ValueError
            return lo, hi
        except ValueError:
            return self._dmin, self._dmax

    def _apply(self) -> None:
        lo, hi = self._range()
        self._min_var.set(str(round(lo, 1)))
        self._max_var.set(str(round(hi, 1)))
        self._on_scale(lo, hi)

    def _reset(self) -> None:
        self._min_var.set(str(int(self._dmin)))
        self._max_var.set(str(int(self._dmax)))
        self._on_scale(self._dmin, self._dmax)

    def _zoom_in(self) -> None:
        lo, hi = self._range()
        mid = (lo + hi) / 2
        half = (hi - lo) / 2 * 0.80
        self._min_var.set(str(round(mid - half, 1)))
        self._max_var.set(str(round(mid + half, 1)))
        self._apply()

    def _zoom_out(self) -> None:
        lo, hi = self._range()
        mid = (lo + hi) / 2
        half = (hi - lo) / 2 * 1.20
        new_lo = max(self._dmin - self._dmax * 0.5, mid - half)
        new_hi = min(self._dmax * 1.5,              mid + half)
        self._min_var.set(str(round(new_lo, 1)))
        self._max_var.set(str(round(new_hi, 1)))
        self._apply()


# ═══════════════════════════════════════════════════════════════════════════════
# CHART FACTORY
# ═══════════════════════════════════════════════════════════════════════════════

def make_chart(
    master: Any,
    y_min: float, y_max: float,
    y_label: str, x_label: str,
    line_colors: list[str],
    chart_width: int = 700,
    chart_height: int = 250,
    palette: dict | None = None,
    on_scale: Any = None,
) -> tuple[ctkchart.CTkLineChart, list[ctkchart.CTkLine], ScaleControl]:
    if palette is None:
        palette = _D

    p        = palette
    bg       = p["surface"]
    x_points = tuple(str(i * 10) for i in range(11))

    wrapper = ctk.CTkFrame(master, fg_color=bg)
    wrapper.pack(fill="both", expand=True, padx=2, pady=2)

    y_canvas = tk.Canvas(wrapper, width=18, bg=bg, highlightthickness=0)
    y_canvas.pack(side="left", fill="y")

    def _draw_ylabel(_e: Any = None) -> None:
        y_canvas.delete("all")
        h = y_canvas.winfo_height() or 300
        y_canvas.create_text(9, h // 2, text=y_label,
                             fill=p["text_dim"], font=(_F_UI, 10),
                             angle=90, anchor="center")

    y_canvas.bind("<Configure>", _draw_ylabel)

    col = ctk.CTkFrame(wrapper, fg_color=bg)
    col.pack(side="left", fill="both", expand=True)

    chart = ctkchart.CTkLineChart(
        master=col,
        x_axis_values=x_points,
        y_axis_values=(y_min, y_max),
        y_axis_label_count=5,
        fg_color=bg, bg_color=bg,
        axis_color=p["axis"],
        x_axis_font_color=p["tick"],
        y_axis_font_color=p["tick"],
        x_axis_label_count=11,
        width=chart_width,
        height=chart_height,
    )
    chart.pack(padx=(50, 0), pady=4)

    ctk.CTkLabel(col, text=x_label,
                 font=(_F_UI, 10), text_color=p["text_dim"],
                 fg_color=bg).pack(pady=(0, 2))

    def _on_scale(lo: float, hi: float) -> None:
        try:
            chart.configure(y_axis_values=(lo, hi))
        except Exception:
            pass
        if on_scale:
            on_scale(lo, hi)

    sc = ScaleControl(col, default_min=y_min, default_max=y_max,
                      on_scale=_on_scale, palette=p)
    sc.pack(fill="x", padx=4, pady=(0, 6))

    lines = [ctkchart.CTkLine(master=chart, color=c, size=2) for c in line_colors]
    return chart, lines, sc


# ═══════════════════════════════════════════════════════════════════════════════
# RECURSIVE RECOLOR
# ═══════════════════════════════════════════════════════════════════════════════

def _recolor(widget: Any, p: dict) -> None:
    is_dark = (p.get("bg") == _D["bg"])
    try:
        if isinstance(widget, tk.Canvas):
            try:
                cur = widget.cget("bg")
                if (not is_dark and cur in _ALL_DARK) or (is_dark and cur in _ALL_LIGHT):
                    widget.configure(bg=p["card"])
            except Exception:
                pass

        elif isinstance(widget, ctk.CTkFrame):
            cur = widget.cget("fg_color")
            if isinstance(cur, (list, tuple)):
                cur = cur[-1]
            if not is_dark and cur in _ALL_DARK:
                new = (p["surface"] if cur in {"#0d1424","#080c14"}
                       else p["card"]   if cur in {"#111827","#162032"}
                       else p["card2"])
                widget.configure(fg_color=new)
            elif is_dark and cur in _ALL_LIGHT:
                new = (p["surface"] if cur in {"#f1f5f9","#f8fafc"}
                       else p["card"]   if cur in {"#ffffff","#f0f7ff"}
                       else p["card2"])
                widget.configure(fg_color=new)

        elif isinstance(widget, ctk.CTkButton):
            cur = widget.cget("fg_color")
            if isinstance(cur, (list, tuple)):
                cur = cur[-1]
            if cur not in _ACCENT_SET:
                widget.configure(fg_color=p["btn"], hover_color=p["btn_hover"],
                                 text_color=p["btn_text"], border_color=p["border"])

        elif isinstance(widget, ctk.CTkLabel):
            tc = widget.cget("text_color")
            if isinstance(tc, (list, tuple)):
                tc = tc[-1]
            if tc not in _ACCENT_SET and tc not in {"#ffffff", "#0f172a"}:
                widget.configure(text_color=p["text_sub"], fg_color="transparent")

        elif isinstance(widget, ctk.CTkEntry):
            widget.configure(fg_color=p["btn"], text_color=p["text"],
                             border_color=p["border"])

    except Exception:
        pass

    try:
        for child in widget.winfo_children():
            _recolor(child, p)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class App(ctk.CTk):

    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("PFE H₂ Monitoring System")
        self.geometry("1280x760")
        self.configure(fg_color=_D["bg"])
        self.resizable(True, True)

        self._is_dark:     bool = True
        self._palette:     dict = _D
        self._current_tab: str  = "production"
        self._filter:      str  = "tout"
        self._live:        bool = True

        self.charts:         dict = {}
        self.lines:          dict = {}
        self.chart_frames:   dict = {}
        self.gauges:         dict = {}
        self.all_gauges:     dict = {}
        self.scale_ctrls:    dict = {}
        self.nav_btns:       dict = {}
        self._tab_frames:    dict = {}
        self._gauge_panels:  dict = {}
        self._filter_btns:   dict = {}
        self._sidebars:      dict = {}

        self._data_log: list[dict] = []
        self._ema:      dict        = {}
        self._columns = ["time", "temperature", "courant", "humidity", "H2 ppm"]
        self._last_current_ma: float = 0.0   # holds last real STM32 reading

        sc = _SENSOR_COLORS["dark"]
        self._cfg: dict = {
            "production": {
                "title": "Production — Real-Time Analytics",
                "lines": {
                    "temperature": {
                        "color": sc["temperature"], "gauge_label": "Temperature",
                        "unit": "°C",
                        "y_range": (0, 100),  "y_label": "Temperature (°C)",
                        "x_label": "Time (ms)", "gauge_max": 100,  "rand": (0, 100),
                    },
                    "courant": {
                        "color": sc["courant"], "gauge_label": "Current",
                        "unit": "mA",
                        "y_range": (0, 1000), "y_label": "Current (mA)",
                        "x_label": "Time (ms)", "gauge_max": 1000, "rand": (0, 1000),
                    },
                },
                "sidebar_labels": ["tout", "temperature", "courant"],
            },
            "storage": {
                "title": "Storage — Real-Time Analytics",
                "lines": {
                    "humidity": {
                        "color": sc["humidity"], "gauge_label": "Humidity",
                        "unit": "%RH",
                        "y_range": (0, 100),   "y_label": "Humidity (%RH)",
                        "x_label": "Time (ms)", "gauge_max": 100,   "rand": (0, 100),
                    },
                    "H2 ppm": {
                        "color": sc["H2 ppm"], "gauge_label": "H₂ Conc.",
                        "unit": "ppm",
                        "y_range": (0, 10000), "y_label": "H₂ Concentration (ppm)",
                        "x_label": "Time (ms)", "gauge_max": 10000, "rand": (0, 10000),
                    },
                },
                "sidebar_labels": ["tout", "humidity", "H2 ppm"],
            },
        }

        self._sidebar_labels = {
            "tout":        "ALL",
            "temperature": "TEMP",
            "courant":     "CURRENT",
            "humidity":    "HUMIDITY",
            "H2 ppm":      "H₂ PPM",
        }

        self._build_ui()
        self.after(100,  self._update_loop)
        self.after(800,  self._blink_live)

    # ═══════════════════════════════════════════════════════════════════
    # UI BUILD
    # ═══════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        self._build_titlebar()
        self._build_nav()

        self._page_stack = ctk.CTkFrame(self, fg_color=_D["bg"])
        self._page_stack.pack(fill="both", expand=True)

        self._main_page = ctk.CTkFrame(self._page_stack, fg_color=_D["bg"])
        self._main_page.place(relwidth=1, relheight=1)
        self._build_main_page()

        self._analytics_page = ctk.CTkFrame(self._page_stack, fg_color=_D["bg"])
        self._analytics_page.place(relwidth=1, relheight=1)
        self._build_analytics_page()

        self._build_statusbar()
        self._show_main_page()

    def _build_titlebar(self) -> None:
        p = self._palette
        bar = ctk.CTkFrame(self, fg_color=p["card"], height=38, corner_radius=0)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        stripe = tk.Frame(bar, bg=p["accent"], width=4)
        stripe.pack(side="left", fill="y")

        ctk.CTkLabel(
            bar, text="H₂",
            font=(_F_MONO, 18, "bold"),
            text_color=p["accent"],
        ).pack(side="left", padx=(14, 4))

        ctk.CTkLabel(
            bar, text="MONITORING SYSTEM",
            font=(_F_UI, 11, "bold"),
            text_color=p["text"],
        ).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(
            bar, text="v2.0  |  PFE PROJECT",
            font=(_F_UI, 9),
            text_color=p["text_dim"],
        ).pack(side="right", padx=16)

    def _build_nav(self) -> None:
        p = self._palette
        nav = ctk.CTkFrame(self, fg_color=p["surface"], height=44, corner_radius=0)
        nav.pack(fill="x", side="top")
        nav.pack_propagate(False)

        btn_frame = ctk.CTkFrame(nav, fg_color="transparent")
        btn_frame.pack(side="left", padx=8, pady=6)

        main_btn = ctk.CTkButton(
            btn_frame, text="⌂  OVERVIEW", width=120, height=30,
            font=(_F_UI, 11, "bold"), fg_color=p["btn"],
            hover_color=p["btn_hover"], text_color=p["btn_text"],
            corner_radius=6, command=self._show_main_page,
        )
        main_btn.pack(side="left", padx=(0, 4))
        self.nav_btns["main"] = main_btn

        for label, key in [("⚙  PRODUCTION", "production"), ("🗃  STORAGE", "storage")]:
            btn = ctk.CTkButton(
                btn_frame, text=label, width=130, height=30,
                font=(_F_UI, 11, "bold"), fg_color=p["btn"],
                hover_color=p["btn_hover"], text_color=p["btn_text"],
                corner_radius=6, command=lambda k=key: self._switch_tab(k),
            )
            btn.pack(side="left", padx=4)
            self.nav_btns[key] = btn

        right = ctk.CTkFrame(nav, fg_color="transparent")
        right.pack(side="right", padx=16)

        ctk.CTkLabel(right, text="DARK",
                     font=(_F_UI, 9, "bold"),
                     text_color=p["text_dim"]).pack(side="left", padx=(0, 6))

        self._theme_switch = ctk.CTkSwitch(
            right, text="", width=46,
            button_color=p["accent"], button_hover_color=p["accent_dim"],
            progress_color=p["accent"],
            command=self._toggle_theme,
        )
        self._theme_switch.pack(side="left")

        ctk.CTkLabel(right, text="LIGHT",
                     font=(_F_UI, 9, "bold"),
                     text_color=p["text_dim"]).pack(side="left", padx=(6, 0))

    def _build_statusbar(self) -> None:
        p = self._palette
        bar = ctk.CTkFrame(self, fg_color=p["card"], height=28, corner_radius=0)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._live_canvas = tk.Canvas(
            bar, width=12, height=12,
            bg=p["card"], highlightthickness=0,
        )
        self._live_canvas.pack(side="left", padx=(12, 4), pady=8)
        self._live_dot = self._live_canvas.create_oval(
            2, 2, 10, 10, fill=p["accent"], outline="")

        # Show serial connection status
        serial_status = "COM5 CONNECTED" if _ser else "NO SERIAL"
        self._status_label = ctk.CTkLabel(
            bar, text=f"● LIVE  |  Sampling: 100 ms  |  {serial_status}",
            font=(_F_UI, 9), text_color=p["accent"],
        )
        self._status_label.pack(side="left")

        tk.Frame(bar, bg=p["border"], width=1).pack(
            side="left", fill="y", padx=12, pady=6)

        self._clock_label = ctk.CTkLabel(
            bar, text="", font=(_F_MONO, 9), text_color=p["text_dim"],
        )
        self._clock_label.pack(side="left")
        self._tick_clock()

        ctk.CTkLabel(
            bar, text="PFE — H₂ Monitoring System  |  All rights reserved",
            font=(_F_UI, 9), text_color=p["text_dim"],
        ).pack(side="right", padx=16)

    def _tick_clock(self) -> None:
        self._clock_label.configure(
            text=datetime.now().strftime("  %Y-%m-%d   %H:%M:%S"))
        self.after(1000, self._tick_clock)

    def _blink_live(self) -> None:
        self._live = not self._live
        p = self._palette
        color = p["accent"] if self._live else p["surface"]
        try:
            self._live_canvas.itemconfig(self._live_dot, fill=color)
        except Exception:
            pass
        self.after(800, self._blink_live)

    # ── Main / Overview page ───────────────────────────────────────────────────

    def _build_main_page(self) -> None:
        p   = self._palette
        par = self._main_page

        hdr = ctk.CTkFrame(par, fg_color=p["card"], height=42, corner_radius=8)
        hdr.pack(fill="x", padx=14, pady=(14, 0))
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=p["accent"], width=3).pack(side="left", fill="y")
        ctk.CTkLabel(hdr, text="  LIVE SENSOR OVERVIEW",
                     font=(_F_UI, 12, "bold"),
                     text_color=p["text"]).pack(side="left", padx=10)

        gauge_row = ctk.CTkFrame(par, fg_color=p["card"], corner_radius=8)
        gauge_row.pack(fill="x", padx=14, pady=(4, 0))

        gauge_cfgs = [
            ("temperature", "Temperature", "°C",   _D["danger"],  100,   "production"),
            ("courant",     "Current",     "mA",   _D["info"],    1000,  "production"),
            ("humidity",    "Humidity",    "%RH",  _D["success"], 100,   "storage"),
            ("H2 ppm",      "H₂ Conc.",   "ppm",  _D["warning"], 10000, "storage"),
        ]
        self.all_gauges = {}
        for lk, lbl, unit, color, max_val, _ in gauge_cfgs:
            cell = ctk.CTkFrame(gauge_row, fg_color=p["card2"], corner_radius=8)
            cell.pack(side="left", expand=True, padx=8, pady=10, fill="both")
            g = CircularGauge(cell, label=lbl, unit=unit,
                              size=110, color=color,
                              max_val=max_val, palette=p)
            g.pack(padx=10, pady=(4, 8))
            self.all_gauges[lk] = g

        ctrl_row = ctk.CTkFrame(par, fg_color="transparent")
        ctrl_row.pack(fill="x", padx=14, pady=(10, 0))

        ctk.CTkButton(
            ctrl_row, text="⬇  EXPORT CSV", width=160, height=36,
            font=(_F_UI, 11, "bold"),
            fg_color=p["accent"], hover_color=p["accent_dim"],
            text_color=p["bg"], corner_radius=6,
            command=self._export_csv,
        ).pack(side="left")

        self._rec_label = ctk.CTkLabel(
            ctrl_row,
            text="0 records",
            font=(_F_MONO, 10),
            text_color=p["text_dim"],
        )
        self._rec_label.pack(side="left", padx=16)

        tbl_card = ctk.CTkFrame(par, fg_color=p["card"], corner_radius=8)
        tbl_card.pack(fill="both", expand=True, padx=14, pady=(10, 14))

        tbl_hdr = ctk.CTkFrame(tbl_card, fg_color=p["card2"], height=36, corner_radius=0)
        tbl_hdr.pack(fill="x")
        tbl_hdr.pack_propagate(False)
        tk.Frame(tbl_hdr, bg=p["accent"], width=3).pack(side="left", fill="y")
        ctk.CTkLabel(tbl_hdr, text="  DATA LOG",
                     font=(_F_UI, 10, "bold"),
                     text_color=p["text_sub"]).pack(side="left", padx=8)

        tbl_inner = ctk.CTkFrame(tbl_card, fg_color="transparent")
        tbl_inner.pack(fill="both", expand=True, padx=6, pady=6)
        self._build_table(tbl_inner, p)

    def _build_table(self, parent: Any, p: dict) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Pro.Treeview",
                         background=p["tbl_bg"],
                         foreground=p["text"],
                         rowheight=32,
                         fieldbackground=p["tbl_bg"],
                         bordercolor=p["border"],
                         borderwidth=0,
                         font=(_F_MONO, 10))
        style.configure("Pro.Treeview.Heading",
                         background=p["tbl_head"],
                         foreground=p["text_sub"],
                         font=(_F_UI, 10, "bold"),
                         relief="flat",
                         borderwidth=0)
        style.map("Pro.Treeview",
                  background=[("selected", p["tbl_sel"])],
                  foreground=[("selected", p["accent"])])

        col_w  = {"time": 90, "temperature": 150, "courant": 130,
                  "humidity": 130, "H2 ppm": 150}
        col_hd = {"time": "TIME", "temperature": "TEMPERATURE (°C)",
                  "courant": "CURRENT (mA)", "humidity": "HUMIDITY (%RH)",
                  "H2 ppm": "H₂ CONC. (ppm)"}

        self._tree = ttk.Treeview(parent, columns=self._columns,
                                   show="headings", style="Pro.Treeview")
        for col in self._columns:
            self._tree.heading(col, text=col_hd.get(col, col))
            self._tree.column(col, width=col_w.get(col, 130), anchor="center")

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)

    # ── Analytics page ─────────────────────────────────────────────────────────

    def _build_analytics_page(self) -> None:
        p    = self._palette
        body = self._analytics_page
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=0)
        body.grid_rowconfigure(0, weight=1)

        sb_wrap = ctk.CTkFrame(body, width=108, fg_color=p["card"], corner_radius=0)
        sb_wrap.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        sb_wrap.grid_propagate(False)

        sb_hdr = ctk.CTkFrame(sb_wrap, fg_color=p["surface"], height=34, corner_radius=0)
        sb_hdr.pack(fill="x")
        sb_hdr.pack_propagate(False)
        ctk.CTkLabel(sb_hdr, text="FILTER",
                     font=(_F_UI, 9, "bold"),
                     text_color=p["text_dim"]).pack(pady=9)

        for tab_key, cfg in self._cfg.items():
            sb = ctk.CTkFrame(sb_wrap, fg_color=p["card"])
            sb.place(relwidth=1, rely=0.045, relheight=0.955)
            self._sidebars[tab_key]    = sb
            self._filter_btns[tab_key] = {}
            for label in cfg["sidebar_labels"]:
                lk = self._cfg[tab_key]["lines"].get(label, {})
                color = lk.get("color", p["accent"]) if isinstance(lk, dict) else p["accent"]
                is_tout = (label == "tout")

                btn = ctk.CTkButton(
                    sb,
                    text=self._sidebar_labels.get(label, label),
                    width=90, height=36,
                    font=(_F_UI, 9, "bold"),
                    fg_color=p["btn"], hover_color=p["btn_hover"],
                    text_color=p["btn_text"],
                    corner_radius=6,
                    border_width=1 if not is_tout else 0,
                    border_color=color if not is_tout else p["border"],
                    command=lambda f=label, t=tab_key: self._set_filter(t, f),
                )
                btn.pack(pady=4, padx=8, anchor="center")
                self._filter_btns[tab_key][label] = btn

        chart_stack = ctk.CTkFrame(body, fg_color=p["bg"])
        chart_stack.grid(row=0, column=1, sticky="nsew", padx=6, pady=10)

        for tab_key, cfg in self._cfg.items():
            self.charts[tab_key]       = {}
            self.lines[tab_key]        = {}
            self.chart_frames[tab_key] = {}
            self.scale_ctrls[tab_key]  = {}

            tab_frame = ctk.CTkFrame(chart_stack, fg_color=p["card"],
                                      corner_radius=10,
                                      border_width=1, border_color=p["border"])
            tab_frame.place(relwidth=1, relheight=1)
            self._tab_frames[tab_key] = tab_frame

            chart_hdr = ctk.CTkFrame(tab_frame, fg_color=p["surface"],
                                      height=40, corner_radius=0)
            chart_hdr.pack(fill="x")
            chart_hdr.pack_propagate(False)
            tk.Frame(chart_hdr, bg=p["accent"], width=3).pack(side="left", fill="y")
            ctk.CTkLabel(chart_hdr,
                         text=f"  {cfg['title'].upper()}",
                         font=(_F_UI, 11, "bold"),
                         text_color=p["text"]).pack(side="left", padx=8)

            inner = ctk.CTkFrame(tab_frame, fg_color=p["surface"])
            inner.pack(fill="both", expand=True, padx=0, pady=0)

            for line_key, lcfg in cfg["lines"].items():
                container = ctk.CTkFrame(inner, fg_color=p["surface"])
                container.place(relwidth=1, relheight=1)
                self.chart_frames[tab_key][line_key] = container
                chart, lines, sc = make_chart(
                    container,
                    y_min=lcfg["y_range"][0], y_max=lcfg["y_range"][1],
                    y_label=lcfg["y_label"],   x_label=lcfg["x_label"],
                    line_colors=[lcfg["color"]],
                    chart_width=760, chart_height=430,
                    palette=p,
                )
                self.charts[tab_key][line_key]      = chart
                self.lines[tab_key][line_key]       = lines[0]
                self.scale_ctrls[tab_key][line_key] = sc

            tout_wrap = ctk.CTkFrame(inner, fg_color=p["surface"])
            tout_wrap.place(relwidth=1, relheight=1)
            self.chart_frames[tab_key]["tout"] = tout_wrap
            self.charts[tab_key]["tout"]       = {}
            self.lines[tab_key]["tout"]        = {}
            self.scale_ctrls[tab_key]["tout"]  = {}

            for idx, (line_key, lcfg) in enumerate(cfg["lines"].items()):
                half = ctk.CTkFrame(tout_wrap, fg_color=p["surface"])
                half.place(relx=0, rely=idx * 0.5, relwidth=1, relheight=0.5)
                chart, lines, sc = make_chart(
                    half,
                    y_min=lcfg["y_range"][0], y_max=lcfg["y_range"][1],
                    y_label=lcfg["y_label"],   x_label=lcfg["x_label"],
                    line_colors=[lcfg["color"]],
                    chart_width=760, chart_height=165,
                    palette=p,
                )
                self.charts[tab_key]["tout"][line_key]      = chart
                self.lines[tab_key]["tout"][line_key]       = lines[0]
                self.scale_ctrls[tab_key]["tout"][line_key] = sc

        right = ctk.CTkFrame(body, width=185, fg_color=p["card"], corner_radius=0)
        right.grid(row=0, column=2, sticky="ns", padx=(0, 10), pady=10)
        right.grid_propagate(False)

        gauge_hdr = ctk.CTkFrame(right, fg_color=p["surface"], height=34, corner_radius=0)
        gauge_hdr.pack(fill="x")
        gauge_hdr.pack_propagate(False)
        ctk.CTkLabel(gauge_hdr, text="GAUGES",
                     font=(_F_UI, 9, "bold"),
                     text_color=p["text_dim"]).pack(pady=9)

        for tab_key, cfg in self._cfg.items():
            panel = ctk.CTkFrame(right, fg_color=p["card"])
            self.gauges[tab_key]        = {}
            self._gauge_panels[tab_key] = panel
            for line_key, lcfg in cfg["lines"].items():
                cell = ctk.CTkFrame(panel, fg_color=p["card2"], corner_radius=8)
                cell.pack(fill="x", padx=8, pady=4)
                g = CircularGauge(
                    cell, label=lcfg["gauge_label"],
                    unit=lcfg["unit"],
                    size=100, color=lcfg["color"],
                    max_val=lcfg["gauge_max"], palette=p,
                )
                g.pack(pady=(2, 6))
                self.gauges[tab_key][line_key] = g

    # ═══════════════════════════════════════════════════════════════════
    # THEME
    # ═══════════════════════════════════════════════════════════════════

    def _toggle_theme(self) -> None:
        is_dark       = not bool(self._theme_switch.get())
        self._is_dark = is_dark
        self._palette = _D if is_dark else _L
        p             = self._palette
        sc            = _SENSOR_COLORS["dark" if is_dark else "light"]

        ctk.set_appearance_mode("dark" if is_dark else "light")

        for tab_key in self._cfg:
            for lk, lcfg in self._cfg[tab_key]["lines"].items():
                lcfg["color"] = sc.get(lk, lcfg["color"])

        _recolor(self, p)

        for tab_key in self.charts:
            for key, obj in self.charts[tab_key].items():
                lst = list(obj.values()) if isinstance(obj, dict) else [obj]
                for chart in lst:
                    try:
                        chart.configure(
                            fg_color=p["surface"], bg_color=p["surface"],
                            axis_color=p["axis"],
                            x_axis_font_color=p["tick"],
                            y_axis_font_color=p["tick"],
                        )
                    except Exception:
                        pass

        for tab_key in self._cfg:
            for lk, lcfg in self._cfg[tab_key]["lines"].items():
                try:
                    self.lines[tab_key][lk].configure(color=lcfg["color"])
                except Exception:
                    pass
                try:
                    self.lines[tab_key]["tout"][lk].configure(color=lcfg["color"])
                except Exception:
                    pass

        for g in self.all_gauges.values():
            if isinstance(g, CircularGauge):
                g.color = sc.get(next((k for k in sc if k in str(g)), ""), g.color)
                g.set_palette(p)
        for tab_key in self.gauges:
            for lk, g in self.gauges[tab_key].items():
                if isinstance(g, CircularGauge):
                    g.color = sc.get(lk, g.color)
                    g.set_palette(p)
        for lk, g in self.all_gauges.items():
            if isinstance(g, CircularGauge):
                g.color = sc.get(lk, g.color)
                g.set_palette(p)

        try:
            self._live_canvas.configure(bg=p["card"])
        except Exception:
            pass

        style = ttk.Style()
        style.configure("Pro.Treeview",
                         background=p["tbl_bg"], foreground=p["text"],
                         fieldbackground=p["tbl_bg"])
        style.configure("Pro.Treeview.Heading",
                         background=p["tbl_head"], foreground=p["text_sub"])

        self._apply_filter(self._current_tab, self._filter)

    # ═══════════════════════════════════════════════════════════════════
    # NAVIGATION
    # ═══════════════════════════════════════════════════════════════════

    def _show_main_page(self) -> None:
        self._main_page.lift()
        p = self._palette
        self.nav_btns["main"].configure(fg_color=p["accent"], text_color=p["bg"])
        for k in ("production", "storage"):
            self.nav_btns[k].configure(fg_color=p["btn"], text_color=p["btn_text"])

    def _switch_tab(self, key: str) -> None:
        self._analytics_page.lift()
        self._current_tab = key
        self._filter      = "tout"
        p = self._palette

        for k, f in self._tab_frames.items():
            if k == key:
                f.lift()
        for k, panel in self._gauge_panels.items():
            if k == key:
                panel.pack(fill="both", expand=True, padx=0)
            else:
                panel.pack_forget()
        for k, sb in self._sidebars.items():
            if k == key:
                sb.lift()

        self._apply_filter(key, "tout")

        self.nav_btns["main"].configure(fg_color=p["btn"], text_color=p["btn_text"])
        for k, btn in self.nav_btns.items():
            if k in ("production", "storage"):
                active = (k == key)
                btn.configure(fg_color=p["accent"] if active else p["btn"],
                              text_color=p["bg"]    if active else p["btn_text"])

    # ═══════════════════════════════════════════════════════════════════
    # FILTER
    # ═══════════════════════════════════════════════════════════════════

    def _set_filter(self, tab_key: str, f: str) -> None:
        if tab_key != self._current_tab:
            return
        self._filter = f
        self._apply_filter(tab_key, f)

    def _apply_filter(self, tab_key: str, f: str) -> None:
        p = self._palette
        for label, btn in self._filter_btns[tab_key].items():
            active = (label == f)
            btn.configure(fg_color=p["accent"] if active else p["btn"],
                          text_color=p["bg"]    if active else p["btn_text"])
        for frame_key, cf in self.chart_frames[tab_key].items():
            if frame_key == f:
                cf.lift()

    # ═══════════════════════════════════════════════════════════════════
    # CSV EXPORT
    # ═══════════════════════════════════════════════════════════════════

    def _export_csv(self) -> None:
        if not self._data_log:
            return
        filename = f"pfe_h2_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = os.path.join(os.path.expanduser("~"), "Desktop", filename)
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=self._columns)
                writer.writeheader()
                writer.writerows(self._data_log)
            self._status_label.configure(
                text=f"● EXPORTED  →  Desktop/{filename}")
            self.after(3000, lambda: self._status_label.configure(
                text="● LIVE  |  Sampling: 100 ms"))
        except OSError as exc:
            print(f"CSV export error: {exc}")

    # ═══════════════════════════════════════════════════════════════════
    # SERIAL READ  ← NEW
    # ═══════════════════════════════════════════════════════════════════

    def _read_current(self) -> float | None:
        """Read one CURRENT sample from STM32. Returns None if no data yet."""
        if _ser is None or _ser.in_waiting < 4:
            return None
        try:
            raw_bytes      = _ser.read(4)
            received_value = int.from_bytes(raw_bytes, byteorder='little')
            voltage        = received_value * 3.3 / 4096
            current        = (voltage - 1.25) / 0.066
            if current < 0:
                current = 0
            return current
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════════════
    # DATA LOOP
    # ═══════════════════════════════════════════════════════════════════

    def _update_loop(self) -> None:
        _ALPHA = 0.25
        try:
            row: dict[str, str] = {"time": datetime.now().strftime("%H:%M:%S")}

            for tab_key, cfg in self._cfg.items():
                # ── Build values — courant comes from STM32, rest random ──
                values = {}
                for lk, lcfg in cfg["lines"].items():
                    if lk == "courant":
                        real = self._read_current()
                        # Convert A → mA; fall back to last EMA if no data yet
                        values[lk] = int(real * 1000) if real is not None else int(self._ema.get(lk, 0))
                    else:
                        values[lk] = random.randint(*lcfg["rand"])

                for line_key, val in values.items():
                    smoothed = self._ema.get(line_key, float(val))
                    smoothed = _ALPHA * val + (1.0 - _ALPHA) * smoothed
                    self._ema[line_key] = smoothed
                    display = round(smoothed)

                    self.charts[tab_key][line_key].show_data(
                        line=self.lines[tab_key][line_key], data=[display])
                    self.charts[tab_key]["tout"][line_key].show_data(
                        line=self.lines[tab_key]["tout"][line_key], data=[display])
                    self.gauges[tab_key][line_key].set_value(display)
                    if line_key in self.all_gauges:
                        self.all_gauges[line_key].set_value(display)
                    row[line_key] = str(display)

            self._data_log.append(row)
            self._tree.insert("", 0, values=[row[c] for c in self._columns])

            if len(self._data_log) > 200:
                self._data_log.pop(0)
                kids = self._tree.get_children()
                if kids:
                    self._tree.delete(kids[-1])

            try:
                self._rec_label.configure(text=f"{len(self._data_log):,} records")
            except Exception:
                pass

        except Exception as exc:
            print(f"Update error: {exc}")

        self.after(100, self._update_loop)


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()