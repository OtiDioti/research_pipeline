# Documentation restructuring verification

Records preservation, navigation and scope checks for DEV-094 without claiming new product or scientific validation.

## Preserved baseline

Source checkout: 9a06b979b7d6cfa439cf33a253578c1c877ea2ce, plus the already-authorized uncommitted AGENTS stop-policy edit. The [manifest](MANIFEST.md) preserves all164 original Markdown inputs and their original paths, lengths and SHA-256 hashes. There are163 verbatim text copies and one deterministic-gzip specification copy; decompression recovers its exact original bytes, including EOF whitespace.

## Required invariants

| Check | Evidence and result |
| --- | --- |
| Original information | All164 recovered source byte streams match their pre-migration SHA-256 values |
| Frozen/product boundaries | All306 protected files unchanged:product source/docs/examples,specification and52 frozen request bodies;request README/index are editable navigation |
| Requirements | All94 requirement rows byte-for-byte identical;stable scope/audit rules retained |
| Decisions | All93 prior definitions extracted with original body text and rebased links;DEV-094 is the new administrative decision |
| Authority | All62 original sections retained individually and in complete history;summary creates no new authority |
| Navigation |26 immediate-child indexes,complete file coverage,no missing local file or heading links |
| Opening descriptions | All360 editable development Markdown files begin with a concise purpose;immutable inputs retain their original bytes and are described in indexes |
| Source/control preservation | Backend revision and52 retained CWI states unchanged;no controller,validator or competing run |
| Validation scope | Whitespace and documentation-integrity checks only;no product-test rerun,CWI model invocation,new CWI start or budget reset |

## Reading-cost result

STATUS and AUTHORIZATION together shrink from132012bytes to approximately11KB (about92percent reduction). Requirement obligations remain substantial by design; read relevant rows and selective evidence records rather than the full history. Run records retain detailed acceptance/integration/usage evidence.

## Reproducibility and limits

The source snapshot manifest is tracked; local check outputs and initial protected/CWI hashes are retained under ignored local/documentation-restructure-20261106/. Git preserves the before/after source revisions. Current acceptance remains productb376faf,final receipt38154ae5 and previously executed1585/1585 checks;this administrative migration changes no scientific or product-completion claim.

The final administrative Git commit identifies the completed checkpoint;the local handoff records its exact identity after creation. Recheck live Git/CWI ownership before future work rather than treating this dated report as current process evidence.
