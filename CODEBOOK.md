# Codebook

This codebook defines the two labels every ad gets. The model prompt `src/adclass/prompts/v2.txt` encodes these same definitions; if you change one, change the other and bump the prompt version.

## Goal: what the ad primarily asks of the viewer

| Label | Definition |
|---|---|
| `persuasion` | Tries to change or reinforce what the viewer thinks about a candidate, party, or issue. Includes contrast, attack, and biographical ads. |
| `mobilization` | Asks for a civic action other than money: register, check registration, request or return a ballot, find a polling place, vote by a date, volunteer, attend, sign. |
| `fundraising` | Asks for money, even while arguing a position. |
| `other` | None of the above (thank-you messages, service announcements, merchandise). |

Tie-breaks, in order:

1. Any explicit request for money → `fundraising`.
2. Practical voting information (registration, ballot requests, polling places, early-voting windows) or a petition, pledge, or volunteer ask → `mobilization`, even if the ad also argues a position.
3. Urging a vote for a **named candidate or ballot measure** is `persuasion`, even with a date ("Vote Joe Strada on November 3rd"), unless the ad also gives practical voting information as in rule 2. A get-out-the-vote ask that names no candidate ("Make a plan to vote") is `mobilization`.

## Issue: the main policy topic

| Label | Covers |
|---|---|
| `economy` | Jobs, wages, prices, inflation, taxes, housing costs, trade, budget |
| `healthcare` | Insurance, Medicare/Medicaid, drug prices, ACA, pre-existing conditions |
| `abortion` | Abortion access or restrictions, reproductive rights, IVF, contraception |
| `immigration` | Border, deportation, asylum, legal immigration |
| `democracy_voting` | Voting rights, election integrity, ballot access, courts as institutions, threats to democracy |
| `candidate_character` | Mainly about a person's honesty, scandal, competence, or biography rather than a policy |
| `public_safety` | Crime, policing, guns, drugs |
| `other` | Anything else (climate, education, veterans, foreign policy), or no identifiable topic |

Tie-breaks:

1. Two issues present → the one with more of the ad's words.
2. Mobilization ad with no topic → `other`.
3. Fundraising ad → the issue the appeal is built around, else `other`.

## Labeling procedure

1. **Label before you run the model.** Labels you assign after seeing the model's answer are anchored on it, and the evaluation stops measuring anything.
2. **Use only the ad text.** That's all the model sees, so it's all the gold label may use.
3. **Write a note on every hard call.** The `notes` column is where codebook gaps show up; recurring notes mean a definition needs tightening.
4. **Check your own consistency.** A few days after the first pass, relabel 20 ads without looking at your earlier labels and compute agreement with `adclass.metrics.cohens_kappa`. That number is the ceiling: a model can't meaningfully beat a codebook its author applies inconsistently.
5. **Aim for coverage, not just volume.** Around 100 ads, with at least 8–10 per goal label, and deliberately include ads that test the tie-breaks.
