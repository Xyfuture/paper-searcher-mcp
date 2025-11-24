# PaperSearcher MCP

A Model Context Protocol (MCP) server for searching and downloading academic papers from DBLP. This MCP server can be used by any LLM that supports the MCP protocol (Claude, GPT, etc.) to help researchers find and download academic papers.

## Features

- **scrape_dblp_conference**: Scrape papers from DBLP conference pages and export to markdown (with optional author information)
- **download_paper**: Download paper PDFs using DOI (supports IEEE and ACM)

## Installation

```bash
uv sync
```

## Usage

### As MCP Server

This MCP server can be integrated with any LLM client that supports the Model Context Protocol.

#### For Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "paper-searcher": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "main.py"],
      "cwd": "/path/to/paper-searcher-mcp"
    }
  }
}
```

#### For Other MCP Clients

Configure your MCP client to connect to this server using the command:
```bash
uv run fastmcp run main.py
```

### Development Mode

Run the MCP server in development mode:
```bash
uv run fastmcp dev main.py
```

## MCP Tools

### scrape_dblp_conference

Scrapes all papers from a DBLP conference page and saves to markdown.

**Parameters:**
- `url` (str): DBLP conference URL
- `output_file` (str, optional): Output markdown file path (default: "papers.md")
- `include_authors` (bool, optional): Whether to include author information (default: False)

**Returns:** Status message with paper count

**Example:**
```python
# Without authors (default)
scrape_dblp_conference("https://dblp.org/db/conf/dac/dac2025.html", "dac2025.md")

# With authors
scrape_dblp_conference("https://dblp.org/db/conf/dac/dac2025.html", "dac2025.md", include_authors=True)
```

### download_paper

Downloads a paper PDF from its DOI. Supports IEEE and ACM papers with direct download methods.

**Parameters:**
- `doi` (str): Paper DOI (with or without https://doi.org/ prefix)
- `output_dir` (str, optional): Directory to save PDF (default: "downloads")

**Supported Publishers:**
- **IEEE**: Uses IEEE Xplore stampPDF API
- **ACM**: Uses ACM Digital Library direct PDF download
- **Others**: Attempts to find PDF links from the publisher's page

**Returns:** Status message with file path or error

**Example:**
```python
# Download IEEE paper
download_paper("10.1109/DAC18074.2021.9586141", "downloads")

# Download ACM paper
download_paper("10.1145/3489517.3530525", "downloads")
```

## Notes

- All downloads are performed without proxy to ensure compatibility with academic publisher websites
- The server automatically handles different publisher-specific download methods
- Author information is optional in conference scraping to reduce output size when not needed
