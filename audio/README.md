# 🎧 French Audio Drills

Turn a small **JSON task** into one self-contained **`.mp4`** (audio + toggleable
subtitles) plus a loose **`.srt`**, using premium Chirp3-HD voices.

```
tasks/<name>/<name>.json  ──tts.py──▶  <name>.mp4  +  <name>.srt
```

You write (or have an AI write) the JSON; `tts.py` renders each line to a TTS
clip, caches it, and stitches everything together.

## Setup

1. Put your Google API key in `audio/.env`:
   ```
   GOOGLE_API_KEY=your_key_here
   ```
   (Enable the **Cloud Text-to-Speech API** in Google Cloud first.)
2. Have `ffmpeg` + `ffprobe` on PATH (`brew install ffmpeg`).

## Run

```bash
cd audio
export $(cat .env)                 # load GOOGLE_API_KEY
python3 tts.py tasks/hello         # render the .json in one task folder
python3 tts.py tasks/              # render every task (recursive)
python3 tts.py tasks/hello/hello.json -o out   # single file, custom output
```

Output lands **next to** the source `.json`. Clips are cached in `segments/` and
reused across every task, so re-runs are mostly free (the run prints
`· cache` / `+ new`).

---

## The task JSON

A task is `{ "lines": [ … ] }`. The full spec is **`tasks/schema.json`** (a real
JSON Schema you can validate against). Each line:

| field | required | default | meaning |
|---|---|---|---|
| `lang` | ✅ | — | language code: `fr`, `en`, … → picks the voice |
| `text` | ✅ | — | what to say; also shown as the subtitle cue |
| `voice` | — | `VOICES[lang]` | `"f"` / `"m"` shorthand (female/male) **or** a full voice id |
| `provider` | — | `google` | only `google` works today (`azure`/`elevenlabs` reserved) |
| `speed` | — | `1.0` | `0.25`–`2.0`; for a slow repeat, add the line again at `0.7` |
| `gap` | — | `1.5` | seconds of silence after this line |

### The drill "item" shape we use

Each phrase is **three lines**: French, French slow, then the English meaning,
with a longer gap before the next item:

```json
{ "lang": "fr", "text": "une table" },
{ "lang": "fr", "text": "une table", "speed": 0.7 },
{ "lang": "en", "text": "a table", "gap": 2.5 }
```

~9s per item → **~64 items ≈ 10 minutes**.

### Two voices (conversations)

Use the `"f"`/`"m"` shorthand to alternate speakers:

```json
{ "lang": "fr", "text": "je m'appelle Marc", "voice": "m" },
{ "lang": "fr", "text": "je m'appelle Marc", "voice": "m", "speed": 0.7 },
{ "lang": "en", "text": "my name is Marc", "voice": "m", "gap": 2.5 }
```

---

## Writing a GOOD task file

The whole point is **patterns, not word lists.** Pick a familiar **anchor word**
and drill a few **varied** collocations around it — different structures each
time, not the same determiner repeated.

**❌ Repetitive (avoid):** same four determiners on every noun
```
le projet · un projet · mon projet · ce projet
le café   · un café   · mon café   · ce café
```

**✅ Varied (do this):** mix possessives, adjectives (before *and* after),
numbers, partitives, and real phrases
```
un projet · mon nouveau projet · un projet important · un grand projet
un café   · un café au lait    · deux cafés          · un café, s'il vous plaît
```

Principles:
- **Familiar anchors** stick best — cognates (`adresse`, `table`, `restaurant`)
  and Persian loanwords (`café`, `taxi`, `manteau`, `hôtel`).
- **Build-up / layering** is great for sentences:
  `mon nom → je m'appelle → je m'appelle Ryan → je viens → je viens du Canada`.
- **~16 anchors × ~4 variations = ~64 items ≈ 10 min.**
- Keep the **FR → FR(0.7) → EN** item shape for every phrase.

### French correctness checklist (the easy things to get wrong)
- Articles: `le`(m) / `la`(f) / `l'` before a vowel or mute h.
- `un`(m) / `une`(f); partitives `du` / `de la` / `des` ("some").
- Possessive `mon`/`ma`, but **`mon` before any vowel sound** (`mon adresse`,
  `mon idée`).
- Demonstrative `ce`/`cette`, `cet` before a masc vowel (`cet hôtel`).
- Adjective **agreement**: `bon/bonne`, `grand/grande`, `vieux/vieille`,
  `bleu/bleue`; invariable: `rouge`, `moderne`, `français→française`.
- Adjective **placement**: BANGS (Beauty, Age, Number, Goodness, Size — `bon`,
  `grand`, `petit`, `nouveau`, `beau`, `vieux`, `joli`, `premier`) go **before**
  the noun; colour / nationality / most others go **after**
  (`une cravate bleue`, `un restaurant français`).

---

## Prompt to generate a task with an AI

Paste this, fill in the topic, and drop the result in
`tasks/<name>/<name>.json`:

> Generate a JSON file for a French audio-drill task. Output **only** valid JSON
> (no markdown fences, no commentary) matching this shape:
> `{ "lines": [ { "lang": "...", "text": "...", ... } ] }`.
>
> **Goal:** pattern-based drilling. Pick ~16 **familiar anchor words** (French
> cognates of English, or words Persian already borrowed) on the topic of
> **\<TOPIC\>**. For each anchor, write **4 VARIED short collocations** — mix
> possessives, adjectives (some before, some after the noun), numbers,
> partitives, and one real everyday phrase. Do **not** repeat the same four
> determiners (the/a/my/this) on every word.
>
> **For every collocation, emit exactly three lines:**
> ```json
> { "lang": "fr", "text": "<french>" },
> { "lang": "fr", "text": "<french>", "speed": 0.7 },
> { "lang": "en", "text": "<english meaning>", "gap": 2.5 }
> ```
> So ~16 × 4 = ~64 items ≈ 10 minutes.
>
> **French must be correct:** right gender (un/une, le/la/l'), `mon` before
> vowels, adjective agreement and BANGS-before / other-after placement,
> partitives (du/des) where natural. Keep phrases short (1–4 words) and useful.
>
> For a two-speaker conversation instead, add `"voice": "m"` or `"voice": "f"`
> to each line and alternate speakers per topic.

After generating, sanity-check the file:
```bash
python3 -c "import json; d=json.load(open('tasks/<name>/<name>.json')); print(len(d['lines']),'lines')"
python3 tts.py tasks/<name>
```

---

## The cache (`segments/`)

Each line → one clip, named by content:
`fr-google-une-table--<hash>.wav` (lang-provider-slug-hash; slow clips get a
`-s0.7` tag). The hash covers provider+voice+speed+text, so identical lines are
reused across every task. Delete `segments/` anytime to force a clean rebuild.

## Notes
- **Voices**: default is Achernar (♀). Change `VOICES` (or per line `voice`) —
  browse https://cloud.google.com/text-to-speech/docs/chirp3-hd
- **Persian (`fa`)**: Google has no working Persian voice yet, so `fa` lines
  can't speak on `google` — they'd need `provider: "azure"` (not wired up yet).
- **Gemini voices** (style-prompt `Achernar` in the web demo) need Vertex AI
  auth, not a plain API key; Chirp3-HD Achernar is the same character and works.
