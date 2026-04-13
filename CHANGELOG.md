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
