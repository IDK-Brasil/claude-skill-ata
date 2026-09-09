#!/usr/bin/env python3
"""Preflight check for the /ata skill. Exit 0 = ready to transcribe.

Exit codes:
    0  ready (diarization may or may not be available — see stderr)
    1  ffmpeg missing
    2  faster-whisper not installed
    3  pyannote.audio not installed (diarization unavailable, transcription still works)
    4  HF_TOKEN not configured (diarization unavailable, transcription still works)
"""
from __future__ import annotations

import os
import shutil
import sys


def setup_cuda_dlls() -> None:
    if sys.platform != "win32":
        return
    try:
        import nvidia.cublas
        import nvidia.cudnn
        for mod in (nvidia.cublas, nvidia.cudnn):
            for path in mod.__path__:
                bin_dir = os.path.join(path, "bin")
                if os.path.isdir(bin_dir):
                    os.add_dll_directory(bin_dir)
                    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    except ImportError:
        pass


def check() -> int:
    setup_cuda_dlls()
    if shutil.which("ffmpeg") is None:
        print("ffmpeg não encontrado no PATH.", file=sys.stderr)
        return 1

    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        print("faster-whisper não instalado. Rode: python -m pip install faster-whisper", file=sys.stderr)
        return 2

    diarize_ok = True
    try:
        import pyannote.audio  # noqa: F401
    except ImportError:
        diarize_ok = False
        print("pyannote.audio não instalado — diarização indisponível (transcrição funciona sem locutor).", file=sys.stderr)

    if diarize_ok and not os.environ.get("HF_TOKEN"):
        try:
            from huggingface_hub import get_token
            if not get_token():
                diarize_ok = False
        except ImportError:
            diarize_ok = False
        if not diarize_ok:
            print(
                "Sem HF_TOKEN configurado — diarização indisponível. "
                "Crie um token em hf.co/settings/tokens, aceite os termos em "
                "hf.co/pyannote/speaker-diarization-3.1 e hf.co/pyannote/segmentation-3.0, "
                "e rode `huggingface-cli login` ou exporte HF_TOKEN.",
                file=sys.stderr,
            )

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"device disponível: {device}", file=sys.stderr)
    except ImportError:
        print("torch não instalado — necessário para faster-whisper/pyannote.", file=sys.stderr)
        return 2

    if not diarize_ok:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
