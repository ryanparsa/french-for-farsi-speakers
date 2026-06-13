#!/usr/bin/env python3
"""
Only the Python standard library is needed. ffmpeg + ffprobe must be on PATH.
"""
import argparse
import base64
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

API_URL = "https://texttospeech.googleapis.com/v1beta1/text:synthesize"
SEG_DIR = os.path.join(os.path.dirname(__file__), "segments")

# Default voice per language code. Override per line with "voice".
# Browse: https://cloud.google.com/text-to-speech/docs/chirp3-hd
VOICES = {
    "fr": "fr-FR-Chirp3-HD-Achernar",
    "en": "en-US-Chirp3-HD-Achernar",
    # "fa": Google has no working Persian voice — needs a different provider.
}

# Shorthand voices: a line can set "voice": "f" or "m" instead of a full id.
VOICES_BY_GENDER = {
    "fr": {"f": "fr-FR-Chirp3-HD-Achernar", "m": "fr-FR-Chirp3-HD-Charon"},
    "en": {"f": "en-US-Chirp3-HD-Achernar", "m": "en-US-Chirp3-HD-Charon"},
}

# Per-line field defaults (see tasks/schema.json).
DEFAULT_PROVIDER = "google"
DEFAULT_SPEED = 1.0
DEFAULT_GAP = 1.5

# Output = one .mp4: AAC audio + a plain background + a soft (toggleable)
# subtitle track. Soft subs need a video track to render, hence the background.
VIDEO_SIZE = "640x360"
BG_COLOR = "0x101418"     # dark slate
AUDIO_BITRATE = "160k"


# --- Task / line resolution -------------------------------------------------
def resolve_line(line: dict) -> dict:
    """Apply defaults + pick the voice. Returns a fully-specified line."""
    if "lang" not in line or "text" not in line:
        sys.exit(f"Each line needs 'lang' and 'text': {line!r}")
    lang = line["lang"]
    raw = line.get("voice")
    if raw in ("m", "f"):                      # gender shorthand
        voice = VOICES_BY_GENDER.get(lang, {}).get(raw)
        if not voice:
            sys.exit(f"No '{raw}' voice for lang '{lang}'. Add it to "
                     f"VOICES_BY_GENDER in tts.py.")
    else:
        voice = raw or VOICES.get(lang)
    if not voice:
        sys.exit(f"No voice for lang '{lang}'. Add it to VOICES in tts.py "
                 f"or set 'voice' on the line.")
    return {
        "lang": lang,
        "text": line["text"],
        "voice": voice,
        "locale": "-".join(voice.split("-")[:2]),   # fr-FR-Chirp3-HD-A -> fr-FR
        "provider": line.get("provider", DEFAULT_PROVIDER),
        "speed": float(line.get("speed", DEFAULT_SPEED)),
        "gap": float(line.get("gap", DEFAULT_GAP)),
    }


# --- Synthesis & audio ------------------------------------------------------
def slug(text: str, maxlen: int = 32) -> str:
    """A short, human-readable, filesystem-safe version of the text."""
    s = re.sub(r"\s+", "-", text.lower().strip())
    s = re.sub(r"[^\w-]", "", s)          # keep letters (incl. accents), digits, - _
    return s[:maxlen].strip("-") or "x"


def clip_path(r: dict) -> str:
    """Cache filename: readable slug + a short content hash for uniqueness.
    The hash covers provider+voice+speed+text, so clips never collide across
    providers/voices/speeds. e.g.  fr-google-bonjour--d4614696.wav"""
    h = hashlib.sha1(
        f"{r['provider']}|{r['voice']}|{r['speed']}|{r['text']}".encode()
    ).hexdigest()[:8]
    speed_tag = "" if r["speed"] == 1.0 else f"-s{r['speed']:g}"
    return os.path.join(SEG_DIR, f"{r['lang']}-{r['provider']}-{slug(r['text'])}{speed_tag}--{h}.wav")


