def register(mcp):

    @mcp.prompt()
    def explain_like_im_new(lesson_id: str) -> str:
        """Explain one lesson simply, using my notes."""
        return (f"Read the resource notes://{lesson_id}. Explain that lesson to a beginner "
                "in simple words, give one real-world example, and end with 2 quick check questions.")

    @mcp.prompt()
    def make_quiz(topic: str, difficulty: str = "medium") -> str:
        """Create a 5-question quiz on a topic at the chosen difficulty (easy, medium or hard)."""
        return (f"Make a quiz of 5 questions about '{topic}' at {difficulty} difficulty. "
                "Use my course notes where they help. Ask one question at a time, wait for my answer, "
                "tell me if I was right and why, and give my final score out of 5 at the end.")

    @mcp.prompt()
    def weekly_review() -> str:
        """Review my course progress and suggest what to study next."""
        return ("Read the resource course://syllabus. List the lessons I have finished and the ones "
                "still unfinished. Suggest the next 2 lessons I should study and explain why in one "
                "sentence each. Then give me 3 flashcard-style questions on the lessons I finished.")
