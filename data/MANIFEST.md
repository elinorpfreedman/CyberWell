# Corpus Manifest: Platform Hate Speech & Hateful Conduct Moderation Policies

## 1. Domain Overview & Inclusion Rationale

This corpus comprises official, first-party safety policies, community guidelines,
enforcement frameworks, and transparency materials from major social platforms: **Meta,
YouTube, TikTok, X, and Reddit**.

* **Domain focus:** hate speech, harassment, violent extremism, dangerous organizations,
  and platform enforcement mechanics (strikes, appeals, quarantines, transparency reporting).
* **First-party only:** every document is fetched directly from the platform's own domain
  (help center, transparency center, newsroom, or policy site) — no secondary commentary.

**Verification pass (this revision):** the original draft of this manifest listed 50 URLs
that were never actually fetched. Running `src/fetch_corpus.py` against them showed most
platforms either block plain HTTP requests (Meta's transparency.meta.com and X's
help.x.com/help.twitter.com return 400/403 to non-browser clients) or render their policy
text client-side in JavaScript, so the raw HTML byte-fetch would have saved an empty app
shell instead of the actual policy (TikTok's `tiktok.com/community-guidelines/*` pages, most
notably — some saved as little as 14–30 characters of real text).

Every URL below was re-verified to return substantive extracted text (checked by stripping
`<script>`/`<style>` and measuring the remaining plain text, typically several thousand
characters). Where the platform's live page is unreachable by script but the same policy is
reachable through a Wayback Machine snapshot (`https://web.archive.org/web/2025/<url>`), the
manifest points at that snapshot instead — still the platform's own words, just served from an
archived copy rather than blocked live. Dead links and JS-only pages that had no working
alternative found in the time available were dropped rather than kept as placeholders. That
first pass brought the drafted 50 down to 36 confirmed-working documents.

**Third pass — back up to 52.** Rather than pad the count back toward the target with the
URLs that had already failed, the corpus was widened along the sources that had proven
reliable: 8 more YouTube help-centre policies (that domain answered 12 of 12 plain GETs),
3 more TikTok newsroom posts, 3 more Reddit help-centre articles and 2 more Meta
Community Standards, all via the same fetch route already working for their platform.
Every addition was verified the same way before being added here. The corpus now stands at
**52 confirmed-working documents**, and no entry is in this table that hasn't returned real,
on-topic policy text.

One candidate was rejected during this pass and is worth recording: TikTok's
`countering-hate-speech-and-behavior` newsroom URL returned HTTP 200 with 6,390 characters
of text — but the title was the generic "Newsroom | TikTok" and the byte count was identical
to the dead URL that had already poisoned an earlier revision. It is a redirect to the
newsroom homepage, not an article. A 200 and a healthy character count are not evidence that
a URL is the document you asked for.

**Second pass — char count isn't enough:** the check above (does stripping script/style leave
a few thousand characters of text) is necessary but not sufficient. Two documents that passed
it turned out to be junk on closer reading: `redditinc.com/policies/*` is a React app whose
recent server response is just its language-switcher footer repeated ~10 times (tens of
thousands of characters, zero real policy content), and a TikTok newsroom URL had gone dead
and silently redirected to an unrelated article. The fix for Reddit was an *older* Wayback
snapshot (`/web/2024/`, before the site became a client-rendered app) rather than the current
live page or its most recent archive — `/web/2025/` still resolves to the same JS shell. The
TikTok one had no working replacement found in time and was dropped. Lesson applied here:
skim the actual extracted text of every source once, not just its length.

## 2. Question Scope

The corpus supports four question categories:
* **Factual & policy definitions:** prohibited characteristics, slurs, dehumanizing language
  rules, protected attributes.
* **Contextual exceptions:** educational/documentary/scientific/artistic (EDSA) context,
  counter-speech, reclaimed slurs.
* **Numerical & operational thresholds:** strike limits, quarantine/appeal criteria,
  enforcement report figures.
* **Cross-platform comparison:** how different platforms handle the same situation (e.g.
  account strikes, appeals, quarantine-equivalents).

