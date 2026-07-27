import os
import PyPDF2
from typing import Optional

class FileProcessor:
    """
    Handles processing of various file types like .txt, .py, .pdf, images, audio, video.
    Extracts text content to be used by the AI model as context.
    """
    
    @staticmethod
    def process_file(file_path: str) -> str:
        """
        Process a file and return its textual content.
        Raises FileNotFoundError if file doesn't exist.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Text based files
        if ext in ['.txt', '.py', '.md', '.csv', '.json', '.js', '.ts', '.tsx', '.html', '.css', '.rs', '.log', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.env']:
            return FileProcessor._process_text_file(file_path)
        # PDF files
        elif ext == '.pdf':
            return FileProcessor._process_pdf(file_path)
        # Image files
        elif ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff']:
            return FileProcessor._process_image(file_path)
        # Audio / Video media files
        elif ext in ['.mp3', '.mp4', '.m4a', '.wav', '.aac', '.flac', '.avi', '.mov', '.mkv', '.webm', '.ogg']:
            return FileProcessor._process_media(file_path)
        else:
            return FileProcessor._process_fallback(file_path)
            
    @staticmethod
    def _process_text_file(file_path: str) -> str:
        """Read and return content of a text file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
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
            return text.strip() or f"[PDF Document: {os.path.basename(file_path)} (No extractable text)]"
        except Exception as e:
            return f"[PDF Document: {os.path.basename(file_path)} | Error: {str(e)}]"

    @staticmethod
    def _process_image(file_path: str) -> str:
        """Process image file and extract metadata."""
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                width, height = img.size
                fmt = img.format or "Image"
                mode = img.mode
                return f"[Attached Image: {file_name} | Path: {file_path} | Format: {fmt} | Dimensions: {width}x{height} | Color Mode: {mode} | Size: {file_size} bytes]"
        except Exception:
            return f"[Attached Image: {file_name} | Path: {file_path} | Size: {file_size} bytes]"

    @staticmethod
    def _process_media(file_path: str) -> str:
        """Process audio/video media file and extract size/type metadata."""
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        size_mb = file_size / (1024 * 1024)
        _, ext = os.path.splitext(file_path)
        media_type = "Audio" if ext.lower() in ['.mp3', '.m4a', '.wav', '.aac', '.flac', '.ogg'] else "Video"
        return f"[Attached {media_type} File: {file_name} | Extension: {ext} | Path: {file_path} | Size: {size_mb:.2f} MB ({file_size} bytes)]"

    @staticmethod
    def _process_fallback(file_path: str) -> str:
        """Fallback text reader for any unknown file type."""
        file_name = os.path.basename(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(5000)
                if content.strip():
                    return f"[File: {file_name}]\n{content}"
        except Exception:
            pass
        return f"[Attached File: {file_name} | Path: {file_path}]"
