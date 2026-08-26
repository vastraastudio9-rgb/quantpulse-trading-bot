# JARVIS 24x7 Research Architecture

## Safety boundary

The control plane operates only on research, shadow observations, and paper positions. It never imports broker order submission, changes trading mode, or grants live eligibility. Model-derived option marks remain engineering evidence and cannot promote a strategy.

## Data flow

```text
Authorized market source -> provenance store -> quality gate -> signal candidates
       -> regime router -> paper risk gates -> actual paper journal
       -> shadow lab (all strategies, model evidence only)
       -> strategy intelligence -> drift review + signal ranking
       -> immutable experiment registry -> forward validation
```

## 24-hour schedule (Asia/Kolkata)

| Phase | Time | Work |
|---|---:|---|
| Pre-market | before 09:00 | health, state reconciliation, data freshness |
| Market monitoring | 09:00-15:30 | ingest, quality checks, signal/paper monitoring |
| Reconciliation | 15:30-16:00 | close gaps, reconcile journals and paper positions |
| Post-market research | after 16:00 | leakage-resistant R&D, experiment registration, forward evaluation |
| Weekend research | weekends | deeper comparisons and dependency review |

## Evidence classes

- `REAL_MARKET`: authorized real candles with provenance and quality checks.
- `PAPER_FILL`: actual forward paper execution with costs and slippage.
- `SHADOW_MODEL`: model-derived option marks; useful for engineering and ranking research only.
- `ENGINEERING_ONLY`: synthetic or proxy data; never promotion evidence.

## Growth decisions

- Keep JSONL registries while the deployment is single-host; move to PostgreSQL only when multiple writers or hosts are required.
- Keep deterministic ranking until enough actual labeled trades exist; then add a calibrated meta-label model.
- Prefer process supervision outside the trading engine. The engine must fail closed and recover persisted PAPER workers only.
