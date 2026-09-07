# Error Analysis

52 documents across Meta, YouTube, TikTok, X, and Reddit (868 chunks). 35 questions —
16 factual, 9 numerical, 7 comparison, 3 with no answer in the corpus — graded by hand
against the model's actual output. No question errored.

## Results

| Metric | Value |
| :--- | :--- |
| Hit rate@5 (headline retrieval metric) | 0.812 |
| Abstain accuracy on absent questions | 1.0 (3/3) |
| Answer grades | 29 correct, 6 incorrect, 0 partially correct, 0 unsupported |

**What hit rate@k measures, and what it doesn't.** For each answerable question: did at
least one of its `expected_chunk_ids` appear in the top k? It says nothing about *where* in
the ranking the hit landed, whether every relevant chunk was found, or whether the answer
actually used it. Recall@k or MRR would be needed for those. Finding 1 below shows a case
where it undercounts a system that is working correctly.

## Ablation 1: hit rate vs. k

`python eval/run_eval.py --ablation` retrieves once per question at k=10 and slices that
ranked list for each smaller k, so the whole sweep costs one query embedding per question
and no generation calls. Full output: `eval/results/ablation.json`.

| k | Hit rate@k | Δ vs. previous |
| :--- | :--- | :--- |
| 1 | 0.438 | — |
| 3 | 0.750 | +0.312 |
| 5 | 0.812 | +0.062 |
| 10 | 0.875 | +0.063 |

The curve is steep then flat: k=1→3 recovers 31 points, because for more than half of all
questions the single best-scoring chunk is not the one holding the answer. That gap is the
argument for retrieving several chunks and letting generation choose, rather than trusting
top-1. After k=3 the returns halve and halve again.

**Why k=5 remains the default** even though k=10 scores 6 points higher: hit rate measures
whether a usable chunk was *retrieved*, not whether the answer used it. Doubling the context
doubles prompt tokens, and this system's dominant failure mode (Finding 2) is the model
declining to answer from context it already has — noisier context is unlikely to help that.
The honest statement is that k=10 is worth testing end-to-end with grading, not that it is
better.

## Ablation 2: loosening the grounding rule

Three of the six failures are the model abstaining on questions whose supporting chunks
*were* retrieved. That points at the prompt rather than retrieval, so the obvious fix was
tested: keep rule 4 (no outside facts) but add a rule explicitly permitting the model to
count items the chunks list and to compare two things when both sides are present. Same
index, same questions, same k, temperature 0 — only the prompt differs, so retrieval and
hit rate are identical by construction. Full output: `eval/results/ablation_prompt.json`.

| | Baseline | Variant |
| :--- | :--- | :--- |
| Correct | 29 | 29 |
| Partially correct | 0 | 1 |
| Incorrect | 6 | 5 |
| Abstain accuracy on absent | 1.0 | 1.0 |

**Rejected, despite the marginally better grade split.** It missed both comparison
abstentions it was aimed at — Q16 was unchanged, Q18 produced a comparison but truncated
TikTok's doxxing definition to "publishing or threatening to publish", dropping the
"with malicious intent" that is the substance of the rule. And on Q14 it replaced a safe
abstention with a **confident miscount**: it answered "there are 10 distinct
protected-attribute categories" and then listed nine of them.

That trade is the wrong direction for this system. A researcher who reads "I could not find
an answer" goes and checks; a researcher who reads "10 categories" in a cited, confident
sentence does not. The over-abstention in Finding 2 is a real cost, but it is the visible
side of calibration that is mostly protecting us — the baseline prompt was kept.

## Finding 1: hit rate@k undercounts facts duplicated across documents

Q5 and Q6 both score `hit_at_5 = false` and both answered correctly and completely. The
YouTube advertiser-friendly category list is pinned to `DOC-18-002` but also appears in
`DOC-18-003`; the dangerous-challenge examples are pinned to `DOC-20-005` and also sit in
`DOC-20-006`. Retrieval surfaced the neighbour, generation answered from it correctly, and
the metric recorded a miss.

The same shape drives Q9's *real* failure, in reverse. YouTube's "what happens when you get
a strike" summary box is embedded verbatim near the end of nearly every YouTube help
article. Retrieval returned five copies of that box (`DOC-61`, `DOC-54`, `DOC-17`,
`DOC-58`, `DOC-16`) and never the pinned `DOC-15-002`. The boilerplate states the
policy-training rule but not the base rule, so the answer conflated the two: it reported
that a warning expires 90 days *after completing training*, when in fact a warning expires
after 90 days on its own and training clears it immediately.

**Why it matters:** a single pinned chunk id gets less meaningful as a corpus grows and
common facts appear in more documents — and near-duplicate chunks crowd out the canonical
one in the top k, which is a retrieval problem the metric cannot see.

**Fix to try:** build the ground truth as a fact's full duplicate-chunk set (exact-text
match across the corpus at test-set-build time) rather than one pinned id; and deduplicate
near-identical chunks at index time so five copies of one boilerplate box cannot occupy
five of the five slots.

## Finding 2: generation abstains on context it already has

Q14, Q16 and Q18 all retrieved their expected chunks at k=5 and still answered "I could not
find an answer to this in the corpus":

- **Q14** asks for a *count* of a list that is fully present in the retrieved chunk. The
  model treats counting as forbidden outside inference.
- **Q16 and Q18** ask for comparisons. Even with both sides in context, the model declines
  to synthesize across them.

Ablation 2 shows this is not simply a prompt-wording bug — explicitly licensing both
behaviours did not reliably fix them, and made Q14 worse. The model appears to have a
genuinely lower confidence bar for comparison- and aggregation-shaped questions,
independent of what it was told it may do.

**Fix to try:** handle these outside the prompt. Decompose comparison questions into
per-side retrievals and ask for each side separately, then compose the comparison
programmatically — so the model only ever answers single-source questions, which it does
well (29/35).

## Finding 3: cross-document comparison retrieval

Q20 and Q21 abstained having missed their expected chunks entirely. Both ask about two
topically distant documents at once — YouTube's illegal-goods vs. harmful-content policies,
and TikTok's vs. YouTube's awareness-content exceptions. A single embedded query for
"compare A and B" lands between A and B in embedding space rather than close to either.

This is the clearest structural weakness in the system. Comparison questions are 7 of 35 in
the test set, and 4 of the 6 failures (Q16, Q18, Q20, Q21) are comparisons — a 43% failure
rate on that category against 6% on everything else.

**Fix to try:** the same query decomposition as Finding 2. It addresses the retrieval half
and the generation half of the comparison problem at once, which is why it is the single
change I would make first with more time.

## Summary

Two weaknesses account for every failure. **Comparison questions** fail at both retrieval
(Finding 3) and generation (Finding 2), and one fix — decomposing them into per-side
queries — would target both. **Boilerplate duplicated across documents** (Finding 1)
distorts the retrieval metric in both directions and caused the one factually wrong answer
in the run, and would be addressed by index-time near-duplicate detection.

The grounding behaviour itself held up: 3/3 correct abstentions on questions with no
answer in the corpus, no fabricated citations across 35 answers, and — per Ablation 2 —
the abstention threshold is where it should be even though it costs three otherwise
answerable questions.
