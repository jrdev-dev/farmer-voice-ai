import os
import requests
from typing import Optional


class LLMService:
    """
    Local LLM service using Ollama.

    Responsibilities
    ----------------
    - Communicate with local Ollama server.
    - Generate grounded responses from prepared prompts.
    - Keep generation deterministic.
    - Handle connection, timeout and malformed-response errors.
    - Allow model/server configuration through environment variables.
    - Never silently return an invalid response.

    IMPORTANT
    ---------
    Agricultural grounding is enforced by:
        PromptBuilder
        -> LLMService
        -> AnswerGuard

    This service only performs model inference.
    """

    DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
    DEFAULT_HEALTH_URL = "http://127.0.0.1:11434/api/tags"

    DEFAULT_MODEL = "qwen2.5:3b"

    DEFAULT_TIMEOUT = 180

    MAX_PROMPT_LENGTH = 50000

    def __init__(
        self,
        model: Optional[str] = None,
        ollama_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):

        # =====================================================
        # Configuration
        # =====================================================

        self.model = model or os.getenv("OLLAMA_MODEL") or self.DEFAULT_MODEL

        self.ollama_url = (
            ollama_url or os.getenv("OLLAMA_URL") or self.DEFAULT_OLLAMA_URL
        )

        self.health_url = os.getenv("OLLAMA_HEALTH_URL") or self.DEFAULT_HEALTH_URL

        try:
            self.timeout = int(
                timeout
                or os.getenv(
                    "OLLAMA_TIMEOUT",
                    self.DEFAULT_TIMEOUT,
                )
            )

        except (TypeError, ValueError):

            self.timeout = self.DEFAULT_TIMEOUT

        # =====================================================
        # Persistent HTTP Session
        # =====================================================

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    # =========================================================
    # Generate
    # =========================================================

    def generate(
        self,
        prompt: str,
    ) -> str:
        """
        Generate one non-streaming response from Ollama.

        Raises RuntimeError when inference cannot be completed.

        GenerationService catches these failures and can safely
        fall back to trusted knowledge.
        """

        # =====================================================
        # 1. Validate Prompt
        # =====================================================

        if prompt is None:

            raise RuntimeError("LLM prompt cannot be None.")

        prompt = str(prompt).strip()

        if not prompt:

            raise RuntimeError("LLM prompt cannot be empty.")

        # Protect against accidental giant prompts.

        if len(prompt) > self.MAX_PROMPT_LENGTH:

            raise RuntimeError("LLM prompt exceeds the maximum allowed length.")

        # =====================================================
        # 2. Build Ollama Payload
        # =====================================================

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            # Do not keep unnecessary model state between
            # independent RAG requests.
            "keep_alive": "30m",
            "options": {
                # ---------------------------------------------
                # Low temperature is intentional.
                #
                # This is a grounded agricultural QA system,
                # not a creative generation system.
                # ---------------------------------------------
                "temperature": 0.05,
                "top_p": 0.85,
                # Existing model/context configuration.
                # Farmer answer should stay concise.
                "num_predict": 160,

                "num_ctx": 2048,
                # Helps reduce repeated generation.
                "repeat_penalty": 1.08,
                # Deterministic behavior where supported.
                "seed": 42,
                # CPU threads - adjust later after benchmark
                "num_thread": 6,
            },
        }

        # =====================================================
        # 3. Ollama Request
        # =====================================================

        try:

            response = self.session.post(
                self.ollama_url,
                json=payload,
                timeout=self.timeout,
            )

        except requests.exceptions.ConnectionError as exc:

            raise RuntimeError(
                "Could not connect to Ollama. "
                "Make sure the Ollama server is running."
            ) from exc

        except requests.exceptions.Timeout as exc:

            raise RuntimeError("Ollama request timed out.") from exc

        except requests.exceptions.RequestException as exc:

            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        # =====================================================
        # 4. HTTP Status Validation
        # =====================================================

        try:

            response.raise_for_status()

        except requests.exceptions.HTTPError as exc:

            error_message = self._extract_error_message(response)

            raise RuntimeError(
                "Ollama returned HTTP " f"{response.status_code}: " f"{error_message}"
            ) from exc

        # =====================================================
        # 5. JSON Validation
        # =====================================================

        try:

            data = response.json()

        except ValueError as exc:

            raise RuntimeError("Ollama returned an invalid JSON response.") from exc

        if not isinstance(data, dict):

            raise RuntimeError("Ollama returned an unexpected response format.")

        # =====================================================
        # 6. Ollama-Level Error
        # =====================================================

        ollama_error = data.get("error")

        if ollama_error:

            raise RuntimeError(f"Ollama generation error: {ollama_error}")

        # =====================================================
        # 7. Extract Answer
        # =====================================================

        answer = data.get(
            "response",
            "",
        )

        if answer is None:

            answer = ""

        answer = self._clean_output(str(answer))

        if not answer:

            raise RuntimeError("Ollama returned an empty response.")

        # =====================================================
        # 8. Debug
        # =====================================================

        print("\n" + "=" * 80)
        print("LLM SERVICE")
        print("=" * 80)

        print(
            "Model          :",
            self.model,
        )

        print(
            "Prompt Length  :",
            len(prompt),
        )

        print(
            "Response Length:",
            len(answer),
        )

        print(
            "Done           :",
            data.get("done"),
        )

        print(
            "Done Reason    :",
            data.get("done_reason"),
        )

        print("=" * 80 + "\n")

        return answer

    # =========================================================
    # Health Check
    # =========================================================

    def health_check(
        self,
    ) -> dict:
        """
        Check whether Ollama is reachable and whether the
        configured model appears in the local model list.

        This is useful for:
        - backend diagnostics
        - final project tests
        - future admin health endpoints
        """

        result = {
            "available": False,
            "model": self.model,
            "model_available": False,
            "error": None,
        }

        try:

            response = self.session.get(
                self.health_url,
                timeout=10,
            )

            response.raise_for_status()

            data = response.json()

            models = data.get(
                "models",
                [],
            )

            model_names = set()

            for item in models:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                name = item.get("name")

                model = item.get("model")

                if name:
                    model_names.add(str(name))

                if model:
                    model_names.add(str(model))

            result["available"] = True

            result["model_available"] = self._model_exists(model_names)

        except Exception as exc:

            result["error"] = str(exc)

        return result

    # =========================================================
    # Model Matching
    # =========================================================

    def _model_exists(
        self,
        model_names,
    ) -> bool:

        if not model_names:

            return False

        configured = self.model.strip().lower()

        for name in model_names:

            name = str(name).strip().lower()

            if name == configured:

                return True

            # Ollama may expose ":latest" differently.

            if name.removesuffix(":latest") == configured.removesuffix(":latest"):

                return True

        return False

    # =========================================================
    # Error Extraction
    # =========================================================

    @staticmethod
    def _extract_error_message(
        response,
    ) -> str:

        try:

            data = response.json()

            if isinstance(
                data,
                dict,
            ):

                error = data.get("error")

                if error:

                    return str(error)

        except Exception:

            pass

        text = getattr(
            response,
            "text",
            "",
        )

        if text:

            text = " ".join(text.split())

            # Avoid dumping a giant server response.

            return text[:500]

        return "Unknown Ollama error."

    # =========================================================
    # Output Cleaning
    # =========================================================

    @staticmethod
    def _clean_output(
        answer: str,
    ) -> str:

        if not answer:

            return ""

        answer = answer.replace(
            "\x00",
            " ",
        )

        # Normalize line endings without destroying useful
        # paragraph structure.

        answer = answer.replace(
            "\r\n",
            "\n",
        )

        answer = answer.replace(
            "\r",
            "\n",
        )

        lines = []

        for line in answer.splitlines():

            line = " ".join(line.split())

            if line:

                lines.append(line)

        return "\n".join(lines).strip()

    # =========================================================
    # Close Session
    # =========================================================

    def close(
        self,
    ):

        try:
            self.session.close()

        except Exception:
            pass
