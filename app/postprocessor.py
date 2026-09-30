import re
import unicodedata
from typing import Dict, List, Any


class DevanagariPostProcessor:
    """
    Post-processing engine for Devanagari / Nepali OCR output.
    Cleans OCR noise, repairs broken Devanagari ligatures, normalizes Unicode,
    and convert extracted raw text into structured Markdown documents.
    """

    def __init__(self):
        # Common Devanagari Unicode Regex Ranges
        self.devanagari_char_pattern = re.compile(r'[\u0900-\u097F]')
        
        # Precompiled regex pattern for performance
        self.pipe_to_danda_pattern = re.compile(r'(?<=[\u0900-\u097F\s])\|(?=[\s\n]|$|[\u0900-\u097F])')
        self.repeated_danda_pattern = re.compile(r'।।+')
        
        # Regex for broken matras (space between consonant and matra)
        # e.g., 'क ो' -> 'को', 'ग ाई' -> 'गाई'
        self.broken_matra_pattern = re.compile(r'([\u0915-\u0939])\s+([\u093E-\u094C\u0901-\u0903])')
        
        # Regex for broken halant (space before or after halant)
        # e.g., 'क ् त' -> 'क्त', 'न ्' -> 'न्'
        self.halant_space_pattern = re.compile(r'([\u0915-\u0939])\s*(\u094D)\s*([\u0915-\u0939])')
        self.halant_isolated_pattern = re.compile(r'\s+(\u094D)\s+')
        
        # Regex for broken Nukta (space before Nukta)
        self.nukta_space_pattern = re.compile(r'([\u0915-\u0939])\s+(\u093C)')
        
        # Regex for OCR artifacts & control characters
        self.garbage_chars_pattern = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F\uFFFD\uFEFF]')
        self.multiple_spaces_pattern = re.compile(r'[ \t]{2,}')
        self.multiple_newlines_pattern = re.compile(r'\n{3,}')
        
        # Hyphenated word break across lines repair (Devanagari or English)
        self.line_hyphen_pattern = re.compile(r'([\u0900-\u097Fa-zA-Z])-\s*\n\s*([\u0900-\u097Fa-zA-Z])')
        
        # Common Nepali ligature pairs requiring explicit join cleanup
        self.ligature_repairs: Dict[str, str] = {
            'क ् त': 'क्त',
            'क ् ष': 'क्ष',
            'त ् र': 'त्र',
            'ज ् ञ': 'ज्ञ',
            'श ् र': 'श्र',
            'न ् न': 'न्न',
            'स ् थ': 'स्थ',
            'द ् ध': 'द्ध',
            'द ् व': 'द्व',
            'क ् र': 'क्र',
            'ग ् र': 'ग्र',
            'प ् र': 'प्र',
            'ट ् ट': 'ट्ट',
            'ड ् ड': 'ड्ड',
            'न ् त': 'न्त',
            'म ् प': 'म्प',
        }

    def normalize_unicode(self, text: str) -> str:
        """Applies Unicode NFKC normalization to ensure uniform character representations."""
        if not text:
            return ""
        return unicodedata.normalize('NFKC', text)

    def strip_ocr_noise(self, text: str) -> str:
        """Strips control characters, broken symbols, and redundant OCR artifacts."""
        if not text:
            return ""
        
        # Remove non-printable control characters and replacement chars
        text = self.garbage_chars_pattern.sub('', text)
        
        # Replace vertical pipe misrecognized as Purna Viram (।) after Devanagari words
        text = self.pipe_to_danda_pattern.sub('।', text)
        
        # Normalize repeated Purna Virams
        text = self.repeated_danda_pattern.sub('॥', text)
        
        # Collapse multiple horizontal spaces
        text = self.multiple_spaces_pattern.sub(' ', text)
        
        return text

    def reformat_devanagari_ligatures(self, text: str) -> str:
        """
        Repairs broken Devanagari ligatures, matra separations, halant spacing,
        and nukta placements.
        """
        if not text:
            return ""

        # Step 1: Explicit dict ligature repairs
        for broken, fixed in self.ligature_repairs.items():
            text = text.replace(broken, fixed)

        # Step 2: Fix halant spacing between consonants (e.g. 'क ् त' -> 'क्त')
        text = self.halant_space_pattern.sub(r'\1\2\3', text)
        
        # Step 3: Remove isolated orphan halants surrounded by spaces
        text = self.halant_isolated_pattern.sub(' ', text)

        # Step 4: Fix spaces before Matras (vowel signs)
        text = self.broken_matra_pattern.sub(r'\1\2', text)

        # Step 5: Fix Nukta spacing
        text = self.nukta_space_pattern.sub(r'\1\2', text)

        # Step 6: Fix hyphenated word breaks at line ends
        text = self.line_hyphen_pattern.sub(r'\1\2', text)

        return text

    def format_danda_spacing(self, text: str) -> str:
        """Ensures proper spacing around Purna Viram (।) and Double Danda (॥)."""
        # Ensure space after Purna Viram if followed immediately by letter/digit
        text = re.sub(r'(।)([\u0900-\u097Fa-zA-Z0-9])', r'\1 \2', text)
        return text

    def auto_markdown_structure(self, text: str) -> str:
        """
        Analyzes line patterns and converts headings, lists, tables, and paragraphs
        into clean, formatted Markdown.
        """
        lines = text.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                formatted_lines.append('')
                continue

            # Detect Header 1 (Single short line, title-like, e.g. uppercase/standalone header)
            if (len(stripped) < 40 and 
                (i == 0 or (i > 0 and lines[i-1].strip() == "")) and 
                not stripped.startswith(('#', '-', '*', '1.', '०', '१', '२', '३', '४', '५', '६', '७', '८', '९')) and
                not stripped.endswith('।')):
                formatted_lines.append(f"# {stripped}")
                continue

            # Detect Devanagari / English List items (१. , २. , 1. , 2. , - , •)
            devanagari_num_list = re.match(r'^([०-९0-9]+\.|\([०-९0-9]+\)|[क-ह]\.)\s+(.*)', stripped)
            if devanagari_num_list:
                num, item = devanagari_num_list.groups()
                formatted_lines.append(f"1. {item}")
                continue

            bullet_list = re.match(r'^[•\-\*\+]\s+(.*)', stripped)
            if bullet_list:
                formatted_lines.append(f"- {bullet_list.group(1)}")
                continue

            # Page Header / Footer pattern detection
            if re.match(r'^(page\s+\d+|पृष्ठ\s+[०-९0-9]+)\b', stripped, re.IGNORECASE):
                formatted_lines.append(f"\n---\n*${stripped}*\n")
                continue

            formatted_lines.append(stripped)

        result = '\n'.join(formatted_lines)
        # Collapse excessive newlines to double newlines maximum
        result = self.multiple_newlines_pattern.sub('\n\n', result)
        return result.strip()

    def process_text(self, raw_text: str, fix_ligatures: bool = True, strip_noise: bool = True) -> Dict[str, Any]:
        """
        Full post-processing pipeline execution.
        Returns a dictionary containing clean text, markdown output, and metadata stats.
        """
        if not raw_text:
            return {
                "cleaned_text": "",
                "markdown": "",
                "stats": {
                    "original_char_count": 0,
                    "cleaned_char_count": 0,
                    "devanagari_char_count": 0,
                    "noise_removed_chars": 0
                }
            }

        original_len = len(raw_text)
        text = self.normalize_unicode(raw_text)

        if strip_noise:
            text = self.strip_ocr_noise(text)

        if fix_ligatures:
            text = self.reformat_devanagari_ligatures(text)

        text = self.format_danda_spacing(text)
        markdown_output = self.auto_markdown_structure(text)

        # Count Devanagari specific characters
        devanagari_chars = len(self.devanagari_char_pattern.findall(markdown_output))
        cleaned_len = len(markdown_output)

        return {
            "cleaned_text": text,
            "markdown": markdown_output,
            "stats": {
                "original_char_count": original_len,
                "cleaned_char_count": cleaned_len,
                "devanagari_char_count": devanagari_chars,
                "noise_removed_chars": max(0, original_len - cleaned_len)
            }
        }


# Convenience instance
post_processor = DevanagariPostProcessor()

# Final formatting fixes

# Final formatting fixes
