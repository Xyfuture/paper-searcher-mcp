import requests
from selectolax.parser import HTMLParser
from pathlib import Path
import re
import time
import os
from fastmcp import FastMCP
from playwright.async_api import async_playwright
import asyncio

mcp = FastMCP("PaperSearcher")

# Disable proxy
for var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
    os.environ.pop(var, None)

session = requests.Session()
session.trust_env = False
session.proxies = {}

def download_ieee_paper(doi: str, page_url: str, output_dir: str) -> str:
    """Download IEEE paper using their PDF API

    Args:
        doi: Paper DOI
        page_url: IEEE paper page URL
        output_dir: Directory to save the PDF
    """
    try:
        doc_id = re.search(r'document/(\d+)', page_url)
        if not doc_id:
            return f"Could not extract IEEE document ID from {page_url}"

        pdf_url = f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={doc_id.group(1)}"

        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        response = session.get(pdf_url, headers=headers, timeout=15)

        if 'pdf' in response.headers.get('content-type', '').lower():
            Path(output_dir).mkdir(exist_ok=True)
            safe_doi = re.sub(r'[^\w\-_.]', '_', doi)
            filename = f"{output_dir}/{safe_doi}.pdf"
            Path(filename).write_bytes(response.content)
            return f"Downloaded to {filename}"
        else:
            return f"Download failed. Try manually: {page_url}"

    except Exception as e:
        return f"IEEE download failed: {e}\nTry manually: {page_url}"

async def download_acm_paper_with_browser_async(doi: str, output_dir: str) -> str:
    """Download ACM paper using headless browser to bypass Cloudflare protection

    Note: Most ACM papers require institutional access or subscription.
    This function will work if you have proper access credentials.
    """
    try:
        async with async_playwright() as p:
            # Launch browser in headless mode without proxy
            browser = await p.chromium.launch(
                headless=True,
                proxy=None  # Explicitly disable proxy
            )
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                proxy=None  # Explicitly disable proxy for context
            )
            page = await context.new_page()

            # Navigate to ACM paper page first to establish session
            page_url = f"https://dl.acm.org/doi/{doi}"
            await page.goto(page_url, wait_until='networkidle', timeout=30000)

            # Wait for page to load and Cloudflare to pass
            await page.wait_for_timeout(2000)

            # Try to download PDF with the correct download parameter
            pdf_url = f"https://dl.acm.org/doi/pdf/{doi}?download=true"

            # Navigate to PDF URL
            response = await page.goto(pdf_url, wait_until='commit', timeout=30000)

            # Check if we got a PDF
            content_type = response.headers.get('content-type', '')
            status = response.status

            if 'pdf' in content_type.lower() and status == 200:
                # Get the PDF content
                pdf_content = await response.body()

                # Save to file
                Path(output_dir).mkdir(exist_ok=True)
                safe_doi = re.sub(r'[^\w\-_.]', '_', doi)
                filename = f"{output_dir}/{safe_doi}.pdf"
                Path(filename).write_bytes(pdf_content)

                await browser.close()
                return f"Downloaded to {filename}"
            else:
                await browser.close()
                if status == 403:
                    return f"Access denied (403). This paper requires institutional access or ACM subscription.\n\nOptions:\n1. Access via your university/institution network\n2. Check if paper is available on arXiv or author's website\n3. Manual download: {page_url}"
                else:
                    return f"Download failed (Status: {status}, Content-Type: {content_type}).\nTry manually: {page_url}"

    except Exception as e:
        return f"Browser download failed: {e}\nTry manually: https://dl.acm.org/doi/{doi}"

def download_acm_paper_with_browser(doi: str, output_dir: str) -> str:
    """Wrapper to run async download in sync context"""
    return asyncio.run(download_acm_paper_with_browser_async(doi, output_dir))

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
    """Download a paper PDF from its DOI

    Supports IEEE and ACM papers with specialized download methods.
    ACM papers use headless browser to bypass Cloudflare protection.
    """
    doi = doi.replace('https://doi.org/', '')

    # Check if it's an ACM DOI pattern (10.1145/...)
    if doi.startswith('10.1145/'):
        return download_acm_paper_with_browser(doi, output_dir)

    # Resolve DOI to get the publisher's URL
    page_url = None
    try:
        response = session.head(f"https://doi.org/{doi}", allow_redirects=True, timeout=5)
        page_url = response.url
    except Exception as e:
        # If DOI resolution fails, try to infer from DOI pattern
        if doi.startswith('10.1145/'):
            return download_acm_paper_with_browser(doi, output_dir)
        return f"DOI resolution failed: {e}"

    # Check publisher and use specialized download methods
    if 'dl.acm.org' in page_url:
        return download_acm_paper_with_browser(doi, output_dir)
    elif 'ieeexplore.ieee.org' in page_url:
        return download_ieee_paper(doi, page_url, output_dir)

    # Generic download for other publishers
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        response = session.get(page_url, headers=headers, timeout=10)

        # Handle Cloudflare or other blocks - check if it might be ACM
        if response.status_code == 403 and 'acm.org' in page_url:
            return download_acm_paper_with_browser(doi, output_dir)

        tree = HTMLParser(response.text)
        pdf_urls = []

        # Find generic PDF links
        for link in tree.css('a[href*=".pdf"]'):
            href = link.attributes.get('href', '')
            if href:
                pdf_urls.append(href if href.startswith('http') else f"{page_url.rsplit('/', 1)[0]}/{href}")

        if not pdf_urls:
            return f"No PDF found for {page_url}"

        # Try to download from found PDF URLs
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

    except Exception as e:
        # If we get an error and suspect it's ACM, try browser method
        if page_url and 'acm.org' in page_url:
            return download_acm_paper_with_browser(doi, output_dir)
        return f"Error finding PDF: {e}"

if __name__ == "__main__":
    mcp.run()
