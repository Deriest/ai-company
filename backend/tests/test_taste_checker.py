"""Unit tests for taste_checker — anti-AI-slop quality gate."""
import sys
import os
import pytest

# Add backend root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.services.taste_checker import scan_text, has_ai_slop, scan_summary, Finding


class TestBannedPhrases:
    """High-severity banned AI-ism phrases."""

    def test_delve_detected(self):
        text = "Let's delve into the architecture of this system."
        findings = scan_text(text)
        assert any(f.pattern == "banned:delve" for f in findings)

    def test_crucial_detected(self):
        text = "This is a crucial component for the system."
        findings = scan_text(text)
        assert any(f.pattern == "banned:crucial" for f in findings)

    def test_comprehensive_detected(self):
        text = "We provide a comprehensive solution for all your needs."
        findings = scan_text(text)
        assert any(f.pattern == "banned:comprehensive" for f in findings)

    def test_id_be_happy_detected(self):
        text = "I'd be happy to help you with that!"
        findings = scan_text(text)
        assert any("happy" in f.pattern for f in findings)

    def test_great_question_detected(self):
        text = "Great question! Let me explain how this works."
        findings = scan_text(text)
        assert any("great question" in f.pattern for f in findings)

    def test_in_conclusion_detected(self):
        text = "In conclusion, the system performs well under load."
        findings = scan_text(text)
        assert any("in conclusion" in f.pattern for f in findings)

    def test_seamless_detected(self):
        text = "The integration is seamless and requires no configuration."
        findings = scan_text(text)
        assert any("seamless" in f.pattern for f in findings)

    def test_game_changer_detected(self):
        text = "This feature is a real game-changer for the industry."
        findings = scan_text(text)
        assert any("game-changer" in f.pattern for f in findings)

    def test_leverage_detected(self):
        text = "We leverage cutting-edge technology to deliver robust solutions."
        findings = scan_text(text)
        assert any("leverage" in f.pattern for f in findings)

    def test_multiple_banned(self):
        text = (
            "In today's fast-paced world, it's crucial to leverage "
            "comprehensive solutions. Let's delve into the details."
        )
        findings = scan_text(text)
        high_findings = [f for f in findings if f.severity == "high"]
        assert len(high_findings) >= 3


class TestStructuralHeuristics:
    """Medium and low severity structural patterns."""

    def test_em_dash_overuse(self):
        text = (
            "The system — built on modern principles — handles requests — "
            "processes data — and returns results — all in real time — "
            "with minimal latency — ensuring performance — across workloads."
        )
        findings = scan_text(text)
        assert any(f.pattern == "em_dash_overuse" for f in findings)

    def test_em_dash_normal_usage(self):
        text = "The system handles requests and returns results. It works well."
        findings = scan_text(text)
        assert not any(f.pattern == "em_dash_overuse" for f in findings)

    def test_ing_tail_opener(self):
        text = "Highlighting the importance of testing, we added more coverage.\nUnderscoring the need for speed, we optimized the query."
        findings = scan_text(text)
        assert any(f.pattern == "ing_tail_opener" for f in findings)

    def test_title_case_heading(self):
        text = "## This Is A Title Case Heading\n### Another Title Case One Here"
        findings = scan_text(text)
        assert any(f.pattern == "title_case_heading" for f in findings)

    def test_emoji_in_heading(self):
        text = "## 🚀 Getting Started\n### 🔧 Configuration"
        findings = scan_text(text)
        assert any(f.pattern == "emoji_in_heading" for f in findings)

    def test_boldface_overuse(self):
        parts = ["This is **bold text** " for _ in range(12)]
        text = " ".join(parts)
        findings = scan_text(text)
        assert any(f.pattern == "boldface_overuse" for f in findings)

    def test_curly_quotes(self):
        text = "The system uses \u201csmart quotes\u201d and \u2018single quotes\u2019 throughout."
        findings = scan_text(text)
        assert any(f.pattern == "curly_quotes" for f in findings)


class TestCleanText:
    """Clean text should produce zero or minimal findings."""

    def test_clean_technical_text(self):
        text = (
            "The API accepts POST requests at /tasks with a JSON body. "
            "Required fields: title (string), type (enum), and description (string). "
            "Responses use standard HTTP status codes: 201 for created, 400 for "
            "validation errors, 500 for server errors."
        )
        findings = scan_text(text)
        high = [f for f in findings if f.severity == "high"]
        assert len(high) == 0

    def test_clean_conversational_text(self):
        text = (
            "I looked at the logs and the issue is in the auth middleware. "
            "The token expires after 24 hours but the refresh logic has a race "
            "condition. Fix is straightforward: add a mutex around the refresh call."
        )
        findings = scan_text(text)
        high = [f for f in findings if f.severity == "high"]
        assert len(high) == 0

    def test_empty_text(self):
        assert scan_text("") == []
        assert scan_text("   ") == []
        assert scan_text("Short") == []

    def test_short_text(self):
        text = "OK, got it."
        findings = scan_text(text)
        assert len(findings) == 0


