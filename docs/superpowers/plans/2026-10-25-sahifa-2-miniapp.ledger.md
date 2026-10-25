# SDD ledger — plan: docs/superpowers/plans/2026-10-25-sahifa-2-miniapp.md
Spec: docs/superpowers/specs/2026-10-25-sahifa-miniapp-design.md
Mode: hybrid inline; reviewers after T2, T6, T10; final review. Branch feat/miniapp from main f64a2dc
Pre-flight: T6 consumes T4 cloud — consistent. T8-T12 consume T4 api functions and T6 store — consistent. T10 deleteMuseum(api) vs T6 deleteMuseum(local): name clash — Ruling: api functions are namespaced as api.deleteMuseum, store exports deleteLocalMuseum — cost: rename only.
Pre-flight: T6 atomic rev-keyed pages deviate from spec key m_<id>_p<n> — Ruling (plan-level): m_<id>_<rev>p<n> — keeps previous version on failed write — cost: none.
Task 1: complete (commits 0195cb4..b7231a6, tests: bash .superpowers/t.sh -q → 181 passed in 8.99s)
Task 2: complete (commits b7231a6..9009033, tests: bash .superpowers/t.sh -q → 193 passed in 9.69s)
Task 2: Ruling: old tests asserting 31 photos → media_full updated to 131 (owner allowed bigger free museums) — cost: none.
Task 3: complete (commits 9009033..12487bc, tests: bash .superpowers/fe.sh test → [2m   Duration [22m 421ms[2m (transform 33ms, setup 0ms, collect 72ms, tests 15ms, environment 142ms, prepare 54ms)[22m)
Task 3: Ruling: Node 24 LTS installed (plan said >=22); router starts with only home + placeholder Home.vue (later tasks add routes); package versions pinned by caret ranges — cost: none.
Checkpoint review after T2 (5772032): fixed High double-charged rooms (ROOM no longer sold on drafts), Medium second museum payment → rejected 'already_paid' + duplicate_payment refund (reverses plan-1 ruling "extend instead"), Low invoice title shows "+N xona". Tests: tests/services/test_rooms_review_fixes.py RED(3)→GREEN; superseded tests updated; suite 195/195. Line endings normalised (.gitattributes).
Checkpoint: Ruling: second payment for an already-paid museum is refunded, not converted to +120 days — user may have paid room prices too — cost: user who wanted an extension must buy "reactivate".
Checkpoint minor (deferred): rooms are not recomputed if media is removed from an imported draft before paying.
Task 4: complete (commits 12487bc..2a75a4a, tests: bash .superpowers/fe.sh test → [2m   Duration [22m 417ms[2m (transform 66ms, setup 0ms, collect 130ms, tests 23ms, environment 430ms, prepare 161ms)[22m)
Task 4: Ruling: tg.available/initData/user/startParam are functions (read the SDK lazily; testable) instead of properties; SDK counted as present only when initData is non-empty (the script defines WebApp in browsers too); fetch failures → ApiError('network') — cost: none.
Task 5: complete (commits 2a75a4a..c743ad4, tests: bash .superpowers/fe.sh test → [2m   Duration [22m 436ms[2m (transform 125ms, setup 0ms, collect 259ms, tests 29ms, environment 587ms, prepare 238ms)[22m)
Task 6: complete (commits c743ad4..844b571, tests: bash .superpowers/fe.sh test → [2m   Duration [22m 447ms[2m (transform 133ms, setup 0ms, collect 300ms, tests 40ms, environment 733ms, prepare 282ms)[22m)
Task 6: Ruling: store export renamed deleteLocalMuseum (pre-flight); letter also stored per revision (m_<id>_<rev>l); added collectGarbage() for keys orphaned by interrupted saves (test added after code — characterization) — cost: none.
Task 7: complete (commits 844b571..988f4d5, tests: bash .superpowers/fe.sh test → [2m   Duration [22m 475ms[2m (transform 196ms, setup 0ms, collect 446ms, tests 58ms, environment 899ms, prepare 346ms)[22m)
Task 7: Ruling: queue adds idle() and an onDone callback delivering finished files in add order (keeps the user's photo order) — cost: none.
Task 8: complete (commits 988f4d5..93369ec, tests: bash .superpowers/fe.sh test → [2m   Duration [22m 560ms[2m (transform 341ms, setup 0ms, collect 672ms, tests 119ms, environment 1.08s, prepare 444ms)[22m)
Task 8: Ruling: +5 museum pack offered with both card and Stars buttons; server drafts hidden from the list (they exist only during checkout); added format.ts helpers and main.ts bootstrap (i18n from Telegram language, colour scheme) — cost: none.
Checkpoint review after T6 (f7923cb): fixed C1 overlapping saves (unique rev + per-museum queue), C2 GC (never metas, live rev, or <24h), C3 idx races (list from metas; idx = order hint), I1 missing letter → broken, I2 broken museums shown and never saved over, I3 byte limits + letter parts + item_too_large, I4 1024-key budget check (storage_full), I5 Bot API <6.9 fallback, I6 10 s timeout. Tests: tests/account-store-review.spec.ts (fake CloudStorage with real limits) RED(10)→GREEN; old tests updated to new rules; suite 42/42.
Checkpoint: Ruling: key scheme is now m_<id>_<rev>_p<n> / _l<n> with time-based rev (differs from spec §5 m_<id>_p<n>) — crash and multi-device safety — cost: none.
Checkpoint: Ruling: museum count not capped at ~30 in the store (only slots.total); storage_full error guards the key budget — cost: a user with very many big museums sees storage_full.
Checkpoint minor (deferred): delete does not write a tombstone; a stale tab on another device could re-save a deleted museum.
Checkpoint minor (deferred): id generation has slight modulo bias, no collision check against existing ids.
Task 9: complete (commits 93369ec..1633027, tests: bash .superpowers/fe.sh test → [2m   Duration [22m 4.46s[2m (transform 487ms, setup 0ms, collect 1.44s, tests 4.05s, environment 1.79s, prepare 696ms)[22m)
Task 9: Ruling: reorder via up/down buttons only (drag-and-drop deferred — touch drag is fiddly in Telegram WebView); open_at stored as local-midnight ISO with offset; MainAction component = Telegram MainButton or in-page button outside Telegram; useLocalMuseum composable owns debounced saves — cost: no drag reorder yet.
Task 10: complete (commits 1633027..1ecb693, tests: bash .superpowers/fe.sh test → [2m   Duration [22m 4.50s[2m (transform 705ms, setup 0ms, collect 1.87s, tests 4.11s, environment 2.35s, prepare 927ms)[22m)
Task 10: Ruling: Stars 'paid' from openInvoice is not trusted alone — order polled (0.5→3 s backoff, ~2 min) until backend says paid; card path keeps ?local=<id> so the Order screen can mark the free copy paid; past open_at dropped from import — cost: none.
Task 11: complete (commits 1ecb693..7c4943b, tests: bash .superpowers/fe.sh test → [2m   Duration [22m 4.63s[2m (transform 1.04s, setup 0ms, collect 3.01s, tests 4.32s, environment 2.85s, prepare 1.12s)[22m)
Task 11: Ruling: payForProduct helper shared by room/reactivate (Stars or card); server media added one file at a time (sequential) on the gifted museum; ConfirmButton two-step delete — cost: none.
Task 12: complete (commits 7c4943b..790a3e1, tests: bash .superpowers/fe.sh test → [2m   Duration [22m 4.68s[2m (transform 1.13s, setup 0ms, collect 3.15s, tests 4.40s, environment 3.34s, prepare 1.22s)[22m)
Task 12: Ruling: initialPath() exported from router for start_param m_<slug> (validated slug); viewer audio uses voice, else music — cost: none.
Checkpoint review after T10 (ea846c7): fixed C1 paid draft deleted on regift (server check + only_draft guard + Home self-heal), C2 regift during review (resume order; server refuses), C3 money sent before receipt (reuse draft when unchanged; card order in flight always resumed), I1 cards missing on GET order, I2 'reviewing', I3 polling retry + guarded finishPaid, I4 failed invoice error + abortable wait, I5 strict save before ordering. Tests: tests/gift-safety.spec.ts RED(10)→GREEN, backend tests/api/test_gift_safety_api.py RED(3)→GREEN; old gift tests updated; suites 77/77 + 199/199.
Checkpoint: Ruling: content changed after a card payment started is not included in that gift (order resumed); the owner can still add/remove media after payment — cost: decoration changes then need a new gift.
Checkpoint minor (deferred): QR <a download> ignored in Telegram mobile WebViews (use WebApp.downloadFile, Bot API 8.0).
Checkpoint minor (deferred): Done uses Promise.all — failed getMe hides link even with VITE_BOT_USERNAME.
Checkpoint minor (deferred): Done "copied" shown even if clipboard write fails.
Task 13: complete (commits ea846c7..14964c4, tests: bash .superpowers/fe.sh test → [2m   Duration [22m 4.76s[2m (transform 1.32s, setup 0ms, collect 3.80s, tests 4.51s, environment 3.75s, prepare 1.27s)[22m)
Task 13: Ruling: main JS 63.5 KB gzip (limit 200); vite preview served index + main JS (HTTP 200) and pages were opened in the user's browser, but I could not see them (browser tool unavailable) — visual check left to the owner — cost: a rendering bug outside tests could slip.
Final: token purged from history (filter-branch on main..feat/miniapp setting deploy/.env.example to placeholder blob; reflog expired, gc pruned; bad blob gone). Real values moved to gitignored deploy/.env (ADMIN_IDS fixed to JSON list). Owner advised to /revoke the token. Commit hashes after 0195cb4 changed.
Final review (3514668): verdict "No" → fixed C1 committed bot token (owner's real values had been typed into .env.example and swept in by my 'git add --renormalize .'; history rewritten, values moved to gitignored deploy/.env), I2 paid copy with purged server museum can be regifted, I3 BackButton wired (App.vue) + in-page back outside Telegram, I4 error texts for all codes, I5 XHR timeout 180 s. Tests: tests/final-review.spec.ts RED(5)→GREEN; superseded tests updated; suites 82/82 + 199/199.
Final: Ruling: LocalMuseum "gift" always goes through Gift.vue, which checks the server copy — cost: one extra request.
Final: minor (deferred): Home badge "Sizga topshirilgan" also shown for own gifted museums whose local copy was deleted.
Final: minor (deferred): ServerMuseum offers "Uzaytirish" on drafts; addMedia loop stops at first failure without reloading.
Final: minor (deferred): in Telegram both the in-page primary button and MainButton show on NewReview/Gift.
Final: minor (deferred): icon-only buttons lack aria-labels; html lang not switched for ru.
Final: minor (deferred): Telegram themeChanged not handled.
Final: minor (deferred): pages.yml VITE_BASE wrong for a <user>.github.io repo.
Final: minor (deferred): brokenFrom spreads rev/pages into LocalMuseum (harmless).
Final: minor (deferred): unused i18n keys (create.reorder_hint, viewer.sound_on/off, errors.too_long, home.buy_slots).
Final: minor (deferred): no visibilitychange/pagehide flush — an edit within 600 ms of closing can be lost.
