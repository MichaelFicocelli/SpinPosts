Can you shrink your LLM bill by rewording the prompt?

I kept hearing the same question in different forms: "does it actually matter how I word the prompt, or is that just vibes?" Prompt length affects the input token count in an obvious way, but the response length is where most of the cost lives, and that is much harder to reason about ahead of time. So I ran a small experiment to find out.

The setup was straightforward. I picked six everyday tasks a developer might hand to an LLM (find bugs in a code snippet, write unit tests, summarize a legal clause, summarize a meeting transcript, extract a resume to JSON, do some chained arithmetic), and eight prompt conditions I wanted to compare against a plain baseline. Every combination ran through Opus 4.7, Sonnet 4.5, Fable 5.1, and GitHub Copilot on GPT-5.4. A coworker later re-ran the same sweep through Codex CLI on two variants of GPT-5.6 (terra and luna). Every answer was scored against a fixed rubric so I could see whether a token savings came with an accuracy cost.

Full data and the interactive per-run breakdown is in the accompanying report. Here I'll just walk through what worked and what didn't.


The tricks that worked

Tell the model to talk like a caveman

This one sounds like a joke and I did not expect it to work. The prompt:

    CAVEMAN MODE. Talk caveman. Drop 'the', 'a', 'is', 'are', 'that', 'to', 'of' when meaning still clear. Short words. Grunt-style. THINK in caveman too, not just output. Save word. Save token. Still solve task correctly.

Response tokens dropped by about 25% on average, and accuracy did not move. The model rewrites its own thinking style, drops articles and stopwords, and stays coherent. There is a floor to how much you can cut this way (code and JSON aren't affected), but for prose-heavy answers it's a free win. Try it. It's ridiculous. It works. Credit to juliusbrussee/caveman on GitHub for planting the idea.


Strip filler from the input

For long inputs, run them through a stopword-stripping preprocessor before sending. Same idea as caveman-speak but on the way in instead of the way out. This is often called SPR (Sparse Priming Representations). Savings on this one were modest, around 5-15% depending on the model, and there was no accuracy hit. A useful thing to have in the back pocket when you're paying by the input token and the input is huge.


Cap the output length

The single biggest lever was also the dumbest one. Prepend this to the prompt:

    OUTPUT CONSTRAINTS: Respond in the minimum tokens possible. No preamble, no disclaimers, no restating the task, no closing remarks. Hard cap: 150 output tokens. Use terse bullets, short phrases, or JSON as fits the task.

That's it. Average total tokens dropped by 40-50% across all six models, and the answer was still correct on most tasks. Older Opus skipped items from long checklists to fit the cap, and Codex Luna managed to blow the arithmetic answer under it, but Sonnet, Fable, Copilot, and Codex Terra all held their scores. If you find yourself paying for a paragraph of "I'll be happy to help you with..." on every call, this fixes it.


The tricks that did not work

Write very detailed instructions

I expected long, prescriptive prompts ("quote the exact line, list every documented rule, prefix your final answer with FINAL:, etc.") to help. Sometimes they did. Fable 5.1 hit -19% on total tokens for detailed instructions, because the specificity kept the response tight. But on Opus 4.7 the same prompts cost more (+9%) because the model responded to the level of detail by writing more detail back. Across the six models it more or less washed out. Not a reliable savings tool.


Wrap CLI reads through a filtering proxy

For the two tasks where the model would invoke command-line tools, I tried the `rtk` proxy, which trims the stdout the model actually sees. Every Claude Code sub-agent spent more with it than without: Opus +15%, Sonnet +23%, Fable +14%, Copilot +30%. The sub-agents responded to each read being cheaper by making more reads. Codex, which reaches for the shell more naturally, did squeeze a small saving out (Terra -17%, Luna -8%) but flunked one of its four applicable runs. So: probably a real technique in the right harness, but it isn't a token-saver by default.


Stack everything together

I combined the three winners (caveman + hard output cap + SPR input) into one prompt to see if the savings would compound. They did (44% total token reduction), but accuracy dropped by about 18 points. The combo was fine on short-answer tasks like arithmetic and JSON extraction, and terrible on long checklist tasks like the legal summary, where the 150-token cap and the caveman speech pattern together made the model skip items. So: worth stacking when the answer is short and structured. Not worth stacking when you're paying the model to be thorough.


Ask for a pretty HTML report

I wanted to check whether asking for a nice, formatted output was expensive. It is. Tacking a "give me the answer as a complete standalone HTML document" onto the prompt roughly doubled the total tokens (a 55-150% jump depending on the model), for the same answer. The extra tokens all went into `<style>` blocks and structural boilerplate. It is unquestionably easier to read, but it comes at a token cost.


A model note

Model choice moves the bill about as much as any prompt trick does. Codex (both GPT-5.6 variants) came in below every Claude model on total tokens across most conditions, sometimes by 30-40%. Fable 5.1 sat about 15% above Sonnet 4.5 on the same tasks. Accuracy isn't free either way. Codex Luna failed the arithmetic task at baseline, hard-cap, and stripped-input, where every other model got it right. It's a lever that doesn't ask you to change any of your prompts, but it does ask you to check the answers before you swap.


What to actually do with this

If you want the smallest, safest change: add the output cap. It's a one-line prepend and it saves you a lot of tokens on almost every task on almost every model.

If you want the ridiculous but free-feeling one: try caveman-speak. Show it to a coworker and see if they think you're joking.

If you're building something that fans a lot of long inputs through an LLM: strip stopwords on the way in.

Finally, instruct your agent to spin up sub-tasks that use the right models for the job. Use the token-expensive ones when you really need max effort, and the lighter and cheaper ones otherwise.
