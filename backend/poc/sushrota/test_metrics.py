import unittest

from evaluate import align_words, error_rate, normalize


class MetricsTests(unittest.TestCase):
    def test_normalization_preserves_devanagari_vowel_marks_and_virama(self):
        self.assertEqual(normalize("सत्येनोत्तभिता भूमि: ॥१॥"), "सत्येनोत्तभिता भूमि")

    def test_cer_ignores_word_boundaries_but_wer_does_not(self):
        ref = "सं गच्छध्वं"
        hyp = "संगच्छध्वं"
        self.assertEqual(error_rate(ref, hyp, characters=True), 0)
        self.assertGreater(error_rate(ref, hyp, characters=False), 0)

    def test_missing_word_increases_both_error_rates(self):
        self.assertGreater(error_rate("रामः गच्छति", "रामः", characters=True), 0)
        self.assertGreater(error_rate("रामः गच्छति", "रामः", characters=False), 0)

    def test_reference_alignment_marks_omissions_and_preserves_timestamps(self):
        aligned = align_words("रामः गच्छति", [{"word": "रामः", "start_ms": 120, "end_ms": 430}])
        self.assertEqual(aligned[0]["status"], "match")
        self.assertEqual((aligned[0]["start_ms"], aligned[0]["end_ms"]), (120, 430))
        self.assertEqual(aligned[1]["status"], "omitted")
        self.assertIsNone(aligned[1]["start_ms"])

    def test_reference_alignment_marks_substitution(self):
        aligned = align_words("रामः गच्छति", [
            {"word": "रामः", "start_ms": 0, "end_ms": 200},
            {"word": "आगच्छति", "start_ms": 220, "end_ms": 800},
        ])
        self.assertEqual([row["status"] for row in aligned], ["match", "substitute"])


if __name__ == "__main__":
    unittest.main()
