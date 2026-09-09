#!/usr/bin/env python3
"""Transcribe + diarize a video/audio recording, 100% local.

Pipeline: ffmpeg (extract mono 16kHz audio) -> faster-whisper (word-level
transcript, GPU-aware) -> pyannote.audio (speaker diarization, optional) ->
word-to-speaker assignment by time overlap -> transcript.json + transcript.md.

Nothing leaves the machine except a one-time model download from Hugging
Face (both for faster-whisper's CTranslate2 weights and pyannote's gated
diarization models, if a token is configured).

Usage:
    python transcribe.py --source <video-or-audio> --output-dir <dir> [options]

Options:
    --model {tiny,base,small,medium,large-v2,large-v3}   default: large-v3 on GPU, medium on CPU
    --device {auto,cuda,cpu}                             default: auto
    --language pt                                        default: auto-detect
    --num-speakers N                                      hint for diarization (optional)
    --no-diarize                                          skip speaker diarization
    --hf-token TOKEN                                      override env/cache HF token
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()


def log(msg: str) -> None:
    print(f"[ata] {msg}", file=sys.stderr, flush=True)


class ProgressPanel:
    """Standalone, stage-aware progress window; failures never stop transcription."""

    STAGES = (
        ("Extraindo áudio", 0, 8, "#5B8DEF"),
        ("Carregando modelo", 8, 15, "#8B6FD8"),
        ("Transcrevendo áudio", 15, 75, "#28A87D"),
        ("Separando locutores", 75, 95, "#E59B3A"),
        ("Gerando arquivos", 95, 100, "#D65F8D"),
    )

    def __init__(self) -> None:
        now = time.monotonic()
        self._state = {"stage": "Extraindo áudio", "detail": "Preparando a gravação", "percent": 0.0, "done": False}
        self._started_at = now
        self._stage_started = {"Extraindo áudio": now}
        self._stage_elapsed: dict[str, float] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True, name="ata-progress-panel").start()

    def update(self, stage: str, percent: float, detail: str = "") -> None:
        with self._lock:
            previous = self._state["stage"]
            now = time.monotonic()
            if stage != previous:
                self._stage_elapsed[previous] = now - self._stage_started.get(previous, now)
                self._stage_started.setdefault(stage, now)
            self._state.update(stage=stage, percent=max(0, min(100, percent)), detail=detail)

    def finish(self, detail: str) -> None:
        with self._lock:
            now = time.monotonic()
            current = self._state["stage"]
            self._stage_elapsed[current] = now - self._stage_started.get(current, now)
            self._state.update(stage="Concluído", percent=100, detail=detail, done=True)

    def fail(self, detail: str) -> None:
        with self._lock:
            self._state.update(stage="Não foi possível concluir", detail=detail, done=True)

    def _run(self) -> None:
        try:
            root = tk.Tk()
            root.title("/ata — andamento")
            root.geometry("560x340")
            root.resizable(False, False)
            root.attributes("-topmost", True)
            frame = ttk.Frame(root, padding=18)
            frame.pack(fill="both", expand=True)
            stage = ttk.Label(frame, font=("Segoe UI", 13, "bold"))
            stage.pack(anchor="w")
            total = ttk.Label(frame)
            total.pack(anchor="w", pady=(2, 12))
            canvas = tk.Canvas(frame, height=30, highlightthickness=0, bg=root.cget("bg"))
            canvas.pack(fill="x")
            rows = ttk.Frame(frame)
            rows.pack(fill="x", pady=(12, 0))
            labels = {name: ttk.Label(rows) for name, *_ in self.STAGES}
            for label in labels.values():
                label.pack(anchor="w", pady=1)
            detail = ttk.Label(frame, wraplength=520)
            detail.pack(anchor="w", pady=(10, 0))

            def fmt(seconds: float) -> str:
                minutes, secs = divmod(int(seconds), 60)
                hours, minutes = divmod(minutes, 60)
                return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"

            def draw_bar(state: dict, now: float) -> None:
                canvas.delete("all")
                width = max(canvas.winfo_width(), 520)
                for name, start, end, color in self.STAGES:
                    left, right = width * start / 100, width * end / 100
                    canvas.create_rectangle(left, 4, right, 27, fill="#D9DDE3", outline="#FFFFFF")
                    fill = max(0, min(end, state["percent"]) - start) / (end - start)
                    if fill:
                        canvas.create_rectangle(left, 4, left + (right - left) * fill, 27, fill=color, outline="")
                    elapsed = self._stage_elapsed.get(name)
                    if elapsed is None and name == state["stage"]:
                        elapsed = now - self._stage_started.get(name, now)
                    marker = "●" if name == state["stage"] and not state["done"] else ("✓" if state["percent"] >= end else "○")
                    labels[name].config(text=f"{marker}  {name}: {fmt(elapsed or 0)}")
            detail.pack(anchor="w")

            def refresh() -> None:
                with self._lock:
                    state = dict(self._state)
                now = time.monotonic()
                stage.config(text=f"{state['stage']}  ({state['percent']:.0f}%)")
                total.config(text=f"Tempo total: {fmt(now - self._started_at)}")
                draw_bar(state, now)
                detail.config(text=state["detail"])
                # Keep the result visible until the user closes the window.
                if not state["done"]:
                    root.after(300, refresh)

            refresh()
            root.mainloop()
        except Exception:
            pass


def setup_cuda_dlls() -> None:
    """On Windows, ctranslate2 (faster-whisper's backend) needs cuBLAS/cuDNN
    DLLs on the loader search path. pip's nvidia-cublas-cu12/nvidia-cudnn-cu12
    wheels ship them under site-packages, but Windows doesn't look there by
    default — torch's own bundled cublas64_13.dll (CUDA 13) is a different
    major version and won't satisfy ctranslate2's cublas64_12 requirement.
    """
    if sys.platform != "win32":
        return
    try:
        import nvidia.cublas
        import nvidia.cudnn
        for mod in (nvidia.cublas, nvidia.cudnn):
            for path in mod.__path__:
                bin_dir = Path(path) / "bin"
                if bin_dir.exists():
                    # os.add_dll_directory alone doesn't cover ctranslate2's
                    # implicit dependent-DLL loading on Windows — PATH does.
                    os.add_dll_directory(str(bin_dir))
                    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    except ImportError:
        pass


def extract_audio(source: Path, out_path: Path) -> Path:
    """Extract mono 16kHz wav — small, fast for whisper/pyannote to chew on."""
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg não está instalado / não está no PATH.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source.resolve()),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(out_path.resolve()),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg falhou ao extrair áudio: {result.stderr.strip()}")
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise SystemExit("ffmpeg não gerou áudio — o arquivo tem trilha de áudio?")
    return out_path


def media_duration(source: Path) -> float | None:
    """Best-effort duration for an honest transcription progress estimate."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(source)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def detect_device(requested: str | None) -> str:
    if requested and requested != "auto":
        return requested
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def default_model_for(device: str) -> str:
    return "large-v3" if device == "cuda" else "medium"


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def transcribe_words(
    audio_path: Path,
    model_size: str,
    device: str,
    language: str | None,
    progress_path: Path | None = None,
    on_progress=None,
    total_seconds: float | None = None,
) -> list[dict]:
    from faster_whisper import WhisperModel

    compute_type = "float16" if device == "cuda" else "int8"
    log(f"carregando modelo faster-whisper '{model_size}' ({device}, {compute_type})…")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    log("transcrevendo (word-level timestamps)…")
    seg_iter, info = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    progress_fh = None
    if progress_path is not None:
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        progress_fh = progress_path.open("a", encoding="utf-8")

    segments: list[dict] = []
    try:
        for seg in seg_iter:
            words = [
                {"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word.strip()}
                for w in (seg.words or [])
                if w.word and w.word.strip()
            ]
            segments.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
                "words": words,
            })
            if progress_fh:
                progress_fh.write(f"[{_fmt_ts(seg.start)}] {seg.text.strip()}\n")
                progress_fh.flush()
            if on_progress:
                percent = 15 + (60 * seg.end / total_seconds) if total_seconds else 15
                on_progress("Transcrevendo áudio", percent, f"Chegou em {_fmt_ts(seg.end)} da gravação")
    finally:
        if progress_fh:
            progress_fh.close()

    log(f"transcrição bruta: {len(segments)} segmentos, idioma detectado={info.language} (p={info.language_probability:.2f})")
    return segments


