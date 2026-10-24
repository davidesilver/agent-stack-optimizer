import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

# Ensure hooks is in path to import pdf_to_text
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

import pdf_to_text

class TestPdfExtract(unittest.TestCase):
    def setUp(self):
        # Create a simple PDF for testing
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        self.pdf_path = Path("test_blank.pdf")
        with open(self.pdf_path, "wb") as f:
            writer.write(f)

    def tearDown(self):
        if self.pdf_path.exists():
            self.pdf_path.unlink()

    def test_extract_pypdf(self):
        pages, body, method = pdf_to_text.extract(self.pdf_path)
        self.assertEqual(pages, 1)
        self.assertIn("--- pagina 1 ---", body)
        self.assertEqual(method, "pypdf")

    @patch("pdf_to_text.markitdown")
    def test_extract_markitdown_fallback(self, mock_markitdown):
        mock_markitdown.return_value = "markitdown success text\n\x0c"

        # We need to simulate pypdf failing. Since extract() does 'from pypdf import PdfReader',
        # we can mock builtins.__import__ to raise an ImportError when 'pypdf' is imported.
        original_import = __import__
        def mocked_import(name, *args, **kwargs):
            if name == "pypdf":
                raise ImportError("Mocked ImportError for pypdf")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mocked_import):
            pages, body, method = pdf_to_text.extract(self.pdf_path)

        self.assertEqual(pages, 2) # string has one \x0c (form feed), so 1 + 1 = 2
        self.assertEqual(body, "markitdown success text\n\x0c")
        self.assertEqual(method, "markitdown")

    @patch("pdf_to_text.markitdown")
    @patch("pdf_to_text.shutil.which")
    @patch("pdf_to_text.subprocess.run")
    def test_extract_pdftotext_fallback(self, mock_run, mock_which, mock_markitdown):
        mock_markitdown.return_value = "" # markitdown fails
        mock_which.return_value = "/usr/bin/pdftotext"

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "pdftotext output\f"
        mock_run.return_value = mock_process

        original_import = __import__
        def mocked_import(name, *args, **kwargs):
            if name == "pypdf":
                raise ImportError("Mocked ImportError for pypdf")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mocked_import):
            pages, body, method = pdf_to_text.extract(self.pdf_path)

        self.assertEqual(pages, 2) # string has one \f, so 1 + 1 = 2
        self.assertEqual(body, "pdftotext output\f")
        self.assertEqual(method, "pdftotext -layout")

        # Verify it was called correctly
        mock_run.assert_called_once_with(
            ["/usr/bin/pdftotext", "-layout", str(self.pdf_path), "-"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )

    @patch("pdf_to_text.markitdown")
    @patch("pdf_to_text.shutil.which")
    def test_extract_all_fail(self, mock_which, mock_markitdown):
        mock_markitdown.return_value = "" # markitdown fails
        mock_which.return_value = None # pdftotext not found

        original_import = __import__
        def mocked_import(name, *args, **kwargs):
            if name == "pypdf":
                raise ImportError("Mocked ImportError for pypdf")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mocked_import):
            pages, body, method = pdf_to_text.extract(self.pdf_path)

        self.assertEqual(pages, 0)
        self.assertEqual(body, "")
        self.assertEqual(method, "")

if __name__ == '__main__':
    unittest.main()
