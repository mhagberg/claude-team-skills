---
name: clear-reply
description: Force the next answer into Mike's accessibility format — diagram/table first, ≤50 words of prose, one decision at a time, recommend-don't-list, request on the last line. Use when Mike runs /clear-reply or says "be clear", "too long", "I can't read that", "give it to me concisely", or when a reply is drifting into walls of text.
---

# clear-reply

You are running the **clear-reply** skill. It is a hard formatting gate for the
reply you are about to give. Mike has **dyslexia and ADHD** — this is a
cognitive constraint, not a style preference. He cannot read more than ~50
words of prose and loses the thread without a visual.

If `/clear-reply <text>` was given an argument, the argument is the question or
the draft you must re-render in this format. If no argument, apply the format
to whatever you were about to say next.

## The format — ALL of these, every time

1. **Lead with a visual.** First thing in the message is a diagram, table, or
   ASCII art. If you cannot think of a visual, you have not understood the
   answer well enough yet — stop and find the structure.
2. **≤50 words of prose, total.** Code blocks, tables, diagrams, ASCII do NOT
   count toward the 50. Prose sentences do. Count them.
3. **ONE decision at a time.** Show one chunk → ask → wait. Never stack two
   open questions or two decisions in one message.
4. **Recommend, don't list.** If there's a choice, lead with
   `**Recommend X — because Y**`, THEN show the comparison table. Never dump
   options and make Mike choose cold.
5. **Request on the LAST line.** Anything you need Mike to do or decide goes on
   the final line of the message. He will not read a request buried higher up.

## Anti-patterns — do NOT do these

- ❌ A paragraph before the first visual
- ❌ Multiple questions / multiple decisions in one reply
- ❌ "Here are the options…" with no recommendation
- ❌ Burying the ask in the middle
- ❌ A long status dump that requires scrolling

## Self-check before you send

Run this gate. If any answer is "no", rewrite before sending.

```
[ ] First element is a diagram/table/ASCII?
[ ] Prose ≤ 50 words (counted, code/tables excluded)?
[ ] Exactly ONE decision or question open?
[ ] If a choice exists, a Recommend line is first?
[ ] The ask is on the very last line?
```

## After this reply

This skill governs **one** reply. Mike will run it again, or say "stay clear",
if he wants it to persist. If he says "stay clear" / "keep it this way", apply
the format to every reply for the rest of the session without being asked.

> Source of truth for *why*: the accessibility hard rule in
> `~/.claude/CLAUDE.md`. This skill is the on-demand enforcement of that rule.
