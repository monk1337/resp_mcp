# Resp MCP

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for scholarly paper search. It gives LLMs and coding agents structured tools to search academic papers, traverse citation graphs, and discover related work across arXiv, Semantic Scholar, OpenReview, OpenAlex, DBLP, Crossref, the ACL Anthology, and the major AI / ML / NLP / CV conference proceedings — all returned as clean, normalized JSON records.

This is the MCP server for [`resp`](https://github.com/monk1337/resp): the same paper-collection capabilities, exposed as tools any MCP client can call.

## Key Features

- **One tool per source.** Dedicated tools for arXiv, Semantic Scholar, OpenReview, OpenAlex, DBLP, Crossref, ACM, Connected Papers, and the ACL Anthology.
- **Conference-aware search.** A single `search_conference` tool routes to the right source for 27 venues (CVPR, ICCV, ECCV, ICML, NeurIPS, AAAI, EMNLP, IJCAI, and more) — you pass a name and year, it handles the rest.
- **Citation graph.** Fetch citations, references, and related papers for any paper by id, DOI, or arXiv id.
- **Normalized output.** Every tool returns the same paper schema (`title`, `authors`, `year`, `venue`, `abstract`, `doi`, `pdf_url`, `num_citations`, `link`, …), so results merge cleanly across sources.
- **No keys required.** Works out of the box; a free Semantic Scholar key is optional for higher rate limits.
- **Lightweight.** Pure Python, only `requests` + `beautifulsoup4` + `mcp`.

## Requirements

- Python 3.9 or newer
- Claude Code, Claude Desktop, Cursor, Windsurf, or any other MCP client

## Getting started

Install the server:

```bash
pip install git+https://github.com/monk1337/resp_mcp
```

This installs a `resp-mcp` command. Standard MCP config works in most clients:

```json
{
  "mcpServers": {
    "resp": {
      "command": "resp-mcp"
    }
  }
}
```

### Claude Code

Add the server with one command:

```bash
claude mcp add resp -- resp-mcp
```

Or, without installing, run it as a module:

```bash
claude mcp add resp -- python -m respmcp.server
```

Then verify it's connected:

```bash
claude mcp list
```

### Claude Desktop

Add this to your `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "resp": {
      "command": "resp-mcp",
      "env": {
        "SEMANTIC_SCHOLAR_API_KEY": "",
        "RESP_CONTACT_EMAIL": "you@example.com"
      }
    }
  }
}
```

Restart the app and the Resp tools appear in the tool picker.

### Cursor / Windsurf / other clients

Use the same standard config block shown in [Getting started](#getting-started) — point the `command` at `resp-mcp` (or `python -m respmcp.server`).

## Configuration

The server is configured through environment variables:

| Variable | Description |
|---|---|
| `SEMANTIC_SCHOLAR_API_KEY` | Optional [Semantic Scholar API key](https://www.semanticscholar.org/product/api) to raise rate limits for the Semantic Scholar and citation tools. |
| `RESP_CONTACT_EMAIL` | Contact email sent to OpenAlex and Crossref for their higher-throughput "polite pool". |
| `RESP_CACHE_DIR` | Where the ACL Anthology index is cached. Defaults to `~/.cache/resp-mcp`. |
| `RESP_MCP_TRANSPORT` | `stdio` (default) or `http` for streamable HTTP transport. |

### HTTP transport

To run the server over HTTP instead of stdio:

```bash
RESP_MCP_TRANSPORT=http resp-mcp
```

Then point your MCP client at the HTTP endpoint:

```json
{
  "mcpServers": {
    "resp": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Tools

### Paper search

| Tool | Description |
|---|---|
| `search_arxiv` | Search arXiv by keyword. |
| `search_semantic_scholar` | Search Semantic Scholar, with optional year range. |
| `search_openreview` | Search OpenReview submissions (ICLR, NeurIPS tracks, …). |
| `search_openalex` | Search OpenAlex with year / host / open-access filters. |
| `search_dblp` | Search DBLP, with an optional venue filter. |
| `search_acl` | Search the ACL Anthology. |
| `search_acm` | Search ACM Digital Library papers. |
| `search_connected_papers` | Search the Connected Papers corpus. |

### Conference proceedings

| Tool | Description |
|---|---|
| `search_conference` | Search any known conference by name + year; auto-routes to the right source. |
| `list_conferences` | List all supported conferences and how each is fetched. |
| `search_neurips` | Search a NeurIPS proceedings year. |
| `search_ijcai` | Search an IJCAI proceedings year. |
| `search_cvf` | Search CVF proceedings (CVPR / ICCV / WACV) for a year. |
| `search_eccv` | Search ECCV proceedings. |
| `search_pmlr` | Search a PMLR volume (e.g. `v235` for ICML 2024). |
| `search_aaai` | Search AAAI proceedings. |

**Supported conferences** (`search_conference`): CVPR, ICCV, WACV, ECCV, ICML, AISTATS, UAI, COLT, ACML, CoLLAs, ACL, EMNLP, EACL, NAACL, CoNLL, COLING, LREC, TACL, Findings, IJCAI, NeurIPS, AAAI, ICPR, KDD, WWW, SIGIR, ICDM.

### Citation graph

| Tool | Description |
|---|---|
| `get_citations` | Papers that cite a given paper (by S2 id, DOI, or `arXiv:<id>`). |
| `get_references` | Papers referenced by a given paper. |
| `get_related_papers` | Related papers for a title, query, or paper id. |

### Aggregate

| Tool | Description |
|---|---|
| `search_all` | Search several sources at once and merge / de-duplicate the results. |

## Example prompts

Once connected, you can ask your agent things like:

- "Search arXiv for recent papers on mixture-of-experts routing."
- "Find EMNLP 2023 papers about retrieval-augmented generation."
- "Get the papers that cite `arXiv:1706.03762`."
- "Find work related to 'Attention Is All You Need'."
- "Search CVPR 2024 and ECCV 2024 for gaussian splatting papers."

## Programmatic usage

The same capabilities are available as a Python library:

```python
from respmcp import Resp

resp = Resp()  # optional: Resp(semantic_scholar_api_key="...")

papers  = resp.arxiv("multi-label text classification", max_results=10)
citing  = resp.citations("arXiv:1706.03762", max_results=20)
related = resp.related_papers("attention is all you need")
icml    = resp.conference("ICML", "diffusion models", year=2024)

for p in papers:
    print(p.year, p.title, p.link)
```

## Development

```bash
git clone https://github.com/monk1337/resp_mcp
cd resp_mcp
pip install -e ".[dev]"
pytest -q            # live integration tests (network required)
```

## License

MIT
