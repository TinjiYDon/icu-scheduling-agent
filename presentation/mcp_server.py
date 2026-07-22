"""stdio MCP server — tool optimize_beds.

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\pip.exe install "mcp>=1.0"
.\.venv\Scripts\python.exe -m presentation.mcp_server
```
"""

from __future__ import annotations

from presentation.mcp_tools import OPTIMIZE_BEDS_SCHEMA, optimize_beds


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Missing optional dependency `mcp`. Install with: pip install 'mcp>=1.0'"
        ) from exc

    server = FastMCP("icu-scheduling-optimize")

    @server.tool(
        name=OPTIMIZE_BEDS_SCHEMA["name"],
        description=OPTIMIZE_BEDS_SCHEMA["description"],
    )
    def optimize_beds_tool(run_id: str | None = None) -> dict:
        return optimize_beds(run_id)

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
