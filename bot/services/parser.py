import asyncio
import os
import tempfile
import uuid

import httpx
from bs4 import BeautifulSoup

from bot.logger import get_logger

logger = get_logger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

PDF_FALLBACK_SIZE_LIMIT = 20 * 1024 * 1024  # 20MB


async def fetch_url_text(url: str) -> str:
    """Download a web page and extract its main textual content."""
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30.0
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    article = soup.find("article")
    container = article if article is not None else soup.body or soup

    paragraphs = [p.get_text(separator=" ", strip=True) for p in container.find_all(["p", "h1", "h2", "h3", "li"])]
    text = "\n".join(p for p in paragraphs if p)

    if not text:
        text = container.get_text(separator="\n", strip=True)

    return text


def extract_pdf_text(path: str) -> str:
    """Fallback local extraction for PDFs over the Gemini inline size limit."""
    import pdfplumber

    chunks = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                chunks.append(page_text)
    return "\n".join(chunks)


def is_pdf_within_inline_limit(path: str) -> bool:
    return os.path.getsize(path) <= PDF_FALLBACK_SIZE_LIMIT


def temp_path(suffix: str) -> str:
    return os.path.join(tempfile.gettempdir(), f"ankibot_{uuid.uuid4().hex}{suffix}")


def cleanup(path: str | None) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            logger.warning("temp_file_cleanup_failed", path=path)


async def download_audio(url: str) -> str:
    """Download audio track from a YouTube/other URL via yt-dlp into /tmp as mp3."""
    import yt_dlp

    output_template = temp_path("")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{output_template}.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
    }

    def _download() -> str:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return f"{output_template}.mp3"

    return await asyncio.to_thread(_download)
