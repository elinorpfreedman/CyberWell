# Error Analysis

Final run against the complete corpus: 36 documents across Meta, YouTube, TikTok, X, and
Reddit (675 chunks). 35 questions, graded by hand.

## Results

| Metric | Value |
| :--- | :--- |
| Hit rate@5 (headline) | 0.812 |
| Abstain accuracy on absent questions | 1.0 (3/3) |
| Grades | 32 correct, 1 partially correct, 2 incorrect, 0 unsupported |

### Ablation: hit rate vs. k

`python eval/run_eval.py --ablation` sweeps k across the 32 answerable questions. It
retrieves once at k=10 and slices that ranked list for each smaller k (the top-3 of a
top-10 retrieval *is* the top-3), so the whole sweep costs one query embedding per
question and no generation calls at all. Full output: `eval/results/ablation.json`.

| k | Hit rate@k | Δ vs. previous |
| :--- | :--- | :--- |
| 1 | 0.531 | — |
| 3 | 0.812 | +0.281 |
| 5 | 0.812 | 0.000 |
| 10 | 0.938 | +0.126 |

**What this shows:** k matters a great deal at both ends and not at all in the middle.
Going from k=1 to k=3 recovers 28 points — for nearly a third of questions the single
best-scoring chunk is *not* the one holding the answer, which is exactly why a
generation step that reads several chunks beats naive top-1 lookup. Between k=3 and k=5
nothing changes: the 4th and 5th chunks never contain the first correct hit for any
question, so the extra context is dead weight for retrieval accuracy (though it's not
free — it's more tokens in every prompt). Then k=10 adds another 12.6 points, meaning a
meaningful set of correct chunks is sitting at ranks 6-10, just below the cutoff.

**Why k=5 is still the default:** the k=10 gain is real but comes with a cost the hit-rate
number doesn't show — twice the context in every prompt, and (per Finding 3 below) this
model already abstains more readily as context grows noisier. Hit rate@k measures whether
a usable chunk was *retrieved*, not whether the answer *used* it. The honest read is that
k=10 is worth testing end-to-end with grading, not that it's automatically better.

An earlier pass of this file analyzed a partial 8-document corpus (25 questions, hit@3=0.762,
hit@5=0.857). Growing the corpus to 36 documents changed which failure modes actually show
up -- some earlier findings (a chunk-overlap boundary bug) turned out to be non-reproducing
noise once the corpus grew, while new ones appeared that only show up at this scale.

Note that hit rate@5 went *down* slightly against the larger corpus (0.857 -> 0.812) even
though the system got strictly more capable. That's expected: more documents means more
plausible-looking competitors for every one of the top 5 slots, and Finding 1 below shows
some of those "losses" aren't losses at all.

## Finding 1: hit rate@k has a blind spot for corpus-wide duplicated boilerplate

Q9 asks how long a YouTube warning takes to expire. The chunk it's pinned to (`DOC-15-002`)
states the fact, but so does the same shared "what happens when you get a strike" summary
box embedded verbatim near the end of essentially every other YouTube help article --
`DOC-12`, `DOC-13`, `DOC-16`, `DOC-17`, `DOC-19`, `DOC-20`, `DOC-51` all carry a copy. At k=5,
retrieval found five of those *other* valid copies and none of the pinned one, so `hit_at_5`
reads `false` even though the model answered correctly from equally legitimate sources.

**Why it matters:** a single-chunk_id ground truth silently gets less meaningful as the
corpus grows and a fact's exact wording is duplicated across more source documents --
hit rate@k measures whether the *specific pinned chunk* was retrieved, not whether *a*
correct source was. On a 36-document corpus this already produces a few of these "misses";
on a much larger real-world corpus it would happen far more often for any near-universal
boilerplate fact.

**Fix to try:** grade hit@k against a fact's full duplicate-chunk set (found by exact-text
match across the corpus at test-set-build time) rather than a single pinned id, or add a
distinct metric for "was the *fact* retrievable" vs. "was *this exact chunk* retrievable."

## Finding 2: a previously-real chunking bug turned out to be non-reproducing

The smaller-corpus error analysis reported that YouTube's strike-system page had a chunk
whose "Second Strike... 2 weeks" heading was overlap-split from its qualifying clause,
causing two wrong answers. Re-verifying against the current chunking (after an unrelated fix
to `loading.py`'s tag-stripping, which shifted this document's chunk boundaries by one), the
exact same underlying content is still split the same way -- but on this run, retrieval
happened to surface the chunk that still carries the "First Strike"/"Second Strike" headings
attached, and both comparison questions that previously got this wrong (Q10, Q17) answered
correctly. The underlying fragility is still there structurally (see the chunking module's
docstring), it just didn't happen to bite this time. **Lesson:** a chunking artifact found
once should be described as "a fragile chunk boundary exists here," not "this specific
question fails" -- which chunk gets retrieved (and whether the fragile one wins) can change
with unrelated changes elsewhere in the pipeline.

## Finding 3: generation sometimes abstains even when retrieval succeeds

Two questions (Q14, Q18) got the correct chunk(s) at both k=3 and k=5, but the model still
answered "I could not find an answer to this in the corpus":
- Q14 asks for a *count* of a list that's fully present in the retrieved chunk -- the model
  won't count items itself, treating that as forbidden "outside" inference.
- Q18 asks for a **comparison across two platforms**, and even with both platforms' relevant
  chunks in context, the model abstained rather than synthesizing them.

This is a different, more concerning failure mode than Finding 4 below (retrieval actually
failing) -- here the grounding is available and the model still declines. Cross-referenced
against Finding 4, generation seems to have a lower bar for abstaining on *comparison-shaped*
questions specifically, independent of whether retrieval actually succeeded.

**Fix to try:** loosen the system prompt to explicitly permit (a) counting/aggregating
retrieved items and (b) synthesizing an explicit comparison when both sides' facts are
present in context, while keeping the no-outside-facts rule for everything else.

## Finding 4: cross-document comparisons still have a real retrieval gap

Comparisons whose two facts live in topically-distant documents continue to fail at
retrieval: Q20 (illegal goods vs. harmful content firearms) and Q21 (TikTok vs. YouTube
exceptions) both missed their expected chunks at k=5, same pattern as the smaller-corpus run.
Q19 looks like a miss by the strict hit@k metric but actually retrieved different, still-
relevant chunks from the same two target documents and answered correctly from them --
a reminder that hit@k is a proxy, and sometimes the proxy undercounts a system that's
actually working (see Finding 1 for the general shape of this problem).

**Fix to try:** unchanged from the smaller-corpus analysis -- query decomposition for
comparison-shaped questions (retrieve once per side of the comparison, merge results).

## Summary across both corpus sizes

The two genuine, reproducible weaknesses are the same at both scales: **cross-document
comparison retrieval** (Finding 4here, Finding 2 in the original analysis) and **generation
being too quick to abstain on some question shapes** (Finding 3 here, Finding 3 originally).
The chunk-overlap boundary bug (original Finding 1) did not reproduce here and should be
read as "a real fragility, severity depends on what gets retrieved" rather than a fixed
defect. The corpus-completeness caveat from the original analysis is resolved -- all 36
manifest documents are now indexed and exercised by the test set.
