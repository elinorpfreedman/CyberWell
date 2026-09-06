# Error Analysis

Run against the current (partial) index: 8 usable documents (7 YouTube + 1 TikTok --
see the corpus-completeness caveat at the bottom). 25 questions, graded by hand.

## Results

| Metric | Value |
| :--- | :--- |
| Hit rate@3 | 0.762 |
| Hit rate@5 | 0.857 |
| Ablation delta (5 - 3) | +0.095 |
| Abstain accuracy on absent questions | 1.0 (4/4) |
| Grades | 22 correct, 2 partially correct, 1 incorrect, 0 unsupported |

## Finding 1: a chunk-overlap boundary artifact caused two real errors

`src/chunking.py` splits on a fixed character window with 150 characters of overlap.
For `DOC-15` (YouTube's strike system), the "Second Strike" heading and its qualifying
clause ("if you get a second strike **within the same 90-day period as your first
strike**...") landed in chunk `DOC-15-005`, but chunk `DOC-15-006` -- built from the
150-char overlap -- opens mid-sentence with just the tail: *"first strike, you will not
be allowed to post content for 2 weeks."* Read in isolation, that fragment reads as "a
first strike costs you 2 weeks," which is wrong (a first strike is 1 week; 2 weeks is
the second-strike penalty).

Both chunks were retrieved together in every case this came up, so the model had the
correct context available, but still leaned on the misleading fragment:
- **Q10** ("how long after a first strike") led with the wrong "2 weeks" claim, then
  separately and correctly cited `DOC-15-004` for 1 week later in the same answer --
  self-contradictory.
- **Q17** (compare first through third strike) stated 2 weeks for *both* the first and
  second strike, collapsing the exact escalation the question asked about.

**Why it matters:** this is a structural chunking problem, not a retrieval or prompt
problem -- overlap-based splitting can sever a heading from the sentence that gives it
meaning, producing a fragment that reads as complete and confident but is actually
misattributed.

**Fix to try:** chunk on structural boundaries (headings, list items) instead of a pure
character count, or at minimum prefix each chunk with the nearest preceding heading so a
fragment can't lose its "which strike is this" context.

## Finding 2: cross-document comparison questions have a real retrieval gap

All 3 comparison questions whose two facts live in different, topically-distant
documents (Q19: advertiser guidelines vs. hate speech; Q20: illegal goods vs. harmful
content; Q21: TikTok bullying exceptions vs. YouTube EDSA) retrieved **zero** of their
expected chunks at k=5. A single embedded query for "compare X and Y" tends to land
between X and Y in embedding space rather than close to either one specifically, so nothing
genuinely relevant surfaces.

The system did the *right* thing given that miss -- it correctly abstained rather than
answering from irrelevant retrieved context, so these are graded "correct," not
"incorrect." But the practical effect is the same as not having an answer: the corpus
does contain the information, retrieval just didn't find it. In contrast, the two
comparison questions that succeeded (Q16, Q18) both had their two facts living in the
same or adjacent documents, which a single query handles fine.

**Fix to try:** query decomposition for comparison-shaped questions -- split "compare A
and B" into two separate retrievals (one biased toward A, one toward B) and merge the
results, instead of embedding the compound question as one query.

## Finding 3: one unnecessary abstention on a derivable answer

Q14 ("how many protected-attribute categories") retrieved the correct chunk
(`DOC-12-001`) at both k=3 and k=5 -- it lists all 9 attributes verbatim -- but the model
refused to answer because the source text never states the number "9" explicitly. It
declined to simply count a list that was fully in front of it.

**Why it matters:** the grounding instruction ("don't fill gaps with outside knowledge")
is working as intended for facts not in the corpus, but it's also suppressing a trivial,
zero-risk inference (counting retrieved items) that isn't "outside knowledge" at all.

**Fix to try:** soften the system prompt to explicitly allow simple counting/aggregation
over the retrieved text itself, while keeping the no-outside-facts rule intact for
everything else.

## Corpus-completeness caveat

This run only exercises 8 of the 37 documents in the current manifest (7 YouTube + 1
TikTok) -- the rest either haven't been fetched yet or were fetched but turned out to be
JS-shell/nav-boilerplate content, not real policy text (see the corpus work still
pending). The 4 "absent" questions about Meta, X, and Reddit are absent only because
those platforms aren't usable in the index *yet*, not because they're permanently out of
scope -- once the corpus is completed, this test set and its hit-rate numbers should be
re-run, since both are expected to change.
