# Selected accepted-milestone evidence

These are unchanged historical records, not new validation runs. Each directory
contains the saved merged pipeline state, final/combined command output and
selected native receipts. Original absolute paths remain evidence identifiers.
The copied files are mapped to their old locations in ../CONTENTS.json.

| Milestone | Integration commit | Records |
| --- | --- | --- |
| L1 | `542ac0dbfa7a9fa13b99773f19e876054f035e54` | [state](l1/state.json), [publication checkpoint](l1/publication.json) |
| L2 | `f9119e31e816e7f83bb475ce01f58a5873f3b6fa` | [acceptance](l2/acceptance.json), [state](l2/state.json) |
| L3 | `c544bf1eefb9dca9da0b96963aff6e7b351c829d` | [acceptance](l3/acceptance.json), [state](l3/state.json) |
| L4 | `3a23c695561f5c92ecd9c71c89da6d4c02114b4f` | [acceptance](l4/acceptance.json), [state](l4/state.json) |

L1 has no separate acceptance.json in the original manager directory. Its merged
pipeline state, final/combined outputs, two successful native receipts and later
publication checkpoint are preserved instead. No acceptance record was invented.
L2-L4 retain their original explicit acceptance.json files.

This selection is sufficient to inspect the recorded engineering outcomes; it
does not include every accepted native project's complete scientific directory or
all earlier failed attempts. Current acceptance remains summarized in STATUS.md.
