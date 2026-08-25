# Contributing

Contributions are welcome through GitHub pull requests.

1. Fork the repository and create a focused branch.
2. Never commit broker credentials, API keys, tokens, passwords, `.env` files,
   account identifiers, or trading records.
3. Keep live trading disabled. Changes to execution or risk controls require
   tests and a clear safety explanation.
4. Run `python -m pytest mini-services/trading-engine/tests -q` and
   `pnpm run build` before opening a pull request.
5. Describe the change, its risk, and how it was tested.

Maintainers review and merge accepted changes. Public access does not grant
untrusted contributors direct write access to the default branch.
