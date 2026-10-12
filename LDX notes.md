Defining the problem is key to success
Measuring current stats is key to identifying the problem
Pick success criteria before trying anything

Mentoring
- Can juniors explain what they are doing? Confidence gap - code looks ok, build is green, but what is it?
- Where is the opportunity to break things to learn? AI fills in the gaps too quickly

- Exercise: AI off
  - Manual code session
  - Take a real ticket-size problem from the codebase
  - Take time to handwrite solution
  - Have AI propose prose designs based on writing.
    - What did the AI do that you didn't?
    - What did you know that the AI didn't?

- Exercise: Code Smell Detection
  - Code smells - early warning of deeper problem
  - Quizzes are fun, better than blank pages


Form a view before the machine speaks: design and plan first, state the problem, then consult
Own the output: Do not ship code you cannot explain
Break it: looking for the places where fluent prose was covering for a claim I could not actually support

be able to explain every line they did not write, defend the reasoning behind it, and own the result as if they had typed it themselves



----  

Are we growing engineers? Or are we just producing engineer-shaped output?

Have you written a bug?
Have you accidentally shown a bug in a demo?
Have you shipped a feature that didn't work?
Have you deleted important data?
Have you broken prod?

Senior Developer (n) : A person who is running low on mistakes they _haven't_ made


How we learned
Stubborn bugs and flaky tests forced us to make a guess, test it, be wrong, and repeat, many many times.
Learn to notice the difference between “it doesn’t work” and “it works, but not when the input is empty on a Tuesday.”


AI removes the resistance, and the resistance is the teacher.
teaching was a side effect of the difficulty, and we optimized the difficulty away.


https://www.anthropic.com/research/AI-assistance-coding-skills
two groups of juniors took on the same task that used an unfamiliar library
half used AI, half worked by hand
Both groups finished in the same amount of time.
Then they quizzed everyone on the code they had just produced. The hand-coding group scored 67 percent. The AI group scored 50 percent, nearly two letter grades lower, on their own code, minutes after writing it.
The widest gap of all was on the debugging questions, which is the one skill you need to supervise an AI in the first place. The study found a seventeen-point comprehension gap without establishing a speed benefit.


Developing deep technical knowledge and good instincts no longer comes for free in our day-to-day jobs the same way that it used to. Mentorship needs to be more deliberate and structured than ever before to close that gap.

Do you reach for the debugger with a hypothesis, or with a prayer, or not at all?
Do you see the edge case before it bites you?


Strategies:

- Every session ends with an artifact.
  - Not just "let's discuss" - a written design note, decision log, or list of ways the code could break.
  - One person owns it and shares it

- Session: Take a real task. Before you consult with anyone/anything, tell me what you would build.
  - Pick something you actually have to build this sprint, and spend ten minutes writing down how you’d build it.
  - Not in code, just in plain English. Your designs, plans, and guesses.
  - After, the notes come onto the shared screen and the room argues about them.
    - The writing is the friction and the discussion is the reward, and you need them in that order
  - After writing, make a "complexity budget" in a few words.
    - about how many files should this touch?
    - about how many public types should this add?
    - Should this introduce new dependencies?
    - what areas should this be limited to?
    - Once prompting later, tweak these numbers. What changes? What is the tradeoff between simplicity and capability?
  - Writing prompts to help:
    - What is this, in one sentence, from the user’s point of view?
    - What are the main pieces, and what is each one responsible for?
    - What states can it be in, including the ugly ones: empty, loading, failed,
      offline?
    - What is the one edge case most likely to bite?
    - How would I test it, and what is the first test I’d write?
    - What would worry me in production?
    - What am I least sure about?

- Session: Review together. I asked them to walk me through a few of their biggest decisions.
  - asked why it was built that way
  - why not some other way?
  - how they’d debug it if it fell over in production at two in the morning

- Session: build a vocabulary for critiquing designs or code changes.
  - Complexity: how hard is it to understand and change?
  - Change amplification: when a small change forces edits in a ton of places
  - Cognitive Load: how much you have to hold in your head to work on a system or file
  - Unknown Unknowns: 

