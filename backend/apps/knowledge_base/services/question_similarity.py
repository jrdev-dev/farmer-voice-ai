from rapidfuzz.fuzz import token_set_ratio

from .normalizer import QuestionNormalizer


class QuestionSimilarity:
    """
    Measures direct similarity between the user's question
    and the stored knowledge question.

    This prevents answer/search_text terms from dominating
    retrieval when the actual question intent is different.
    """

    def __init__(self):
        self.normalizer = QuestionNormalizer()

    def score(self, user_question: str, knowledge) -> float:

        if not user_question or not knowledge:
            return 0.0

        query = self.normalizer.normalize(user_question)

        stored_question = knowledge.normalized_question or self.normalizer.normalize(
            knowledge.question
        )

        score = token_set_ratio(
            query,
            stored_question,
        )

        return float(score) / 100.0
