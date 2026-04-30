import os
import PyPDF2
from typing import Optional

class FileProcessor:
    """
    Handles processing of various file types like .txt, .py, .pdf.
    Extracts text content to be used by the AI model as context.
    """
    
    @staticmethod
    def process_file(file_path: str) -> str:
        """
        Process a file and return its textual content.
        Raises FileNotFoundError if file doesn't exist.
        Raises ValueError if file type is unsupported.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Text based files
        if ext in ['.txt', '.py', '.md', '.csv', '.json', '.js', '.ts', '.tsx', '.html', '.css', '.rs']:
            return FileProcessor._process_text_file(file_path)
        # PDF files
        elif ext == '.pdf':
            return FileProcessor._process_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
            
    @staticmethod
    def _process_text_file(file_path: str) -> str:
        """Read and return content of a text file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Fallback to latin-1 if utf-8 fails
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
                
    @staticmethod
    def _process_pdf(file_path: str) -> str:
        """Extract and return text from a PDF file."""
        text = ""
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            return text.strip()
        except Exception as e:
            raise RuntimeError(f"Error processing PDF: {str(e)}")
