# User research

## Round 1: neighbourhood conversations (Peshawar, Sep 2026)

Informal conversations with neighbours, both with and without rooftop solar.

### What people said

- **Solar owners** mostly want to understand **how many units they sold (sent to the grid)
  vs. how many they used**, and **how those two net out into the current bill**.
- **Households without solar** mostly worry about **units used in peak hours vs. off-peak**.
- **Almost nobody reads the bill.** People commonly ask the **lineman to summarise it**.
  What they want is a short summary of what affects them, not the full breakdown.
- Many are not comfortable reading English, so **Urdu is the natural default**.

### What we changed because of it

| Finding | Decision |
|---|---|
| People want a summary, not an audit | New `explain` layer: a short summary is the first thing a user sees. The full audit stays available for people who want it (`rehnuma-audit`). |
| Urdu is more accessible | Summaries are **Urdu by default**, English with `--lang en`. |
| Solar: sold vs used vs bill | Summary states grid units taken vs sent back, per time slot, the banked units, the settlement month, and what this bill added or credited. |
| No solar: peak-hour worry | For **A-1a (flat)** meters we say plainly that peak hours do **not** change the rate. For **A-1b (time-of-use)** we show peak vs off-peak units. |
| What actually hurts flat-tariff homes | The **200-unit protected limit**: going above it once removes protected rates for 6 months. The summary warns protected households from 170 units. |
| Trust | Every number in a summary must come from the verified engine. A numeric-faithfulness check enforces this, and the future LLM summary will be scored with it. |

### Insight worth noting

The peak-hour concern of households without solar is **partly a misconception**: households
below 5 kW are on a flat tariff where the time of use doesn't change the price. For them, the
200-unit limit matters far more. At 150 units, unprotected rates cost about **2.3x** the protected
ones (2026 schedule, secondary-source rates).

## Round 2: first reader check (Sep 2026)

- **Who:** one reader, the owner of the PESCO solar household whose bills are in
  `data/labels/real/` (a native Urdu speaker, exactly the target user).
- **What he saw:** the Urdu summaries of his own bills.
- **Verdict:** the summary "looks good": it covers what he'd look for in the bill.
- **Weight:** n = 1, and he knows the builder, so this is an early sanity check, not
  validation. It supports the Round 1 decisions (summary first, Urdu default, solar
  sent vs used) but doesn't prove them.

## Next round

- Show the Urdu summaries to 3–5 neighbours, including at least 2 households **without**
  solar, and ask: *what did you understand, what was confusing, what's missing?*
  Record the answers here.
