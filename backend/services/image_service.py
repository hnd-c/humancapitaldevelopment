#!/usr/bin/env python3
"""
Image Service - Abstract image serving for development and production

This service handles:
- Environment-based image URL resolution
- Local development serving via FastAPI static files
- Production S3 URL generation
- Image path validation and transformation
"""

import os
from typing import List, Dict, Any
from pathlib import Path
from config.environments import is_production, is_development, get_environment


class ImageService:
    """Service to abstract image serving between local development and S3 production"""

    def __init__(self, config=None):
        self.config = config
        self.environment = get_environment()

        # Configuration based on environment
        if is_production():
            self.s3_bucket = os.getenv("S3_BUCKET_NAME", "your-hcd-images-bucket")
            self.s3_region = os.getenv("S3_REGION", "us-east-1")
            self.cloudfront_domain = os.getenv("CLOUDFRONT_DOMAIN")  # Optional CDN

        self.local_images_path = Path("p1_images")

    def get_image_url(self, image_path: str) -> str:
        """
        Convert internal image path to accessible URL based on environment

        Args:
            image_path: Internal path like "p1_images/9702_w22_qp_13/page_16/image.png"

        Returns:
            Full URL for the image based on environment
        """
        # Remove p1_images prefix if present (normalize the path)
        if image_path.startswith("p1_images/"):
            relative_path = image_path[10:]  # Remove "p1_images/" prefix
        else:
            relative_path = image_path

        if is_production():
            return self._get_s3_url(relative_path)
        else:
            return self._get_local_url(relative_path)

    def get_multiple_image_urls(self, image_paths: List[str]) -> List[str]:
        """Convert multiple image paths to URLs"""
        return [self.get_image_url(path) for path in image_paths]

    def _get_s3_url(self, relative_path: str) -> str:
        """Generate S3 URL for production"""
        if self.cloudfront_domain:
            # Use CloudFront CDN if configured
            return f"https://{self.cloudfront_domain}/{relative_path}"
        else:
            # Direct S3 URL
            return f"https://{self.s3_bucket}.s3.{self.s3_region}.amazonaws.com/{relative_path}"

    def _get_local_url(self, relative_path: str) -> str:
        """Generate local development URL"""
        # This will be served by FastAPI static files mount
        return f"/static/images/{relative_path}"

    def validate_image_exists(self, image_path: str) -> bool:
        """
        Check if image exists (only for local development)
        In production, we assume S3 images exist
        """
        if is_development():
            full_path = self.local_images_path / image_path.replace("p1_images/", "")
            return full_path.exists()
        else:
            # In production, assume S3 images exist (or implement S3 head_object check)
            return True

    def get_image_metadata(self, image_path: str) -> Dict[str, Any]:
        """Get image metadata"""
        metadata = {
            "path": image_path,
            "url": self.get_image_url(image_path),
            "exists": self.validate_image_exists(image_path),
            "environment": self.environment
        }

        if is_development() and metadata["exists"]:
            try:
                full_path = self.local_images_path / image_path.replace("p1_images/", "")
                stat = full_path.stat()
                metadata.update({
                    "size_bytes": stat.st_size,
                    "modified_time": stat.st_mtime
                })
            except Exception:
                pass

        return metadata


class QuestionImageComposer:
    """Helper to prepare question image data for frontend composition"""

    def __init__(self, image_service: ImageService):
        self.image_service = image_service

    def prepare_question_images(self, question_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare question image data for frontend composition

        Returns structured data that frontend can use to compose images
        """
        images = question_data.get('images', [])
        if isinstance(images, str):
            try:
                import json
                images = json.loads(images)
            except Exception:
                images = []

        # Convert paths to URLs
        image_data = []
        for i, img_path in enumerate(images):
            image_info = {
                "index": i,
                "original_path": img_path,
                "url": self.image_service.get_image_url(img_path),
                "filename": Path(img_path).name,
                "exists": self.image_service.validate_image_exists(img_path)
            }
            image_data.append(image_info)

        return {
            "question_id": question_data.get('question_id'),
            "paper_code": question_data.get('paper_code'),
            "paper_name": question_data.get('paper_name'),
            "question_number": question_data.get('question_number'),
            "question_text": question_data.get('question_text', question_data.get('combined_text')),
            "images": image_data,
            "total_images": len(image_data),
            "composition_metadata": {
                "recommended_layout": "vertical",
                "suggested_width": 800,
                "suggested_height": 600 * len(image_data) if image_data else 300
            }
        }


# Global image service instance
_image_service_instance = None

def get_image_service() -> ImageService:
    """Get singleton image service instance"""
    global _image_service_instance
    if _image_service_instance is None:
        _image_service_instance = ImageService()
    return _image_service_instance
