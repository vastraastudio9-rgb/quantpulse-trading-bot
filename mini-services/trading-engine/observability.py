"""
JARVIS Structured Logging + Metrics

- JSON-formatted logs with request_id, trace_id, strategy_id, symbol
- Prometheus-compatible /metrics endpoint (counters, histograms, gauges)
- Thread-safe metric collection

Usage in endpoints:
    from observability import log_request, metrics
    
    @app.middleware("http")
    async def add_logging(request, call_next):
        request_id = str(uuid.uuid4())[:8]
        log_request("request_start", request_id=request_id, path=request.url.path)
        response = await call_next(request)
        metrics.record_request(request.url.path, response.status_code, duration)
        return response
"""
import json
import time
import threading
from typing import Dict, List, Optional
from datetime import datetime, timezone
from collections import defaultdict
import sys


# ============ STRUCTURED LOGGER ============
class StructuredLogger:
    """JSON-formatted logger with request/trace/strategy IDs."""

    def __init__(self, name: str = "jarvis"):
        self.name = name
        self._lock = threading.Lock()

    def _log(self, level: str, message: str, **kwargs):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "logger": self.name,
            "message": message,
        }
        entry.update(kwargs)
        with self._lock:
            print(json.dumps(entry, default=str), file=sys.stdout, flush=True)

    def info(self, message: str, **kwargs):
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log("ERROR", message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._log("CRITICAL", message, **kwargs)

    def trade(self, message: str, strategy: str = "", symbol: str = "", **kwargs):
        """Log trade-related events."""
        self._log("TRADE", message, strategy=strategy, symbol=symbol, **kwargs)

    def risk(self, message: str, alert_level: str = "", **kwargs):
        """Log risk events."""
        self._log("RISK", message, alert_level=alert_level, **kwargs)


logger = StructuredLogger("jarvis")


# ============ METRICS ============
class MetricsRegistry:
    """Thread-safe metrics registry. Prometheus-compatible output."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._labels: Dict[str, Dict[str, str]] = {}

    def inc_counter(self, name: str, value: float = 1, **labels):
        """Increment a counter."""
        key = self._label_key(name, labels)
        with self._lock:
            self._counters[key] += value
            self._labels[key] = labels

    def set_gauge(self, name: str, value: float, **labels):
        """Set a gauge value."""
        key = self._label_key(name, labels)
        with self._lock:
            self._gauges[key] = value
            self._labels[key] = labels

    def observe_histogram(self, name: str, value: float, **labels):
        """Record a histogram observation (latency, size, etc.)."""
        key = self._label_key(name, labels)
        with self._lock:
            self._histograms[key].append(value)
            # Keep only last 1000 observations
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]
            self._labels[key] = labels

    def _label_key(self, name: str, labels: Dict) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def record_request(self, path: str, status_code: int, duration_ms: float):
        """Record an HTTP request."""
        self.inc_counter("http_requests_total", path=path, status=str(status_code))
        self.observe_histogram("http_request_duration_ms", duration_ms, path=path)

    def record_signal(self, strategy: str, symbol: str, confidence: float):
        """Record a signal generation."""
        self.inc_counter("signals_generated_total", strategy=strategy, symbol=symbol)
        self.observe_histogram("signal_confidence", confidence, strategy=strategy)

    def record_trade(self, strategy: str, symbol: str, pnl: float):
        """Record a closed trade."""
        self.inc_counter("trades_total", strategy=strategy, symbol=symbol, outcome="win" if pnl > 0 else "loss")
        self.observe_histogram("trade_pnl", pnl, strategy=strategy)

    def record_backtest(self, strategy: str, symbol: str, duration_ms: float, sharpe: float):
        """Record a backtest run."""
        self.inc_counter("backtests_total", strategy=strategy, symbol=symbol)
        self.observe_histogram("backtest_duration_ms", duration_ms, strategy=strategy)
        self.observe_histogram("backtest_sharpe", sharpe, strategy=strategy)

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []
        with self._lock:
            # Counters
            seen = set()
            for key, value in sorted(self._counters.items()):
                name = key.split("{")[0]
                if name not in seen:
                    lines.append(f"# TYPE {name} counter")
                    seen.add(name)
                labels = self._labels.get(key, {})
                label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
                if label_str:
                    lines.append(name + "{" + label_str + "} " + str(value))
                else:
                    lines.append(f"{name} {value}")

            # Gauges
            seen = set()
            for key, value in sorted(self._gauges.items()):
                name = key.split("{")[0]
                if name not in seen:
                    lines.append(f"# TYPE {name} gauge")
                    seen.add(name)
                labels = self._labels.get(key, {})
                label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
                if label_str:
                    lines.append(name + "{" + label_str + "} " + str(value))
                else:
                    lines.append(f"{name} {value}")

            # Histograms (summarized)
            seen = set()
            for key, values in sorted(self._histograms.items()):
                name = key.split("{")[0]
                if name not in seen:
                    lines.append(f"# TYPE {name} histogram")
                    seen.add(name)
                if values:
                    import numpy as np
                    arr = np.array(values)
                    labels = self._labels.get(key, {})
                    label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
                    # Build label prefix carefully (Prometheus format: {key="val",...})
                    if label_str:
                        prefix = "{" + label_str + ","
                    else:
                        prefix = "{"
                    lines.append(f'{name}{prefix}count="{len(arr)}"}} {len(arr)}')
                    lines.append(f'{name}{prefix}sum="{arr.sum():.4f}"}} {arr.sum():.4f}')
                    for p in [0.5, 0.95, 0.99]:
                        pval = float(np.percentile(arr, p * 100))
                        lines.append(f'{name}{prefix}quantile="{p}"}} {pval:.4f}')

        return "\n".join(lines) + "\n"

    def to_dict(self) -> Dict:
        """Export metrics as dict (for /api/jarvis/metrics JSON endpoint)."""
        with self._lock:
            import numpy as np
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    key: {
                        "count": len(vals),
                        "sum": sum(vals),
                        "p50": float(np.percentile(vals, 50)) if vals else 0,
                        "p95": float(np.percentile(vals, 95)) if vals else 0,
                        "p99": float(np.percentile(vals, 99)) if vals else 0,
                    }
                    for key, vals in self._histograms.items()
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


metrics = MetricsRegistry()


# ============ REQUEST TRACKING ============
_request_id_counter = 0
_request_id_lock = threading.Lock()

def generate_request_id() -> str:
    """Generate a short request ID for tracing."""
    global _request_id_counter
    with _request_id_lock:
        _request_id_counter += 1
        return f"req-{_request_id_counter:06d}-{int(time.time()) % 100000:05d}"


def log_request_event(event: str, request_id: str = "", **kwargs):
    """Log a request lifecycle event."""
    logger.info(
        f"request_event: {event}",
        event=event,
        request_id=request_id,
        **kwargs,
    )
