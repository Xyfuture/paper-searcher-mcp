import requests
from selectolax.parser import HTMLParser
from pathlib import Path
import re
import time
import os
from fastmcp import FastMCP
from playwright.sync_api import sync_playwright

mcp = FastMCP("PaperSearcher")

# Disable proxy
for var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
    os.environ.pop(var, None)

session = requests.Session()
session.trust_env = False
session.proxies = {}

def download_acm_paper_with_browser(doi: str, output_dir: str) -> str:
    """Download ACM paper using headless browser to bypass Cloudflare protection

    Note: Most ACM papers require institutional access or subscription.
    This function will work if you have proper access credentials.
    """
    try:
        with sync_playwright() as p:
            # Launch browser in headless mode without proxy
            browser = p.chromium.launch(
                headless=True,
                proxy=None  # Explicitly disable proxy
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                proxy=None  # Explicitly disable proxy for context
            )
            page = context.new_page()

            # Navigate to ACM paper page first to establish session
            page_url = f"https://dl.acm.org/doi/{doi}"
            page.goto(page_url, wait_until='networkidle', timeout=30000)

            # Wait for page to load and Cloudflare to pass
            page.wait_for_timeout(2000)

            # Try to download PDF with the correct download parameter
            pdf_url = f"https://dl.acm.org/doi/pdf/{doi}?download=true"

            # Navigate to PDF URL
            response = page.goto(pdf_url, wait_until='commit', timeout=30000)

            # Check if we got a PDF
            content_type = response.headers.get('content-type', '')
            status = response.status

            if 'pdf' in content_type.lower() and status == 200:
                # Get the PDF content
                pdf_content = response.body()

                # Save to file
                Path(output_dir).mkdir(exist_ok=True)
                safe_doi = re.sub(r'[^\w\-_.]', '_', doi)
                filename = f"{output_dir}/{safe_doi}.pdf"
                Path(filename).write_bytes(pdf_content)

                browser.close()
                return f"Downloaded to {filename}"
            else:
                browser.close()
                if status == 403:
                    return f"Access denied (403). This paper requires institutional access or ACM subscription.\n\nOptions:\n1. Access via your university/institution network\n2. Check if paper is available on arXiv or author's website\n3. Manual download: {page_url}"
                else:
                    return f"Download failed (Status: {status}, Content-Type: {content_type}).\nTry manually: {page_url}"

    except Exception as e:
        return f"Browser download failed: {e}\nTry manually: https://dl.acm.org/doi/{doi}"

@mcp.tool()
def scrape_dblp_conference(url: str, output_file: str = "papers.md", include_authors: bool = False) -> str:
    """Scrape papers from a DBLP conference page and save to markdown file

    Args:
        url: DBLP conference page URL
        output_file: Output markdown file path
        include_authors: Whether to include author information (default: False)
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        return f"Error fetching URL: {e}"

    tree = HTMLParser(response.text)
    papers = []

    for item in tree.css("li.entry.inproceedings"):
        title_node = item.css_first("span.title")
        title = title_node.text(strip=True) if title_node else "N/A"

        authors = [author.text(strip=True) for author in item.css("span[itemprop='author'] span[itemprop='name']")]

        doi_node = item.css_first("a[itemprop='url']")
        doi_url = doi_node.attributes.get('href', 'N/A') if doi_node else 'N/A'

        papers.append({"title": title, "authors": authors, "doi_url": doi_url})

    # Write to markdown
    md_content = f"# Conference Papers\n\nSource: {url}\n\n"
    for i, paper in enumerate(papers, 1):
        md_content += f"## {i}. {paper['title']}\n\n"
        if include_authors:
            md_content += f"**Authors:** {', '.join(paper['authors'])}\n\n"
        md_content += f"**DOI:** {paper['doi_url']}\n\n"
        md_content += "---\n\n"

    Path(output_file).write_text(md_content, encoding='utf-8')
    return f"Scraped {len(papers)} papers to {output_file}"

@mcp.tool()
def download_paper(doi: str, output_dir: str = "downloads") -> str:
    """Download a paper PDF from its DOI"""
    doi = doi.replace('https://doi.org/', '')

    # Resolve DOI
    try:
        response = session.head(f"https://doi.org/{doi}", allow_redirects=True, timeout=5)
        page_url = response.url
    except Exception as e:
        return f"DOI resolution failed: {e}"

    # Find PDF URLs
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        response = session.get(page_url, headers=headers, timeout=10)
        tree = HTMLParser(response.text)

        pdf_urls = []

        # IEEE specific
        if 'ieeexplore.ieee.org' in page_url:
            doc_id = re.search(r'document/(\d+)', page_url)
            if doc_id:
                pdf_urls.append(f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={doc_id.group(1)}")

        # ACM specific - use headless browser to bypass Cloudflare
        elif 'dl.acm.org' in page_url:
            return download_acm_paper_with_browser(doi, output_dir)

        # Generic PDF links
        for link in tree.css('a[href*=".pdf"]'):
            href = link.attributes.get('href', '')
            if href:
                pdf_urls.append(href if href.startswith('http') else f"{page_url.rsplit('/', 1)[0]}/{href}")

        if not pdf_urls:
            return f"No PDF found for {page_url}"

    except Exception as e:
        return f"Error finding PDF: {e}"

    # Download PDF
    Path(output_dir).mkdir(exist_ok=True)
    safe_doi = re.sub(r'[^\w\-_.]', '_', doi)
    filename = f"{output_dir}/{safe_doi}.pdf"

    for url in pdf_urls:
        try:
            response = session.get(url, headers=headers, timeout=15)
            if 'pdf' in response.headers.get('content-type', '').lower():
                Path(filename).write_bytes(response.content)
                return f"Downloaded to {filename}"
        except Exception:
            continue

    return f"Download failed. Try manually: {page_url}"

if __name__ == "__main__":
    mcp.run()
