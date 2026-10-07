from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from scanner_engine import ScanResult, UmutScanner


class UmutScannerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("UMUT Scanner")
        self.geometry("1380x780")
        self.minsize(1150, 680)

        self.scanner = UmutScanner(workers=6)
        self.events: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.results: list[ScanResult] = []

        self._build_ui()
        self.after(100, self._drain_events)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        header = ttk.Frame(self, padding=(12, 10))
        header.pack(fill="x")

        ttk.Label(header, text="UMUT SCANNER", font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Label(header, text="Binance Spot USDT Teknik Tarama", font=("Segoe UI", 10)).pack(side="left", padx=(12, 0))

        controls = ttk.LabelFrame(self, text="Tarama Ayarları", padding=10)
        controls.pack(fill="x", padx=12, pady=(0, 8))

        self.interval_var = tk.StringVar(value="1h")
        self.max_symbols_var = tk.IntVar(value=60)
        self.min_volume_var = tk.StringVar(value="10000000")
        self.min_score_var = tk.DoubleVar(value=55.0)

        ttk.Label(controls, text="Zaman Dilimi").grid(row=0, column=0, sticky="w")
        interval = ttk.Combobox(controls, textvariable=self.interval_var, values=["15m", "1h", "4h", "1d"], width=8, state="readonly")
        interval.grid(row=1, column=0, padx=(0, 12), sticky="w")

        ttk.Label(controls, text="Maks. Coin").grid(row=0, column=1, sticky="w")
        ttk.Spinbox(controls, from_=20, to=200, increment=10, textvariable=self.max_symbols_var, width=9).grid(row=1, column=1, padx=(0, 12), sticky="w")

        ttk.Label(controls, text="Min 24s Hacim (USDT)").grid(row=0, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.min_volume_var, width=16).grid(row=1, column=2, padx=(0, 12), sticky="w")

        ttk.Label(controls, text="Min Genel Skor").grid(row=0, column=3, sticky="w")
        ttk.Spinbox(controls, from_=0, to=100, increment=1, textvariable=self.min_score_var, width=10).grid(row=1, column=3, padx=(0, 12), sticky="w")

        self.scan_button = ttk.Button(controls, text="TARAMAYI BAŞLAT", command=self.start_scan)
        self.scan_button.grid(row=1, column=4, padx=(6, 6))

        self.stop_button = ttk.Button(controls, text="DURDUR", command=self.stop_scan, state="disabled")
        self.stop_button.grid(row=1, column=5, padx=6)

        self.progress = ttk.Progressbar(controls, mode="determinate", length=220)
        self.progress.grid(row=1, column=6, padx=(14, 6), sticky="ew")
        controls.columnconfigure(6, weight=1)

        self.status_var = tk.StringVar(value="Hazır")
        ttk.Label(controls, textvariable=self.status_var).grid(row=0, column=6, sticky="w", padx=(14, 6))

        table_frame = ttk.Frame(self, padding=(12, 0, 12, 8))
        table_frame.pack(fill="both", expand=True)

        columns = (
            "symbol", "price", "change", "trend", "setup", "entry", "general",
            "adx", "rsi", "rvol", "structure", "mtf", "regime", "signal", "warning"
        )
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=24)

        headers = {
            "symbol": "Coin", "price": "Fiyat", "change": "24s %", "trend": "Trend",
            "setup": "Setup", "entry": "Entry", "general": "Genel", "adx": "ADX",
            "rsi": "RSI", "rvol": "RVOL", "structure": "Yapı", "mtf": "MTF",
            "regime": "Rejim", "signal": "Sinyal", "warning": "Uyarı"
        }
        widths = {
            "symbol": 100, "price": 100, "change": 80, "trend": 70, "setup": 70,
            "entry": 70, "general": 75, "adx": 65, "rsi": 65, "rvol": 65,
            "structure": 75, "mtf": 65, "regime": 130, "signal": 95, "warning": 125
        }
        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col], minwidth=55, anchor="center")

        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree.tag_configure("strong_buy", background="#d9f7df")
        self.tree.tag_configure("buy", background="#eef9ef")
        self.tree.tag_configure("sell", background="#fdeaea")
        self.tree.tag_configure("strong_sell", background="#ffd9d9")
        self.tree.bind("<Double-1>", self.open_selected_symbol)

        footer = ttk.Frame(self, padding=(12, 0, 12, 10))
        footer.pack(fill="x")
        ttk.Label(
            footer,
            text="Çift tık: Binance spot sayfasını açar. Skorlar başarı olasılığı değildir; teknik koşul uyum skorudur.",
            font=("Segoe UI", 9),
        ).pack(side="left")

    def start_scan(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        try:
            max_symbols = int(self.max_symbols_var.get())
            min_volume = float(self.min_volume_var.get())
            min_score = float(self.min_score_var.get())
        except ValueError:
            messagebox.showerror("Geçersiz değer", "Tarama ayarlarında sayısal alanları kontrol et.")
            return

        self.results = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.cancel_event.clear()
        self.progress["value"] = 0
        self.progress["maximum"] = max_symbols
        self.scan_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Piyasa listesi hazırlanıyor...")

        self.worker = threading.Thread(
            target=self._scan_worker,
            args=(self.interval_var.get(), max_symbols, min_volume, min_score),
            daemon=True,
        )
        self.worker.start()

    def stop_scan(self) -> None:
        self.cancel_event.set()
        self.status_var.set("Durdurma isteniyor...")

    def _scan_worker(self, interval: str, max_symbols: int, min_volume: float, min_score: float) -> None:
        def progress(done: int, total: int, symbol: str, result: ScanResult | None, error: str | None) -> None:
            self.events.put(("progress", done, total, symbol, result, error))

        try:
            results, errors = self.scanner.scan(
                interval=interval,
                max_symbols=max_symbols,
                min_quote_volume=min_volume,
                min_score=min_score,
                progress=progress,
                cancel_event=self.cancel_event,
            )
            self.events.put(("done", results, errors, self.cancel_event.is_set()))
        except Exception as exc:
            self.events.put(("fatal", str(exc)))

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "progress":
                    _, done, total, symbol, result, error = event
                    self.progress["maximum"] = max(total, 1)
                    self.progress["value"] = done
                    suffix = "" if error is None else " | hata"
                    self.status_var.set(f"{done}/{total} tarandı — {symbol}{suffix}")
                    if result is not None:
                        self.results.append(result)
                        self._insert_result(result)
                elif kind == "done":
                    _, results, errors, cancelled = event
                    self.results = results
                    self._render_sorted()
                    self.scan_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    if cancelled:
                        self.status_var.set(f"Tarama durduruldu — {len(results)} sonuç")
                    else:
                        self.status_var.set(f"Tamamlandı — {len(results)} sonuç, {errors} hata")
                elif kind == "fatal":
                    _, error = event
                    self.scan_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.status_var.set("Tarama başarısız")
                    messagebox.showerror("Tarama hatası", error)
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _render_sorted(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for result in sorted(self.results, key=lambda x: x.general_score, reverse=True):
            self._insert_result(result)

    def _insert_result(self, r: ScanResult) -> None:
        tag = ""
        if r.signal == "GÜÇLÜ AL":
            tag = "strong_buy"
        elif r.signal == "AL":
            tag = "buy"
        elif r.signal == "SAT":
            tag = "sell"
        elif r.signal == "GÜÇLÜ SAT":
            tag = "strong_sell"

        values = (
            r.symbol,
            self._fmt_price(r.price),
            f"{r.change_pct:.2f}",
            f"{r.trend_score:.1f}",
            f"{r.setup_score:.1f}",
            f"{r.entry_score:.1f}",
            f"{r.general_score:.1f}",
            f"{r.adx:.1f}",
            f"{r.rsi:.1f}",
            f"{r.rvol:.2f}",
            r.structure,
            f"{r.mtf_score:.0f}",
            r.regime,
            r.signal,
            r.warning,
        )
        self.tree.insert("", "end", values=values, tags=(tag,) if tag else ())

    @staticmethod
    def _fmt_price(value: float) -> str:
        if value >= 1000:
            return f"{value:,.2f}"
        if value >= 1:
            return f"{value:.4f}"
        if value >= 0.01:
            return f"{value:.6f}"
        return f"{value:.8f}"

    def open_selected_symbol(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        if not values:
            return
        symbol = str(values[0])
        if not symbol.endswith("USDT"):
            return
        base = symbol[:-4]
        webbrowser.open(f"https://www.binance.com/en/trade/{base}_USDT?type=spot")


if __name__ == "__main__":
    app = UmutScannerApp()
    app.mainloop()