- Session: AI Decision Log
  - For every meaningful chunk of AI code, the engineer writes down
    four things:
    - what the AI decided
    - what they accepted
    - what they rejected / changed
    - what they still have to verify

- Session: Break it.
  - Pick an area of the code or a page in the app.
  - Come up with every way you can think of that will make it break
    - bad input, partial data, lifecycle, race conditions, retries, caching, feature flags
  - Afterwards, ask the AI to make a similar list
    - What parts are hallucinated?
    - what parts are not a concern?
    - what did it miss from your list?


Think first. Before you ask the AI for anything, form a view. Not a full design,
just an opinion: here is roughly what I think this should look like, here is the part
I’m unsure about, here is what would make it hard. Thirty seconds of opinion
is enough. The point is to walk into the exchange with something of your own,
because you can’t challenge an answer you have no alternative to. Skip this
step and everything after it collapses, because you have nothing to compare
the AI’s output against except the AI’s own confidence.

Ask. Now ask, and ask well. A vague prompt gets a vague, average answer,
the code equivalent of “it depends.” A good ask carries your thinking into the
request: the constraints, the platform, the thing you’re worried about. You will
see, again and again, that the quality of what comes back is mostly a reflection
of the quality of what went in.

Challenge. This is one of the moves people skip, and it is where the
teaching happens. The AI has handed you something confident and plausible.
Now attack it. Where does it hide complexity? What did it assume that you
never told it? What breaks if the input is empty, or the network drops, or the
user does the thing users always do? The attack should end in an opinion you
can defend. Sometimes that opinion is “this is actually right,” and recognizing
when the machine is right is its own hard skill. The attack is not only rhetorical:
run the code, feed it the ugly input, watch what happens. Verify is challenge
with evidence, and a whole session ahead is given to it.

Improve. Take what the challenge surfaced and do something with it. Reject
the parts that fail. Change the parts that are close. Ask again with what you
have learned. The output that ends up in the codebase should have passed
through a human who checked it and made a decision. Sometimes that means
keeping it as it is, with reasons.

Explain. Last, and least optional of all: say why. Out loud, to another person,
explain what this code does, how it works, and why it is built this way rather
than the three other ways it could have been. If you can do that calmly, in
your own words, the judgment is yours now. If you can’t, you’ve found the
exact edge of your understanding, which is the most useful thing a mentoring
session can produce.



The vocabulary I lean on comes almost entirely from one book, John
Ousterhout’s A Philosophy of Software Design.
3
I introduce a handful of its ideas in the first minutes of a session, one or two at a time, never as a lecture.

Complexity first, because it is the thing all the others describe. Complexity comes from badly drawn boundaries between the pieces of a system.

complexity is, roughly, anything about a
system’s structure that makes it hard to understand or change. That is the
whole test. Size doesn’t count, and neither does cleverness; a short, clever
module can be a nightmare and a long, plain one can be simple. What matters is
the cost to the next person who has to understand or change it. That reframing
moves the question from taste (“do I like this?”) to consequence (“what will this
cost whoever comes next?”).
Then the three shapes complexity takes, which become the things an
engineer actually scans for.

Change amplification: when one small change forces edits in many places.
You wanted to change the colour of a button and you are now editing nine files.
The design has smeared a single decision across the codebase, so every future
change to it costs nine times what it should.

Cognitive load: how much you have to hold in your head to work on a piece
of code safely. Length is a poor measure; a short function can carry a crushing
load. The measure that counts is how much you must hold at once before you
dare touch it. When the load is high, the bug lives in the gap between what you
remember and what is actually true.

Unknown unknowns: the worst of the three, because you can’t see them.
These are the things you would need to know to make a change correctly,
that the code gives you no way of discovering. You change what looks like a
local detail and break something three modules away that you had no reason
to suspect. Ousterhout argues this is the most dangerous form of complexity.
The least experienced engineers are hit hardest by it, because experience can
help you anticipate dependencies the code does not make obvious

smart vs dumb components / inversion of control

information leakage