def synth_clip(r: dict, api_key: str):
    """Render one line to a lossless wav clip. Returns (path, was_cached)."""
    path = clip_path(r)
    if os.path.exists(path):
        return path, True
    if r["provider"] != "google":
        sys.exit(f"Provider '{r['provider']}' is not implemented yet "
                 f"(line: {r['text'][:40]!r}). Only 'google' works today.")
    audio = {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}
    if r["speed"] != 1.0:
        audio["speakingRate"] = r["speed"]
    body = json.dumps({
        "input": {"text": r["text"]},
        "voice": {"languageCode": r["locale"], "name": r["voice"]},
        "audioConfig": audio,
    }).encode()
    req = urllib.request.Request(f"{API_URL}?key={api_key}", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            content = json.load(resp)["audioContent"]
    except urllib.error.HTTPError as e:
        sys.exit(f"\nAPI error {e.code} for {r['voice']}:\n{e.read().decode()}\n")
    with open(path, "wb") as f:
        f.write(base64.b64decode(content))
    return path, False


def run_ffmpeg(cmd: list) -> None:
    """Run ffmpeg, surfacing stderr on failure instead of a bare traceback."""
    res = subprocess.run(["ffmpeg", "-y", *cmd], capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"\nffmpeg failed:\n{res.stderr[-1800:]}\n")


def silence_clip(seconds: float) -> str:
    """Return a cached wav of N seconds of silence (matches the LINEAR16 clips)."""
    ms = round(seconds * 1000)
    path = os.path.join(SEG_DIR, f"sil_{ms}.wav")
    if not os.path.exists(path) and ms > 0:
        run_ffmpeg(["-f", "lavfi",
                    "-i", "anullsrc=channel_layout=mono:sample_rate=24000",
                    "-t", f"{seconds}", path])
    return path


def ffprobe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


# --- SRT --------------------------------------------------------------------
def srt_time(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


def build_srt(cues) -> str:
    merged = []
    for start, end, text in cues:            # merge consecutive same-text cues
        if merged and merged[-1][2] == text:
            merged[-1][1] = end
        else:
            merged.append([start, end, text])
    return "\n".join(
        f"{i}\n{srt_time(s)} --> {srt_time(e)}\n{t}\n"
        for i, (s, e, t) in enumerate(merged, 1)
    )


# --- Driver -----------------------------------------------------------------
def collect_tasks(paths):
    """Expand paths into a sorted list of task .json files. A directory is
    searched recursively; the schema.json definition file is ignored."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            found = glob.glob(os.path.join(p, "**", "*.json"), recursive=True)
            out += sorted(g for g in found if os.path.basename(g) != "schema.json")
        else:
            out.append(p)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Render JSON task(s) to .mp4 (audio + soft subs) + .srt.")
    ap.add_argument("inputs", nargs="+",
                    help="one or more task .json files, and/or a folder of them")
    ap.add_argument("-o", "--out",
                    help="output basename (single-input only; default: same as input)")
    args = ap.parse_args()

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("Set GOOGLE_API_KEY first.")
    os.makedirs(SEG_DIR, exist_ok=True)

    files = collect_tasks(args.inputs)
    if not files:
        sys.exit("No task .json files found.")
    if args.out and len(files) > 1:
        sys.exit("-o/--out only works with a single input file.")

    for task_path in files:
        render_file(task_path, args.out, api_key)


def render_file(task_path: str, out: str, api_key: str) -> None:
    try:
        data = json.load(open(task_path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  (can't read {task_path}: {e}, skipped)")
        return
    lines = data.get("lines") if isinstance(data, dict) else None
    if not lines:
        print(f"  (no 'lines' in {task_path}, skipped)")
        return

    base = out or os.path.splitext(task_path)[0]
    mp4_path, srt_path = base + ".mp4", base + ".srt"

    print(f"Rendering {task_path} ...")
    clips, cues, offset = [], [], 0.0
    n_cached = n_new = 0
    for line in lines:
        r = resolve_line(line)
        path, cached = synth_clip(r, api_key)
        n_cached, n_new = n_cached + cached, n_new + (not cached)
        print(f"  {'· cache' if cached else '+ new  '}  [{r['lang']}] {r['text'][:44]}")
        dur = ffprobe_duration(path)
        clips.append(path)
        cues.append([offset, offset + dur, r["text"]])
        offset += dur
        if r["gap"] > 0:
            clips.append(silence_clip(r["gap"]))
            offset += r["gap"]

    if not clips:
        print(f"  (no lines in {task_path}, skipped)")
        return

    # Subtitle file (also muxed into the mp4 as a soft track).
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(build_srt(cues))

    # Concat list of the lossless wav clips (audio source).
    list_path = os.path.join(SEG_DIR, "_concat.txt")
    with open(list_path, "w") as f:
        for p in clips:
            f.write(f"file '{os.path.abspath(p)}'\n")

    # Mux -> one .mp4: plain background video + AAC audio + soft mov_text subs.
    # Inputs: 0 = concatenated audio, 1 = background, 2 = subtitles.
    run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", list_path,
        "-f", "lavfi", "-t", f"{offset:.3f}",
        "-i", f"color=c={BG_COLOR}:s={VIDEO_SIZE}:r=5",
        "-i", srt_path,
        "-map", "1:v", "-map", "0:a", "-map", "2:s",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-tune", "stillimage", "-crf", "30",
        "-c:a", "aac", "-b:a", AUDIO_BITRATE,
        "-c:s", "mov_text",
        mp4_path,
    ])

    print(f"  {n_new} new, {n_cached} reused from cache")
    print(f"  -> {mp4_path}  ({offset:.1f}s, audio + soft subs)")
    print(f"  -> {srt_path}  (also embedded in the mp4)")


if __name__ == "__main__":
    main()
