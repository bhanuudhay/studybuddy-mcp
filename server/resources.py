import json
from server import db


def register(mcp):

    @mcp.resource("course://syllabus", mime_type="application/json")
    def syllabus() -> str:
        """All lessons with their completion status."""
        return json.dumps(db.list_lessons(), indent=2)

    @mcp.resource("notes://{lesson_id}")
    def lesson_notes(lesson_id: str) -> str:
        """The lesson summary plus all my notes for that lesson."""
        lesson = db.get_lesson(int(lesson_id))
        if lesson is None:
            return f"Lesson {lesson_id} not found. Valid IDs are 32-49."

        notes = db.get_notes(int(lesson_id))
        lines = [f"Lesson {lesson['id']}: {lesson['title']}",
                 f"Summary: {lesson['summary']}", "", "My notes:"]
        if notes:
            for n in notes:
                lines.append("- " + n["text"])
        else:
            lines.append("(no notes yet)")
        return "\n".join(lines)