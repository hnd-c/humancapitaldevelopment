#!/usr/bin/env python3
"""
Question Service - Clean question data operations without rendering

This service handles:
- Question database operations
- Question data retrieval and formatting
- Search and filtering operations
- Question metadata and summaries
"""

import json
from typing import List, Dict, Any, Optional
from data.models import Question, ModelValidator, ValidationError, convert_db_row_to_question


class QuestionService:
    """Clean service for question database operations without rendering dependencies"""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    def get_question_by_id(self, question_id: str) -> Optional[Question]:
        """Get question data from database by question_id (string) or internal_question_id (integer)"""
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


# Global question service instance
_question_service_instance = None

def get_question_service(db_manager) -> QuestionService:
    """Get singleton question service instance"""
    global _question_service_instance
    if _question_service_instance is None:
        _question_service_instance = QuestionService(db_manager)
    return _question_service_instance
