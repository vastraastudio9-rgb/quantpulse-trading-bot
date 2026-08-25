"""
JARVIS Auto-Trading Bot Loop

Autonomously: classify regime → filter strategies by regime → generate signals →
risk check → execute (paper mode). Runs in background thread with safety guards.

SAFETY GUARDS (fail-closed):
  - Kill switch blocks all auto-trades
  - Daily loss limit blocks new trades
  - Max positions enforced
  - Regime must be TRADE OK (not RISK_OFF/ABNORMAL)
  - Strategy must be in recommended list for current regime
  - Confidence must be > 60
  - Human approval required to enable (not on by default)

This is the autonomous trading loop that connects everything:
  regime.py → strategies.py → execution_engine.py → risk_engine.py
"""
import time
import threading
import random
from typing import Dict, List, Optional, Set
from datetime import datetime, timezone
from dataclasses import dataclass, field

from market_data import INSTRUMENTS, get_live_quote, generate_history
from strategies import STRATEGIES, generate_signal
from regime import classify_full_regime, route_strategies, RegimeState, StrategyRouting
from execution_engine import get_execution_engine
from risk_engine import get_portfolio_engine
from observability import logger, metrics
import brokers.telegram_bot as telegram_bot


@dataclass
class BotConfig:
    """Auto-trading bot configuration."""
    enabled: bool = False
    # Symbols to trade (rotates through these)
    symbols: List[str] = field(default_factory=lambda: ["NIFTY", "BANKNIFTY", "GOLD", "NATURALGAS"])
    # Minimum confidence to execute (0-100)
    min_confidence: float = 65.0
    # Only trade strategies recommended by regime router
    use_regime_filter: bool = True
    # Max trades per day (circuit breaker)
    max_trades_per_day: int = 10
    # Interval between signal scans (seconds)
    scan_interval_seconds: int = 30
    # Send Telegram alerts on execution
    send_telegram_alerts: bool = True
    # Strategies to skip (blacklist)
    strategy_blacklist: Set[str] = field(default_factory=set)
    # Paper mode (always True in autonomous — live requires human approval)
    paper_mode: bool = True


