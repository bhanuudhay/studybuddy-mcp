import random
import sys
import time
from typing import Annotated, Literal

import httpx
from pydantic import Field
from mcp.server.fastmcp.exceptions import ToolError
from server import db


def register(mcp):

    @mcp.tool()
    def get_lesson(lesson_id: int) -> dict:
        """Get the title, module and summary of one course lesson by its number (32-49).
        Use this when the user names a specific lesson number.
        Do not use this to search notes by topic."""
        lesson = db.get_lesson(lesson_id)
        if lesson is None:
            raise ToolError(f"Lesson {lesson_id} not found. Valid IDs are 32-49.")
        return lesson
    
    @mcp.tool()
    def add_note(lesson_id: int, text: str) -> dict:
        """Save a personal study note for one lesson (32-49).
        Use this when the user wants to remember or write down something about a lesson.
        Do not use this to read notes."""
        
        lesson = db.get_lesson(lesson_id)
        if lesson is None:
            raise ToolError(f"Lesson {lesson_id} not found. Valid IDs are 32-49.")
        
        if not text.strip():
            raise ToolError("Please enter some text")
        
        return db.add_note(lesson_id, text.strip())

    @mcp.tool()
    def search_notes(
        query: str,
        lesson_id: int | None = None,
        limit: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> list[dict]:
        """Search my saved study notes by keyword, newest first.
        Use this when the user asks what they wrote about a topic, e.g. "my notes on retries".
        Optionally narrow to one lesson with lesson_id. Do not use this to get a lesson's official summary; use get_lesson."""
        if not query.strip():
            raise ToolError("Search query is empty. Give a keyword such as 'retry' or 'schema'.")
        if lesson_id is not None and db.get_lesson(lesson_id) is None:
            raise ToolError(f"Lesson {lesson_id} not found. Valid IDs are 32-49, or leave lesson_id out to search all lessons.")
        return db.search_notes(query.strip(), lesson_id, limit)

    @mcp.tool()
    def start_quiz(
        lesson_id: int,
        num_questions: Annotated[int, Field(ge=1, le=20, description="How many questions, 1-20")] = 5,
        difficulty: Literal["easy", "medium", "hard"] = "medium",
    ) -> list[dict]:
        """Get flashcard questions for a quiz on one lesson (32-49). Returns question ids and text only, never the answers.
        Use this when the user wants to be quizzed or tested. Ask the questions one at a time,
        then check each answer with grade_answer."""
        if db.get_lesson(lesson_id) is None:
            raise ToolError(f"Lesson {lesson_id} not found. Valid IDs are 32-49.")
        cards = db.get_flashcards(lesson_id, difficulty, num_questions)
        if not cards:
            others = [d for d in ("easy", "medium", "hard") if d != difficulty]
            raise ToolError(
                f"No {difficulty} flashcards for lesson {lesson_id}. "
                f"Try difficulty='{others[0]}' or '{others[1]}', or create some with create_flashcard."
            )
        return [{"card_id": c["id"], "question": c["q"]} for c in cards]

    @mcp.tool()
    def grade_answer(card_id: int, user_answer: str) -> dict:
        """Get the correct answer for one quiz flashcard so you can judge the user's answer.
        Use this after the user answers a question from start_quiz. Compare the meaning, not the exact words."""
        card = db.get_flashcard(card_id)
        if card is None:
            raise ToolError(f"Flashcard {card_id} not found. Use a card_id returned by start_quiz.")
        return {"card_id": card_id, "question": card["q"], "correct_answer": card["a"], "user_answer": user_answer}

    @mcp.tool()
    def create_flashcard(
        lesson_id: int,
        question: str,
        answer: str,
        difficulty: Literal["easy", "medium", "hard"] = "medium",
    ) -> dict:
        """Create one new flashcard for a lesson (32-49).
        Use this when the user asks to make a flashcard or wants to remember a question and answer.
        For many cards at once, use bulk_import_flashcards."""
        if db.get_lesson(lesson_id) is None:
            raise ToolError(f"Lesson {lesson_id} not found. Valid IDs are 32-49.")
        if not question.strip() or not answer.strip():
            raise ToolError("Both question and answer must have text. Fill in the empty one and try again.")
        return db.add_flashcard(lesson_id, question.strip(), answer.strip(), difficulty)

    @mcp.tool()
    def log_progress(
        lesson_id: int,
        score: Annotated[int, Field(ge=0)],
        total: Annotated[int, Field(ge=1)],
    ) -> dict:
        """Save the result of a finished quiz, e.g. 4 correct out of 5.
        Use this once at the end of a quiz, after all questions are graded."""
        if db.get_lesson(lesson_id) is None:
            raise ToolError(f"Lesson {lesson_id} not found. Valid IDs are 32-49.")
        if score > total:
            raise ToolError(f"Score {score} is higher than total {total}. Score must be between 0 and {total}.")
        return db.log_progress(lesson_id, score, total)

    @mcp.tool()
    def bulk_import_flashcards(lesson_id: int, cards: list[dict]) -> dict:
        """Import many flashcards for one lesson (32-49) at once.
        Each card is an object with 'q' (question), 'a' (answer) and optional 'difficulty' (easy/medium/hard, default medium).
        Valid cards are saved even if some fail; the result lists each failed card's index and reason so you can fix and resend only those."""
        if db.get_lesson(lesson_id) is None:
            raise ToolError(f"Lesson {lesson_id} not found. Valid IDs are 32-49.")

        imported, failed = [], []
        for i, card in enumerate(cards):
            q = str(card.get("q", "")).strip()
            a = str(card.get("a", "")).strip()
            difficulty = card.get("difficulty", "medium")

            if not q:
                failed.append({"index": i, "reason": "missing 'q' (question text)"})
                continue
            if not a:
                failed.append({"index": i, "reason": "missing 'a' (answer text)"})
                continue
            if difficulty not in ("easy", "medium", "hard"):
                failed.append({"index": i, "reason": f"difficulty '{difficulty}' is invalid; use easy, medium or hard"})
                continue

            imported.append(db.add_flashcard(lesson_id, q, a, difficulty)["id"])

        return {"imported": len(imported), "card_ids": imported, "failed": failed}

    @mcp.tool()
    def define_term(term: str) -> str:
        """Look up the dictionary definition of one English word, e.g. 'idempotent' or 'latency'.
        Use this when the user asks what a word means. Only single words work, not phrases."""
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{term.strip()}"

        for attempt in range(1, 4):
            try:
                if random.random() < 0.3:  # fake flakiness so you can see retries
                    raise httpx.ConnectError("simulated network failure")
                r = httpx.get(url, timeout=5)

                if r.status_code == 404:
                    # permanent: retrying won't help
                    raise ToolError(f"No definition found for '{term}'. Check the spelling or try a simpler word.")
                if r.status_code >= 500:
                    # temporary: let it retry
                    raise httpx.ConnectError(f"server error {r.status_code}")

                data = r.json()
                meaning = data[0]["meanings"][0]
                return f"{term} ({meaning['partOfSpeech']}): {meaning['definitions'][0]['definition']}"

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                print(f"define_term attempt {attempt} failed: {e}", file=sys.stderr)
                if attempt < 3:
                    time.sleep(2 ** (attempt - 1))  # wait 1s, then 2s

        raise ToolError("Dictionary service failed 3 times. Tell the user to try again later.")