# Contributing to Solace

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/solace.git
   cd solace
   ```

2. **Start infrastructure:**
   ```bash
   docker compose up postgres redis -d
   ```

3. **Backend setup:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   alembic upgrade head
   uvicorn backend.main:app --reload
   ```

4. **Frontend setup:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Running Tests

```bash
pytest tests/ -v
```

## Adding a New Normalizer

1. Create `backend/integrations/your_provider.py`
2. Implement `BaseNormalizer` with `validate()` and `normalize()` methods
3. Register in `backend/integrations/__init__.py`
4. Add tests in `tests/test_your_provider.py`
5. Send alerts via `POST /api/v1/webhooks/your_provider`

See `backend/integrations/prometheus.py` for a complete example.

## Code Style

- **Python:** Formatted with `ruff`, type hints encouraged
- **TypeScript:** Standard React/TS conventions
- **Commits:** Use conventional commits (`feat:`, `fix:`, `docs:`, etc.)

## Pull Requests

- Keep PRs focused on a single change
- Add tests for new functionality
- Update the README if adding user-facing features