_NORM_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _normalize(text: str) -> str:
    return _NORM_RE.sub("", text).strip().lower()


def dedupe_hallucination_loops(segments: list[dict], min_repeats: int = 3) -> list[dict]:
    """Collapse runs of the same short segment repeated back-to-back.

    Known Whisper failure mode on ambiguous audio (overlapping speech,
    laughter, background noise): the decoder gets stuck repeating a short
    phrase ("ok", "é isso") dozens of times. Detected and confirmed on the
    2026-09-09 meeting transcript — this is not lost audio, it's a decode
    artifact on genuinely ambiguous/lateral-conversation audio.
    """
    out: list[dict] = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        norm = _normalize(seg["text"])
        if norm and len(norm) <= 30:
            j = i + 1
            while j < len(segments) and _normalize(segments[j]["text"]) == norm:
                j += 1
            run_len = j - i
            if run_len >= min_repeats:
                collapsed = dict(seg)
                collapsed["end"] = segments[j - 1]["end"]
                collapsed["text"] = f"{seg['text']} [repetido {run_len}x — provável alucinação em trecho ambíguo/sobreposto]"
                out.append(collapsed)
                i = j
                continue
        out.append(seg)
        i += 1
    return out


def diarize(audio_path: Path, hf_token: str, device: str, num_speakers: int | None) -> list[tuple[float, float, str]]:
    from pyannote.audio import Pipeline
    import torch
    import soundfile as sf

    log("carregando pipeline de diarização pyannote (speaker-diarization-3.1)…")
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=hf_token)
    if device == "cuda":
        pipeline.to(torch.device("cuda"))

    log("rodando diarização (separando vozes por locutor)…")
    # Pass a decoded waveform instead of a file path: both pyannote's own
    # Audio() and torchaudio.load() default to torchcodec for file I/O, which
    # needs FFmpeg's *shared* library DLLs — not present with a static
    # ffmpeg.exe build (our case on Windows). soundfile (libsndfile, bundled
    # wheel, no ffmpeg dependency at all) reads our own ffmpeg-produced PCM
    # WAV directly, sidestepping torchcodec entirely.
    data, sample_rate = sf.read(str(audio_path), dtype="float32", always_2d=True)
    waveform = torch.from_numpy(data.T)  # (channel, time)
    kwargs = {"num_speakers": num_speakers} if num_speakers else {}
    output = pipeline({"waveform": waveform, "sample_rate": sample_rate}, **kwargs)
    # pyannote 4.x returns a DiarizeOutput dataclass, not a bare Annotation.
    # exclusive_speaker_diarization has overlapping speech resolved to one
    # speaker per instant — the right shape for assigning a speaker to each
    # (non-overlapping) whisper segment.
    diarization = output.exclusive_speaker_diarization

    turns = [(turn.start, turn.end, speaker) for turn, _, speaker in diarization.itertracks(yield_label=True)]
    speakers = sorted(set(s for _, _, s in turns))
    log(f"diarização: {len(turns)} turnos, {len(speakers)} locutores detectados ({', '.join(speakers)})")
    return turns


