# PaperSearcher MCP

MCP server for searching and downloading academic papers from DBLP.

## Features

- **scrape_dblp_conference**: Scrape papers from DBLP conference pages and export to markdown
- **download_paper**: Download paper PDFs using DOI

## Installation

```bash
uv sync
```

## Usage

### As MCP Server

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "paper-searcher": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "main.py"],
      "cwd": "/Users/xyw/code/PaperMachine/paper-searcher-mcp"
    }
  }
}
```

### Direct Usage

```python
from main import scrape_dblp_conference, download_paper

# Scrape conference papers
scrape_dblp_conference("https://dblp.org/db/conf/dac/dac2025.html", "dac2025.md")

# Download paper by DOI
download_paper("10.1145/1234567.1234568", "downloads")
```

## Tools

### scrape_dblp_conference(url, output_file="papers.md")
Scrapes all papers from a DBLP conference page and saves to markdown.

**Parameters:**
- `url`: DBLP conference URL
- `output_file`: Output markdown file path

**Returns:** Status message with paper count

### download_paper(doi, output_dir="downloads")
Downloads a paper PDF from its DOI.

**Parameters:**
- `doi`: Paper DOI (with or without https://doi.org/ prefix)
- `output_dir`: Directory to save PDF

**Returns:** Status message with file path or error
