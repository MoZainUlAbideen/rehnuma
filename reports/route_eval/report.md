# Router eval

| Split/lang | n | accuracy |
|---|---|---|
| dev/en | 12 | 100% |
| dev/ur | 8 | 100% |
| heldout/en | 14 | 86% |
| heldout/ur | 9 | 100% |

Confusion (expected -> got), all splits:

| expected \ got | bill | policy | both |
|---|---|---|---|
| bill | 18 | 1 | 0 |
| policy | 0 | 16 | 0 |
| both | 1 | 0 | 7 |

Misrouted:

- h2b1 (heldout, en): expected bill, got policy - How many units did I import from the grid?
- h2x1 (heldout, en): expected both, got bill - Was my bill averaged legally after my meter broke?
