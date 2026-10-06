# Codebook

This codebook defines the two labels every ad gets. The model prompt `src/adclass/prompts/v2.txt` encodes these same definitions; if you change one, change the other and bump the prompt version.

## Goal: what the ad primarily asks of the viewer

| Label | Definition |
|---|---|
| `persuasion` | Tries to change or reinforce what the viewer thinks about a candidate, party, or issue. Includes contrast, attack, and biographical ads. |
| `mobilization` | Asks for a civic action other than money, **when that action is the ad's main purpose**: register, check registration, request or return a ballot, find a polling place, learn early-voting dates, make a plan to vote (no named candidate), volunteer, attend an event. Petitions and sign-ups are not mobilization (rule 4). |
| `fundraising` | Asks for money, even while arguing a position. The ask may be implied: a campaign or organization asking for the viewer's "help" or "support" to keep fighting, with no other concrete action named. |
| `other` | None of the above (thank-you messages, service announcements, merchandise). |

Tie-breaks, in order:

1. Any explicit request for money → `fundraising`.
2. Practical voting information (registration, ballot requests, polling places, early-voting windows) or a volunteer or event ask → `mobilization` **when it is the ad's main purpose**. An ad that mainly argues for a candidate or position and also lists voting dates stays `persuasion`.
3. Urging a vote for a **named candidate or ballot measure** is `persuasion`, even with a date or early-voting window ("Vote Joe Strada on November 3rd"). A get-out-the-vote ask that names no candidate ("Make a plan to vote") is `mobilization`.
4. **Implied asks, petitions, and sign-ups.** A campaign or organization asking for "help" or "support" to keep fighting, with no other concrete action named, is an implied money ask → `fundraising`. Petitions and sign-ups ("sign the petition", "add your name", "join us") are not `mobilization`; label them by the rest of the ad. If the ad argues an issue or position ("A nation without borders is not a nation… sign the petition"), it is `persuasion`. If it is an organization's appeal for support with no argument beyond its mission ("We'll never back down… if you're with us, add your name"), it is `fundraising`.
5. **Too little text to judge.** If the ad promotes a named candidate, it is `persuasion` even when vague ("I'm ready to bring a winning game plan to Washington"). If you can't tell what it asks at all ("Clock it ⏰"), it is `other`. Either way, the issue is `other` unless a topic is named.

## Issue: the main policy topic

| Label | Covers |
|---|---|
| `economy` | Jobs, wages, prices, inflation, taxes, housing costs, trade, budget |
| `healthcare` | Insurance, Medicare/Medicaid, drug prices, ACA, pre-existing conditions |
| `abortion` | Abortion access or restrictions, reproductive rights, IVF, contraception |
| `immigration` | Border, deportation, asylum, legal immigration |
| `democracy_voting` | Voting rights, election integrity, ballot access, courts as institutions, threats to democracy |
| `candidate_character` | Mainly about the candidate or the race itself rather than a policy: a person's honesty, scandal, competence, or biography, or the stakes and competitiveness of the race ("one of the closest seats in the country") |
| `public_safety` | Crime, policing, guns, drugs |
| `other` | Anything else (climate, education, veterans, foreign policy), or no identifiable topic |

Tie-breaks:

1. Two issues present → the one with more of the ad's words.
2. Mobilization ad with no topic → `other`.
3. Fundraising ad → the issue the appeal is built around, else `other`.

## Labeling procedure

1. **Label before you run the model.** Labels you assign after seeing the model's answer are anchored on it, and the evaluation stops measuring anything. The keyword-rule suggestions on assisted rows are the one sanctioned exception: they come from a different kind of model than the one being evaluated, and the blind holdout measures their influence (see README, "Labeling protocol").
2. **Read the ad before the suggestion.** On assisted rows, form your own view from the text, then compare it with the pre-filled labels. Set `checked = yes` only after both labels match your judgment.
3. **Use only the ad text.** That's all the model sees, so it's all the gold label may use.
4. **Write a note on every hard call.** The `notes` column is where codebook gaps show up; recurring notes mean a definition needs tightening.
5. **Check your own consistency.** A few days after the first pass, relabel 20 ads without looking at your earlier labels and compute agreement with `adclass.metrics.cohens_kappa`. That number is the ceiling: a model can't meaningfully beat a codebook its author applies inconsistently.
6. **Aim for coverage, not just volume.** Around 100 ads, with at least 8–10 per goal label, and deliberately include ads that test the tie-breaks.
