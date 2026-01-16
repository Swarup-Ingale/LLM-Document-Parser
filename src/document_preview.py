import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Dict
import logging
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import sys

# Fix Windows encoding issues
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ... rest of your existing document_preview.py code remains the same

# Enhanced dependency checking with better error handling
HAS_PDF2IMAGE = False
HAS_PYMUPDF = False

try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
    print("✓ pdf2image is available for PDF processing")
except ImportError as e:
    print("⚠ pdf2image not available. Install with: pip install pdf2image")
    print("  Also install poppler-utils: sudo apt-get install poppler-utils")

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
    print("✓ PyMuPDF (fitz) is available for PDF processing")
except ImportError as e:
    print("⚠ PyMuPDF not available. Install with: pip install PyMuPDF")

class DocumentPreviewGenerator:
    def __init__(self, previews_dir: str = "data/previews"):
        self.previews_dir = Path(previews_dir)
        self.previews_dir.mkdir(exist_ok=True, parents=True)
        self.logger = logging.getLogger(__name__)
        self.thumbnail_size = (200, 280)  # Standard thumbnail size
        self.preview_size = (800, 1120)   # Standard preview size
        
        # Log available features
        if HAS_PDF2IMAGE or HAS_PYMUPDF:
            self.logger.info("PDF preview generation is available")
        else:
            self.logger.warning("No PDF processing libraries available. Using placeholder images only.")

    def generate_pdf_preview(self, pdf_path: str, document_id: str, 
                           generate_thumbnail: bool = True) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate preview and thumbnail for PDF document
        Returns (preview_path, thumbnail_path)
        """
        try:
            # Check if PDF processing is available
            if not HAS_PDF2IMAGE and not HAS_PYMUPDF:
                self.logger.warning("No PDF processing libraries available. Using placeholder.")
                return self._generate_placeholder(pdf_path, document_id, "PDF")
            
            preview_path = None
            thumbnail_path = None
            
            # Method 1: Use pdf2image (better quality)
            if HAS_PDF2IMAGE:
                try:
                    preview_path, thumbnail_path = self._generate_with_pdf2image(
                        pdf_path, document_id, generate_thumbnail
                    )
                    if preview_path:
                        self.logger.info(f"✓ PDF preview generated with pdf2image: {document_id}")
                        return preview_path, thumbnail_path
                except Exception as e:
                    self.logger.warning(f"pdf2image failed, trying PyMuPDF: {e}")
            
            # Method 2: Fallback to PyMuPDF
            if HAS_PYMUPDF and (preview_path is None):
                try:
                    preview_path, thumbnail_path = self._generate_with_pymupdf(
                        pdf_path, document_id, generate_thumbnail
                    )
                    if preview_path:
                        self.logger.info(f"✓ PDF preview generated with PyMuPDF: {document_id}")
                        return preview_path, thumbnail_path
                except Exception as e:
                    self.logger.warning(f"PyMuPDF also failed: {e}")
            
            # Method 3: Generate placeholder if both methods failed
            self.logger.warning(f"All PDF processing methods failed for {document_id}, using placeholder")
            return self._generate_placeholder(pdf_path, document_id, "PDF")
            
        except Exception as e:
            self.logger.error(f"Error generating PDF preview for {pdf_path}: {e}")
            return self._generate_placeholder(pdf_path, document_id, "PDF")

    def _generate_with_pdf2image(self, pdf_path: str, document_id: str, 
                               generate_thumbnail: bool) -> Tuple[Optional[str], Optional[str]]:
        """Generate preview using pdf2image"""
        try:
            # Check if file exists and is readable
            if not os.path.exists(pdf_path):
                self.logger.error(f"PDF file not found: {pdf_path}")
                return None, None
            
            # Convert first page to image
            images = convert_from_path(
                pdf_path, 
                first_page=1, 
                last_page=1, 
                size=self.preview_size[0],
                dpi=150  # Good quality for preview
            )
            
            if not images:
                self.logger.warning(f"No images extracted from PDF: {pdf_path}")
                return None, None
            
            preview_image = images[0]
            
            # Save preview
            preview_filename = f"{document_id}_preview.png"
            preview_path = self.previews_dir / preview_filename
            preview_image.save(preview_path, "PNG", quality=85, optimize=True)
            
            # Generate thumbnail
            thumbnail_path = None
            if generate_thumbnail:
                thumbnail = preview_image.copy()
                thumbnail.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
                thumbnail_filename = f"{document_id}_thumbnail.png"
                thumbnail_path = self.previews_dir / thumbnail_filename
                thumbnail.save(thumbnail_path, "PNG", quality=80, optimize=True)
            
            return str(preview_path), str(thumbnail_path) if thumbnail_path else None
            
        except Exception as e:
            self.logger.error(f"pdf2image conversion failed for {pdf_path}: {e}")
            return None, None

    def _generate_with_pymupdf(self, pdf_path: str, document_id: str,
                             generate_thumbnail: bool) -> Tuple[Optional[str], Optional[str]]:
        """Generate preview using PyMuPDF"""
        try:
            # Check if file exists and is readable
            if not os.path.exists(pdf_path):
                self.logger.error(f"PDF file not found: {pdf_path}")
                return None, None
            
            doc = fitz.open(pdf_path)
            
            # Check if document has pages
            if len(doc) == 0:
                self.logger.warning(f"PDF has no pages: {pdf_path}")
                doc.close()
                return None, None
            
            page = doc[0]
            
            # Create preview with good quality
            mat = fitz.Matrix(2.0, 2.0)  # Zoom factor for better quality
            pix = page.get_pixmap(matrix=mat)
            
            preview_filename = f"{document_id}_preview.png"
            preview_path = self.previews_dir / preview_filename
            
            # Save as PNG
            pix.save(str(preview_path))
            
            # Generate thumbnail
            thumbnail_path = None
            if generate_thumbnail:
                # Create smaller version for thumbnail
                mat_thumb = fitz.Matrix(0.5, 0.5)
                pix_thumb = page.get_pixmap(matrix=mat_thumb)
                
                thumbnail_filename = f"{document_id}_thumbnail.png"
                thumbnail_path = self.previews_dir / thumbnail_filename
                pix_thumb.save(str(thumbnail_path))
            
            doc.close()
            return str(preview_path), str(thumbnail_path) if thumbnail_path else None
            
        except Exception as e:
            self.logger.error(f"PyMuPDF conversion failed for {pdf_path}: {e}")
            return None, None

    def generate_image_preview(self, image_path: str, document_id: str,
                             generate_thumbnail: bool = True) -> Tuple[Optional[str], Optional[str]]:
        """Generate preview for image documents"""
        try:
            # Check if file exists
            if not os.path.exists(image_path):
                self.logger.error(f"Image file not found: {image_path}")
                return self._generate_placeholder(image_path, document_id, "IMAGE")
            
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P', 'LA'):
                    # Create white background for transparent images
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                    else:
                        background.paste(img)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Save preview (resize if too large)
                if max(img.size) > self.preview_size[0]:
                    img.thumbnail(self.preview_size, Image.Resampling.LANCZOS)
                
                preview_filename = f"{document_id}_preview.jpg"
                preview_path = self.previews_dir / preview_filename
                img.save(preview_path, "JPEG", quality=85, optimize=True)
                
                # Generate thumbnail
                thumbnail_path = None
                if generate_thumbnail:
                    thumbnail = img.copy()
                    thumbnail.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
                    thumbnail_filename = f"{document_id}_thumbnail.jpg"
                    thumbnail_path = self.previews_dir / thumbnail_filename
                    thumbnail.save(thumbnail_path, "JPEG", quality=80, optimize=True)
                
                self.logger.info(f"✓ Image preview generated: {document_id}")
                return str(preview_path), str(thumbnail_path) if thumbnail_path else None
                
        except Exception as e:
            self.logger.error(f"Error generating image preview for {image_path}: {e}")
            return self._generate_placeholder(image_path, document_id, "IMAGE")

    def _generate_placeholder(self, file_path: str, document_id: str, 
                            file_type: str) -> Tuple[str, str]:
        """Generate placeholder preview when conversion fails"""
        try:
            # Create a placeholder image with nicer design
            img = Image.new('RGB', self.preview_size, color='#f8f9fa')
            draw = ImageDraw.Draw(img)
            
            # Try to load fonts, fallback to default
            try:
                # Try to use a larger font for title
                title_font = ImageFont.truetype("arial.ttf", 32)
                normal_font = ImageFont.truetype("arial.ttf", 18)
            except:
                # Use default font
                title_font = ImageFont.load_default()
                normal_font = ImageFont.load_default()
            
            # Draw decorative elements
            draw.rectangle([50, 50, self.preview_size[0]-50, self.preview_size[1]-50], 
                         outline='#dee2e6', width=2)
            
            # Draw document type
            doc_type_text = f"{file_type} DOCUMENT"
            bbox = draw.textbbox((0, 0), doc_type_text, font=title_font)
            text_width = bbox[2] - bbox[0]
            x = (self.preview_size[0] - text_width) // 2
            y = self.preview_size[1] // 2 - 40
            draw.text((x, y), doc_type_text, fill='#495057', font=title_font)
            
            # Draw filename (truncate if too long)
            filename = Path(file_path).name
            if len(filename) > 30:
                filename = filename[:27] + "..."
            
            bbox = draw.textbbox((0, 0), filename, font=normal_font)
            text_width = bbox[2] - bbox[0]
            x = (self.preview_size[0] - text_width) // 2
            y = self.preview_size[1] // 2 + 20
            draw.text((x, y), filename, fill='#6c757d', font=normal_font)
            
            # Draw info message
            info_text = "Preview not available"
            bbox = draw.textbbox((0, 0), info_text, font=normal_font)
            text_width = bbox[2] - bbox[0]
            x = (self.preview_size[0] - text_width) // 2
            y = self.preview_size[1] // 2 + 60
            draw.text((x, y), info_text, fill='#868e96', font=normal_font)
            
            # Save preview
            preview_filename = f"{document_id}_preview.png"
            preview_path = self.previews_dir / preview_filename
            img.save(preview_path, "PNG", optimize=True)
            
            # Create thumbnail (smaller version)
            thumbnail = img.copy()
            thumbnail.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
            thumbnail_filename = f"{document_id}_thumbnail.png"
            thumbnail_path = self.previews_dir / thumbnail_filename
            thumbnail.save(thumbnail_path, "PNG", optimize=True)
            
            self.logger.info(f"✓ Placeholder preview generated: {document_id}")
            return str(preview_path), str(thumbnail_path)
            
        except Exception as e:
            self.logger.error(f"Error generating placeholder for {document_id}: {e}")
            # Last resort - return None values
            return None, None

    def get_preview_urls(self, document_id: str) -> Dict[str, Optional[str]]:
        """Get URLs for document preview and thumbnail"""
        # Check for PNG versions first
        preview_path = self.previews_dir / f"{document_id}_preview.png"
        thumbnail_path = self.previews_dir / f"{document_id}_thumbnail.png"
        
        # Check for JPG versions
        if not preview_path.exists():
            preview_path = self.previews_dir / f"{document_id}_preview.jpg"
        if not thumbnail_path.exists():
            thumbnail_path = self.previews_dir / f"{document_id}_thumbnail.jpg"
        
        return {
            "preview_url": f"/api/previews/{document_id}/preview" if preview_path.exists() else None,
            "thumbnail_url": f"/api/previews/{document_id}/thumbnail" if thumbnail_path.exists() else None,
            "preview_exists": preview_path.exists(),
            "thumbnail_exists": thumbnail_path.exists()
        }

    def generate_base64_thumbnail(self, document_id: str) -> Optional[str]:
        """Generate base64 encoded thumbnail for immediate frontend display"""
        try:
            # Try PNG first
            thumbnail_path = self.previews_dir / f"{document_id}_thumbnail.png"
            if not thumbnail_path.exists():
                # Try JPG
                thumbnail_path = self.previews_dir / f"{document_id}_thumbnail.jpg"
            
            if thumbnail_path.exists():
                with open(thumbnail_path, "rb") as img_file:
                    encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
                    
                # Determine MIME type
                if thumbnail_path.suffix.lower() == '.jpg':
                    mime_type = 'jpeg'
                else:
                    mime_type = 'png'
                    
                return f"data:image/{mime_type};base64,{encoded_string}"
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error generating base64 thumbnail for {document_id}: {e}")
            return None

    def cleanup_previews(self, document_id: str):
        """Clean up preview files for a document"""
        try:
            patterns = [
                f"{document_id}_preview.*",
                f"{document_id}_thumbnail.*"
            ]
            
            files_removed = 0
            for pattern in patterns:
                for file_path in self.previews_dir.glob(pattern):
                    try:
                        file_path.unlink()
                        files_removed += 1
                        self.logger.info(f"Removed preview file: {file_path.name}")
                    except Exception as e:
                        self.logger.error(f"Error removing {file_path}: {e}")
            
            if files_removed > 0:
                self.logger.info(f"Cleaned up {files_removed} preview files for {document_id}")
                    
        except Exception as e:
            self.logger.error(f"Error cleaning up previews for {document_id}: {e}")

    def get_system_info(self) -> Dict[str, bool]:
        """Get information about available preview generation capabilities"""
        return {
            "pdf2image_available": HAS_PDF2IMAGE,
            "pymupdf_available": HAS_PYMUPDF,
            "pillow_available": True,  # We know this is available since we import it
            "previews_directory": str(self.previews_dir),
            "previews_directory_exists": self.previews_dir.exists()
        }