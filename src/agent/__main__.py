"""Allow `python -m agent` to invoke the CLI."""
from agent.cli import main

raise SystemExit(main())
