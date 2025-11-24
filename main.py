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

def download_ieee_paper(doi: str, page_url: str, output_dir: str, custom_filename: str | None = None) -> str:
    """Download IEEE paper using their PDF API

    Args:
        doi: Paper DOI
        page_url: IEEE paper page URL
        output_dir: Directory to save the PDF
        custom_filename: Custom filename (without .pdf extension). If None, uses DOI as filename
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

            # Use custom filename or DOI as filename
            if custom_filename:
                filename = f"{output_dir}/{custom_filename}.pdf"
            else:
                safe_doi = re.sub(r'[^\w\-_.]', '_', doi)
                filename = f"{output_dir}/{safe_doi}.pdf"

            Path(filename).write_bytes(response.content)
            return f"Downloaded to {filename}"
        else:
            return f"Download failed. Try manually: {page_url}"

    except Exception as e:
        return f"IEEE download failed: {e}\nTry manually: {page_url}"

def download_acm_paper_with_browser(doi: str, output_dir: str, custom_filename: str | None = None) -> str:
    """Download ACM paper using browser's built-in PDF download functionality

    Opens the PDF URL and uses JavaScript to trigger download.

    Args:
        doi: Paper DOI
        output_dir: Directory to save the PDF
        custom_filename: Custom filename (without .pdf extension). If None, uses DOI as filename
    """
    try:
        with sync_playwright() as p:
            print('Launching browser to download ACM paper...')

            # Launch browser in headed mode
            browser = p.chromium.launch(
                headless=False,
                proxy=None
            )

            # Create context with realistic browser settings and download handling
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                accept_downloads=True,
                locale='en-US',
                timezone_id='America/New_York',
            )

            page = context.new_page()

            # Directly navigate to PDF URL
            pdf_url = f"https://dl.acm.org/doi/pdf/{doi}"
            print(f'Opening PDF URL directly: {pdf_url}')

            # Set up download handler
            download_promise = None

            def handle_download(download):
                nonlocal download_promise
                download_promise = download
                print(f'Download started: {download.suggested_filename}')

            page.on('download', handle_download)

            # Navigate to PDF URL
            try:
                print('Navigating to PDF URL...')
                page.goto(pdf_url, wait_until='domcontentloaded', timeout=60000)

                # Check page title for Cloudflare challenge
                title = page.title()
                print(f'Page title: {title}')

                # Check if we hit Cloudflare
                if 'just a moment' in title.lower() or '请稍候' in title:
                    print('Cloudflare challenge detected! Waiting for it to complete...')
                    print('If challenge requires manual interaction, please complete it in the browser window.')

                    # Wait for title to change
                    try:
                        page.wait_for_function(
                            "document.title !== '请稍候…' && document.title !== 'Just a moment...'",
                            timeout=60000
                        )
                        print('Cloudflare challenge passed!')
                    except Exception as e:
                        print(f'Cloudflare wait timeout: {e}')

                # Wait for PDF to fully load
                print('Waiting for PDF to fully load (10 seconds)...')
                page.wait_for_timeout(10000)

                # Trigger download using JavaScript
                print('Triggering download via JavaScript...')
                page.evaluate('''
                    () => {
                        const link = document.createElement('a');
                        link.href = window.location.href;
                        link.download = 'paper.pdf';
                        link.click();
                    }
                ''')
                page.wait_for_timeout(3000)

                # Wait for download to complete
                if download_promise:
                    print('Download detected, saving file...')

                    # Use custom filename or DOI as filename
                    if custom_filename:
                        filename = f"{custom_filename}.pdf"
                    else:
                        safe_doi = re.sub(r"[^\w\-_.]", "_", doi)
                        filename = f"{safe_doi}.pdf"

                    Path(output_dir).mkdir(exist_ok=True)
                    save_path = str(Path(output_dir) / filename)

                    download_promise.save_as(save_path)
                    print(f"Successfully saved to: {save_path}")

                    browser.close()
                    return f"Downloaded to {save_path}"
                else:
                    browser.close()
                    return f"Could not trigger download. Please try manually: {pdf_url}"

            except Exception as nav_error:
                print(f'Navigation error: {nav_error}')
                browser.close()
                return f"Navigation failed: {nav_error}\nTry manually: {pdf_url}"

    except Exception as e:
        return f"Browser download failed: {e}\nTry manually: https://dl.acm.org/doi/pdf/{doi}"

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
def download_paper(doi: str, output_dir: str = "downloads", custom_filename: str | None = None) -> str:
    """Download a paper PDF from its DOI

    Supports IEEE and ACM papers with specialized download methods.
    ACM papers use browser to bypass Cloudflare protection.

    Args:
        doi: Paper DOI (e.g., "10.1145/3695053.3731073" or full URL)
        output_dir: Directory to save the PDF (default: "downloads")
        custom_filename: Custom filename without .pdf extension. If None, uses DOI as filename
    """
    doi = doi.replace('https://doi.org/', '')

    # Check if it's an ACM DOI pattern (10.1145/...)
    if doi.startswith('10.1145/'):
        return download_acm_paper_with_browser(doi, output_dir, custom_filename)

    # Resolve DOI to get the publisher's URL
    page_url = None
    try:
        response = session.head(f"https://doi.org/{doi}", allow_redirects=True, timeout=5)
        page_url = response.url
    except Exception as e:
        # If DOI resolution fails, try to infer from DOI pattern
        if doi.startswith('10.1145/'):
            return download_acm_paper_with_browser(doi, output_dir, custom_filename)
        return f"DOI resolution failed: {e}"
    # Check publisher and use specialized download methods
    if 'dl.acm.org' in page_url:
        return download_acm_paper_with_browser(doi, output_dir, custom_filename)
    elif 'ieeexplore.ieee.org' in page_url:
        return download_ieee_paper(doi, page_url, output_dir, custom_filename)

    # Generic download for other publishers
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        response = session.get(page_url, headers=headers, timeout=10)

        # Handle Cloudflare or other blocks - check if it might be ACM
        if response.status_code == 403 and 'acm.org' in page_url:
            return download_acm_paper_with_browser(doi, output_dir, custom_filename)

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

        # Use custom filename or DOI as filename
        if custom_filename:
            filename = f"{output_dir}/{custom_filename}.pdf"
        else:
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