class AutoTradingBot:
    """Autonomous trading bot with safety guards.
    
    USAGE:
        bot = get_auto_bot()
        bot.config.symbols = ["NIFTY", "BANKNIFTY"]
        bot.start()  # begins background loop
    
    The bot will:
      1. Every scan_interval_seconds, pick a random symbol
      2. Classify regime for that symbol
      3. If regime says TRADE OK, pick a recommended strategy
      4. Generate signal for that strategy + symbol
      5. If signal confidence > min_confidence, execute via paper engine
      6. Log + send Telegram alert
    
    SAFETY: bot checks kill_switch, daily loss, max positions before every trade.
    """

    def __init__(self, config: BotConfig = None):
        self.config = config or BotConfig()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._trades_today = 0
        self._last_reset_date = None
        self._scan_count = 0
        self._execution_count = 0
        self._rejection_count = 0
        self._last_scan: Optional[Dict] = None

    def start(self) -> bool:
        """Start the auto-trading bot. Returns True if started."""
        if self._running:
            return False
        if not self.config.enabled:
            logger.warning("Auto bot start requested but config.enabled=False")
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Auto-trading bot started", symbols=self.config.symbols, interval=self.config.scan_interval_seconds)
        metrics.inc_counter("auto_bot_starts_total")
        return True

    def stop(self) -> bool:
        """Stop the auto-trading bot."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("Auto-trading bot stopped")
        metrics.inc_counter("auto_bot_stops_total")
        return True

    def enable(self) -> Dict:
        """Enable the bot (requires explicit call — not on by default)."""
        self.config.enabled = True
        started = self.start()
        return {
            "enabled": self.config.enabled,
            "started": started,
            "message": "Auto-trading bot enabled and started" if started else "Enabled but failed to start",
        }

    def disable(self) -> Dict:
        """Disable the bot."""
        self.stop()
        self.config.enabled = False
        return {"enabled": False, "message": "Auto-trading bot disabled and stopped"}

    def _check_daily_reset(self):
        """Reset daily trade counter at start of new day."""
        today = datetime.now(timezone.utc).date()
        if self._last_reset_date is None or today > self._last_reset_date:
            self._trades_today = 0
            self._last_reset_date = today

    def _loop(self):
        """Main bot loop — runs in background thread."""
        while self._running:
            try:
                self._check_daily_reset()
                self._scan_and_trade()
            except Exception as e:
                logger.error(f"Auto bot loop error: {e}")
            time.sleep(self.config.scan_interval_seconds)

    def _scan_and_trade(self):
        """One iteration: pick symbol → classify regime → generate signal → execute."""
        self._scan_count += 1
        risk_engine = get_portfolio_engine()
        
        # === SAFETY CHECK 1: Kill switch ===
        if risk_engine.limits.kill_switch:
            logger.warning("Auto bot: kill switch active, skipping scan")
            return
        
        # === SAFETY CHECK 2: Daily loss limit ===
        if risk_engine._daily_loss_lock:
            logger.warning("Auto bot: daily loss limit hit, skipping scan")
            return
        
        # === SAFETY CHECK 3: Max trades today ===
        if self._trades_today >= self.config.max_trades_per_day:
            logger.warning(f"Auto bot: max trades per day ({self.config.max_trades_per_day}) reached")
            return
        
        # === SAFETY CHECK 4: Max open positions ===
        if len(risk_engine.positions) >= risk_engine.limits.max_open_positions:
            return  # silently skip — normal condition
        
        # Pick a random symbol to scan
        symbol = random.choice(self.config.symbols)
        
        # Classify regime
        try:
            bars = generate_history(symbol, days=60, timeframe="1d")
            if not bars or len(bars) < 30:
                return
            regime_state = classify_full_regime(bars)
            routing = route_strategies(regime_state)
        except Exception as e:
            logger.error(f"Auto bot: regime classification failed for {symbol}: {e}")
            return
        
        # === SAFETY CHECK 5: Regime must be TRADE OK ===
        if not routing.should_trade:
            self._last_scan = {
                "symbol": symbol,
                "regime": regime_state.composite_regime,
                "action": "NO_TRADE",
                "reason": routing.reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            return
        
        # Pick a recommended strategy (not blacklisted)
        candidates = [
            s for s in routing.recommended_strategies
            if s not in self.config.strategy_blacklist and s in STRATEGIES
        ]
        if not candidates:
            return
        
        strategy_key = random.choice(candidates)
        
        # Generate signal
        try:
            signal = generate_signal(strategy_key, symbol)
        except Exception as e:
            logger.error(f"Auto bot: signal generation failed for {strategy_key}/{symbol}: {e}")
            return
        
        if signal is None:
            return
        
        # === SAFETY CHECK 6: Confidence threshold ===
        if signal.get("confidence", 0) < self.config.min_confidence:
            self._rejection_count += 1
            self._last_scan = {
                "symbol": symbol,
                "strategy": strategy_key,
                "confidence": signal.get("confidence", 0),
                "action": "REJECTED_LOW_CONFIDENCE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            return
        
        # Execute via paper trading engine
        execution_engine = get_execution_engine()
        result = execution_engine.process_signal(signal)
        
        if result.get("accepted"):
            self._execution_count += 1
            self._trades_today += 1
            self._last_scan = {
                "symbol": symbol,
                "strategy": strategy_key,
                "confidence": signal.get("confidence", 0),
                "regime": regime_state.composite_regime,
                "action": "EXECUTED",
                "position_id": result.get("position_id"),
                "side": result.get("side"),
                "entry_price": result.get("entry_price"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            logger.trade(
                "Auto bot executed trade",
                strategy=strategy_key,
                symbol=symbol,
                position_id=result.get("position_id"),
                confidence=signal.get("confidence"),
                regime=regime_state.composite_regime,
            )
            metrics.inc_counter("auto_bot_executions_total", strategy=strategy_key, symbol=symbol)
            
            # Send Telegram alert
            if self.config.send_telegram_alerts and telegram_bot.is_configured():
                try:
                    telegram_bot.send_alert(
                        title="🤖 Auto-Trade Executed",
                        message=(
                            f"Strategy: {signal.get('strategy_name', strategy_key)}\n"
                            f"Symbol: {symbol}\n"
                            f"Regime: {regime_state.composite_regime}\n"
                            f"Confidence: {signal.get('confidence')}%\n"
                            f"Side: {result.get('side')}\n"
                            f"Entry: ₹{result.get('entry_price')}\n"
                            f"SL: ₹{signal.get('stop_loss')}\n"
                            f"Target: ₹{signal.get('target')}\n"
                            f"Position ID: {result.get('position_id')}\n"
                            f"Trades today: {self._trades_today}/{self.config.max_trades_per_day}"
                        ),
                        alert_type="SUCCESS",
                    )
                except Exception:
                    pass  # don't let Telegram failure break trading
        else:
            self._rejection_count += 1
            self._last_scan = {
                "symbol": symbol,
                "strategy": strategy_key,
                "confidence": signal.get("confidence", 0),
                "action": "REJECTED_RISK",
                "reason": result.get("reason", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            logger.warning(
                "Auto bot trade rejected by risk engine",
                strategy=strategy_key,
                symbol=symbol,
                reason=result.get("reason"),
            )
            metrics.inc_counter("auto_bot_rejections_total", reason="risk_check")

    def status(self) -> Dict:
        """Get bot status."""
        return {
            "enabled": self.config.enabled,
            "running": self._running,
            "paper_mode": self.config.paper_mode,
            "symbols": self.config.symbols,
            "min_confidence": self.config.min_confidence,
            "max_trades_per_day": self.config.max_trades_per_day,
            "scan_interval_seconds": self.config.scan_interval_seconds,
            "use_regime_filter": self.config.use_regime_filter,
            "send_telegram_alerts": self.config.send_telegram_alerts,
            "strategy_blacklist": list(self.config.strategy_blacklist),
            "stats": {
                "scans_total": self._scan_count,
                "executions_total": self._execution_count,
                "rejections_total": self._rejection_count,
                "trades_today": self._trades_today,
                "execution_rate": round(self._execution_count / max(1, self._scan_count) * 100, 1),
            },
            "last_scan": self._last_scan,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Singleton
_auto_bot: Optional[AutoTradingBot] = None

def get_auto_bot() -> AutoTradingBot:
    global _auto_bot
    if _auto_bot is None:
        _auto_bot = AutoTradingBot()
    return _auto_bot
