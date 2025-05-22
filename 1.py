#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""xpath_scraper.py  (v5 – CSV live write **and** XLSX export)
• Writes each row immediately to results.csv (UTF‑8‑SIG) to avoid data loss
• After scraping finishes, converts the CSV to results.xlsx (UTF‑8) using pandas

Usage:
    python xpath_scraper.py urls.txt results.csv
Requires:
    pip install requests lxml pandas openpyxl
"""

import sys, csv, time, re
from pathlib import Path
import requests
from lxml import html

# Optional: only import pandas at the end to speed initial runtime
import importlib

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; XpathScraper/5.0; +https://example.com)"
}

XPATHS = {
    "breadcrumb": '//*[@id="breadcrumb"]',
    "brand":      '//*[@id="product-header"]/div[2]/div[1]/div[1]/div/a/span',
    "title":      '//*[@id="product-header"]/div[2]/div[1]/div[1]/div/h1',
    "subtitle":   '//*[@id="product-header"]/div[2]/div[1]/div[1]/div/span/div/div[2]/text()',
    "desc_p1":    '//*[@id="product-info"]/div/div[1]/p[1]',
    "desc_p2":    '//*[@id="product-info"]/div/div[1]/p[2]',
    "price":      '//*[@id="product-info"]/div/div[2]/span[1]/text()[1]',
    "compare_price": '//*[@id="product-info"]/div/div[2]/span[4]',
    "video_embed":   '//*[@id="player"]',
    "img1": '//*[@id="preview"]/div[1]/div[1]/div[1]/img',
    "img2": '//*[@id="preview"]/div[2]/div/div[2]',
    "img3": '//*[@id="preview"]/div[2]/div/div[3]',
    "img4": '//*[@id="preview"]/div[2]/div/div[4]',
    "img5": '//*[@id="preview"]/div[2]/div/div[5]',
}

def extract_node(tree, xpath: str) -> str:
    try:
        nodes = tree.xpath(xpath)
    except Exception:
        return ""
    if not nodes:
        return ""
    node = nodes[0]
    if isinstance(node, str):
        return node.strip()
    tag = (node.tag or "").lower()
    if tag == "img" and node.get("src"):
        return node.get("src").strip()
    if node.get("src"):
        return node.get("src").strip()
    style = node.get("style", "")
    m = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
    if m:
        return m.group(1).strip()
    return node.text_content().strip()

def resolve_product_url(tree, original_url: str) -> str:
    for xp in ('//link[@rel="canonical"]/@href', '//meta[@property="og:url"]/@content'):
        res = tree.xpath(xp)
        if res and isinstance(res[0], str) and res[0].strip():
            return res[0].strip()
    return original_url

def scrape_url(url: str) -> dict | None:
    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        res.raise_for_status()
        res.encoding = res.apparent_encoding or res.encoding
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None
    tree = html.fromstring(res.text)
    data = {"url": url, "product_url": resolve_product_url(tree, url)}
    for key, xp in XPATHS.items():
        data[key] = extract_node(tree, xp)
    return data

def main(urls_file: str, out_csv: str):
    urls = [u.strip() for u in Path(urls_file).read_text(encoding="utf-8-sig").splitlines() if u.strip()]
    if not urls:
        print("No URLs to scrape.")
        return

    fieldnames = ["url", "product_url"] + list(XPATHS.keys())
    out_path = Path(out_csv)
    need_header = not out_path.exists() or out_path.stat().st_size == 0

    with open(out_csv, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if need_header:
            writer.writeheader()

        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] Scraping {url}")
            row = scrape_url(url)
            if row:
                writer.writerow(row)
                f.flush()
                print("  ✔ saved")
            else:
                print("  ✖ failed")
            time.sleep(1)

    # Convert CSV to XLSX using pandas
    print("Converting CSV → XLSX …")
    pd = importlib.import_module("pandas")
    df = pd.read_csv(out_csv, encoding="utf-8-sig")
    xlsx_path = out_path.with_suffix(".xlsx")
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    print(f"Done! Excel saved to {xlsx_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python xpath_scraper.py urls.txt results.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
