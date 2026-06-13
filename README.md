# 🇫🇷 French for Farsi Speakers

A French course written **for native Persian/Farsi speakers** — leaning on the
words Persian already borrowed from French and the huge overlap with English, so
you start from what you already know.

## 📚 Lessons

| File                                                     | What it covers                                      |
|----------------------------------------------------------|-----------------------------------------------------|
| [`00-pronunciation-guide.md`](00-pronunciation-guide.md) | French sounds, explained for Farsi speakers         |
| [`01-persian-loanwords.md`](01-persian-loanwords.md)     | French words Persian already uses (free vocabulary) |
| [`02-english-cognates.md`](02-english-cognates.md)       | French words that look like English                 |
| [`03-false-friends.md`](03-false-friends.md)             | *Faux amis* — words that look familiar but mislead  |
| [`04-foundation-core.md`](04-foundation-core.md)         | Core grammar: pronouns, articles, the glue          |
| [`05-root-clusters.md`](05-root-clusters.md)             | Word families grouped by root                       |
| [`06-freq-0001-0200.md`](06-freq-0001-0200.md)           | The most frequent words first                       |

## 🎧 Audio drills

The [`audio/`](audio/) folder turns small JSON "tasks" into bilingual
listen-and-repeat **MP4s** (audio + subtitles), using Google's premium
text-to-speech voices. Each drill is built on a **pattern** — a familiar anchor
word plus varied collocations — rather than flat word lists.

See [`audio/README.md`](audio/README.md) for how it works and how to write a task.

```bash
cd audio
export $(cat .env)            # your GOOGLE_API_KEY
python3 tts.py tasks/hello    # -> tasks/hello/hello.mp4 + .srt
```
