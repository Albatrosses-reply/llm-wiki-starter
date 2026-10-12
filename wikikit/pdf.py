"""PDF 텍스트. 모델에게는 앞쪽(초록·서론)과 결론 쪽만 준다. 쪽 번호는 PDF 쪽 순번(저널 쪽 번호 아님)."""
from __future__ import annotations

import re
from pathlib import Path

LIMIT = re.compile(r"^\s*(\d+(\.\d+)*\.?|[IVX]+\.?)?\s*(Limitations?( and Future (Research|Work|Directions))?|연구의 한계|한계와 향후 연구)\s*$", re.I | re.M)
CONCL = re.compile(r"^\s*(\d+\.?|[IVX]+\.?)?\s*(Conclusions?|Concluding Remarks|Discussion and Conclusions?|Summary and Conclusions?|결론|맺음말)\b",
                   re.I | re.M)


def pages(path: Path) -> list[str]:
    import pymupdf
    with pymupdf.open(str(path)) as doc:
        return [pg.get_text("text") for pg in doc]


def pick(texts: list[str], head: int = 4, tail: int = 2, max_chars: int = 45_000) -> list[int]:
    """읽을 쪽 번호(1부터): 앞 head쪽 + 결론 절이 시작하는 쪽부터 tail쪽. 결론을 못 찾으면 참고문헌 앞 두 쪽."""
    n = len(texts)
    chosen = list(range(1, min(head, n) + 1))
    start = None
    for i in range(n - 1, head - 1, -1):
        if CONCL.search(texts[i]):
            start = i + 1
            break
    if start is None:
        ref = next((i + 1 for i in range(n - 1, head - 1, -1) if re.search(r"^\s*(References|Bibliography|참고문헌)\s*$", texts[i], re.M)), None)
        start = max(head + 1, (ref or n + 1) - tail)
    chosen += [p for p in range(start, min(start + tail, n + 1)) if p not in chosen]
    lim = next((i + 1 for i in range(n - 1, head - 1, -1) if LIMIT.search(texts[i])), None)   # 한계 절이 따로 있으면 그 쪽도
    if lim and lim not in chosen:
        chosen.append(lim)
    chosen.sort()
    out, total = [], 0
    for p in chosen:
        total += len(texts[p - 1])
        if total > max_chars and out:
            break
        out.append(p)
    return out


def excerpt(texts: list[str], chosen: list[int], per_page: int = 9000) -> str:
    return "\n\n".join(f"[PDF p.{p}]\n{texts[p - 1][:per_page].strip()}" for p in chosen)
