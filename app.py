from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from scanner_engine import RiskSettings, ScanResult, UmutScanner


class UmutScannerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("UMUT Scanner")
        self.geometry("1550x820")
        self.minsize(1250, 700)

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
        ttk.Label(
            header,
            text="Tarama → Teknik → Entry → Stop → Pozisyon → İzin / Ret",
            font=("Segoe UI", 10),
        ).pack(side="left", padx=(12, 0))

        controls = ttk.LabelFrame(self, text="Tarama ve Risk Ayarları", padding=10)
        controls.pack(fill="x", padx=12, pady=(0, 8))

        self.interval_var = tk.StringVar(value="1h")
        self.max_symbols_var = tk.IntVar(value=60)
        self.min_volume_var = tk.StringVar(value="10000000")
        self.min_score_var = tk.DoubleVar(value=55.0)
        self.account_balance_var = tk.DoubleVar(value=1000.0)
        self.risk_pct_var = tk.DoubleVar(value=0.5)
        self.max_position_pct_var = tk.DoubleVar(value=20.0)
        self.max_stop_pct_var = tk.DoubleVar(value=5.0)

        specs = [
            ("Zaman Dilimi", self.interval_var, "combo"),
            ("Maks. Coin", self.max_symbols_var, "symbols"),
            ("Min 24s Hacim", self.min_volume_var, "entry"),
            ("Min Genel", self.min_score_var, "score"),
            ("Bakiye USDT", self.account_balance_var, "balance"),
            ("Risk / İşlem %", self.risk_pct_var, "risk"),
            ("Maks. Pozisyon %", self.max_position_pct_var, "position"),
            ("Maks. Stop %", self.max_stop_pct_var, "stop"),
        ]

        for idx, (label, variable, kind) in enumerate(specs):
            ttk.Label(controls, text=label).grid(row=0, column=idx, sticky="w")
            if kind == "combo":
                widget = ttk.Combobox(
                    controls,
                    textvariable=variable,
                    values=["15m", "1h", "4h", "1d"],
                    width=8,
                    state="readonly",
                )
            elif kind == "symbols":
                widget = ttk.Spinbox(controls, from_=20, to=200, increment=10, textvariable=variable, width=9)
            elif kind == "score":
                widget = ttk.Spinbox(controls, from_=0, to=100, increment=1, textvariable=variable, width=9)
            elif kind == "balance":
                widget = ttk.Spinbox(controls, from_=0, to=10_000_000, increment=100, textvariable=variable, width=11)
            elif kind == "risk":
                widget = ttk.Spinbox(controls, from_=0.1, to=5.0, increment=0.1, textvariable=variable, width=9)
            elif kind == "position":
                widget = ttk.Spinbox(controls, from_=1, to=100, increment=1, textvariable=variable, width=10)
            elif kind == "stop":
                widget = ttk.Spinbox(controls, from_=0.5, to=20.0, increment=0.5, textvariable=variable, width=9)
            else:
                widget = ttk.Entry(controls, textvariable=variable, width=14)
            widget.grid(row=1, column=idx, padx=(0, 10), sticky="w")

        self.scan_button = ttk.Button(controls, text="TARAMAYI BAŞLAT", command=self.start_scan)
        self.scan_button.grid(row=1, column=8, padx=(6, 6))

        self.stop_button = ttk.Button(controls, text="DURDUR", command=self.stop_scan, state="disabled")
        self.stop_button.grid(row=1, column=9, padx=6)

        self.status_var = tk.StringVar(value="Hazır")
        ttk.Label(controls, textvariable=self.status_var).grid(
            row=2, column=0, columnspan=8, sticky="w", pady=(8, 0)
        )
        self.progress = ttk.Progressbar(controls, mode="determinate", length=260)
        self.progress.grid(row=2, column=8, columnspan=2, padx=(6, 6), pady=(8, 0), sticky="ew")

        table_frame = ttk.Frame(self, padding=(12, 0, 12, 8))
        table_frame.pack(fill="both", expand=True)

        columns = (
            "permission", "symbol", "price", "trend", "setup", "entry", "general",
            "adx", "rvol", "structure", "mtf", "stop", "stop_pct",
            "position", "position_pct", "risk_stop", "signal", "reason"
        )
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=24)

        headers = {
            "permission": "İzin",
            "symbol": "Coin",
            "price": "Fiyat",
            "trend": "Trend",
            "setup": "Setup",
            "entry": "Entry",
            "general": "Genel",
            "adx": "ADX",
            "rvol": "RVOL",
            "structure": "Yapı",
            "mtf": "MTF",
            "stop": "Stop",
            "stop_pct": "Stop %",
            "position": "Pozisyon $",
            "position_pct": "Pozisyon %",
            "risk_stop": "Stop Risk $",
            "signal": "Sinyal",
            "reason": "Karar Nedeni",
        }
        widths = {
            "permission": 65,
            "symbol": 95,
            "price": 95,
            "trend": 65,
            "setup": 65,
            "entry": 65,
            "general": 65,
            "adx": 55,
            "rvol": 60,
            "structure": 70,
            "mtf": 55,
            "stop": 95,
            "stop_pct": 70,
            "position": 90,
            "position_pct": 80,
            "risk_stop": 85,
            "signal": 95,
            "reason": 330,
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

        self.tree.tag_configure("allowed", background="#d9f7df")
        self.tree.tag_configure("rejected", background="#f7eeee")
        self.tree.bind("<Double-1>", self.open_selected_symbol)

        footer = ttk.Frame(self, padding=(12, 0, 12, 10))
        footer.pack(fill="x")
        ttk.Label(
            footer,
            text=(
                "İZİN = teknik eşikler + risk kapısı birlikte geçti. "
                "Pozisyon hesabı: risk bütçesi / stop mesafesi, ardından maks. pozisyon limiti uygulanır. "
                "Bu uygulama emir göndermez."
            ),
            font=("Segoe UI", 9),
        ).pack(side="left")

    def start_scan(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        try:
            max_symbols = int(self.max_symbols_var.get())
            min_volume = float(self.min_volume_var.get())
            min_score = float(self.min_score_var.get())
            settings = RiskSettings(
                account_balance=float(self.account_balance_var.get()),
                risk_per_trade_pct=float(self.risk_pct_var.get()),
                max_position_pct=float(self.max_position_pct_var.get()),
                max_stop_pct=float(self.max_stop_pct_var.get()),
            )
        except ValueError:
            messagebox.showerror("Geçersiz değer", "Tarama ve risk ayarlarında sayısal alanları kontrol et.")
            return

        if settings.account_balance <= 0:
            messagebox.showerror("Bakiye gerekli", "Pozisyon boyutu için hesap bakiyesini USDT olarak gir.")
            return
        if settings.risk_per_trade_pct <= 0:
            messagebox.showerror("Risk gerekli", "İşlem başına risk yüzdesi 0'dan büyük olmalı.")
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
            args=(self.interval_var.get(), max_symbols, min_volume, min_score, settings),
            daemon=True,
        )
        self.worker.start()

    def stop_scan(self) -> None:
        self.cancel_event.set()
        self.status_var.set("Durdurma isteniyor...")

    def _scan_worker(
        self,
        interval: str,
        max_symbols: int,
        min_volume: float,
        min_score: float,
        settings: RiskSettings,
    ) -> None:
        def progress(done: int, total: int, symbol: str, result: ScanResult | None, error: str | None) -> None:
            self.events.put(("progress", done, total, symbol, result, error))

        try:
            results, errors = self.scanner.scan(
                interval=interval,
                max_symbols=max_symbols,
                min_quote_volume=min_volume,
                min_score=min_score,
                risk_settings=settings,
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
                    allowed = sum(1 for item in results if item.trade_permission == "İZİN")
                    if cancelled:
                        self.status_var.set(f"Tarama durduruldu — {len(results)} sonuç / {allowed} izin")
                    else:
                        self.status_var.set(
                            f"Tamamlandı — {len(results)} sonuç / {allowed} izin / {errors} hata"
                        )
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
        for result in sorted(
            self.results,
            key=lambda x: (x.trade_permission == "İZİN", x.general_score, x.entry_score),
            reverse=True,
        ):
            self._insert_result(result)

    def _insert_result(self, r: ScanResult) -> None:
        tag = "allowed" if r.trade_permission == "İZİN" else "rejected"
        values = (
            r.trade_permission,
            r.symbol,
            self._fmt_price(r.price),
            f"{r.trend_score:.1f}",
            f"{r.setup_score:.1f}",
            f"{r.entry_score:.1f}",
            f"{r.general_score:.1f}",
            f"{r.adx:.1f}",
            f"{r.rvol:.2f}",
            r.structure,
            f"{r.mtf_score:.0f}",
            self._fmt_price(r.stop_price),
            f"{r.stop_distance_pct:.2f}",
            f"{r.position_usdt:.2f}",
            f"{r.position_pct:.1f}",
            f"{r.risk_at_stop_usdt:.2f}",
            r.signal,
            r.reject_reason,
        )
        self.tree.insert("", "end", values=values, tags=(tag,))

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
        symbol = str(values[1])
        if not symbol.endswith("USDT"):
            return
        base = symbol[:-4]
        webbrowser.open(f"https://www.binance.com/en/trade/{base}_USDT?type=spot")


if __name__ == "__main__":
    app = UmutScannerApp()
    app.mainloop()
