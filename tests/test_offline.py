"""오프라인 테스트 (Zotero·Codex·네트워크 없이). 실행: python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="wikikit-test-")
os.environ["WIKI_HOME"] = TMP
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wikikit import briefing, collect, config, doctor, pages, pdf, zotero  # noqa: E402
from wikikit.util import fm_parse, quote_found  # noqa: E402

CFG = config._merge(config.DEFAULTS, {"me": {"topics": ["스테이블코인 런 위험", "플랫폼 추천 알고리즘"]}})
B = {"citekey": "MoehringEtAl2026", "zotero_key": "ABCD1234", "title": "Personalization and Content Quality", "authors": ["Moehring, Alex"],
     "year": 2026, "venue": "Management Science", "doi": "10.1287/mnsc.2024.06298", "abstract": "We study ranking.", "pdf_key": "PDF12345",
     "pdf_path": ""}
TEXTS = ["Abstract. Platforms rank content to maximize engagement.", "1 Introduction\nWe exploit a novel discontinuity in the ranking algorithm.",
         "Data", "Model", "Results", "6 Conclusion\nAlgorithmic interventions can balance engagement and quality.", "References\nA. B. (2020)"]
D = {"summary": "랭킹이 신뢰도에 주는 영향 — 회귀불연속으로 추정", "rq": ["랭킹의 효과는? (PDF p.2)"], "design": "실증 (PDF p.2)", "data": "Reddit (PDF p.9)",
     "method": "회귀불연속 (PDF p.2)", "findings": ["참여 극대화가 신뢰도 격차를 키운다 (PDF p.6)"], "mechanism": "자료에 없음", "limitations": [],
     "future": [], "contribution": "저자는 새 불연속을 쓴다(PDF p.2).", "caveats": ["한 커뮤니티 자료다(PDF p.1)."],
     "relations": [{"target": "topic-2", "why": "추천 알고리즘을 다룬다(PDF p.1)."}, {"target": "p-없는원고", "why": "x"}],
     "concepts": [{"slug": "Regression Discontinuity", "name": "회귀불연속", "kind": "method", "definition": "문턱 — 근처 비교"}],
     "quotes": [{"text": "We exploit a novel discontinuity", "page": 2}, {"text": "made up sentence not in pdf", "page": 2}],
     "tags": ["Ranking Algorithms", "rdd"], "read": "PDF p.1-4, 6"}


class PdfTests(unittest.TestCase):
    def test_pick_front_and_conclusion(self):
        self.assertEqual(pdf.pick(TEXTS, head=2, tail=2), [1, 2, 6, 7])
        self.assertIn("[PDF p.6]", pdf.excerpt(TEXTS, [6]))

    def test_pick_includes_limitations_page(self):
        texts = ["a", "b", "c", "d", "e", "7 Limitations\nOur sample", "f", "8 Conclusion\nx", "References"]
        self.assertEqual(pdf.pick(texts, head=2, tail=2), [1, 2, 6, 8, 9])

    def test_pick_without_conclusion_uses_pages_before_references(self):
        texts = ["a", "b", "c", "d", "e", "f", "References\nx"]
        self.assertEqual(pdf.pick(texts, head=2, tail=2), [1, 2, 5, 6])


class RenderTests(unittest.TestCase):
    def test_render_source(self):
        slugs = pages.upsert_concepts(D["concepts"], B["citekey"])
        self.assertEqual(slugs, ["regression-discontinuity"])
        self.assertTrue((config.CONCEPTS / "regression-discontinuity.md").exists())
        text, notes = pages.render_source(B, D, CFG, [1, 2, 6], TEXTS, set(), slugs)
        meta, body = fm_parse(text)
        self.assertEqual(meta["title"], B["title"])           # 서지는 Zotero 값
        self.assertNotIn("—", text)                           # em dash 정리
        self.assertIn("(PDF 쪽 확인 필요)", body)              # 읽지 않은 p.9
        self.assertIn('> "We exploit a novel discontinuity" (PDF p. 2)', body)
        self.assertNotIn("made up sentence", body)            # PDF에 없는 인용문 제거
        self.assertIn("PDF에서 확인 안 된 인용문 지움", notes)
        self.assertIn("- 내 연구 주제 2(플랫폼 추천 알고리즘):", body)
        self.assertNotIn("p-없는원고", body)                   # 없는 원고로는 연결하지 않음
        self.assertEqual(body.count("<!-- llm-draft"), 3)
        self.assertEqual(meta["tags"], ["ranking-algorithms", "rdd"])

    def test_keep_human_sections(self):
        new, _ = pages.render_source(B, D, CFG, [1, 2], TEXTS, set(), [])
        old = new.replace("<!-- llm-draft: 자동 초안", "<!-- x", 1)   # 첫 섹션(Contribution)을 사람이 고쳤다고 가정
        old = old.replace("저자는 새 불연속을 쓴다(PDF p.2).", "내가 쓴 기여 평가.")
        merged = pages.keep_human_sections(old, new)
        self.assertIn("내가 쓴 기여 평가.", merged)
        self.assertEqual(merged.count("<!-- llm-draft"), 2)

    def test_no_pdf(self):
        text, notes = pages.render_source(B, D, CFG, [], [], set(), [])
        self.assertIn("초록만(PDF 없음)", text)
        self.assertNotIn("(PDF p.", fm_parse(text)[1].split("## 🔬")[0])   # PDF 없으면 쪽 근거를 남기지 않음

    def test_quote_found(self):
        self.assertTrue(quote_found("novel discontinuity", "a novel dis-\ncontinuity here"))
        self.assertFalse(quote_found("", "x"))


class ZoteroTests(unittest.TestCase):
    def test_citekey_and_item(self):
        d = {"title": "X", "date": "2024-03", "creators": [{"lastName": "Müller", "firstName": "A", "creatorType": "author"}] * 3}
        self.assertEqual(zotero.make_citekey(d, set()), "MullerEtAl2024")
        self.assertEqual(zotero.make_citekey(d, {"mulleretal2024"}), "MullerEtAl2024a")
        it = zotero.crossref_to_item({"DOI": "10.1/ABC", "title": ["T"], "author": [{"given": "A", "family": "B"}],
                                      "issued": {"date-parts": [[2025, 1]]}}, "wiki-inbox")
        self.assertEqual((it["DOI"], it["date"], it["tags"]), ("10.1/abc", "2025-01", [{"tag": "wiki-inbox"}]))


class CollectBriefingTests(unittest.TestCase):
    def test_skip_titles_and_journals(self):
        self.assertTrue(collect.SKIP_TITLE.search("Editorial Board"))
        self.assertFalse(collect.SKIP_TITLE.search("Collective Activism"))
        cfg = config._merge(CFG, {"journals": {"fields": ["재무", "경영"], "extra": [{"name": "J", "issn": "1234-5678"}]}})
        issns = [j["issn"] for j in collect.journal_list(cfg)]
        self.assertEqual(len(issns), len(set(issns)))
        self.assertIn("1234-5678", issns)

    def test_briefing_render_without_model(self):
        g = {"new": [], "cands": [{"id": 3, "doi": "10.1/x", "title": "T", "journal": "MS", "abstract": ""}], "pdf_needed": [], "failed": [],
             "collect": {}}
        text = briefing.render(CFG, g, None, "codex: 사용 한도")
        self.assertIn("| 3 |", text)
        self.assertIn("사용 한도", text)
        self.assertIn("새 논문 없음", text)

    def test_library_link(self):
        cfg = config._merge(CFG, {"library": {"ebsco_search": "https://e/x?q=DO%20{doi}"}})
        self.assertEqual(briefing.library_link(cfg, "10.1/a b"), "https://e/x?q=DO%2010.1%2Fa%20b")


class DoctorTests(unittest.TestCase):
    def test_sync_folder_detection(self):
        for p in (r"C:\Users\kim\OneDrive\llm-wiki", r"C:\Users\kim\OneDrive - 서강대학교\wiki", "/Users/k/Library/CloudStorage/GoogleDrive-x/llm",
                  "/Users/k/Library/Mobile Documents/x", r"G:\내 드라이브\wiki"):
            self.assertTrue(doctor.in_sync_folder(p), p)
        for p in (r"C:\Users\kim\llm-wiki", "/tmp/-Users-k-Library-CloudStorage-GoogleDrive-x/vault"):
            self.assertFalse(doctor.in_sync_folder(p), p)


if __name__ == "__main__":
    unittest.main()