class TestHasAiSlop:
    """Quick boolean check for high-severity slop."""

    def test_sloppy_text(self):
        text = "Let's delve into this comprehensive solution. It's crucial."
        assert has_ai_slop(text) is True

    def test_clean_text(self):
        text = "The function returns a list of active users from the database."
        assert has_ai_slop(text) is False

    def test_threshold(self):
        # Single word-level AI-isms ("crucial", "leverage", "comprehensive") are
        # demoted to medium — they must NOT trigger high-slop at threshold=1.
        text = "This is crucial for the system."
        assert has_ai_slop(text, threshold=1) is False
        assert has_ai_slop(text, threshold=5) is False

        # 2+ distinct word-level AI-isms ARE promoted to high and do trigger.
        heavy = "This is crucial and comprehensive for the system."
        assert has_ai_slop(heavy, threshold=1) is True


class TestBUG20GreetingAIisms:
    """BUG-20: greeting AI-ism wordlist expansion."""

    def test_how_can_i_help_detected(self):
        text = "Hi! How can I help you today?"
        findings = scan_text(text)
        assert any("how can i help" in f.pattern for f in findings), \
            f"Expected 'how can i help' finding, got: {[f.pattern for f in findings]}"
        assert any(f.severity == "high" for f in findings)

    def test_happy_to_help_detected(self):
        text = "I'm happy to help you with that task."
        findings = scan_text(text)
        assert any("happy to help" in f.pattern for f in findings)

    def test_is_there_anything_else_detected(self):
        text = "Is there anything else I can assist you with?"
        findings = scan_text(text)
        assert any("is there anything else" in f.pattern for f in findings)

    def test_anything_else_i_can_detected(self):
        text = "Let me know if there is anything else I can do for you."
        findings = scan_text(text)
        assert any("anything else i can" in f.pattern or "let me know if" in f.pattern for f in findings)

    def test_do_not_hesitate_detected(self):
        text = "Do not hesitate to contact me for further assistance."
        findings = scan_text(text)
        assert any("do not hesitate" in f.pattern for f in findings)

    def test_hope_this_helps_detected(self):
        text = "I hope this helps you understand the concept better."
        findings = scan_text(text)
        assert any("hope this helps" in f.pattern or "i hope this helps" in f.pattern for f in findings)

    def test_as_an_ai_detected(self):
        text = "As an AI, I don't have personal opinions on this matter."
        findings = scan_text(text)
        assert any("as an ai" in f.pattern for f in findings)

    def test_as_a_language_model_detected(self):
        text = "As a language model, I can process various types of input."
        findings = scan_text(text)
        assert any("as a language model" in f.pattern for f in findings)

    def test_im_here_to_help_detected(self):
        text = "I'm here to help you with any questions you might have."
        findings = scan_text(text)
        assert any("i'm here to help" in f.pattern for f in findings)

    def test_here_to_help_you_detected(self):
        text = "I am here to help you navigate this complex system."
        findings = scan_text(text)
        assert any("here to help you" in f.pattern for f in findings)

    def test_absolutely_exclamation_detected(self):
        text = "Absolutely! That's exactly the right approach for this problem."
        findings = scan_text(text)
        assert any("absolutely!" in f.pattern for f in findings)

    def test_of_course_exclamation_detected(self):
        text = "Of course! I can explain that in more detail for you."
        findings = scan_text(text)
        assert any("of course!" in f.pattern for f in findings)

    def test_certainly_exclamation_detected(self):
        text = "Certainly! Let me walk you through the steps."
        findings = scan_text(text)
        assert any("certainly!" in f.pattern for f in findings)

    def test_good_question_detected(self):
        text = "Good question! The answer lies in the configuration."
        findings = scan_text(text)
        assert any("good question" in f.pattern for f in findings)

    def test_what_else_can_i_do_detected(self):
        text = "What else can I do to improve this implementation?"
        findings = scan_text(text)
        assert any("what else can i do" in f.pattern for f in findings)

    # ── False-positive guard: Indonesian must NOT trigger ──

    def test_indonesian_greeting_no_false_positive(self):
        text = "Halo! Ada yang bisa saya bantu hari ini."
        findings = scan_text(text)
        high = [f for f in findings if f.severity == "high"]
        assert len(high) == 0, \
            f"Indonesian greeting should NOT trigger high findings, got: {high}"

    def test_indonesian_saya_bisa_membantu_no_false_positive(self):
        text = "Saya bisa membantu Anda dengan pertanyaan tersebut."
        findings = scan_text(text)
        high = [f for f in findings if f.severity == "high"]
        assert len(high) == 0

    # ── Core acceptance: the exact phrase from the bug report ──

    def test_exact_bug_phrase_triggers_rewrite(self):
        """The exact phrase that triggered BUG-20 must be caught."""
        text = "Hi! How can I help you today?"
        assert has_ai_slop(text, threshold=1) is True


class TestScanSummary:
    """Summary dict for API responses."""

    def test_summary_structure(self):
        text = "Let's delve into this comprehensive, crucial solution."
        summary = scan_summary(text)
        assert "total_findings" in summary
        assert "high" in summary
        assert "medium" in summary
        assert "low" in summary
        assert "findings" in summary
        assert isinstance(summary["findings"], list)

    def test_summary_clean(self):
        text = "The API returns JSON with status codes."
        summary = scan_summary(text)
        assert summary["high"] == 0

    def test_finding_to_dict(self):
        f = Finding(pattern="test", severity="high", count=2, examples=["a", "b"])
        d = f.to_dict()
        assert d["pattern"] == "test"
        assert d["severity"] == "high"
        assert d["count"] == 2
        assert d["examples"] == ["a", "b"]
