---
name: concise-reply
description: Force the answer into Mike's accessibility format AS A SELF-CONTAINED HTML FILE that auto-opens in the browser — big visual diagrams first, tiny captions, one decision at a time, recommend-don't-list. Use when Mike runs /concise-reply or says "be clear", "too long", "I can't read that", "make me an html", "give it to me concisely", or when a reply is drifting into walls of text.
---

# concise-reply

You are running the **concise-reply** skill.

Mike has **dyslexia and ADHD**. He HATES reading. Terminal walls of text —
even short ones — are the **worst possible** answer for him. This skill's job
is to STOP replying in chat prose and instead **build a visual HTML file and
open it in his browser.** Pictures and diagrams do the talking; words barely
appear.

> Direct from Mike: *"I have dyslexia. I do not have the capacity to read more
> than fifty words... unless there is diagrams, unless there is pictures,
> unless it's concise, unless it's easy to understand, unless you break it up
> simply."*

If `/concise-reply <text>` was given an argument, that argument is the question
or draft you must render as the HTML file. If no argument, render whatever you
were about to say next as the HTML file instead.

---

## The hard rule: ALWAYS produce an HTML file

Every time this skill runs you MUST:

1. **Write a self-contained `.html` file** to `/tmp/concise/<short-slug>.html`
   (create the dir; one file per answer; slug from the topic).
2. **Open it** for Mike:  `open /tmp/concise/<short-slug>.html`  (macOS).
3. In the **chat**, say almost nothing — one line: *"Opened → `<path>`"* plus
   the single decision/ask. The thinking lives in the HTML, not the chat.

Never answer the question in chat prose and *then* offer an HTML file. The HTML
file IS the answer.

---

## What goes IN the HTML (in this order, top to bottom)

| Block | What it is | Rule |
|-------|-----------|------|
| **1. Big diagram** | The answer as a picture — flow, boxes+arrows, before/after, decision tree | First thing on the page. Large. No paragraph above it. |
| **2. One-line caption** | Plain-language summary of the diagram | ≤ 15 words |
| **3. Recommend banner** | If there's a choice: `Recommend X — because Y` in a colored box | Comes BEFORE any comparison table |
| **4. Compare table** | Options side by side, only if a choice exists | Short cells, icons (✅ ❌ ⚠️) over words |
| **5. How it works** | Numbered steps, each ≤ 10 words, each with an emoji/icon | Steps, never a paragraph |
| **6. How it's tested** | What proves it worked — a checklist or a "you'll see X" line | Concrete + visual |
| **7. Background** | Any extra context, collapsed inside `<details>` so it's HIDDEN by default | Mike opens it only if he wants it |
| **8. The ONE ask** | The single decision, big, at the bottom, in a colored box | Exactly one open question |

Every section title is one or two words with an emoji. If a section would be a
paragraph, convert it to a diagram, list, or table instead.

---

## HTML style (make it easy on dyslexic eyes)

- Big font (18px+ body, huge headings), generous spacing, high contrast.
- Dyslexia-friendly font stack:
  `font-family: 'Comic Sans MS','Trebuchet MS',Verdana,sans-serif;`
- Color-code blocks: green = recommended / good, red = avoid, amber = caution,
  blue = info. Left color bar on each card.
- Use inline SVG **or** simple HTML boxes-and-arrows for the diagram (no
  external libs, no network). A `<pre>` ASCII diagram is acceptable as a
  fallback, but a real boxed/SVG diagram is better.
- Self-contained: all CSS inline in a `<style>` tag, no CDNs, no JS required
  (a tiny bit of JS for `<details>` is fine but optional).
- Short lines. Never a wide block of text. Wrap thoughts in cards.

---

## Chat reply rules (the few words you DO type)

- ≤ 50 words of prose, total, ever.
- First line: `Opened → /tmp/concise/<slug>.html`.
- Last line: the single ask/decision.
- Nothing else. No summary of the HTML — that defeats the purpose.

---

## Self-check before you send

If any box is "no", fix it before sending.

```
[ ] Did I WRITE an .html file and run `open` on it?
[ ] Is the FIRST thing in the HTML a diagram/picture (not prose)?
[ ] Background hidden inside <details>?
[ ] Exactly ONE decision open (in chat AND in the HTML)?
[ ] If a choice exists, a Recommend banner is above the table?
[ ] Chat reply ≤ 50 words, ask on the last line?
[ ] Dyslexia-friendly: big font, color cards, icons over words?
```

---

## After this reply

Governs **one** reply. Mike re-runs it, or says "stay clear" / "keep it this
way" to apply the HTML-file format to every reply for the rest of the session
without being asked.

> Source of truth for *why*: the accessibility hard rule in
> `~/.claude/CLAUDE.md`. This skill is the on-demand enforcement of that rule.
