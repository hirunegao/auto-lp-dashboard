"""笹岡さんレポート（reports_tmp/*.txt）→ dashboard/data.js 変換。

使い方:
    python auto-lp/dashboard/build_data.py

将来DataForSEO/GSC同期が動いたら、このスクリプトをBigQuery読み出しに差し替える。
"""
import json
import re
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parent
PCTOWER = DASHBOARD_DIR.parents[1]
REPORTS = PCTOWER / "reports_tmp"

POS_RE = re.compile(r"(?:\d+→)?(\d+)（(\d{2}/\d{2})）")


def parse_pos(cell: str):
    """'24→24（06/28）' → (24, '06/28')。'-' は None。"""
    m = POS_RE.match(cell.strip())
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def is_pos_cell(line: str) -> bool:
    return line == "-" or bool(POS_RE.match(line))


def parse_comparison(path: Path, sellers: list[str]):
    """比較レポート（KW / 一致数 / セラー数分の順位 / 検索数 / 広告）をパース。"""
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()]
    n = len(sellers)
    out = []
    i = 0
    while i < len(lines) - (n + 3):
        kw = lines[i]
        if kw and re.fullmatch(r"[1-9]", lines[i + 1]):
            block = lines[i + 2 : i + 2 + n]
            vol_line = lines[i + 2 + n]
            ad_line = lines[i + 3 + n] if i + 3 + n < len(lines) else ""
            if all(is_pos_cell(b) for b in block) and re.fullmatch(r"[\d,]+", vol_line):
                positions = {}
                for seller, cell in zip(sellers, block):
                    p = parse_pos(cell)
                    if p:
                        positions[seller] = p[0]
                out.append(
                    {
                        "kw": kw,
                        "vol": int(vol_line.replace(",", "")),
                        "ad": float(ad_line) if re.fullmatch(r"[\d.]+", ad_line) else None,
                        "positions": positions,
                    }
                )
                i += n + 4
                continue
        i += 1
    return out


def parse_own(path: Path):
    """自社レポート（KW / 順位 / 検索数 / 広告 / 予想流入 / URL）をパース。"""
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()]
    out = []
    i = 0
    while i < len(lines) - 5:
        kw = lines[i]
        pos = parse_pos(lines[i + 1])
        if kw and pos and re.fullmatch(r"[\d,]+", lines[i + 2]):
            vol = int(lines[i + 2].replace(",", ""))
            ad = float(lines[i + 3]) if re.fullmatch(r"[\d.]+", lines[i + 3]) else None
            traffic = int(lines[i + 4].replace(",", "")) if re.fullmatch(r"[\d,]+", lines[i + 4]) else None
            url = lines[i + 5] if lines[i + 5].startswith("/") else None
            out.append(
                {"kw": kw, "vol": vol, "ad": ad, "pos": pos[0], "traffic": traffic, "url": url}
            )
            i += 6 if url else 5
            continue
        i += 1
    return out


def main():
    # report_1: hirunegao / cocosilk / koala / brain-sleep / nell / g-nap の6列比較
    six = parse_comparison(
        REPORTS / "report_1.txt",
        ["hirunegao", "cocosilk", "koala", "brainsleep", "nell", "gnap"],
    )
    # report_0: hirunegao / tential の2列比較
    two = parse_comparison(REPORTS / "report_0.txt", ["hirunegao", "tential"])
    own = parse_own(REPORTS / "report_2.txt")

    merged: dict[str, dict] = {}
    for row in six + two:
        e = merged.setdefault(
            row["kw"], {"kw": row["kw"], "vol": 0, "ad": None, "positions": {}}
        )
        e["vol"] = max(e["vol"], row["vol"])
        if row["ad"] is not None:
            e["ad"] = row["ad"]
        e["positions"].update(row["positions"])

    for row in own:
        e = merged.setdefault(
            row["kw"], {"kw": row["kw"], "vol": 0, "ad": None, "positions": {}}
        )
        e["vol"] = max(e["vol"], row["vol"])
        if row["ad"] is not None and e["ad"] is None:
            e["ad"] = row["ad"]
        e["positions"]["hirunegao"] = row["pos"]
        if row.get("url"):
            e["own_url"] = row["url"]
        if row.get("traffic") is not None:
            e["own_traffic"] = row["traffic"]

    keywords = sorted(merged.values(), key=lambda x: -x["vol"])

    meta = {
        "sellers": [
            {"id": "hirunegao", "name": "自社 (hirunegao)", "domain": "hirunegao.jp", "traffic": 1736, "kwCount": 544},
            {"id": "brainsleep", "name": "BrainSleep", "domain": "brain-sleep.com", "traffic": 181269, "kwCount": 20962},
            {"id": "nell", "name": "NELL", "domain": "nell.life", "traffic": 151479, "kwCount": 33780},
            {"id": "cocosilk", "name": "CocoSilk", "domain": "cocosilk.jp", "traffic": 55585, "kwCount": 2839},
            {"id": "koala", "name": "Koala", "domain": "jp.koala.com", "traffic": 47611, "kwCount": 4045},
            {"id": "gnap", "name": "G-nap", "domain": "g-nap.com", "traffic": 17702, "kwCount": 2411},
            {"id": "tential", "name": "TENTIAL", "domain": "tential.jp", "traffic": 528729, "kwCount": 29573},
        ],
        "source": "笹岡さん最終レポート3本（2026-07取得）",
        "generated": "build_data.py",
    }

    js = (
        "// 自動生成ファイル。編集しないこと。再生成: python auto-lp/dashboard/build_data.py\n"
        f"const META = {json.dumps(meta, ensure_ascii=False)};\n"
        f"const KEYWORDS = {json.dumps(keywords, ensure_ascii=False)};\n"
    )
    (DASHBOARD_DIR / "data.js").write_text(js, encoding="utf-8")
    print(f"keywords: {len(keywords)}")
    for s in meta["sellers"]:
        cnt = sum(1 for k in keywords if s["id"] in k["positions"])
        print(f"  {s['id']}: {cnt} KWs in data")


if __name__ == "__main__":
    main()
