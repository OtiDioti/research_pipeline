# Initial scope from the authorized pipeline request

The following are verbatim excerpts of the researcher's pipeline request, staged
before the first session. This is initial scope, not a subsequent question change.
The original RESEARCH_QUESTIONS.md remains the authoritative question.

> For scientific scope: reconcile conventions, operator ordering, basis/units and model assumptions between the manuscript, its supporting primary sources and the notes. Identify the physically meaningful mechanisms contributing to the linear coefficient and explain any convention/model dependence in assigning fractions. Derive the relevant projection/decomposition, quantify signed contributions and their total for a defensible paper-relevant reference point and a small informative parameter variation, check numerical convergence/limiting cases and distinguish exact reproduction from an explicitly approximate model. Treat LH–SO mixing, material/interface terms and structural asymmetry as candidate issues to investigate, not an asserted answer. Do not invent missing material parameters or claim percentages without defensible inputs. If required inputs/supplements cannot be accessed, retain the actual analytical/partial numerical progress and name the specific blocker rather than manufacture agreement.

> Consequential results need an actual separate Codex verifier using the existing bounded objection/response/re-examination mechanism. Prefer an independent reconstruction or check instead of self-endorsement. Unresolved disagreement stays disputed. Verification does not certify human scientific competence. Save enough reproducible artifacts, versions/parameters, sources and handoffs for useful scientific continuation.

> Demonstrate multi-session continuation on this scientific task using the existing fresh-context mechanism if the bounded allocation permits. Do not fabricate edits to the authoritative researcher question to simulate human direction.

## Pipeline execution interface (engineering metadata, not scientific evidence)

The supplied PDF is the October 29, 2026 manuscript. Distinguish any earlier public
version; preserve actual source URLs/access quality. Evaluate the supplied notes
critically; never repair their original bytes. Keep substantive linked Markdown
for source assessment, derivation, assumptions/conventions, numerical study,
parameters, dependency versions, uncertainty, preliminary answer and continuation.
All science, models, calculations and verification must be authored by the actual
research sessions. No target formulas, parameters or answers are supplied here.

Prioritize useful early artifacts, a meaningful bounded calculation and a separate
independent verifier using control(action="verify"). The packet requires sections:
- ## Claim and scope
- ## Parent question
- ## Scientific benefit
- ## Assumptions and approximation regime
- ## Sources and artifacts
- ## Reproduction instructions

Link all local dependencies explicitly in the packet, including dependencies of
linked Markdown. Allow time for the existing one-response/one-re-examination
exchange when warranted. Do not manufacture an objection, consensus or rollover.
Checkpoint real progress early; continue saved work when automatic rollover occurs.
Use admitted jobs (60 seconds maximum, concurrency one). Two simultaneous sessions
share 2048 MiB, zero swap and 128 tasks. Fixed sessions reserve saving time; they do
not measure context occupancy. Missing model spending/context telemetry is unknown.
Do not upload private manuscript/notes to literature services.

For the saved-science reproduction interface, author work/m5-study.json:
{
  "quantitative_target": "achieved OR partial OR blocked",
  "blockers": ["specific missing scientific inputs or remaining uncertainty"],
  "artifacts": {
    "source_assessment": "sources/LITERATURE.md",
    "derivation": "work/<your derivation>.md",
    "numerical_study": "work/<your study>.md",
    "parameters": "work/<your parameters file>",
    "versions": "work/<your dependency/version file>",
    "code": "work/<your study program>",
    "results": "work/<your numerical results>.json",
    "report": "outputs/REPORT.md"
  },
  "dependency_environments": ["work/<optional persistent dependency environment>"],
  "reproduction": {
    "argv": ["python3", "/project/work/<your study program>", "<your rerun options>"],
    "cwd": "work",
    "comparisons": [{
      "original": "work/<your numerical results>.json",
      "reproduced": "work/m5-reproduction/<alternate results>.json",
      "rtol": 1e-9, "atol": 1e-12,
      "rationale": "<justify YOUR chosen tolerances, these example values are not requirements>"
    }]
  }
}
Choose your own paths and rerun options. Reproduction must finish within 60 seconds
including startup, run unchanged saved code with alternate output paths beneath
work/m5-reproduction/, and preserve original code/data. List every consequential
numerical JSON output in comparisons. The harness recursively compares numerical
values (finite numbers with the declared tolerances) and requires identical
structure/non-numerical values; exclude changing timestamps from numerical files.
List every consequential source/code/data file in artifacts, including helper
modules and computational inputs. Dependency environments are optional directory
paths under work/ recorded separately; their interpreter links, libraries and
caches are not fingerprinted as scientific artifacts. Document versions and
recreation instructions in the versions artifact and rerun instructions.
Link the study interface and code/data/parameters/versions from outputs/REPORT.md.
Include the final outputs/REPORT.md and all consequential artifacts in the verifier
packet. Its interpretations and conclusions must match the reviewed report bytes;
any revision needs the existing bounded re-examination before workflow completion.
If submitting a response for re-examination, explicitly link the complete current
declared consequential-artifact set, including unchanged artifacts and
outputs/REPORT.md. The response packet alone supplies the final reviewed evidence;
links from the initial packet are not carried forward.
The numerical study can be explicitly approximate/partial when justified;
never claim exact manuscript reproduction without defensible inputs.
If no meaningful numerical calculation is possible, save the actual analytical
progress and precise blocker. The workflow will retain an incomplete receipt,
which is not scientific acceptance. Human acceptance remains outstanding.
