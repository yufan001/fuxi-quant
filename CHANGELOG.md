# Changelog

## Unreleased

### Added
- Added a Parquet mirror for market tables and a DuckDB-backed history read path behind `backend/app/data/storage.py`.
- Added sync hooks so daily downloads and market database imports refresh the Parquet mirror.
- Added `scripts/deploy_mac.py` for macOS bootstrap: install dependencies, initialize databases, download baostock data, and start the API.
- Added README screenshots for the platform and backtest pages.

### Changed
- Kept business data on SQLite while starting the Phase 1 storage-decoupling rollout for heavy market reads.
- Updated README to document the market storage layout and macOS deployment workflow.
- Builtin factor backtests now compute from a frame-oriented pipeline while preserving legacy `histories` script compatibility.

### Added
- Added a frame-based factor history path and `score_frame(frame, context)` script protocol for vectorized factor execution.
- Added a supervised worker-process sandbox for factor scripts with `success`, `script_error`, `timeout`, and `cancelled` terminal states.

### Changed
- Sync API, job results, and MCP wrappers now preserve structured factor-script failure payloads instead of exposing only plain error strings.
