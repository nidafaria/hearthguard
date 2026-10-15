# Copy guide: how Hearthguard speaks

The voice is calm and plain. It is the voice of a senior colleague who has read the file and will not waste your time. It does not sell fear, and it does not flatter. It leaves out anything the data cannot back. Short sentences. Common words. One idea per line.

The craft comes from `docs/design/show_craft.md`. The product never names a show and never borrows a line, scene, character or catchphrase from one.

## Fixed rules

1. **A note is a question, never a verdict.** It asks the owner to look. It never says what a person is or meant.
2. **"Not computed" is a plain fact with its reason, never a warning.** It uses the same weight and colour family as other facts. Its reason is copied from the file.
3. **Silence is a result.** If a check did not run, say so in the same sentence as the result. "No move fired" is never written alone when a move was not checked.
4. **The real maintainer is never a character.** His life, health, feelings and motives are not described. His public words appear only where a screen needs them, exactly as in `eval/results/video_quotes.json`, attributed to the archived message file, not to a person.
5. **Every claim traces to a file.** Each screen names its source file and its data kind: "public record (xz)" or "synthetic (tallowdate)".
6. **The real attacker persona is not named.** Roles, not names. Hashed ids only.

## Rule 1: open on the consequence, then earn the cause

A screen leads with what happened, in one line. The method comes second, on request.

- **Say:** "Held. Two of five checks could not run, so this quarter is not clear." Then: "Show me why."
- **Must not say:** "Our multi-agent graph engine analysed 4,679 nodes to produce a decision." (That is method before consequence, and it puts a big number where the result belongs.)
- **Must not say:** "Attack detected." (A claim beyond the data. The xz replay has no FIRED move.)

## Rule 2: trust the reader; cut what the record already shows

Do not explain a table that the table already explains. Put one plain definition next to each term, once.

- **Say:** "Rush: someone gets rights faster than this project usually grants them."
- **Must not say:** "Rush is a sophisticated behavioural indicator of adversarial privilege escalation." (Jargon that hides a simple idea.)
- **Must not say:** "Clearly, the newcomer was rushing." (A label for a person.)

## Rule 3: a number is only as good as what it measured

Every number carries its source and its limit: what was counted, out of how many, and what was not counted.

- **Say:** "88 of 100 planted campaigns caught with full memory. Synthetic. Three real attacks are too few to claim precision."
- **Say:** "Reader coverage: 90 of 240 messages read. A 'did not fire' here covers those 90 only."
- **Must not say:** "88% accurate." (No accuracy was measured. A detection rate on synthetic campaigns is not accuracy on real ones.)
- **Must not say:** "Takeover cost: 1." for xz. (The saved file says NOT COMPUTED. The spec's illustration is not a result.)

## Rule 4: mystery, not confusion

Leave open only what is truly unknown, and mark it as open in plain words.

- **Say:** "Not computed: no public record of who was given commit or release rights was found."
- **Say:** "Unreachable means no loaded record shows this role in that place before the signal. It is not proof the role was not watching."
- **Must not say:** "Data unavailable." (Confusion. Which data, and why?)
- **Must not say:** "Nobody was watching." (Converts absence of evidence into a claim.)

## Rule 5: end on the question that moves the reader forward

Each screen closes with one line that points to the next useful act: a question to ask, a record to add, a step to try.

- **Say:** "Would you like to add the records for the unknown moves, so they can be checked?"
- **Say:** "Before this upgrade was accepted, could the person deciding see the earlier signals?"
- **Must not say:** "Act now before it's too late." (Fear selling.)
- **Must not say:** "This contributor should be removed." (A verdict about a person.)

## Headlines

Headlines work like a good print advert: one idea, set large, with a plain support line under it. The headline states what the screen holds. It never promises a result the screen does not show.

- **Say:** "Who saw what." Support: "Four downstream decisions. Twenty-two gaps between an earlier signal and the role that decided."
- **Must not say:** "The hidden conspiracy, revealed."

## Words we use

| Use | Avoid |
|---|---|
| held, did not fire, fired, not computed | safe, clean, guilty, suspicious |
| a role, an account, a hashed id | the attacker, the villain, the victim |
| the saved file says | we believe, we detected |
| synthetic, fictional project | simulation of the real attack |
| question, note | alert, alarm, verdict |

## Final check before any copy ships

Read each sentence and ask three questions. Which file says this? Does it claim more than that file? Does it describe a real person's inner life? If the answer to the first is "none", or to either of the others is "yes", cut the sentence.
