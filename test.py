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
    """Download ACM paper using browser's built-in PDF download functionality

    Opens the PDF URL and uses Chromium's built-in PDF viewer download button.
    """
    try:
        async with async_playwright() as p:
            print('Launching browser to download ACM paper...')

            # Launch browser in headed mode
            browser = await p.chromium.launch(
                headless=False,
                proxy=None
            )

            # Create context with realistic browser settings and download handling
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                accept_downloads=True,
                locale='en-US',
                timezone_id='America/New_York',
            )

            page = await context.new_page()

            # Directly navigate to PDF URL
            pdf_url = f"https://dl.acm.org/doi/pdf/{doi}"
            print(f'Opening PDF URL directly: {pdf_url}')

            # Set up download handler
            download_promise = None

            async def handle_download(download):
                nonlocal download_promise
                download_promise = download
                print(f'Download started: {download.suggested_filename}')

            page.on('download', handle_download)

            # Navigate to PDF URL
            try:
                print('Navigating to PDF URL...')
                await page.goto(pdf_url, wait_until='domcontentloaded', timeout=60000)

                # Check page title for Cloudflare challenge
                title = await page.title()
                print(f'Page title: {title}')

                # Check if we hit Cloudflare
                if 'just a moment' in title.lower() or '请稍候' in title:
                    print('Cloudflare challenge detected! Waiting for it to complete...')
                    print('If challenge requires manual interaction, please complete it in the browser window.')

                    # Wait for title to change
                    try:
                        await page.wait_for_function(
                            "document.title !== '请稍候…' && document.title !== 'Just a moment...'",
                            timeout=60000
                        )
                        print('Cloudflare challenge passed!')
                    except Exception as e:
                        print(f'Cloudflare wait timeout: {e}')

                # Wait for PDF to fully load
                print('Waiting for PDF to fully load (10 seconds)...')
                await page.wait_for_timeout(10000)

                # Trigger download using JavaScript
                print('Triggering download via JavaScript...')
                await page.evaluate('''
                    () => {
                        const link = document.createElement('a');
                        link.href = window.location.href;
                        link.download = 'paper.pdf';
                        link.click();
                    }
                ''')
                await page.wait_for_timeout(3000)

                # Wait for download to complete
                if download_promise:
                    print('Download detected, saving file...')

                    safe_doi = re.sub(r"[^\w\-_.]", "_", doi)
                    filename = f"{safe_doi}.pdf"

                    Path(output_dir).mkdir(exist_ok=True)
                    save_path = str(Path(output_dir) / filename)

                    await download_promise.save_as(save_path)
                    print(f"Successfully saved to: {save_path}")

                    await browser.close()
                    return f"Downloaded to {save_path}"
                else:
                    await browser.close()
                    return f"Could not trigger download. Please try manually: {pdf_url}"

            except Exception as nav_error:
                print(f'Navigation error: {nav_error}')
                await browser.close()
                return f"Navigation failed: {nav_error}\nTry manually: {pdf_url}"

    except Exception as e:
        return f"Browser download failed: {e}\nTry manually: https://dl.acm.org/doi/pdf/{doi}"

def download_acm_paper_with_browser(doi: str, output_dir: str) -> str:
    """Wrapper to run async download in sync context"""
    return asyncio.run(download_acm_paper_with_browser_async(doi, output_dir))


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
    print('here')
    try:
        response = session.head(f"https://doi.org/{doi}", allow_redirects=True, timeout=5)
        page_url = response.url
        print(response)
    except Exception as e:
        # If DOI resolution fails, try to infer from DOI pattern
        if doi.startswith('10.1145/'):
            return download_acm_paper_with_browser(doi, output_dir)
        return f"DOI resolution failed: {e}"
    print(f'page_url,f{page_url}')
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

    print('start')
    s = download_paper('https://doi.org/10.1145/3695053.3731073','./')
    print(s)
    print('end')