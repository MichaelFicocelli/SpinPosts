First meeting: Discussing Problems with agentic development
Core Problems with AI-Heavy Development

* Two notable problems, likely to exist regardless of where AI goes:
    * Developers are too removed from the code to build fundamentals
    * Generated code is hard to review: huge, plausible-looking even when wrong
        * Agentic development compounds the review problem
            * Imperfectly specified goals produce hacked outputs
            * Developer awareness of being stuck decreases as agents paper over it
            * Proliferating near-duplicate code makes future agent work worse too
* Atomic’s business rides on delivering quality code; both problems threaten that directly


Mentorship is harder, but more important than ever

* Having an easy place to ask for help reduces team communications & mentorship opportunities
* The “ask for help” skill is now broken as a signal
    * Previously, stand-up progress gaps or workflow frustration triggered a check-in
    * Now, AI masks that gap and makes it easy to never ask teammates
    * Strategies that used to work: normalizing help-seeking, retrospecting on spinning-wheels stories, explicitly repeating “come to me first”
        * All three are degraded or bypassed by AI side-channels
* Pairing during agentic development feels broken
    * driver/navigator dynamic doesn’t apply; everyone is idle during generation
* Small teams (2-3 people) make proactive mentorship especially hard


Mitigation Ideas

* Use AI time savings for more mentorship, lunch-and-learns, and deliberate manual development
    * Leadership has given explicit approval to invest freed-up time this way
    * Risk: older processes included training implicitly; the new one requires active diligence to replace it
* Possible new "role" or hat: mentor focused on breaking silos more than crushing sprint work
* Paired code walk-through for large code reviews
    * Forces the developer to explain and own the code
    * Surfaces “what does this do?” questions naturally
    * Helps with the review problem too: slower, human-paced pass catches flagrant issues
* Use pairing more for planning and design, then execute separately
* Normalize and promote good code quality practices
    * Direct human interaction with the code
    * Discuss questions with team, not just the bot
    * Foster deliberate, diligent mentorship culture
    * Train protege(s) to have both core technical skills as well as silo-busting mentorship skills

* Learning to use LLMs as teachers/explainers/thought partners
* Senior devs holding junior devs accountable for really understanding what they're delivering



--------

Lunch and Learn / AMA

How to be involved in key decisions:
    Plan out in advance where you want it to ask you questions, or pick a tool that interviews you first
    Bring in humans on spec before implementing
    Dial in your scope to be smaller and more focused

Claude / codex hooks:
    deterministic places or gates where code can be run
    e.g. run lint before commit
    main .md instruction files are ignored - use these to enforce good practice

Pairing practices:
    dive into more detailed planning together
    Record meetings, especially technical and alignment meetings


Rob blog post on permissions / auto-mode
https://spin.atomicobject.com/permission-fatigue-claude-code/

Set up a sandbox!

make it quiz you
https://github.com/mattpocock/skills/blob/main/skills/productivity/grilling/SKILL.md