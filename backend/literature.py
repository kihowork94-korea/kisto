"""실제 논문 검색 — 연구 코치가 기억에 의존하지 않고 진짜 문헌을 근거로 말하게 한다.

OpenAlex(전 분야, 키 불필요)를 먼저 쓰고, 실패하면 PubMed(생의학)로 대체한다.
검색이 실패해도 대화는 계속되어야 하므로 예외를 밖으로 내보내지 않고 빈 목록을 돌려준다.
"""

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

TIMEOUT_SEC = 12
ABSTRACT_CHARS = 700
_HEADERS = {"User-Agent": "KISTO-research-companion/0.1"}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as res:
        return res.read()


def _openalex(query: str, n: int) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "search": query,
            "per_page": n * 2,
            "select": "title,publication_year,cited_by_count,doi,authorships,"
            "primary_location,abstract_inverted_index",
        }
    )
    data = json.loads(_get(f"https://api.openalex.org/works?{params}"))
    papers = []
    for w in data.get("results", []):
        inverted = w.get("abstract_inverted_index") or {}
        # OpenAlex는 초록을 {단어: [위치...]} 형태로 준다 — 위치 순서대로 다시 이어 붙인다.
        words = sorted((pos, word) for word, positions in inverted.items() for pos in positions)
        abstract = " ".join(word for _, word in words)
        source = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
        papers.append(
            {
                "title": w.get("title") or "(제목 없음)",
                "year": w.get("publication_year"),
                "venue": source,
                "authors": [
                    a["author"]["display_name"] for a in (w.get("authorships") or [])[:3]
                ],
                "doi": w.get("doi"),
                "cited_by": w.get("cited_by_count"),
                "abstract": abstract[:ABSTRACT_CHARS],
            }
        )
    # 초록이 있는 논문을 우선한다 — 연구 코치와 검증 에이전트가 내용을 확인할 수 있어야 한다.
    papers.sort(key=lambda p: not p["abstract"])
    return papers[:n]


def _pubmed(query: str, n: int) -> list[dict]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    term = urllib.parse.quote(query)
    ids = json.loads(_get(f"{base}/esearch.fcgi?db=pubmed&retmode=json&retmax={n}&term={term}"))
    idlist = ids["esearchresult"]["idlist"]
    if not idlist:
        return []
    root = ET.fromstring(_get(f"{base}/efetch.fcgi?db=pubmed&retmode=xml&id={','.join(idlist)}"))
    papers = []
    for art in root.iter("PubmedArticle"):
        title = "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else ""
        abstract = " ".join("".join(t.itertext()) for t in art.iter("AbstractText"))
        year = art.findtext(".//PubDate/Year") or art.findtext(".//PubDate/MedlineDate", "")[:4]
        doi = next(
            (i.text for i in art.iter("ArticleId") if i.get("IdType") == "doi"), None
        )
        pmid = art.findtext(".//PMID")
        authors = [
            f"{a.findtext('LastName', '')} {a.findtext('Initials', '')}".strip()
            for a in art.iter("Author")
        ][:3]
        papers.append(
            {
                "title": title or "(제목 없음)",
                "year": int(year) if year and year.isdigit() else None,
                "venue": art.findtext(".//Journal/Title"),
                "authors": authors,
                "doi": f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "cited_by": None,
                "abstract": abstract[:ABSTRACT_CHARS],
            }
        )
    return papers


def search_papers(query: str, n: int = 6) -> tuple[list[dict], str]:
    """(논문 목록, 출처 이름). 둘 다 실패하면 ([], "").

    생의학 주제는 PubMed가 훨씬 정확하고(신생아 rPPG 검색에서 OpenAlex는 일반 원격
    모니터링 논문이 섞였다), 그 밖의 분야는 PubMed 결과가 없으니 OpenAlex가 채운다.
    """
    merged, used, seen = [], [], set()
    for name, fn in (("PubMed", _pubmed), ("OpenAlex", _openalex)):
        try:
            found = fn(query, n)
        except Exception:
            continue
        added = 0
        for p in found:
            key = (p.get("doi") or p["title"]).lower()
            if key not in seen and len(merged) < n:
                seen.add(key)
                merged.append(p)
                added += 1
        if added:
            used.append(name)
    return merged, "·".join(used)


def format_for_prompt(papers: list[dict], start: int = 1) -> str:
    """모델에게 줄 번호 매긴 논문 목록. 인용은 이 번호로만 하게 한다."""
    lines = []
    for i, p in enumerate(papers, start):
        authors = ", ".join(p["authors"]) + (" 외" if len(p["authors"]) == 3 else "")
        lines.append(
            f"[{i}] {p['title']} ({p['year']}, {p['venue'] or '출처 미상'}; {authors})\n"
            f"    초록: {p['abstract'] or '(초록 없음)'}"
        )
    return "\n".join(lines)


def format_reference_list(papers: list[dict], start: int = 1) -> str:
    """사용자에게 보여줄 참고문헌 목록 (모델이 아니라 코드가 만든다 — 인용 조작 방지)."""
    lines = []
    for i, p in enumerate(papers, start):
        authors = ", ".join(p["authors"]) + (" 외" if len(p["authors"]) == 3 else "")
        link = f" {p['doi']}" if p.get("doi") else ""
        lines.append(f"[{i}] {authors} ({p['year']}). {p['title']}. *{p['venue'] or ''}*.{link}")
    return "\n".join(lines)
