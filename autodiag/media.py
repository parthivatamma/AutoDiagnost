"""Optional, dependency-light media feature extraction."""

from pathlib import Path
import wave


def audio_features(path: str | Path) -> dict[str, float | int | str]:
    """Extract conservative WAV metadata without making media mandatory."""
    source = Path(path)
    try:
        with wave.open(str(source), "rb") as audio:
            frames = audio.getnframes()
            rate = audio.getframerate()
            duration = frames / rate if rate else 0.0
            return {
                "path": str(source),
                "format": "wav",
                "duration_seconds": round(duration, 3),
                "sample_rate_hz": rate,
                "channels": audio.getnchannels(),
                "frames": frames,
            }
    except (wave.Error, OSError) as error:
        raise ValueError(
            f"Only readable WAV files are supported without optional media tools: {source}"
        ) from error
