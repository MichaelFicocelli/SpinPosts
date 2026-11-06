Can you shrink your LLM bill by rewording the prompt?

I just had hit my token limit. Again. That was the third time that week! It was a nice opportunity to take a break and write code, but it also got me thinking. What actually affects your token usage? Does anything you  change about your prompts or tools actually matter? So I ran an experiment to find out.

The setup was simple. I picked six different kinds of tasks a user might hand to an LLM (find bugs code, write tests, explain a technical document, summarize a meeting transcript, extract info to JSON, do some math), and eight prompt conditions I wanted to compare against a plain baseline. Every combination ran through Opus 4.7, Sonnet 4.5, Fable 5.1, and GPT-5.4. I measured the token usage, and also the accuracy, of each task. And the results were not what I expected.

Full data and the interactive per-run breakdown is in the [published report](https://michaelficocelli.github.io/SpinPosts/token-usage-experiment/). Here I'll walk through what worked and what didn't.


The tricks that worked

Tell the model to talk like a caveman

This one sounds like a joke and I did not expect it to work. The prompt:

    CAVEMAN MODE. Talk caveman. Drop 'the', 'a', 'is', 'are', 'that', 'to', 'of' when meaning still clear. Short words. Grunt-style. THINK in caveman too, not just output. Save word. Save token. Still solve task correctly.

Response tokens dropped by about 25% on average, and accuracy did not move. The model rewrites its own thinking style, drops articles and stopwords, and stays coherent. There is a floor to how much you can cut this way (code and JSON aren't affected), but for prose-heavy answers it's a free win. It's ridiculous. It works. Credit to juliusbrussee/caveman on GitHub for the idea.


Strip filler from the input

For long inputs, run them through a stopword-stripping preprocessor before sending. Same idea as caveman-speak but on the way in instead of the way out (called Sparse Priming Representations). Savings on this one were only around 5-15% with no accuracy loss. Situationally useful if the input is huge on a task.


Cap the output length

The single biggest prompt lever was also the most low-tech one. Prepend this to the prompt:

    OUTPUT CONSTRAINTS: Respond in the minimum tokens possible. No preamble, disclaimers, restating, or closing remarks. Hard cap: 150 output tokens. Use terse bullets, short phrases, or JSON as fits the task.

That's it. Average total tokens dropped by 40-50% across all six models, and the answer was still correct on most tasks. If you find yourself paying for a paragraph of "I'll be happy to help you with..." on every call, this fixes it.

Choose the right model for the job

Model choice made as big of a difference as any prompt trick did. GPT-5.6 came in below every Claude model on total tokens across most conditions, sometimes by 30-40%. Fable 5.1 sat about 15% above Sonnet 4.5 on the same tasks. Accuracy took a hit on some of the ligher models, however. It's a lever that doesn't ask you to change any of your prompts, but it does ask you to check the answers after you swap.



The tricks that did not work

Write very detailed instructions

I expected long, prescriptive prompts ("quote the exact line, list every documented rule, etc.") to help. Sometimes they did. Fable 5.1 hit -19% on total tokens for detailed instructions, because the specificity kept the response tight. But on Opus 4.7 the same prompts cost more (+9%) because the model responded to the level of detail by writing more detail back. Across the six models it more or less washed out. Not a reliable savings tool.


Wrap CLI reads through a filtering proxy

For the two tasks where the model would invoke command-line tools, I tried the `rtk` proxy, which trims the stdout the model actually sees. The sub-agents responded to each read being cheaper by making more reads. Not a significant help, at least in these small tasks. 


Stack everything together

I combined the three winners (caveman + hard output cap + SPR input) into one prompt to see if the savings would compound. They did (44% total token reduction), but accuracy dropped by about 18 points. The combo was fine on short-answer tasks like arithmetic and JSON extraction, and terrible on long checklist tasks like the legal summary, where the 150-token cap and the caveman speech pattern together made the model skip items. So: worth stacking when the answer is short and structured. Not worth stacking when you're paying the model to be thorough.


Ask for a pretty HTML report

I wanted to check whether asking for a nice, formatted output was expensive. It is. Tacking a "give me the answer as a complete standalone HTML document" onto the prompt roughly doubled the total tokens (a 55-150% jump depending on the model), for the same answer. The extra tokens all went into `<style>` blocks and structural boilerplate. It is unquestionably easier to read, but it comes at a token cost.


What to actually do with this

If you want the smallest, safest change: add an output cap (or restrict commentary, or try caveman-speak). It's a one-line addition to the prompt, and it saves a lot of tokens on almost every task & model tested.

If you're building something that fans a lot of long inputs through an LLM: strip stopwords on the way in.

Finally, instruct your agent to spin up sub-tasks that use the right models for the job. Use the token-expensive ones only when you really need max effort, and the lighter and cheaper ones otherwise.
