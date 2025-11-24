# PaperSearcher MCP

A Model Context Protocol (MCP) server for searching and downloading academic papers from DBLP. This MCP server can be used by any LLM that supports the MCP protocol (Claude, GPT, etc.) to help researchers find and download academic papers.

## Features

- **scrape_dblp_conference**: Scrape papers from DBLP conference pages and export to markdown (with optional author information)
- **download_paper**: Download paper PDFs using DOI (supports IEEE and ACM)

## Installation

### Quick Install (Recommended)

Install directly from GitHub using uvx:

```bash
uvx --from git+https://github.com/Xyfuture/paper-searcher-mcp paper-searcher-mcp
```

### Development Install

Clone and install locally:

```bash
git clone https://github.com/Xyfuture/paper-searcher-mcp.git
cd paper-searcher-mcp
uv sync
```

### Browser Installation (for ACM downloads)

ACM paper downloads require a headless browser to bypass Cloudflare protection. Install Chromium:

```bash
uv run playwright install chromium
```

**Note:** This is automatically handled when using uvx, but required for local development.

### Updating

To update to the latest version, simply reinstall using uvx:

```bash
uvx --from git+https://github.com/Xyfuture/paper-searcher-mcp paper-searcher-mcp
```

uvx will automatically fetch and use the latest version from GitHub.

## Usage

### As MCP Server

This MCP server can be integrated with any LLM client that supports the Model Context Protocol.

#### For Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

**Option 1: Using uvx (Recommended - Auto-updates)**
```json
{
  "mcpServers": {
    "paper-searcher": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Xyfuture/paper-searcher-mcp", "paper-searcher-mcp"]
    }
  }
}
```

**Option 2: Using local installation**
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

**Using uvx:**
```bash
uvx --from git+https://github.com/Xyfuture/paper-searcher-mcp paper-searcher-mcp
```

**Using local installation:**
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
- **IEEE**: Uses IEEE Xplore stampPDF API (works without authentication)
- **ACM**: Uses headless browser to bypass Cloudflare protection (requires institutional access or subscription for most papers)
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

### ACM Download Limitations

ACM papers typically require institutional access or a personal subscription. The tool uses a headless browser to bypass Cloudflare protection, but cannot bypass access restrictions. If you encounter a 403 error:

1. **Use institutional network**: Access from your university/research institution network
2. **Check alternative sources**: Many papers are available on arXiv or authors' personal websites
3. **Manual download**: Visit the paper page directly through your institution's proxy

The headless browser approach will work successfully if you have proper access credentials through your network.

## How Updates Work

### For uvx Users (Recommended)

When using uvx with the GitHub URL, updates are handled automatically:

- **First run**: uvx downloads and caches the latest version from GitHub
- **Subsequent runs**: uvx checks for updates and uses the cached version if current
- **Manual update**: Simply restart your MCP client (e.g., Claude Desktop) - uvx will fetch the latest version on next launch
- **Force update**: Run the uvx command again manually to force a fresh download

**No manual update steps needed!** Just restart your LLM client to get the latest features.

### For Local Installation Users

If you cloned the repository locally, update with:

```bash
cd /path/to/paper-searcher-mcp
git pull
uv sync
```

Then restart your MCP client to use the updated version.
