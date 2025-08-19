#!/usr/bin/env python3
"""
Question Rendering Service - Database-driven question visualization

This module handles:
- Question image rendering from database
- Image composition and layout
- Question text formatting
- Export to various formats
"""

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from pathlib import Path
import io
import base64
import json
import hashlib
import time
from typing import List, Dict, Any, Optional, Tuple
import warnings

# Import Question model and validation
from data.models import Question, ModelValidator, ValidationError, convert_db_row_to_question

warnings.filterwarnings('ignore')


class QuestionRenderingService:
    """Database-driven question rendering service with advanced caching"""

    def __init__(self, db_manager, cache_service=None):
        self.db_manager = db_manager
        self.cache_service = cache_service
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'renders': 0
        }

    def get_question_by_id(self, question_id: str) -> Optional[Question]:
        """Get question data from database by question_id (string) or internal_question_id (integer) and return as Question model"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                # Support both question_id (string) and internal_question_id (integer)
                if question_id.isdigit():
                    # Search by internal_question_id
                    query = """
                    SELECT
                        q.internal_question_id,
                        q.question_id,
                        q.paper_id,
                        q.question_number,
                        q.combined_text AS question_text,
                        q.images,
                        q.text_length,
                        q.soft_cluster,
                        q.openai_embedding,
                        q.umap_embedding,
                        q.embedding_model,
                        q.created_at,
                        q.updated_at,
                        p.paper_name,
                        p.paper_code
                    FROM questions q
                    JOIN papers p ON q.paper_id = p.paper_id
                    WHERE q.internal_question_id = %s
                    """
                    cursor.execute(query, (int(question_id),))
                else:
                    # Search by question_id string
                    query = """
                    SELECT
                        q.internal_question_id,
                        q.question_id,
                        q.paper_id,
                        q.question_number,
                        q.combined_text AS question_text,
                        q.images,
                        q.text_length,
                        q.soft_cluster,
                        q.openai_embedding,
                        q.umap_embedding,
                        q.embedding_model,
                        q.created_at,
                        q.updated_at,
                        p.paper_name,
                        p.paper_code
                    FROM questions q
                    JOIN papers p ON q.paper_id = p.paper_id
                    WHERE q.question_id = %s
                    """
                    cursor.execute(query, (question_id,))

                result = cursor.fetchone()

                if result:
                    # Convert to Question model and validate
                    question = convert_db_row_to_question(dict(result))
                    ModelValidator.validate_question(question)
                    return question
                return None

        except ValidationError as e:
            print(f"Validation error for question {question_id}: {e}")
            return None
        except Exception as e:
            print(f"Error fetching question {question_id}: {e}")
            return None

    def get_random_questions(self, count: int = 10) -> List[Question]:
        """Get random questions from database and return as Question models"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                query = """
                SELECT
                    q.internal_question_id,
                    q.question_id,
                    q.paper_id,
                    q.question_number,
                    q.combined_text AS question_text,
                    q.images,
                    q.text_length,
                    q.soft_cluster,
                    q.openai_embedding,
                    q.umap_embedding,
                    q.embedding_model,
                    q.created_at,
                    q.updated_at,
                    p.paper_name,
                    p.paper_code
                FROM questions q
                JOIN papers p ON q.paper_id = p.paper_id
                WHERE 1=1
                ORDER BY RANDOM()
                LIMIT %s
                """

                cursor.execute(query, (count,))
                results = cursor.fetchall()

                # Convert to Question models and validate
                questions = []
                for result in results:
                    try:
                        question = convert_db_row_to_question(dict(result))
                        ModelValidator.validate_question(question)
                        questions.append(question)
                    except ValidationError as e:
                        print(f"Validation error for question {result.get('question_id')}: {e}")
                        continue  # Skip invalid questions

                return questions

        except Exception as e:
            print(f"Error fetching random questions: {e}")
            return []

    def question_to_summary(self, question: Question) -> Dict[str, Any]:
        """Convert Question model to summary format for API responses"""
        # Parse images if they exist
        images = []
        try:
            # The images field might be stored as JSON string or list
            if question.images:
                if isinstance(question.images, str):
                    images = json.loads(question.images)
                elif isinstance(question.images, list):
                    images = question.images
        except (json.JSONDecodeError, TypeError):
            images = []

        return {
            "question_id": question.question_id,
            "paper_code": question.paper_code,
            "paper_name": question.paper_name,
            "question_number": question.question_number or 0,
            "text_length": question.text_length or 0,
            "num_images": len(images),
            "has_images": len(images) > 0,
            "text_preview": (question.question_text or "")[:200] + "..." if question.question_text else "",
            "image_paths": images
        }

    def get_questions_by_paper(self, paper_code: str) -> List[Dict[str, Any]]:
        """Get questions by paper code"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                query = """
                SELECT
                    q.internal_question_id,
                    q.question_id,
                    q.paper_id,
                    q.question_number,
                    q.combined_text,
                    q.images,
                    q.text_length,
                    q.soft_cluster,
                    p.paper_name,
                    p.paper_code
                FROM questions q
                JOIN papers p ON q.paper_id = p.paper_id
                WHERE p.paper_code ILIKE %s
                ORDER BY q.question_number
                """

                cursor.execute(query, (f"%{paper_code}%",))
                results = cursor.fetchall()

                return [dict(result) for result in results]

        except Exception as e:
            print(f"Error fetching questions for paper {paper_code}: {e}")
            return []

    def parse_images_data(self, images_json: Any) -> List[str]:
        """Parse images data from database (handles JSON format)"""
        if not images_json:
            return []

        try:
            if isinstance(images_json, str):
                # Parse JSON string
                images = json.loads(images_json)
            elif isinstance(images_json, list):
                images = images_json
            else:
                return []

            # Ensure all items are strings (image paths)
            return [str(img) for img in images if img]

        except (json.JSONDecodeError, TypeError):
            return []

    def render_question_to_bytes(self, question: Question,
                                figsize: Tuple[int, int] = (12, 16),
                                format: str = 'PNG') -> Optional[bytes]:
        """Render question to image bytes with Redis caching"""
        start_time = time.time()

        try:
            # Generate cache key from question content hash
            cache_key = self._generate_cache_key_from_question(question, figsize, format)

            # Check cache first
            if self.cache_service and self.cache_service.redis:
                try:
                    cached_image = self.cache_service.redis.get(cache_key)
                    if cached_image:
                        self.cache_stats['hits'] += 1
                        print(f"📷 Cache HIT for question {question.question_id} ({(time.time() - start_time)*1000:.1f}ms)")
                        return cached_image
                except Exception as cache_error:
                    print(f"Cache read error: {cache_error}")

            # Cache miss - render question
            self.cache_stats['misses'] += 1
            self.cache_stats['renders'] += 1

            # Parse images from Question model (images might be stored differently)
            images = []
            try:
                if hasattr(question, 'images') and question.images:
                    if isinstance(question.images, str):
                        images = json.loads(question.images)
                    elif isinstance(question.images, list):
                        images = question.images
            except (json.JSONDecodeError, TypeError):
                images = []

            if not images:
                rendered_image = self._render_text_only_question_from_model(question, figsize, format)
            else:
                rendered_image = self._render_question_with_images_from_model(question, images, figsize, format)

            # Cache the rendered image (1 hour TTL)
            if self.cache_service and self.cache_service.redis and rendered_image:
                try:
                    self.cache_service.redis.setex(cache_key, 3600, rendered_image)  # 1 hour TTL
                    render_time = (time.time() - start_time) * 1000
                    print(f"📷 Rendered and cached question {question.question_id} ({render_time:.1f}ms)")
                except Exception as cache_error:
                    print(f"Cache write error: {cache_error}")

            return rendered_image

        except Exception as e:
            print(f"Error rendering question: {e}")
            return None

    def _generate_cache_key_from_question(self, question: Question, figsize: Tuple[int, int], format: str) -> str:
        """Generate cache key from Question model"""
        content_hash = hashlib.md5(
            f"{question.question_id}{question.question_text}{question.text_length}".encode()
        ).hexdigest()
        return f"rendered_question:{content_hash}:{figsize}:{format}"

    def _render_text_only_question_from_model(self, question: Question, figsize: Tuple[int, int], format: str) -> bytes:
        """Render question with only text from Question model"""
        # Use existing text rendering logic but with Question model data
        question_data = {
            'question_id': question.question_id,
            'question_text': question.question_text,
            'paper_name': question.paper_name,
            'paper_code': question.paper_code
        }
        return self._render_text_only_question(question_data, figsize, format)

    def _render_question_with_images_from_model(self, question: Question, images: List[str], figsize: Tuple[int, int], format: str) -> bytes:
        """Render question with images from Question model"""
        # Use existing image rendering logic but with Question model data
        question_data = {
            'question_id': question.question_id,
            'question_text': question.question_text,
            'paper_name': question.paper_name,
            'paper_code': question.paper_code,
            'images': images
        }
        return self._render_question_with_images(question_data, images, figsize, format)

    def _render_question_with_images(self, question_data: Dict[str, Any],
                                   images: List[str],
                                   figsize: Tuple[int, int],
                                   format: str) -> bytes:
        """Render question with images in vertical layout"""
        num_images = len(images)

        # Calculate figure height based on number of images
        image_height = 4
        total_height = max(image_height * num_images + 2, 8)  # +2 for text
        fig_width, _ = figsize

        # Create figure with extra space for text
        fig, axes = plt.subplots(num_images + 1, 1,
                                figsize=(fig_width, total_height),
                                gridspec_kw={'height_ratios': [1] * num_images + [0.3]})

        if num_images == 0:
            axes = [axes]
        elif num_images == 1:
            axes = [axes[0], axes[1]]

        # Display images vertically
        images_displayed = 0
        for i, img_path in enumerate(images):
            ax = axes[i]

            if not Path(img_path).exists():
                ax.text(0.5, 0.5, f'Image {i+1}\nNot Found\n{Path(img_path).name}',
                       ha='center', va='center', transform=ax.transAxes, fontsize=12)
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
            else:
                try:
                    img = mpimg.imread(img_path)
                    ax.imshow(img)

                    img_name = Path(img_path).name
                    ax.set_title(f'Image {i+1}: {img_name}', fontsize=10, pad=10)
                    images_displayed += 1
                except Exception as e:
                    ax.text(0.5, 0.5, f'Error loading Image {i+1}\n{str(e)[:50]}...',
                           ha='center', va='center', transform=ax.transAxes, fontsize=10)
                    ax.set_xlim(0, 1)
                    ax.set_ylim(0, 1)

            ax.axis('off')

        # Add text content at the bottom
        text_ax = axes[-1]
        combined_text = question_data.get('combined_text', 'No text available')

        # Truncate text if too long
        if len(combined_text) > 500:
            combined_text = combined_text[:500] + "..."

        text_ax.text(0.05, 0.5, f"Question Text:\n{combined_text}",
                    ha='left', va='center', transform=text_ax.transAxes,
                    fontsize=9, wrap=True)
        text_ax.axis('off')

        # Set main title
        paper_code = question_data.get('paper_code', 'Unknown')
        question_num = question_data.get('question_number', 'Unknown')
        question_id = question_data.get('question_id', 'Unknown')

        title_text = f'Paper {paper_code} - Question {question_num}\n'
        title_text += f'ID: {question_id} | Images: {num_images}'

        plt.suptitle(title_text, fontsize=14, fontweight='bold', y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])

        # Convert to bytes
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format=format, dpi=150, bbox_inches='tight',
                   facecolor='white')
        plt.close(fig)

        img_buffer.seek(0)
        return img_buffer.getvalue()

    def _render_text_only_question(self, question_data: Dict[str, Any],
                                  figsize: Tuple[int, int],
                                  format: str) -> bytes:
        """Render question with text only (no images)"""
        fig, ax = plt.subplots(1, 1, figsize=(figsize[0], 6))

        paper_code = question_data.get('paper_code', 'Unknown')
        question_num = question_data.get('question_number', 'Unknown')
        question_id = question_data.get('question_id', 'Unknown')
        combined_text = question_data.get('combined_text', 'No text available')

        # Display text
        ax.text(0.05, 0.8, f"Paper: {paper_code} - Question: {question_num}",
               ha='left', va='top', transform=ax.transAxes,
               fontsize=14, fontweight='bold')

        ax.text(0.05, 0.7, f"Question ID: {question_id}",
               ha='left', va='top', transform=ax.transAxes,
               fontsize=10)

        ax.text(0.05, 0.6, "No images available for this question",
               ha='left', va='top', transform=ax.transAxes,
               fontsize=10, style='italic', color='gray')

        # Wrap text
        if len(combined_text) > 1000:
            combined_text = combined_text[:1000] + "..."

        ax.text(0.05, 0.5, f"Question Text:\n{combined_text}",
               ha='left', va='top', transform=ax.transAxes,
               fontsize=9, wrap=True)

        ax.axis('off')

        plt.tight_layout()

        # Convert to bytes
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format=format, dpi=150, bbox_inches='tight',
                   facecolor='white')
        plt.close(fig)

        img_buffer.seek(0)
        return img_buffer.getvalue()

    def render_question_to_base64(self, question_data: Dict[str, Any],
                                 figsize: Tuple[int, int] = (12, 16)) -> Optional[str]:
        """Render question and return as base64 string"""
        img_bytes = self.render_question_to_bytes(question_data, figsize, 'PNG')
        if img_bytes:
            return base64.b64encode(img_bytes).decode('utf-8')
        return None

    def get_question_summary(self, question_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get question summary without rendering images"""
        images = self.parse_images_data(question_data.get('images'))
        combined_text = question_data.get('combined_text', '')

        return {
            'question_id': question_data.get('question_id'),
            'paper_code': question_data.get('paper_code'),
            'paper_name': question_data.get('paper_name'),
            'question_number': question_data.get('question_number'),
            'text_length': question_data.get('text_length', len(combined_text)),
            'num_images': len(images),
            'has_images': len(images) > 0,
            'text_preview': combined_text[:200] + "..." if len(combined_text) > 200 else combined_text,
            'image_paths': images
        }

    def search_questions(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search questions by text content"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                search_query = """
                SELECT
                    q.internal_question_id,
                    q.question_id,
                    q.paper_id,
                    q.question_number,
                    q.combined_text,
                    q.images,
                    q.text_length,
                    p.paper_name,
                    p.paper_code,
                    ts_rank(to_tsvector('english', q.combined_text),
                           plainto_tsquery('english', %s)) as rank
                FROM questions q
                JOIN papers p ON q.paper_id = p.paper_id
                WHERE to_tsvector('english', q.combined_text) @@ plainto_tsquery('english', %s)
                ORDER BY rank DESC, q.question_number
                LIMIT %s
                """

                cursor.execute(search_query, (query, query, limit))
                results = cursor.fetchall()

                return [dict(result) for result in results]

        except Exception as e:
            print(f"Error searching questions: {e}")
            return []

    def get_papers_list(self) -> List[Dict[str, Any]]:
        """Get list of available papers with question counts"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                query = """
                SELECT
                    p.paper_id,
                    p.paper_code,
                    p.paper_name,
                    COUNT(q.internal_question_id) as question_count,
                    COUNT(CASE WHEN q.images IS NOT NULL THEN 1 END) as questions_with_images
                FROM papers p
                LEFT JOIN questions q ON p.paper_id = q.paper_id
                GROUP BY p.paper_id, p.paper_code, p.paper_name
                ORDER BY p.paper_code
                """

                cursor.execute(query)
                results = cursor.fetchall()
                return [dict(result) for result in results]

        except Exception as e:
            print(f"Error fetching papers list: {e}")
            return []

    def _generate_cache_key(self, question_data: Dict[str, Any],
                           figsize: Tuple[int, int], format: str) -> str:
        """Generate a unique cache key for the rendered question"""
        # Create content hash from question data
        content_str = json.dumps({
            'question_id': question_data.get('question_id'),
            'combined_text': question_data.get('combined_text', ''),
            'images': question_data.get('images'),
            'paper_code': question_data.get('paper_code'),
            'question_number': question_data.get('question_number')
        }, sort_keys=True)

        content_hash = hashlib.md5(content_str.encode()).hexdigest()[:12]

        return f"rendered_question:{content_hash}:{figsize[0]}x{figsize[1]}:{format}"

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = self.cache_stats['hits'] / total_requests if total_requests > 0 else 0

        return {
            'cache_hits': self.cache_stats['hits'],
            'cache_misses': self.cache_stats['misses'],
            'total_renders': self.cache_stats['renders'],
            'hit_rate': hit_rate,
            'hit_rate_percentage': f"{hit_rate * 100:.1f}%"
        }

    def warm_popular_questions_cache(self, question_ids: Optional[List[str]] = None,
                                   figsize: Tuple[int, int] = (12, 16)) -> Dict[str, Any]:
        """Pre-warm cache with popular questions"""
        warming_stats = {
            'started_at': time.time(),
            'questions_processed': 0,
            'questions_cached': 0,
            'errors': []
        }

        try:
            if question_ids is None:
                # Get popular questions from recent activity
                with self.db_manager.get_db_connection() as conn:
                    cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                    # Get most accessed questions in last 24 hours
                    cursor.execute("""
                        SELECT q.question_id, COUNT(*) as access_count
                        FROM questions q
                        JOIN student_question_history sqh ON q.internal_question_id = sqh.internal_question_id
                        WHERE sqh.timestamp >= NOW() - INTERVAL '24 hours'
                        GROUP BY q.question_id
                        ORDER BY access_count DESC
                        LIMIT 50
                    """)

                    popular_questions = cursor.fetchall()
                    question_ids = [q['question_id'] for q in popular_questions]

            # Pre-render and cache popular questions
            for question_id in question_ids:
                try:
                    question_data = self.get_question_by_id(question_id)
                    if question_data:
                        # Render with different formats
                        for format_type in ['PNG', 'JPEG']:
                            self.render_question_to_bytes(question_data, figsize, format_type)

                        warming_stats['questions_cached'] += 1

                    warming_stats['questions_processed'] += 1

                except Exception as e:
                    warming_stats['errors'].append(f"Error warming {question_id}: {str(e)}")
                    continue

            warming_stats['duration'] = time.time() - warming_stats['started_at']
            print(f"Cache warming completed: {warming_stats}")
            return warming_stats

        except Exception as e:
            warming_stats['fatal_error'] = str(e)
            return warming_stats
