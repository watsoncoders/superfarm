#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, csv, time, re, random
from pathlib import Path
import requests
from lxml import html
import importlib

def get_random_headers():
    return {
        "User-Agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/89.0.4389.82 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/88.0.4324.96 Safari/537.36",
        ])
    }

XPATHS = {
    "breadcrumb": '//*[@id="breadcrumb"]',
    "brand":      '//*[@id="product-header"]/div[2]/div[1]/div[1]/div/a/span',
    "title":      '//*[@id="product-header"]/div[2]/div[1]/div[1]/div/h1',
    "subtitle":   '//*[@id="product-header"]/div[2]/div[1]/div[1]/div/span/div/div[2]/text()',
    "desc_p1":    '//*[@id="product-info"]/div/div[1]/p[1]',
    "desc_p2":    '//*[@id="product-info"]/div/div[1]/p[2]',
    "compare_price": '//*[@id="product-info"]/div/div[2]/span[4]',
    "video_embed":   '//*[@id="player"]',
    "img1": '//*[@id="preview"]/div[1]/div[1]/div[1]/img',
    "price_html": 'css:#product-header > div.product-details > div.details-wrap > div.row > div > span > div',
}

def extract_node(tree, xpath: str, field_name: str = "") -> str:
    try:
        if xpath.startswith('css:'):
            sel = xpath[4:]
            nodes = tree.cssselect(sel)
        else:
            nodes = tree.xpath(xpath)
    except Exception:
        return ""
    if not nodes:
        return ""
    node = nodes[0]
    if field_name == "price_html":
        return html.tostring(node, encoding="unicode", with_tail=False).strip()
    if isinstance(node, str):
        return node.strip()
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
        res = requests.get(url, headers=get_random_headers(), timeout=20)
        res.raise_for_status()
        res.encoding = res.apparent_encoding or res.encoding
    except Exception as e:
        print(f"שגיאה בטעינת {url}: {e}")
        return None
    tree = html.fromstring(res.text)
    data = {"url": url, "product_url": resolve_product_url(tree, url)}
    for key, xp in XPATHS.items():
        data[key] = extract_node(tree, xp, key)
    return data

def main(urls_file: str, out_csv: str):
    urls = [u.strip() for u in Path(urls_file).read_text(encoding="utf-8-sig").splitlines() if u.strip()]
    if not urls:
        print("לא נמצאו כתובות.")
        return

    fieldnames = ["url", "product_url"] + list(XPATHS.keys())
    out_path = Path(out_csv)
    need_header = not out_path.exists() or out_path.stat().st_size == 0

    with open(out_csv, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if need_header:
            writer.writeheader()

        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] טוען {url}")
            row = scrape_url(url)
            if row:
                writer.writerow(row)
                f.flush()
                print("  ✔ נשמר")
            else:
                print("  ✖ נכשל")
            time.sleep(random.uniform(2, 5))  # מניעת חסימות

    # המרה ל-Excel
    print("ממיר CSV לקובץ Excel …")
    pd = importlib.import_module("pandas")
    df = pd.read_csv(out_csv, encoding="utf-8-sig")
    xlsx_path = out_path.with_suffix(".xlsx")
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    print(f"הסתיים! נשמר אל {xlsx_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("שימוש: python xpath_scraper.py urls.txt results.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
