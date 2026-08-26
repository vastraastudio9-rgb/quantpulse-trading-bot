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
from zoneinfo import ZoneInfo

from market_data import INSTRUMENTS, get_live_quote, generate_history
from strategies import STRATEGIES, generate_signal
from regime import classify_full_regime, route_strategies, iv_rank, RegimeState, StrategyRouting
from execution_engine import get_execution_engine
from risk_engine import get_portfolio_engine
from observability import logger, metrics
from research_optimizer import load_policy
from shadow_lab import get_shadow_lab
import brokers.telegram_bot as telegram_bot


def select_policy_candidates(candidates: List[str], policy: Dict, symbol: str, trading_mode: str):
    """Separate live-approved routing from PAPER_RND candidate learning."""
    policy_choice = policy.get("approved_by_symbol", {}).get(symbol, {}).get("strategy")
    if policy_choice:
        return [candidate for candidate in candidates if candidate == policy_choice], "VALIDATED_POLICY"
    if trading_mode == "PAPER":
        return list(candidates), "PAPER_RND"
    return [], "LIVE_POLICY_BLOCKED"


def apply_strategy_entry_gates(candidates: List[str], current_iv_rank: float) -> List[str]:
    """Apply strategy-specific evidence gates after regime routing."""
    return [
        candidate for candidate in candidates
        if candidate != "VRP_HARVEST" or current_iv_rank >= 70
    ]


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
    # Avoid repeating the same qualifying paper signal every scan.
    signal_alert_cooldown_minutes: int = 15
    # Evaluate every strategy in an isolated, non-promotable paper laboratory.
    shadow_lab_enabled: bool = True
    shadow_scan_interval_seconds: int = 300
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
      1. Every scan_interval_seconds, scan the full configured watchlist
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
        self._cycle_count = 0
        self._execution_count = 0
        self._rejection_count = 0
        self._last_scan: Optional[Dict] = None
        self._symbol_scans: Dict[str, Dict] = {}
        self._signal_alert_times: Dict[str, float] = {}
        self._signal_alert_count = 0
        self._last_signal_alert: Optional[Dict] = None
        self._last_shadow_scan_monotonic = 0.0
        self._latest_regimes: Dict[str, Dict] = {}

    def _notify_paper_signal(self, signal: Dict, regime: str, execution_scope: str) -> Dict:
        """Deliver valid PAPER signals independently of position acceptance."""
        if not (self.config.send_telegram_alerts and telegram_bot.is_configured()):
            return {"sent": False, "reason": "Telegram alerts are disabled or not configured"}
        if signal.get("paper_execution_eligible") is not True:
            return {"sent": False, "reason": "Signal failed structural paper validation"}
        key = f"{signal.get('symbol')}:{signal.get('strategy_key')}:{signal.get('direction', '')}"
        now = time.monotonic()
        cooldown = max(1, int(self.config.signal_alert_cooldown_minutes)) * 60
        remaining = cooldown - (now - self._signal_alert_times.get(key, -cooldown))
        if remaining > 0:
            return {"sent": False, "reason": "Signal alert cooldown", "retry_after_seconds": round(remaining)}
        result = telegram_bot.send_alert(
            title="JARVIS Paper Signal",
            message=(
                f"PAPER ONLY — no live order\n"
                f"Strategy: {signal.get('strategy_name', signal.get('strategy_key', ''))}\n"
                f"Symbol: {signal.get('symbol', '')}\n"
                f"Regime: {regime}\n"
                f"Confidence: {signal.get('confidence', 0)}%\n"
                f"Direction: {signal.get('direction', '')}\n"
                f"Entry: ₹{signal.get('entry_price', 0)}\n"
                f"SL: ₹{signal.get('stop_loss', 0)}\n"
                f"Target: ₹{signal.get('target', 0)}\n"
                f"Scope: {execution_scope}"
            ),
            alert_type="INFO",
        )
        sent = result.get("ok") is True
        self._last_signal_alert = {
            "sent": sent, "symbol": signal.get("symbol"), "strategy": signal.get("strategy_key"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": None if sent else result.get("description", result.get("error", "Telegram delivery failed")),
        }
        if sent:
            self._signal_alert_times[key] = now
            self._signal_alert_count += 1
            metrics.inc_counter("paper_signal_alerts_total", strategy=signal.get("strategy_key", ""),
                                symbol=signal.get("symbol", ""))
        return self._last_signal_alert

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

    def reset_session_stats(self) -> None:
        self._trades_today = 0
        self._scan_count = 0
        self._cycle_count = 0
        self._execution_count = 0
        self._rejection_count = 0
        self._last_scan = None
        self._symbol_scans = {}
        self._last_reset_date = datetime.now(ZoneInfo("Asia/Kolkata")).date()

    def _check_daily_reset(self):
        """Reset daily trade counter at start of new day."""
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
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
        """Scan the full watchlist once; risk locks block positions, not research."""
        risk_engine = get_portfolio_engine()
        self._cycle_count += 1
        for symbol in list(dict.fromkeys(self.config.symbols)):
            self._scan_count += 1
            previous = self._last_scan
            self._scan_symbol(symbol, risk_engine)
            if self._last_scan is not previous and self._last_scan and self._last_scan.get("symbol") == symbol:
                self._symbol_scans[symbol] = self._last_scan
            else:
                self._symbol_scans[symbol] = {
                    "symbol": symbol, "action": "NO_SIGNAL", "reason": "No qualifying signal generated",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        self._run_shadow_cycle()

    def _run_shadow_cycle(self) -> None:
        """Observe every strategy without calling broker or execution modules."""
        if not self.config.shadow_lab_enabled:
            return
        now = time.monotonic()
        if now - self._last_shadow_scan_monotonic < max(30, self.config.shadow_scan_interval_seconds):
            return
        self._last_shadow_scan_monotonic = now
        lab = get_shadow_lab()
        for symbol in list(dict.fromkeys(self.config.symbols)):
            context = self._latest_regimes.get(symbol)
            if not context:
                continue
            instrument = INSTRUMENTS.get(symbol, {})
            for strategy_key in STRATEGIES:
                try:
                    signal = generate_signal(strategy_key, symbol)
                    if signal:
                        lab.observe(
                            signal,
                            context["regime"],
                            strategy_key in context["recommended"],
                            int(instrument.get("lot_size", 1)),
                            float(instrument.get("tick_size", .01)),
                        )
                except Exception as exc:
                    logger.error(f"Shadow lab observation failed for {strategy_key}/{symbol}: {exc}")

    def _scan_symbol(self, symbol: str, risk_engine) -> None:
        """Classify and report one symbol, then request a paper position if risk allows."""
        
        # Classify regime
        try:
            bars = generate_history(symbol, days=60, timeframe="1d")
            if not bars or len(bars) < 30:
                return
            regime_state = classify_full_regime(bars)
            routing = route_strategies(regime_state)
            self._latest_regimes[symbol] = {
                "regime": regime_state.composite_regime,
                "recommended": list(routing.recommended_strategies),
            }
        except Exception as e:
            logger.error(f"Auto bot: regime classification failed for {symbol}: {e}")
            return
        
        # Regime must be TRADE OK before a candidate is generated.
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
        candidates = apply_strategy_entry_gates(candidates, iv_rank(bars))
        policy = load_policy()
        from trading_mode import get_trading_mode
        candidates, execution_scope = select_policy_candidates(
            candidates, policy, symbol, get_trading_mode().status()["mode"]
        )
        if not candidates:
            self._last_scan = {
                "symbol": symbol, "regime": regime_state.composite_regime,
                "action": "NO_TRADE_POLICY_REGIME_MISMATCH",
                "reason": "No policy-compatible strategy is suitable for the current regime",
                "research_mode": policy.get("mode", "RISK_OFF"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            return
        
        strategy_key = random.choice(candidates)

        # Evidence governance can quarantine a strategy after enough poor paper
        # results. Sparse history remains eligible for paper learning.
        try:
            from autonomy import get_autonomy_supervisor
            supervisor = get_autonomy_supervisor()
            allowed, governance_reason = supervisor.strategy_allowed(strategy_key)
            if not allowed:
                self._rejection_count += 1
                self._last_scan = {
                    "symbol": symbol, "strategy": strategy_key,
                    "action": "REJECTED_GOVERNANCE", "reason": governance_reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                supervisor.record_decision("SIGNAL_REJECTED", strategy_key, governance_reason,
                                           {"symbol": symbol, "gate": "strategy_governance"})
                return
        except Exception as e:
            logger.error(f"Auto bot: governance check failed closed: {e}")
            return
        
        # Generate signal
        try:
            signal = generate_signal(strategy_key, symbol)
        except Exception as e:
            logger.error(f"Auto bot: signal generation failed for {strategy_key}/{symbol}: {e}")
            return
        
        if signal is None:
            return
        signal["execution_scope"] = execution_scope
        signal["research_candidate"] = execution_scope == "PAPER_RND"
        
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

        # Dynamic quantity considers stop distance, confidence, volatility, and
        # portfolio drawdown. Any sizing failure blocks execution.
        try:
            sizing = supervisor.position_size(signal, regime_state.confidence)
            signal["quantity"] = sizing["quantity"]
            supervisor.record_decision("PAPER_RND_SIGNAL_APPROVED" if execution_scope == "PAPER_RND" else "SIGNAL_APPROVED",
                                       strategy_key, "All autonomous paper gates passed", {
                "symbol": symbol, "confidence": signal.get("confidence", 0),
                "regime": regime_state.composite_regime, "sizing": sizing, "execution_scope": execution_scope,
            })
        except Exception as e:
            logger.error(f"Auto bot: position sizing failed closed: {e}")
            return

        # A qualifying paper signal remains useful when portfolio risk later
        # rejects a new position because of duplication or exposure limits.
        notification = self._notify_paper_signal(signal, regime_state.composite_regime, execution_scope)
        from paper_signal_journal import get_paper_signal_journal
        paper_signal_id = get_paper_signal_journal().record_detected(
            signal, regime_state.composite_regime, execution_scope, notification,
        )
        
        # Execute via paper trading engine
        execution_engine = get_execution_engine()
        if self._trades_today >= self.config.max_trades_per_day:
            result = {"accepted": False, "reason": f"Daily paper trade limit {self.config.max_trades_per_day} reached"}
        else:
            result = execution_engine.process_signal(signal)
        get_paper_signal_journal().record_outcome(
            paper_signal_id,
            "POSITION_OPENED" if result.get("accepted") else "RISK_BLOCKED",
            {"position_id": result.get("position_id"), "reason": result.get("reason", "")},
        )
        
        if result.get("accepted"):
            self._execution_count += 1
            self._trades_today += 1
            self._last_scan = {
                "symbol": symbol,
                "strategy": strategy_key,
                "confidence": signal.get("confidence", 0),
                "regime": regime_state.composite_regime,
                "action": "PAPER_RND_EXECUTED" if execution_scope == "PAPER_RND" else "EXECUTED",
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
            if execution_scope != "PAPER_RND" and signal.get("execution_eligible") is True and self.config.send_telegram_alerts and telegram_bot.is_configured():
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
        policy = load_policy()
        return {
            "enabled": self.config.enabled,
            "running": self._running,
            "paper_mode": self.config.paper_mode,
            "research_mode": policy.get("mode", "RISK_OFF"),
            "research_data_source": policy.get("data_source", "NONE"),
            "symbols": self.config.symbols,
            "min_confidence": self.config.min_confidence,
            "max_trades_per_day": self.config.max_trades_per_day,
            "scan_interval_seconds": self.config.scan_interval_seconds,
            "use_regime_filter": self.config.use_regime_filter,
            "send_telegram_alerts": self.config.send_telegram_alerts,
            "signal_alert_cooldown_minutes": self.config.signal_alert_cooldown_minutes,
            "shadow_lab_enabled": self.config.shadow_lab_enabled,
            "shadow_scan_interval_seconds": self.config.shadow_scan_interval_seconds,
            "shadow_lab": get_shadow_lab().status(),
            "strategy_blacklist": list(self.config.strategy_blacklist),
            "stats": {
                "scans_total": self._scan_count,
                "cycles_total": self._cycle_count,
                "executions_total": self._execution_count,
                "rejections_total": self._rejection_count,
                "trades_today": self._trades_today,
                "execution_rate": round(self._execution_count / max(1, self._scan_count) * 100, 1),
            },
            "paper_signal_alerts": {"sent_total": self._signal_alert_count, "last": self._last_signal_alert},
            "watchlist_coverage": {"symbols_per_cycle": len(set(self.config.symbols)),
                                   "latest_by_symbol": self._symbol_scans},
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
