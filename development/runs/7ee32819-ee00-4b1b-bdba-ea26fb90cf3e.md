# REQ-D03-004-R1 readable snapshots — 7ee32819-ee00-4b1b-bdba-ea26fb90cf3e

Records this CWI run’s source, checks, acceptance/integration and unresolved limits; authoritative controller evidence remains separately preserved.

## Identity and outcome

| Field | Observed value |
| --- | --- |
| Request / attempt | REQ-D03-004-R1 / D03-004-R1-attempt-001; continuous start 14/50 |
| Target / frozen base | main / 6b1059a20015c6e5ee9023f6d4e368250bb517ea |
| Request SHA-256 | 0f8a1abea71fd625cf38fc87cddd6bde561a22356d6f0ffd6c17ccf0614a8f08 |
| Authority / specification | AUTH-2026-10-30-001 revision 5; v1.4, SHA-256 fefc5b9b750ca270f286c7b799f71da610f33c3babf77e53b2321bf1d060664f |
| Backend / executable | Clean unchanged 1f68060b5a5a9964c91811a53d3a515e0b01a073; Codex 0.166.0, SHA-256 b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8 |
| Model / limits | Explicit gpt-6-astra/high; two milestones; repairs 2/review and 6/run; agent/validation 2700 seconds; no --merge; soft RLIMIT_NOFILE 4096, hard 1048576 |
| Start / wrapper completion | 2026-10-31T15:24:58.628589Z / 2026-10-31T17:01:48.211212Z; exit 0 |
| Historical controller outcome | ACCEPTED_UNMERGED; 2/2 accepted milestones, two repairs, all four findings resolved |
| Accepted / integrated commit | c57a621c3e3f7806030de13b75b4fe2890b81cc7 |
| Accepted tree / Git state digest | fc3e8d4fe1a54439dc0c827217f25e237a8b9fd1 / bb0f36816ace2fd5e167256b56162cbfdbeb2715c85c9c3c41dad342bd08f849 |
| Final receipt SHA-256 | 1b96a3436abd490eeff767c7c0bc9a015aa70d72a4ed340e90762a23f0404d16 |
| Whole binary diff SHA-256 | d8e4a178c8595644aa789938b68fc82f7d272df396f3912408df37dfa3f4ac2c |
| Exact fast-forward | 2026-10-31T17:06:53.465641Z; clean main, scoped automatic approval, no intervening tracked commit |
| Target validation | 489/489, zero skips/failures/errors, 340.412 test seconds; clean unchanged accepted source; completed 2026-10-31T17:12:46.950703+00:00; stdout SHA-256 781599a6858d5e2b51cb3c96c6d6317a4196af9f617c1a702407be7a5300fd32 |

The source remains finally accepted even though historical CWI state still says ACCEPTED_UNMERGED after external integration. No controller state, receipt, managed worktree, old failure or lease was edited. No unresolved owner, quarantine, in-flight operation or recording gap remained at the integration gate.

## Frozen inputs and meaningful checks

The unchanged stable non-secret launch map is retained in local/attempts/D03-004-R1-attempt-001/launch-environment.json. One model/effort is frozen for every role; actual invocation configuration and completed role transport evidence were inspected. This is not independent server-side model attestation. Existing ChatGPT development allowance only; quota, invoice and liabilities remain unknown.

The supported --context input contains twelve verified files: eleven exact unaccepted CWI-authored files from predecessor candidate 81ec2f3 and SALVAGE.md, 296,842 UTF-8 bytes total. Only the replacement delegated Writer reused them in its assigned worktree. The coordinator never applied unaccepted product source to main. The old terminal run remains unchanged.

Frozen ordered checks, profile SHA-256 2b5dca0c01372459e91c242757b71be02fb8da52d0942f7cca64efa06dba7bce:

1. `python3 -B implementation/scripts/validate.py`
2. `git diff --check 6b1059a20015c6e5ee9023f6d4e368250bb517ea HEAD --`

Baseline passed 396/396 in 307.556 seconds; check-2 also passed. Both commands ran against each candidate and at final validation. The second captures the entire committed range, including added files; it does not replace meaningful tests. No permanent validator, dependency, launch environment, old test assertion or backend changed.

## Milestones, failures and repairs

| Stage | Exact source / result |
| --- | --- |
| First planner candidate | 02a48b539011bc7e2d296ef734c076e313dc0b78; 439/439 and full-diff check passed, but reviewer requested F001/F002 repairs |
| Accepted planner | 61311e57c27b25cd91dc5a902087c598740800c0, tree 41bc700c4032f762b58dd7b7a4e47577886e57b0; 443/443 in 331.543 seconds; both checks and independent review passed |
| First publication candidate | 97393235177a581dda748934b9b0c83800398d1d, tree 41d0f96fde67ddc574f923e249fcf05cbbbb0477; 484 run, 467 successful, 7 failures, 10 errors in 337.691 seconds; full-diff check passed; F003/F004 repairs required |
| Accepted publication | c57a621c3e3f7806030de13b75b4fe2890b81cc7; 489/489 in 341.836 seconds; full-diff check and independent review passed |
| Final acceptance | Same c57a621; 489/489 in 341.396 seconds, zero skips/failures/errors/source mutation; full-diff check and final independent review passed |

Repair 1 removed an arbitrary-provenance dictionary reference heuristic, preserving only real explicit navigation relationships. It also allowed the five fixed artifact-manifest wrapper levels above valid depth 64 provenance (manifest 69; record/envelope limits unchanged). Real literal-lookalike/depth regressions were added. Repair patch SHA-256 5610e76f9b02900996e1407002e9b4c7e6563907fdd7710a13befb608663fdee.

