from pathlib import Path

P = Path('prompts'); P.mkdir(exist_ok=True)

CAVEMAN = ("CAVEMAN MODE. Talk caveman. Drop 'the', 'a', 'is', 'are', 'that', 'to', 'of' when meaning still clear. "
           "Short words. Grunt-style. THINK in caveman too, not just output. Save word. Save token. Still solve task correctly.\n\nTASK:\n")
HARDCAP = ("OUTPUT CONSTRAINTS: Respond in the minimum tokens possible. No preamble, no disclaimers, no restating the task, "
           "no closing remarks. Hard cap: 150 output tokens. Use terse bullets, short phrases, or JSON as fits the task.\n\n")
HTML = "\n\nRespond with a complete standalone HTML document (with <!doctype html>, <head>, <style>, <body>) that presents the task and your answer clearly."
SPRPRE = "INPUT IS SPR-COMPRESSED (stopwords stripped, prose condensed). Interpret charitably.\n\n"

T1_CODE = Path('inputs/task1_buggy_code.py').read_text()
T2_CODE = Path('inputs/task2_code_for_tests.py').read_text()
T3_DOC  = Path('inputs/task3_legal_snippet.md').read_text()
T4_DOC  = Path('inputs/task4_meeting_transcript.md').read_text()
T5_DOC  = Path('inputs/task5_resume_snippet.md').read_text()
T6_DOC  = Path('inputs/task6_word_problem.md').read_text()

BASE = {
 't1_bugs': "The following Python code has one or more subtle bugs. Identify the bug(s) and propose a specific fix for each. Code:\n\n" + T1_CODE,
 't2_tests': "Write unit tests for the following Python class that would achieve >90% branch coverage. Use pytest style. Code:\n\n" + T2_CODE,
 't3_legal': "Summarize the following contract section for a non-technical reader, and define the key legal terms in plain language.\n\n" + T3_DOC,
 't4_meeting': "Summarize the following meeting transcript as bullet points covering the key decisions/points and the next steps / action items.\n\n" + T4_DOC,
 't5_extract': "Extract information from the following resume into a JSON object with fields: name (string), years_experience (integer), skills (array of strings), most_recent_role (object with title, company, dates). Respond with only the JSON object.\n\nResume:\n\n" + T5_DOC,
 't6_math': "Solve the following word problem. Show your work and give a final numeric answer.\n\n" + T6_DOC,
}

DETAILED = {
 't1_bugs': "You are reviewing Python code for correctness. Read every function carefully. For EACH bug: (1) name the function it lives in, (2) quote the exact line or expression that is wrong, (3) explain why it is wrong in one sentence, and (4) show the specific code change that fixes it. Check for off-by-one errors, wrong sort order, missing edge cases, and any place a docstring or function name contradicts what the code actually does. Do not invent bugs that are not real. Code:\n\n" + T1_CODE,
 't2_tests': "Write a pytest-style test suite for the following Python class targeting >90% branch coverage. Enumerate every documented rule (grace period, minimum fee, maximum cap, weekend exclusion, rounding, non-positive balance short-circuit, and the `today` injection). Write ONE test per rule with a clearly-named function (e.g. test_returns_zero_when_balance_is_zero). Use small, deterministic date fixtures. Do not test private helpers directly if you can hit them through the public API. Code:\n\n" + T2_CODE,
 't3_legal': "You are explaining a contract section to a business owner with no legal training. Do two things: (1) In 5-8 short bullet points, translate what the section actually requires each party to do, and when the promises do or do not apply. Include the dollar cap and its exceptions. (2) Then, in a 'Key terms' glossary, define each of the following in one plain sentence: indemnify / hold harmless, third-party claim, gross negligence vs. willful misconduct, intellectual property infringement or misappropriation, consequential / incidental / punitive damages, cap on liability, sole control of the defense, materially prejudiced. Avoid legalese; use everyday words.\n\n" + T3_DOC,
 't4_meeting': "Produce a structured summary of the following meeting transcript. Include: (1) 'Key points' — bullet list of every decision made or major discussion outcome, one line each. (2) 'Action items' — bullet list of every commitment, in the form 'Owner: what, by when'. Include the anchor decisions on reconciliation, the mobile receipt-capture scope call, the vendor payout SLA plan, the Q4 push of audit-log retention, and the on-call rotation ask. Do not include chit-chat or restate the transcript.\n\n" + T4_DOC,
 't5_extract': "Extract the following fields from this resume into a single JSON object. Rules: 'name' is the person's full name as written; 'years_experience' is the single integer count of years of professional experience stated in the summary (not computed from dates); 'skills' is a de-duplicated flat array of the skill strings listed in the Skills section, preserving order; 'most_recent_role' is the CURRENTLY-HELD role (dates end with 'present') with keys 'title', 'company', and 'dates'. Respond with ONLY the JSON object, no code fences or commentary.\n\nResume:\n\n" + T5_DOC,
 't6_math': "Solve this word problem step by step. Enumerate: (1) base fees per case type, (2) subtotal, (3) surcharge applied, (4) electronic-filing credits per case type and total credit, (5) net collected, (6) the courthouse's 82% share. Watch for irrelevant numbers explicitly stated to be out of scope. Give the final answer as a single dollar figure rounded to the nearest dollar on its own line, prefixed 'FINAL:'.\n\n" + T6_DOC,
}

for task, base in BASE.items():
    (P / f'{task}__c1_baseline.txt').write_text(base)
    (P / f'{task}__c2_detailed.txt').write_text(DETAILED[task])
    (P / f'{task}__c3_caveman.txt').write_text(CAVEMAN + base)
    (P / f'{task}__c4_html.txt').write_text(base + HTML)
    (P / f'{task}__c6_hardcap.txt').write_text(HARDCAP + base)
    spr = Path(f'spr/{task}.txt')
    (P / f'{task}__c7_spr.txt').write_text(SPRPRE + spr.read_text())

print(len(list(P.glob('*.txt'))), 'prompts written')
