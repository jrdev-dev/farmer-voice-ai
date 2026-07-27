import logging
import os
import tempfile
from pathlib import Path
import filetype

logger = logging.getLogger(__name__)


class AudioConverter:
    """
    Robust Audio Validation and Transcoding Utility.

    Converts incoming audio files (wav, mp3, m4a, webm, ogg, flac, etc.)
    into standardized 16kHz mono 16-bit PCM WAV audio optimal for Faster-Whisper ASR.
    """

    ALLOWED_MIME_TYPES = {
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/ogg",
        "audio/webm",
        "audio/flac",
        "audio/x-flac",
        "application/ogg",
    }

    ALLOWED_EXTENSIONS = {
        ".wav",
        ".mp3",
        ".m4a",
        ".ogg",
        ".webm",
        ".flac",
        ".aac",
        ".wma",
    }

    @classmethod
    def validate_audio_file(cls, file_path: str) -> Path:
        """
        Validate file existence, non-emptiness, and basic magic byte MIME detection.
        """
        if not file_path:
            raise ValueError("Audio file path cannot be empty.")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file does not exist: {file_path}")

        if not path.is_file():
            raise ValueError(f"Audio path is not a file: {file_path}")

        if path.stat().st_size == 0:
            raise ValueError("Uploaded audio file is empty (0 bytes).")

        # Magic byte check using filetype
        kind = filetype.guess(str(path))
        ext = path.suffix.lower()

        if kind is not None:
            if kind.mime not in cls.ALLOWED_MIME_TYPES and not kind.mime.startswith("audio/"):
                logger.warning(
                    "Strict MIME check notice: file %s has guessed MIME %s",
                    path.name,
                    kind.mime,
                )
        elif ext not in cls.ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported or unrecognised audio format: {ext}")

        return path

    @classmethod
    def prepare_wav_for_asr(cls, input_path: str) -> str:
        """
        Prepares and normalizes input audio for Faster-Whisper.
        If file is already valid WAV or audio conversion tool isn't available, returns original path.
        Otherwise converts using av/pydub if installed.
        """
        path = cls.validate_audio_file(input_path)

        # Attempt transcoding using PyAV or pydub if available
        try:
            import av

            output_temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            output_temp.close()

            container = av.open(str(path))
            stream = next((s for s in container.streams if s.type == "audio"), None)

            if stream is None:
                os.unlink(output_temp.name)
                return str(path)

            resampler = av.AudioResampler(
                format="s16",
                layout="mono",
                rate=16000,
            )

            out_container = av.open(output_temp.name, mode="w", format="wav")
            out_stream = out_container.add_stream("pcm_s16le", rate=16000)
            out_stream.layout = "mono"

            for frame in container.decode(stream):
                frame.pts = None
                resampled_frames = resampler.resample(frame)
                if resampled_frames:
                    for rframe in resampled_frames:
                        for packet in out_stream.encode(rframe):
                            out_container.mux(packet)

            for packet in out_stream.encode(None):
                out_container.mux(packet)

            out_container.close()
            container.close()

            cls.normalize_audio_volume(output_temp.name)
            logger.info("Successfully converted & normalized %s to 16kHz WAV (%s)", path.name, output_temp.name)
            return output_temp.name

        except Exception as exc:
            logger.debug("PyAV transcoding skipped/failed (%s), falling back to raw audio path", exc)
            return str(path)

    @classmethod
    def normalize_audio_volume(cls, wav_path: str, target_peak: float = 0.95):
        """
        Auto-Gain Control: Normalizes audio volume to peak target level (0.95)
        to boost quiet spoken farmer speech for accurate Faster-Whisper ASR.
        """
        try:
            import wave
            import numpy as np

            with wave.open(wav_path, 'rb') as wf:
                params = wf.getparams()
                frames = wf.readframes(params.nframes)

            if not frames:
                return

            audio_data = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
            max_val = np.max(np.abs(audio_data))

            if max_val > 0 and max_val < 25000:
                scale = (target_peak * 32767.0) / max_val
                # Limit max gain boost to 6x to prevent amplification of extreme static
                scale = min(scale, 6.0)
                normalized = np.clip(audio_data * scale, -32768, 32767).astype(np.int16)

                with wave.open(wav_path, 'wb') as wf:
                    wf.setparams(params)
                    wf.writeframes(normalized.tobytes())

        except Exception as e:
            logger.warning("Audio volume AGC normalization skipped: %s", e)