Repair 2 corrected a real publication-layout defect: cross-parent rename of an already 0500 directory failed with EACCES. The Writer separated private 0700 evidence from a sibling payload under the same held destination parent, then published the finished 0500/0400 generation with same-parent exclusive rename. No elevated privilege, temporary writable published directory, host change or guard waiver was used. Explicit paired reservations and retained evidence cover interruption, races and uncertain acknowledgment. Final inspection now propagates I/O/resource errors instead of mislabeling them ordinary divergence. Mode-at-visibility, paired-reservation, replacement, stat/fstat and operational-error regressions cover these changes. Repair patch SHA-256 3b5264f0fd5519a45a0fc372b61956387e0f01b3b7bfd32b0d278d65abc5d7e4. See DEV-040.

Writer-local /tmp/socket/source-confinement failures remain advisory evidence and did not justify changing guards or skipping controller tests. The real first-publication controller failures are retained separately; they were not dismissed as sandbox effects. All 396 baseline tests remain unchanged, with 93 new tests in the final suite.

## Acceptance and integration evidence

Milestone receipts SHA-256, in order:

- ef17957a62a36c3d8fd16c4584fbd517b996285279c29e4eab329f479e754c6d
- d51c3643f82f59e99237a202cb9aa666b9d358f2c31dd5a53fa1ad2b4b86f035

Final review binding SHA-256 29a48354fde5da935542a110ccbe03c1d99f53d33f9465f5d7af53e40ac463e3, reviewer artifact 21d393d5f5831839363862d18c43e63b3579dadb560f18c78e8773b411fb52e4. Final candidate_kind=no_op means no extra changes after accepted milestones; the complete base-to-final product diff is nonempty.

Final check-1 validation-b18c737b-528c-4e65-b043-d0f26dea3012 completed at 17:00:39.585407Z. Result SHA-256 fa46d1dad5176bf3e336740263c4c58ac128694cea16c846a712df50ef596f59; stdout 83b3abc96b3a2a4597f0742af459bc23b88ddd97944f4f0776a2107c06ce07f0. Final check-2 validation-bd429046-e442-4230-a9b8-1ceefbad2ea0 completed at 17:00:39.706136Z; result 8d5c1612b3bfb5c9b8e964e8d97fd39c9798e2ef66b86e22ab60da2a704cc9ac. Both bind the exact final source and report no mutation.

Coordinator reviewed all fourteen changed files through the full draft and final deltas, verified all 156 tracked blobs/modes, 25 referenced immutable artifacts and the complete binary diff. Fresh integration checks confirmed base/branch/cleanliness/ancestry, no executable hooks, no changed-path attributes or ignored-path collisions, clean accepted worktree and unchanged backend/executable. Host process inspection at 17:06:26Z confirmed wrapper 1014269/controller 1014272/final reviewer 1027974 gone and no related process. Status/diagnose/reconstruct confirmed terminal acceptance with no open findings, obligations, lease/quarantine or recording gaps. Scoped automatic approval allowed only the guarded exact fast-forward and unchanged host validation.

Retained authority: /home/francesco/.local/state/cwi/runs/7ee32819-ee00-4b1b-bdba-ea26fb90cf3e/ and workflow_logs/7ee32819-ee00-4b1b-bdba-ea26fb90cf3e/. Local coordinator evidence: local/attempts/D03-004-R1-attempt-001/, including final-receipt.json, final-validation.json, both accepted reviews/receipts, all failed results/repair diffs, preintegration.json, integration-refresh.json, owner-resolution-final.json, integration-result.json, target-validation.json and usage-final.json. Raw logs and account state remain untracked.

## Delivered scope and remaining obligations

Delivered: bounded consistent detached metadata closure under one SQLite read transaction; exact roots/revisions/watermark and strict canonical decoding; deterministic ordinary Markdown navigation, seven-field folder READMEs, companion pages and exact manifests; independent verified artifact copies; private complete generation with exclusive publication to an absent destination; bounded offline inventory/hash/mode inspection; real mutation/race/process/sync/close-failure tests and a verbatim executed synthetic example. Provenance remains literal, generic records remain honestly labeled, and links never grant scientific support or authority.

All evidence is for engineering subsets of R-004/R-008/R-019/R-025–028/R-031. Refresh/direct-edit-and-rename preservation, mutable current-view management, full branch/runtime/report layout, filtered workspaces, authorized readiness, remaining lifecycle/eligibility/fences/resources, orchestration/tools/verification and scientific evaluation remain mandatory. A private view is neither a full backup nor an externally shareable export. M0-E overall, M0-S, D02/D03 and product completion remain open.

## Resources and continuation

Fourteen completed role events report 16,409,272 input tokens (14,421,760 cached), 133,446 output (48,832 reasoning), zero cache-write input. Cumulative reported lower bound: 86,268,253 input (76,711,296 cached), 1,022,856 output (253,866 reasoning), plus unknown timed-out 46114120 Writer usage. Nested categories are included, not extra charges; these are not invoices or remaining-quota measurements.

Commissioning 1/3 closed; continuous 14/50 consumed, 36 remain; cumulative CWI repairs 9 (two this run), coordinator recoveries 4, backend attempted/adopted/reverted 0/0/0. Fifteen actual runs now comprise twelve accepted/integrated and three preserved terminal failures. Missing-check recovery B-016 succeeds without erasing its 1/2 consumption; one further same-blocker action remains, as for each other recorded recovery. No grant, counter, scientific/live or model limit changed.

At the administrative checkpoint, hand off at a safe session/context boundary with no active operation or accepted source awaiting integration. The single next safe action is to prepare a bounded CWI request for generated-view refresh that preserves direct edits and renames, consuming these accepted contracts under the unchanged grant. No new implementation start is consumed by that handoff; no automatic session restart is installed or promised.
