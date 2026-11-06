# Complete supplied-file inventory

Every regular archive member is listed below. All text files were decoded/inventoried; Python modules were parsed into a static index of imports, top-level symbols, docstrings and test methods. Integration-critical control paths, CLI, prompts, configuration, state/recovery, validation, Git operations and associated tests received detailed behavior review. This coverage is not a claim of a line-by-line correctness proof or complete security review.

The archive contains 98 regular files and 50,420 text lines. SHA-256 identities below describe the original contents; those hashes remained unchanged after test execution. Directory entries are not counted as files. The archive has no independent remote-history attestation.

| Path | Lines | Bytes | Purpose / static description | SHA-256 |
| --- | ---: | ---: | --- | --- |
| `.github/workflows/tests.yml` | 37 | 1232 | Continuous-integration test configuration. | `566dceb3eaaf1cc5797c4ae7b8ffb139d3a8764dbcfdd6ccbb3c389411f8b21a` |
| `.gitignore` | 7 | 70 | Local source-development ignore patterns. | `cf507fcf68b0fd0bfc9aac607c723e295f95aff91cb0689c49f196391d0a9be1` |
| `README.md` | 440 | 25028 | Public operating, trust, recovery and development documentation. | `8315c140e5bba23b726d72f1f92b2581fc4618c57374123e3603feb7ee3b1e45` |
| `benchmarks/forensic_logging.py` | 270 | 12684 | Opt-in deterministic forensic benchmarks; run from the checkout with -m. | `38e51556d4aa92ab6f829c3b65314b4113a1236c785014d0e9f2aaca8cf5c7d0` |
| `bin/agentic-flow` | 14 | 326 | Source-checkout launcher. | `536ead1e10aadfd380a89079d263d26f13867e7178e92e434be3d539654ba1c6` |
| `cwi/__init__.py` | 2 | 57 | Codex Workflow Controller implementation package. | `987e93829ebabd1b8c161e43b2ccc32cb6b9a8d3ee33ebb34f26e3b6db4bc4d7` |
| `cwi/agent_logging.py` | 266 | 14936 | Observe existing agent boundaries without owning execution or output storage. | `575a2f3219454e67b369b6bb2b9964d2673fc8c0761dd5084d4c575e02db86b0` |
| `cwi/amendment.py` | 274 | 16872 | Bounded original-session Architect–Designer turns under repository coordination. | `ac6bb22f2c9e4fdf4fe8508bd856d0e759044a6df4ed2ebfcbf14a20451353bc` |
| `cwi/cli.py` | 253 | 10366 | Argument parsing and terminal diagnostics for CWI commands. | `f076d173026cf848db6627443d073273411f04ed32ea5166e68eda77cf908f8f` |
| `cwi/codex_cli.py` | 723 | 31098 | Small synchronous adapter for isolated codex exec invocations. | `ffc9b73b3ead8ec5dddd8c92cc6267dc1f8a1af7bc62d370d60199742768f4c9` |
| `cwi/codex_runtime.py` | 157 | 7499 | Bounded local Codex discovery and immutable executable identity checks. | `3b804ff28bc5682839e92f61c3199986c389dfa26c9c429c7f4f65fd24b7350b` |
| `cwi/config.py` | 260 | 9761 | Parse the small, frozen CWI v1 TOML configuration contract. | `345548396170e2ced68efd640c1019a4fb7d4a04366eecdde42595888e987684` |
| `cwi/context.py` | 566 | 29366 | Bounded, role-specific prompts assembled from authoritative CWI evidence. | `0b68543873077972b5d98cd48daf0d58a0ca4cc842c7600716763f1db04f2fdd` |
| `cwi/contracts.py` | 800 | 33248 | Typed immutable records and strict parsers for untrusted role responses. | `bba93ead6264c2b1bde15cd2d160bc3f243fe35c1bd667fec06a7361e91c1d10` |
| `cwi/controller.py` | 1151 | 47373 | Pure M-01 workflow transitions, acceptance gates, and retry decisions. | `dd98abd05d9f8e8e0bda287950dc20ef24397ecaa56be6244b6d74e3a9bcf8ec` |
| `cwi/controller_logging.py` | 404 | 21448 | Project controller execution into observations without participating in decisions. | `361700e129e1678d3b9beaada7b06bae80eed944da9d8b1d05bbeb7a817dd3fa` |
| `cwi/diagnostics.py` | 375 | 21407 | Render read-only recovery guidance and redact credentials at presentation. | `4750bcf1501a88c0d7f455acd99797fd1c8f61ed042cdb7aeac3a9307b51fd6b` |
| `cwi/evidence.py` | 1121 | 48448 | Immutable controller evidence and its canonical content identity. | `d04c5fd797025646bf0b3d13260fdc0b105375b3270701e204e4374bf61d45f6` |
| `cwi/finalization.py` | 329 | 20309 | Whole-change acceptance, immutable final receipts and guarded local merging. | `e3b416c3fe1ffec80bd53b101fbd9f459111a78f8393833943033765825162c6` |
| `cwi/git_logging.py` | 146 | 7224 | Observe high-level Git effects using existing values and the active RunLogger. | `ff2c2d44c9cff86230079dc4df3c00051061f5a588c3ab94e32cc5a665a90dde` |
| `cwi/git_workspace.py` | 1555 | 58410 | Exact Git observation and setup mutations for controller-owned worktrees. | `136e74dd4fda07897deb7905bfb68ce6f97b05a0a7bf91b649939d47ba4eda8c` |
| `cwi/milestone.py` | 2372 | 108268 | Synchronous role orchestration for ordered independently accepted milestones. | `e549fe52945e034a44906197bb333056dcf129d264847a2efba876a85e999c97` |
| `cwi/observability.py` | 514 | 23863 | Best-effort asynchronous JSONL observations for one published CWI run. | `538b6483b3f666aa7540da33bcae24ab10118414e0a6e5b92b7cb66e70645df8` |
| `cwi/orchestration.py` | 546 | 23349 | Synchronous command orchestration for CWI setup and baseline validation. | `8995c826f2fb308c7cdc5ef2a8a7d7699b3701748cacf6198442b26af1f34c78` |
| `cwi/preflight.py` | 1354 | 52347 | Repository/input verification, including the reserved local log exclusion. | `6fdb800867538ea25fd71d89d4e7903726a8be282185c44201d508e263b8af1e` |
| `cwi/prompts/architect.md` | 46 | 4678 | Controller role/interaction instruction template. | `235967bdc365be4397d7cb54a12a55b016fc3bcd08cd3913cc16666cf7c7edfd` |
| `cwi/prompts/architect_amendment_feedback.md` | 17 | 1419 | Controller role/interaction instruction template. | `9a9188b32c5e9fb3f0dc4e49d9d5398a3d79175f3befacafedbd3d58084f8591` |
| `cwi/prompts/common.md` | 30 | 3248 | Controller role/interaction instruction template. | `e93f9f91c1fad3f5a91448cd0ce3aaadd0c4dd54ff32ab831d0e7fd205398881` |
| `cwi/prompts/correction.md` | 7 | 637 | Controller role/interaction instruction template. | `d1a126bcedbb6888850304ff05e64992ba926d492221032121ac29a43d63ea29` |
| `cwi/prompts/designer.md` | 38 | 3150 | Controller role/interaction instruction template. | `d7ab2d9e7801efdb5e9c3b23dcdcfff2f7ae576b757aad49ac41665af1e121cc` |
| `cwi/prompts/designer_amendment.md` | 11 | 1315 | Controller role/interaction instruction template. | `9f39e962d2887bc4ba42167d12ae7cda8657820a2773d95066754b41fb8c8768` |
| `cwi/prompts/reviewer.md` | 59 | 5961 | Controller role/interaction instruction template. | `1aa505294e1a70083ff35b11dbdaf429683a14ed5f17ff60dc90f2e361823190` |
| `cwi/prompts/reviewer_clarification.md` | 18 | 1385 | Controller role/interaction instruction template. | `08bc08f7d5bed7bd62675a60b4460e04dacd37e077a3938d48c491a3491b90c6` |
| `cwi/prompts/writer.md` | 41 | 4023 | Controller role/interaction instruction template. | `3f336e08a7ff12e7a22fe8e92a9199773910ffab4894dfb2f9cc75224fe186d4` |
| `cwi/reconstruction.py` | 701 | 38473 | Reconstruct recorded run history offline, without granting logs workflow authority. | `e0da1b38eecf340e9b71d00db6d2edb648465819bf48fd5592d6d5e8052fe392` |
| `cwi/repository_logs.py` | 129 | 5601 | Reserved repository log paths and the sole preflight Git exclusion update. | `3d2b35b6c64d6645ef360aefc4c9dc394be1e9f71c4f7a4461dded7eb68967b8` |
| `cwi/response_schemas.py` | 130 | 4938 | Native Codex response shapes; Python contracts remain authoritative. | `b44981830baecd3a8b8b907afac6355ae817f8ae6f34e2583457d179404a2856` |
| `cwi/roadmap.py` | 137 | 7558 | Repository-locked deterministic roadmap amendment admission and publication. | `4c7a7cdc312d4994f0c027912949bb2c94cac8afb4fe43b653f5e694a6f40e2d` |
| `cwi/run_setup.py` | 465 | 18532 | Durable start and crash reconciliation for a CWI run workspace. | `065c28cebb22353bd8fbd1dc21bf83ac028f03fdcbd9b82cccd4e0c977838b5c` |
| `cwi/state.py` | 1612 | 73483 | Immutable run snapshots and in-flight operation intent records. | `7fb1295365d8e3c55f08df8aa923501fd40d4601a6dc61b5022202a0279ab31e` |
| `cwi/state_store.py` | 2027 | 98765 | Durable snapshots, audit events, and immutable artifacts for one CWI account. | `793968d83cc9b5a1e7679275f355a7d3e159b02d1e631e5f71bdeb8144625d3c` |
| `cwi/terminal_progress.py` | 321 | 17488 | Best-effort terminal presentation of existing observations and saved snapshots. | `5e3f85b24339d1cc7b6189c1c9cb8d739aa1121564fcfb07f9bac6a79f449cdb` |
| `cwi/test_discovery.py` | 476 | 23960 | Bounded, read-only test selection from the verified starting Git revision. | `ea718a7d0f328a0c7b54f9fb26660a224390a273fab214d17a7d2b3748ba6e7d` |
| `cwi/test_execution.py` | 177 | 7970 | Small native-report readers for test-free runs; never execute project code. | `b2cf77426e9773129bdb0be523b62aa03b0302dc260e77ce4f935eda845bba12` |
| `cwi/validation.py` | 1200 | 50202 | Frozen-profile validation with exact Git binding and process quarantine. | `21bd2fadb352247130a6a419048ddbbb82c5fc0ffed7b541417b3f49baaa7809` |
| `cwi/validation_logging.py` | 195 | 10408 | Compact validation observations through the controller's existing recorder. | `e0170072b40571a6742a7665aa5c2f70a872776b24ef830aac72094cd6acd45d` |
| `probes/__init__.py` | 1 | 71 | Opt-in and deterministic feasibility probes for CWI development. | `ed85341b8ec79b0cddc381b47b85379b9dd3b915fb91622c501c45443f28303f` |
| `probes/m00/__init__.py` | 1 | 44 | M-00 runtime and Git evidence probes. | `4a346fa80ea979b4b7a91fd67f31dd59ba8794b1e0a8fe95efeb3dcf074185e1` |
| `probes/m00/git_probe.py` | 586 | 21641 | Exercise M-00 Git plumbing in one disposable linked-worktree repository. | `7eab603aa30539320cf827552c9b84d357760cf12c2f7e9cb4320a56c2ba32ca` |
| `pyproject.toml` | 23 | 575 | Packaging metadata and build requirements. | `7c08dabb00fb8c0295591a5f0e0fcd67684deaf4cfbcef065dd2a567fa56adfb` |
| `tests/agent_process.py` | 18 | 650 | Authentic process-state evidence for interrupted agent recovery tests. | `0e48ed2cd408a551b96e41ffc9293a31cd580afd20882d8167222745d683887c` |
| `tests/codex_fixture.py` | 41 | 1744 | Deterministic installed CLI fixtures; no credentials or model service required. | `2f8569879d27fd5b239d4374cbefd89ba1d3e2f7d64220e2c2e2b7ddd92f7e59` |
| `tests/criterion_fixtures.py` | 17 | 752 | Explicit criterion assessments shared by deterministic Reviewer fixtures. | `3fc78efef19c303a367225097a60a343b43f00488475c905294afb26d8d3fdc8` |
| `tests/test_agent_logging.py` | 470 | 29137 | Agent observations through real public workflows and deterministic adapters. | `c4d9a375b1045c9e120b60e8b77ea1ced4d98c6c2a3784fba9abd3970a922db0` |
| `tests/test_amendment_conversations.py` | 756 | 48822 | Original-session roadmap negotiations using deterministic disposable workflows. | `bead8d6fd6c6a7c1ba317d5bbf29e0166dc832467bb85eaab43e917cce8253ca` |
| `tests/test_automatic_start.py` | 186 | 10961 | Automatic command selection through the real startup and acceptance pipeline. | `67d6409ab112984ca8da01cfeaa2b497eeab2c824faa7e346ce070203d4027d8` |
| `tests/test_cli.py` | 157 | 6589 | Command-line behavior tests for the operational M-02E application. | `c46d5e2dd7e103531b0570be3e08ff8c7ce3e59fa74c77a2a3a2130db45bba14` |
| `tests/test_codex_cli.py` | 1655 | 85543 | Deterministic adapter tests and explicitly enabled real-CLI probes. | `10d749993f27b48119c19e23187f72b7edadb68b16e54ca2ad3407d477c2a869` |
| `tests/test_codex_runtime.py` | 167 | 8912 | Bounded executable discovery, semantic ordering and frozen native identity. | `5d14f328d5754fe2ab019222f82c2a2242cc4a37110644aa81a3a19300021e00` |
| `tests/test_codex_selection.py` | 160 | 8657 | Production start/resume selection using deterministic local Codex installations. | `36dfb92f7d9e93ec093f87c6053edff7a3dfdfcecb5d8e1f591e478d3d22b218` |
| `tests/test_command_start.py` | 343 | 17829 | Single-command configuration, frozen inputs and local-input Git admission. | `68cde2ead04c729205edcfe62d47d58c8eb775d44c5dcbf3c445dd5198195256` |
| `tests/test_config.py` | 249 | 9131 | Deterministic tests for the v1 TOML configuration boundary. | `8a89fab9490c34a16c880a9a22e175767679a4111d861691786786608659ed29` |
| `tests/test_contracts.py` | 972 | 45975 | Deterministic tests for strict role-response JSON contracts. | `f0c272b6e7fa2e994749489215d712ad68567d9166901137f228ab17e6e53009` |
| `tests/test_controller.py` | 1350 | 53153 | Deterministic tests for M-01B2 pure controller transitions and gates. | `761fd7a4830f4da75f18e97f40c4e8acd81ec9784584586da1f0ec3ed1795a67` |
| `tests/test_controller_logging.py` | 466 | 28580 | Controller-only forensic recording through real persistence and fake roles. | `8a081748f191f2f26089a77ed7677fe02841c04fa4d6a0c3d9950a55bf195d5b` |
| `tests/test_conversations.py` | 382 | 21885 | Persistent repair conversations through real state, Git and workflow gates. | `18b8321278852bd3b4db0c3d93c99b391108de693deb19e1768b3cb5e93a92e3` |
| `tests/test_criterion_evidence.py` | 315 | 20310 | Criterion coverage contracts and exact accepted-evidence persistence. | `7238496b26123d25c934fd9a8a5c41bd9c05d650be5d4b1b37a9987a34253dba` |
| `tests/test_diagnostics.py` | 525 | 28395 | Read-only recovery guidance over real snapshots and disposable repositories. | `726ce401087b50f2af2c4a667ba8a07fe38a60d3dfe99c6b5f8be484a78d361e` |
| `tests/test_evidence.py` | 1079 | 43166 | Deterministic tests for controller-owned evidence records and digests. | `a3c60bab4867d582dc5944cbeb7d566efdfaeddd6d04e6e08583bcbde87f2597` |
| `tests/test_finalization.py` | 975 | 58020 | M-06 whole-change acceptance and guarded merge in disposable repositories. | `7e78038f55cc3155b8c992cc0bd31956a1ffcd21cdf86812cd0bde2b8f13999f` |
| `tests/test_git_logging.py` | 461 | 29267 | Git observations through disposable repositories and scripted workflow roles. | `560db87cf1f00eb1daf7281aee952c5920ba433167047a100f3a7f7f2797ea8a` |
| `tests/test_logging_hardening.py` | 317 | 17487 | Final forensic integration checks using real controller/storage and fake roles. | `25e6dd3a3718a276230dc8c9f93c4cd1fa9c55c05770532c785d17f43d340766` |
| `tests/test_m00_probes.py` | 110 | 3934 | Deterministic tests for the retained M-00 Git evidence probe. | `56efd076d45dc0483d941aeb843592fd478d956b3e2c2f45ace2cdef1fde8a42` |
| `tests/test_milestone.py` | 1924 | 88683 | Disposable-repository tests of production milestone execution and recovery. | `5b81ec68b256468dba46e9e692d3899b14181975a5ad863551eda784c2c1ce8a` |
| `tests/test_observability.py` | 592 | 31063 | Deterministic observational logging tests; no agents or authenticated services. | `a21d8eb92dae01ed3743c28e317694f55c046c82289856772b8ccdba5bcf6651` |
| `tests/test_orchestration.py` | 841 | 39868 | Disposable-repository tests for M-02E command orchestration. | `6e4371ae1ae266d44f408f3bdac8e4c04df549c525180272611b519a82cab8d3` |
| `tests/test_preflight.py` | 702 | 29436 | Disposable-repository tests for read-only M-02A preflight. | `5ed9166ce919cddfb8722e11aa0afd936437ae7180bb415328dc2f7ab20e4c0d` |
| `tests/test_prompts.py` | 240 | 14179 | Packaged prompt selection, failure boundaries, and installed-resource regressions. | `e4f98c6b7f7dd93fd0ec6acad7a6d635ede7f204bab524191a5bfe45a0f9ae89` |
| `tests/test_reconstruction.py` | 743 | 44501 | Offline inspection of real private storage and deterministic recorded histories. | `1f7775b00ce452441ac373c0ebd1a5b4501c38f61a9ecbd4c7fba68d9d917dd2` |
| `tests/test_recovery_logging.py` | 491 | 29176 | Failure and recovery chronology through real persistence and deterministic roles. | `04b96cc077829495076a99de7dc9c9c55e243929caf575980065621791defc45` |
| `tests/test_release.py` | 357 | 18421 | Release diagnostics, cancellation and installation-boundary regressions. | `a628fb91708769f4edd1e121067d3941225429205ebf899bc2c0034950f8e224` |
| `tests/test_release_live.py` | 121 | 6916 | Explicit opt-in full M-07 workflow; every role uses authenticated Codex. | `3c1a6495a744d6ddcf8ce664c4213585c6e19c963206a2cce4c62302fd1d77a1` |
| `tests/test_repair.py` | 1210 | 58715 | M-05 repair cycles against fake roles and disposable Git repositories. | `f4189094f25dfdeee47d2c0b742e8c0c70261039fb665ab90765ae0ee6faa685` |
| `tests/test_repository_coordination.py` | 623 | 25088 | Disposable-repository tests for same-account repository coordination. | `6a77dd373c3fcd6d6861eb828fe4e1e7ed4bb5bb90e7a9f6947cc418f4cc9d73` |
| `tests/test_repository_logs.py` | 297 | 16296 | Reserved repository log isolation with real Git and deterministic workflow roles. | `3afa04fd8f477a9062fd4b631f1c2c7502f2e4fddd40f423e53955d34eecc295` |
| `tests/test_roadmap.py` | 514 | 31369 | Bounded roadmap contracts, durable amendments and historical acceptance. | `51fd846b9e75225a56f62bea0fc762aaf055595e319c42c1f1cf03f48cd2dcfe` |
| `tests/test_run_setup.py` | 630 | 24972 | Disposable-Git tests for durable branch and linked-worktree setup. | `ae700bff2f5a331ec1391ea089670de9eb47af86115a5b20ecdbfacfb5648da0` |
| `tests/test_sessions.py` | 559 | 33136 | Explicit session transport, durable ownership and no-replay recovery tests. | `b6e64dca8f5a76848b014532ca421687c9c1c41dc9745cde47f40ee8c79c3511` |
| `tests/test_source_launcher.py` | 364 | 19292 | Source launching and narrowly scoped embedded-checkout admission with real Git. | `bafcdab726817fe016356c9b54f197efce7b40e061110db9785380c14ce5086a` |
| `tests/test_state.py` | 1057 | 43753 | Deterministic tests for immutable lifecycle and in-flight state records. | `29a12946cd3de4373ab732f951f569a339d0995020aa26e9ba326b2262575b8b` |
| `tests/test_state_store.py` | 894 | 36240 | Deterministic tests for durable M-02B state and artifact storage. | `5ef5a3bae168988f518c8fffd9bfbf5b5999eb279d42af15d674dc0da4cba561` |
| `tests/test_terminal_progress.py` | 451 | 25156 | Live presentation tests using simulated terminals and real workflow persistence. | `5aab4b8ee3eb1d42cf0e2d740f3442b2cadd244bea58323e3f6f99626d4b945c` |
| `tests/test_test_bootstrap.py` | 432 | 25754 | Test-free admission and acceptance through actual Git, validators and role fixtures. | `bb38666553e91c5980dd3f6e0dee3f6eee678d6112674130a160198d7f3cba56` |
| `tests/test_test_discovery.py` | 372 | 22080 | Conservative runner selection from disposable, verified Git snapshots. | `533240212534c2dabf7b85fa71455e33fb6fac4f47e825adca27b1437672bb8a` |
| `tests/test_test_execution.py` | 74 | 5387 | Native execution evidence must distinguish tests, skips, failures and no report. | `d8a956b301f7af8ada504660ccfffcc88e5079456a54cf7ea5c3ddcb87856bb3` |
| `tests/test_validation.py` | 1639 | 75051 | Disposable-Git tests for M-02D validation supervision and recovery. | `0a054a3275c75375f2c60a79795d973aa875eaea8c87b4b51429e0c7525157af` |
| `tests/test_validation_logging.py` | 377 | 22506 | Validation observations and persistent captures in disposable repositories. | `02f1a71a5f2044ed6b16538f402f639e6b269c763be673df5f111baeb8f31a7f` |
| `tests/test_workflow.py` | 1361 | 60100 | Disposable-repository tests for the M-04 ordered role workflow. | `66e09f78d8a7d1c19a45ea619ec65cb802d78adc94dd41f709f4704fea6854d5` |
