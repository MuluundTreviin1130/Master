from __future__ import annotations

import csv
import multiprocessing as mp
import re
from pathlib import Path

from verify_T8_software_cites import CITE_TO_PDF, FULLTEXTS, PACKAGES


OUT = Path(__file__).with_name("software_mention_snippets.csv")
LANDSCAPE = Path(__file__).with_name("software_landscape.csv")
MAX_PAGES = 20
PDF_TIMEOUT_S = 8


def clean_snippet(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def first_snippet(text: str, patterns: list[str], window: int = 180) -> tuple[str, str] | None:
    for pattern in patterns:
        compiled = re.compile(pattern, re.IGNORECASE)
        match = compiled.search(text)
        if not match:
            continue
        start = max(match.start() - window, 0)
        end = min(match.end() + window, len(text))
        return pattern, clean_snippet(text[start:end])
    return None


def extract_text_capped(pdf: Path) -> str:
    if not pdf.exists():
        return ""


def extract_worker(path: str, queue: mp.Queue) -> None:
    queue.put(extract_text_capped(Path(path)))


def extract_with_timeout(pdf: Path) -> str:
    queue: mp.Queue = mp.Queue()
    process = mp.Process(target=extract_worker, args=(str(pdf), queue))
    process.start()
    process.join(PDF_TIMEOUT_S)
    if process.is_alive():
        process.terminate()
        process.join()
        return ""
    if queue.empty():
        return ""
    return queue.get()
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf))
        texts = []
        for page in reader.pages[:MAX_PAGES]:
            texts.append(page.extract_text() or "")
        return "\n".join(texts)
    except Exception:
        return ""


def confirmed_pairs() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    with LANDSCAPE.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("confidence") != "high":
                continue
            package = row["package"]
            for cite_key in (row.get("sources") or "").split(";"):
                cite_key = cite_key.strip()
                if cite_key:
                    pairs.add((package, cite_key))
    return pairs


def main() -> None:
    rows: list[dict[str, str]] = []
    pairs = confirmed_pairs()
    packages = {package: patterns for package, patterns in PACKAGES}
    text_cache: dict[str, str] = {}
    needed_cites = {cite for _package, cite in pairs}
    for cite_key, filename in CITE_TO_PDF.items():
        if cite_key not in needed_cites or filename is None:
            continue
        text_cache[cite_key] = extract_with_timeout(FULLTEXTS / filename)

    for package, cite_key in sorted(pairs):
        patterns = packages.get(package)
        if not patterns:
            continue
        text = text_cache.get(cite_key, "")
        if not text:
            continue
        hit = first_snippet(text, patterns)
        if hit is None:
            continue
        pattern, snippet = hit
        rows.append(
            {
                "package": package,
                "cite_key": cite_key,
                "matched_pattern": pattern,
                "snippet": snippet,
            }
        )

    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["package", "cite_key", "matched_pattern", "snippet"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT}")
    print(f"rows={len(rows)}")


if __name__ == "__main__":
    main()
