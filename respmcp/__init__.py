"""resp-mcp — SERP-free scholarly search, exposed as a library and MCP server."""
from .core import Resp
from .providers import Paper

__version__ = "0.1.0"
__all__ = ["Resp", "Paper"]