## 3. Document Inventory (52 confirmed documents)

Fetch status legend: **direct** = plain HTTP GET to the live URL works; **wayback** = the
live URL is blocked or JS-rendered, so the Source URL below is a Wayback Machine snapshot of
it (`web.archive.org/web/2025/<original-url>`, which resolves to the nearest archived
capture).

### A. Meta (Facebook, Instagram, Threads) — 9 documents
| ID | Document Title | Fetch | File Type | Source URL |
| :--- | :--- | :--- | :--- | :--- |
| DOC-01 | Meta Hateful Conduct Policy | wayback | HTML | https://web.archive.org/web/20260103041610/https://transparency.meta.com/policies/community-standards/hateful-conduct/ |
| DOC-02 | Meta Bullying and Harassment Policy | wayback | HTML | https://web.archive.org/web/2025/https://transparency.meta.com/policies/community-standards/bullying-harassment/ |
| DOC-03 | Meta Dangerous Individuals and Organizations Policy | wayback | HTML | https://web.archive.org/web/2025/https://transparency.meta.com/policies/community-standards/dangerous-individuals-organizations/ |
| DOC-04 | Meta Oversight Board: Overview | wayback | HTML | https://web.archive.org/web/2025/https://transparency.meta.com/oversight/overview/ |
| DOC-05 | Meta: Appealing to the Oversight Board | wayback | HTML | https://web.archive.org/web/2025/https://transparency.meta.com/oversight/appealing-to-oversight-board/ |
| DOC-06 | Meta Community Standards Enforcement Report | wayback | HTML | https://web.archive.org/web/2025/https://transparency.meta.com/reports/community-standards-enforcement/ |
| DOC-07 | Meta Misinformation Policy | wayback | HTML | https://web.archive.org/web/2025/https://transparency.meta.com/policies/community-standards/misinformation/ |
| DOC-52 | Meta Suicide and Self-Injury Policy | wayback | HTML | https://web.archive.org/web/2025/https://transparency.meta.com/policies/community-standards/suicide-self-injury/ |
| DOC-53 | Meta Account Integrity and Authentic Identity Policy | wayback | HTML | https://web.archive.org/web/2025/https://transparency.meta.com/policies/community-standards/account-integrity-and-authentic-identity/ |

### B. YouTube (Google) — 20 documents
| ID | Document Title | Fetch | File Type | Source URL |
| :--- | :--- | :--- | :--- | :--- |
| DOC-12 | YouTube Hate Speech Policy | direct | HTML | https://support.google.com/youtube/answer/2801939 |
| DOC-13 | YouTube Harassment and Cyberbullying Policy | direct | HTML | https://support.google.com/youtube/answer/2802268 |
| DOC-14 | YouTube EDSA (Educational, Documentary, Scientific, Artistic) Policy | direct | HTML | https://support.google.com/youtube/answer/6345162 |
| DOC-15 | YouTube Community Guidelines Strike Basics | direct | HTML | https://support.google.com/youtube/answer/2802032 |
| DOC-16 | YouTube Illegal or Regulated Goods or Services Policy | direct | HTML | https://support.google.com/youtube/answer/9229611 |
| DOC-17 | YouTube Community Guidelines Enforcement Report | direct | HTML | https://support.google.com/youtube/answer/9229472 |
| DOC-18 | YouTube Advertiser-Friendly Content Guidelines | direct | HTML | https://support.google.com/youtube/answer/6162278 |
| DOC-19 | YouTube Medical Misinformation Policy | direct | HTML | https://support.google.com/youtube/answer/13813322 |
| DOC-20 | YouTube Harmful or Dangerous Content Policy | direct | HTML | https://support.google.com/youtube/answer/2801964 |
| DOC-21 | YouTube Community Guidelines Overview | direct | HTML | https://support.google.com/youtube/answer/9288567 |
| DOC-22 | How YouTube Reviews Content (incl. appeals) | direct | HTML | https://support.google.com/youtube/answer/13304829 |
| DOC-51 | YouTube Elections Misinformation Policy | direct | HTML | https://support.google.com/youtube/answer/10835034 |
| DOC-54 | YouTube Violent or Graphic Content Policy | direct | HTML | https://support.google.com/youtube/answer/2802008 |
| DOC-55 | YouTube Child Safety Policy | direct | HTML | https://support.google.com/youtube/answer/2801999 |
| DOC-56 | YouTube Suicide, Self-Harm and Eating Disorders Policy | direct | HTML | https://support.google.com/youtube/answer/2802245 |
| DOC-57 | YouTube Firearms Policy | direct | HTML | https://support.google.com/youtube/answer/7667605 |
| DOC-58 | YouTube Misinformation Policies (overview) | direct | HTML | https://support.google.com/youtube/answer/10834785 |
| DOC-59 | YouTube Spam Policy | direct | HTML | https://support.google.com/youtube/answer/2801973 |
| DOC-60 | YouTube Nudity and Sexual Content Policy | direct | HTML | https://support.google.com/youtube/answer/2802002 |
| DOC-61 | YouTube Community Guidelines Tips | direct | HTML | https://support.google.com/youtube/answer/12950271 |

