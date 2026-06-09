# Contributing to Hermes + OpenCode Integration

We love contributions! Here's how to help.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USER/hermes-opencode-integration.git`
3. Set up the integration locally: `bash install.sh`
4. Run tests: `python3 -m pytest tests/ -v`

## Making Changes

1. Create a branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Run existing tests to ensure nothing breaks
4. Add tests for new functionality
5. Commit using conventional commits:

```
feat: add new feature
fix: correct bug in proxy
docs: update README
test: add tests for _resolve_model
chore: update dependencies
```

## Testing

```bash
python3 -m pytest tests/ -v              # Run all tests
python3 -m pytest tests/test_proxy_core.py  # Run specific suite
```

All changes must maintain 73/73 passing tests.

## Code Style

- Python: Follow PEP 8
- Shell scripts: Use `set -euo pipefail` and shellcheck
- Keep lines under 100 characters
- Document new functions with docstrings
- No personal data, API keys, or absolute paths

## Pull Request Process

1. Update `CHANGELOG.md` with your changes
2. Update `VERSION` if needed (semantic versioning)
3. Ensure all tests pass
4. Submit the PR with a clear description

## Security

- Never commit API keys or secrets
- Never commit absolute paths with usernames
- Use environment variables or `.env` for sensitive data
- Run the security audit before submitting: `bash verify.sh`

## Questions?

Open an issue or start a discussion. We're happy to help!