def assign_speakers(segments: list[dict], turns: list[tuple[float, float, str]]) -> list[dict]:
    """Assign each segment the speaker with the most time-overlap."""
    def overlap(a0: float, a1: float, b0: float, b1: float) -> float:
        return max(0.0, min(a1, b1) - max(a0, b0))

    for seg in segments:
        best_speaker, best_overlap = None, 0.0
        for t0, t1, speaker in turns:
            ov = overlap(seg["start"], seg["end"], t0, t1)
            if ov > best_overlap:
                best_overlap, best_speaker = ov, speaker
        seg["speaker"] = best_speaker or "SPEAKER_UNKNOWN"
    return segments


def merge_into_turns(segments: list[dict]) -> list[dict]:
    """Merge consecutive same-speaker segments into readable turns."""
    turns: list[dict] = []
    for seg in segments:
        if turns and turns[-1].get("speaker") == seg.get("speaker") and seg["start"] - turns[-1]["end"] < 2.0:
            turns[-1]["end"] = seg["end"]
            turns[-1]["text"] = f"{turns[-1]['text']} {seg['text']}".strip()
        else:
            turns.append({"start": seg["start"], "end": seg["end"], "speaker": seg.get("speaker"), "text": seg["text"]})
    return turns


def format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def write_markdown(turns: list[dict], out_path: Path, diarized: bool) -> None:
    lines = ["# Transcrição", ""]
    if not diarized:
        lines.append("_Sem diarização de locutor — todo o áudio aparece como um único bloco por segmento._")
        lines.append("")
    for t in turns:
        label = t.get("speaker") or "?"
        lines.append(f"**[{format_time(t['start'])} – {format_time(t['end'])}] {label}:** {t['text']}")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcreve e diariza um vídeo/áudio localmente.")
    ap.add_argument("--source", required=True, help="Caminho do vídeo ou áudio (local)")
    ap.add_argument("--output-dir", required=True, help="Diretório de saída")
    ap.add_argument("--model", default=None, help="Modelo faster-whisper (default: auto por device)")
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--language", default=None, help="Código do idioma (default: auto-detect)")
    ap.add_argument("--num-speakers", type=int, default=None)
    ap.add_argument("--no-diarize", action="store_true")
    ap.add_argument("--hf-token", default=None)
    args = ap.parse_args()

    setup_cuda_dlls()

    t0 = time.time()
    panel = ProgressPanel()
    panel.start()
    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Arquivo não encontrado: {source}")

    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    device = detect_device(args.device)
    model_size = args.model or default_model_for(device)
    log(f"device={device} model={model_size} source={source.name}")

    try:
        panel.update("Extraindo áudio", 0, "Preparando a faixa de áudio localmente")
        duration = media_duration(source)
        audio_path = extract_audio(source, out_dir / "audio.wav")
        panel.update("Carregando modelo", 8, "O modelo de transcrição está sendo preparado na GPU")

        progress_path = out_dir / "progress.log"
        progress_path.write_text("", encoding="utf-8")  # reset from any previous run
        segments = transcribe_words(
            audio_path, model_size, device, args.language, progress_path=progress_path,
            on_progress=panel.update, total_seconds=duration,
        )
        segments = dedupe_hallucination_loops(segments)

        diarized = False
        hf_token = args.hf_token or os.environ.get("HF_TOKEN")
        if not hf_token:
            try:
                from huggingface_hub import get_token
                hf_token = get_token()
            except ImportError:
                hf_token = None

        if not args.no_diarize and hf_token:
            panel.update("Separando locutores", 78, "Analisando as vozes da reunião")
            with progress_path.open("a", encoding="utf-8") as f:
                f.write("\n--- diarização (separando locutores) ---\n")
            try:
                turns_raw = diarize(audio_path, hf_token, device, args.num_speakers)
                segments = assign_speakers(segments, turns_raw)
                diarized = True
                with progress_path.open("a", encoding="utf-8") as f:
                    f.write("--- diarização concluída ---\n")
            except Exception as exc:  # noqa: BLE001
                log(f"diarização falhou, seguindo sem locutor: {exc}")
                with progress_path.open("a", encoding="utf-8") as f:
                    f.write(f"--- diarização falhou: {exc} ---\n")
        elif not args.no_diarize:
            log("sem HF_TOKEN configurado — pulando diarização (transcrição segue sem locutor)")

        panel.update("Gerando arquivos", 96, "Salvando transcrição e metadados")
        turns = merge_into_turns(segments) if diarized else [
            {"start": s["start"], "end": s["end"], "speaker": None, "text": s["text"]} for s in segments
        ]

        (out_dir / "transcript.json").write_text(
            json.dumps({"diarized": diarized, "segments": segments, "turns": turns}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_markdown(turns, out_dir / "transcript.md", diarized)

        elapsed = time.time() - t0
        speakers = sorted(set(t["speaker"] for t in turns if t.get("speaker"))) if diarized else []
        metadata = {
            "source": str(source),
            "device": device,
            "model": model_size,
            "diarized": diarized,
            "speakers": speakers,
            "elapsed_seconds": round(elapsed, 1),
        }
        (out_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        panel.finish("Transcrição e arquivos prontos.")
        log(f"concluído em {elapsed/60:.1f} min — transcript.md, transcript.json, metadata.json em {out_dir}")
        print(json.dumps(metadata, ensure_ascii=False))
        return 0
    except Exception as exc:
        panel.fail(str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
