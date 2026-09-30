import unittest
from app.postprocessor import DevanagariPostProcessor


class TestDevanagariPostProcessor(unittest.TestCase):

    def setUp(self):
        self.processor = DevanagariPostProcessor()

    def test_unicode_normalization(self):
        text = "नेपाल"
        normalized = self.processor.normalize_unicode(text)
        self.assertEqual(normalized, "नेपाल")

    def test_strip_ocr_noise(self):
        raw_noise = "नेपाल\x00\x08 | प्रशासन....."
        cleaned = self.processor.strip_ocr_noise(raw_noise)
        self.assertNotIn("\x00", cleaned)
        self.assertIn("नेपाल", cleaned)

    def test_ligature_repairs(self):
        # Broken ligatures with spaces
        broken_text = "क ् त र ् म क ् ष त ् र"
        repaired = self.processor.reformat_devanagari_ligatures(broken_text)
        self.assertIn("क्त", repaired)
        self.assertIn("क्ष", repaired)
        self.assertIn("त्र", repaired)

    def test_matra_repairs(self):
        broken_matra = "क ो न ाई"
        repaired = self.processor.reformat_devanagari_ligatures(broken_matra)
        self.assertEqual(repaired, "को नाई")

    def test_markdown_auto_structure(self):
        sample = "नेपाल सरकार\n\n१. पहिलो बुँदा\n२. दोस्रो बुँदा"
        markdown = self.processor.auto_markdown_structure(sample)
        self.assertIn("# नेपाल सरकार", markdown)
        self.assertIn("1. पहिलो बुँदा", markdown)

    def test_full_process_pipeline(self):
        input_text = "नेपाल सरकार | \n\nक ् त तथा त ् र"
        result = self.processor.process_text(input_text)
        self.assertIn("markdown", result)
        self.assertIn("stats", result)
        self.assertGreater(result["stats"]["devanagari_char_count"], 0)


if __name__ == "__main__":
    unittest.main()
