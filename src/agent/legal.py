"""Legal notice shown at agent startup.

This is shown once on the console (and optionally persisted to the system
log on Windows) to comply with the principle of transparency for endpoint
monitoring agents. The exact wording should be reviewed by legal counsel
before deployment; this is a template.
"""

from __future__ import annotations

BANNER = """\
================================================================
  UEBA Endpoint Agent v{version}
================================================================
  This device is the property of your employer and is being
  monitored. The following activity is collected and sent to
  the central Security Operations Center:
    - Logon / logoff events
    - File and device (USB) access
    - Web browsing and DNS queries
    - Running processes and network connections
    - Email and other application activity
  Collection is used solely for security and compliance.
  By continuing, you acknowledge this monitoring.
  State file: {state_path}
  Server:     {server_url}
  Agent ID:   {agent_id}
================================================================
"""


def render_banner(
    version: str, state_path: str, server_url: str, agent_id: str
) -> str:
    return BANNER.format(
        version=version,
        state_path=state_path,
        server_url=server_url,
        agent_id=agent_id,
    )
