# JARVIS Automation Control Plane

The dashboard reports automation readiness for PAPER trading and strategy R&D. LIVE activation is deliberately excluded and always remains a human decision.

```text
Market data -> research/backtests -> evidence policy -> paper scanner
     |                                      |              |
     +-> quality/provenance                 +-> RISK_OFF   +-> risk engine
                                                               |
Dashboard <- readiness/status <- supervisor <- reconciliation <-+
     |
     +-> Telegram alerts, worker recovery, daily reports
```

Readiness is calculated from nine observable checks: supervisor, scanner, position monitor, reconciliation, real-market evidence, R&D enablement, paper mode, Telegram, and Kite. It is never hard-coded. A missing credential or stopped worker remains visible as a blocker.

Reliability choices:

- The supervisor heartbeat recovers stopped paper workers.
- Reconciliation mismatches activate the kill switch.
- Dashboard polling is read-only and does not change trading state.
- RISK_OFF blocks live execution while research and paper testing remain available.
- Credentials are never stored in dashboard responses or committed files.

As the system grows, move long-running futures research to a durable job queue and retain a point-in-time expired-contract archive for rollover studies.