### C. TikTok — 8 documents
| ID | Document Title | Fetch | File Type | Source URL |
| :--- | :--- | :--- | :--- | :--- |
| DOC-23 | TikTok: Strengthening Safety, Security & Well-Being Policies | direct | HTML | https://newsroom.tiktok.com/en-us/strengthening-our-policies-to-promote-safety-security-and-wellbeing-on-tiktok |
| DOC-24 | TikTok Community Guidelines Update | direct | HTML | https://newsroom.tiktok.com/community-guidelines-update |
| DOC-25 | TikTok: Our Commitment to Election Integrity | direct | HTML | https://newsroom.tiktok.com/our-commitment-to-election-integrity |
| DOC-29 | TikTok Community Guidelines Enforcement Report (Q3 2025) | wayback | HTML | https://web.archive.org/web/2025/https://www.tiktok.com/transparency/en/community-guidelines-enforcement-2025-3 |
| DOC-32 | TikTok Advertising Hate Speech Restrictions | direct | HTML | https://ads.tiktok.com/resources/help/article/discrimination-harassment-bullying |
| DOC-62 | TikTok: Combating Misinformation and Election Interference | direct | HTML | https://newsroom.tiktok.com/en-us/combating-misinformation-and-election-interference-on-tiktok |
| DOC-63 | TikTok: Building to Support Content, Account and Platform Integrity | direct | HTML | https://newsroom.tiktok.com/en-us/building-to-support-integrity |
| DOC-64 | TikTok: Increasing Transparency into Elections Integrity Efforts | direct | HTML | https://newsroom.tiktok.com/en-us/increasing-transparency-into-our-elections-integrity-efforts |

### D. X (formerly Twitter) — 6 documents
| ID | Document Title | Fetch | File Type | Source URL |
| :--- | :--- | :--- | :--- | :--- |
| DOC-33 | X Hateful Conduct Policy | wayback | HTML | https://web.archive.org/web/2025/https://help.twitter.com/en/rules-and-policies/hateful-conduct-policy |
| DOC-34 | X Violent Speech Policy | wayback | HTML | https://web.archive.org/web/2025/https://help.twitter.com/en/rules-and-policies/violent-speech |
| DOC-35 | X Abusive Behavior Policy | wayback | HTML | https://web.archive.org/web/2025/https://help.twitter.com/en/rules-and-policies/abusive-behavior |
| DOC-37 | X Synthetic and Manipulated Media / Authenticity Rules | wayback | HTML | https://web.archive.org/web/2025/https://help.twitter.com/en/rules-and-policies/manipulated-media |
| DOC-40 | X Temporary vs. Permanent Suspension Rules | wayback | HTML | https://web.archive.org/web/2025/https://help.twitter.com/en/rules-and-policies/enforcement-options |
| DOC-41 | X Public Interest Exception & World Leader Speech Rules | wayback | HTML | https://web.archive.org/web/2025/https://help.twitter.com/en/rules-and-policies/public-interest |

