"""Allow `python -m agent` to invoke the CLI."""
from src.agent.cli import main

raise SystemExit(main())
