import threading

import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """
    Generates sentence embeddings using a multilingual model.

    The SentenceTransformer model is expensive to load.
    Therefore, one model instance is shared across all
    EmbeddingService objects inside the Django process.
    """

    MODEL_NAME = "intfloat/multilingual-e5-base"

    # Shared model for the whole Django process.
    _model = None

    # Prevent two simultaneous requests from loading
    # the model at the same time.
    _model_lock = threading.Lock()

    def __init__(self):
        """
        Create an embedding service without reloading
        SentenceTransformer for every service instance.
        """

        self.model = self._get_model()

    # =========================================================
    # MODEL CACHE
    # =========================================================

    @classmethod
    def _get_model(cls):
        """
        Load SentenceTransformer only once per Django process.
        """

        if cls._model is None:

            with cls._model_lock:

                # Double-check after acquiring lock.
                if cls._model is None:

                    print()
                    print("=" * 80)
                    print("LOADING EMBEDDING MODEL")
                    print("=" * 80)
                    print(f"Model : {cls.MODEL_NAME}")
                    print("=" * 80)
                    print()

                    cls._model = SentenceTransformer(
                        cls.MODEL_NAME
                    )

                    print()
                    print("=" * 80)
                    print("EMBEDDING MODEL READY")
                    print("=" * 80)
                    print()

        return cls._model

    # =========================================================
    # SINGLE EMBEDDING
    # =========================================================

    def encode(self, text: str):
        """
        Generate embedding for a single text.
        """

        if not text:
            text = ""

        embedding = self.model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return np.asarray(
            embedding,
            dtype=np.float32,
        )

    # =========================================================
    # BATCH EMBEDDINGS
    # =========================================================

    def batch_encode(self, texts):
        """
        Generate embeddings for multiple texts.
        """

        if texts is None:
            texts = []

        texts = [
            "" if text is None else str(text)
            for text in texts
        ]

        if not texts:
            return np.empty(
                (0, 0),
                dtype=np.float32,
            )

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return np.asarray(
            embeddings,
            dtype=np.float32,
        )

    # =========================================================
    # CACHE INFORMATION
    # =========================================================

    @classmethod
    def is_model_loaded(cls):
        """
        Useful for debugging/tests.
        """

        return cls._model is not None