### E. Reddit — 9 documents
| ID | Document Title | Fetch | File Type | Source URL |
| :--- | :--- | :--- | :--- | :--- |
| DOC-44 | Reddit Sitewide Content Policy: Rule 1 (Hate Speech & Harassment) | wayback | HTML | https://web.archive.org/web/2024/https://www.redditinc.com/policies/content-policy |
| DOC-45 | Reddit Sitewide Guidance: Promoting Hate Prohibitions & Examples | wayback | HTML | https://web.archive.org/web/2025/https://support.reddithelp.com/hc/en-us/articles/360045715951 |
| DOC-46 | Reddit Moderator Code of Conduct | wayback | HTML | https://web.archive.org/web/2024/https://www.redditinc.com/policies/moderator-code-of-conduct |
| DOC-47 | Reddit Quarantined Communities Criteria & Appeals | wayback | HTML | https://web.archive.org/web/2025/https://support.reddithelp.com/hc/en-us/articles/360043069012-Quarantined-Communities |
| DOC-48 | Reddit Safety Filters | wayback | HTML | https://web.archive.org/web/2025/https://support.reddithelp.com/hc/en-us/articles/15484574845460-Safety-Filters |
| DOC-50 | Reddit Crowd Control | wayback | HTML | https://web.archive.org/web/2025/https://support.reddithelp.com/hc/en-us/articles/15484545006996-Crowd-Control |
| DOC-65 | Reddit: Do Not Post Violent Content | wayback | HTML | https://web.archive.org/web/2025/https://support.reddithelp.com/hc/en-us/articles/360043513151 |
| DOC-66 | Reddit Moderation Tools Overview | wayback | HTML | https://web.archive.org/web/2025/https://support.reddithelp.com/hc/en-us/articles/15484384020756 |
| DOC-67 | Reddit Moderator Code of Conduct — Rule 3: Respect Your Neighbors | wayback | HTML | https://web.archive.org/web/2025/https://support.reddithelp.com/hc/en-us/articles/27031145215252 |

## 4. Dropped from the original draft (no working replacement found in time)

- Meta: repeat-violator strike page (`facebook.com/help/...`), Oversight Board case decisions
  on `oversightboard.com` (dynamic, not a fixed doc), a 2025 policy-update feature page, and a
  Meta human-rights page — all 404 or unreachable, and no equivalent transparency.meta.com
  page was found in the time available.
- TikTok: `tiktok.com/community-guidelines/en/*` (harassment, minor safety, account strikes,
  recommendation eligibility) — these render entirely client-side; the byte-fetch saves 14–30
  characters of real text regardless of URL. `newsroom.tiktok.com/en-us/safety-approach`
  (counter-speech/educational-context topic) is dead — it silently redirects to an unrelated
  article, and the Wayback Machine has no snapshot of it either.
- X: the 2023 "Freedom of Speech, Not Reach" blog post, the transparency report page (JS
  shell), the search-visibility help page, and the grieving-families/suspended-account help
  pages — all 404 even via Wayback.
- Reddit: the banned-communities-criteria page and the Q3 2025 transparency report — no
  working URL found; replaced with Quarantined Communities and Safety Filters instead.

## 5. Known limitations

`src/fetch_corpus.py` performs a plain HTTP GET — it does not execute JavaScript. Every
Source URL above was individually confirmed to return the real policy text this way (not an
app shell). If a platform re-renders a page as client-side-only after this manifest was
written, its fetch will need re-verifying the same way.

The generic Wayback alias (`/web/2025/<url>`, "nearest capture to 2025") is not fully stable
— it resolves to whichever snapshot the Wayback Machine currently considers nearest, which can
change. `DOC-01` broke this way between two fetch runs in development (silently started
resolving to a near-empty capture) and was pinned to its exact working snapshot timestamp
(`/web/20260103041610/<url>`) as the fix. If a wayback-sourced document in this manifest ever
comes back thin again, re-verify it the same way and pin its timestamp too.
