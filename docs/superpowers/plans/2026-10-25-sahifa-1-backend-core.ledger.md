# SDD ledger — plan: docs/superpowers/plans/2026-10-25-sahifa-1-backend-core.md
Spec: docs/superpowers/specs/2026-10-25-sahifa-design.md
Mode: hybrid inline; fresh reviewer after Task 5, 7, 9, 10; final whole-branch review.
Branch: feat/backend-core from main 61b2bb6

Pre-flight:
- T4 consumes T1 limits_for/locked_fields/validate_open_at/DomainError, T2 slots_status/is_free_now, T3 processors — consistent.
- T4 needs Museum.template — plan says add it in T4; Ruling: add `template` column in T2 models directly — avoids migration churn — cost if wrong: none.
- T5 consumes T2 settings_store.get_price & users.is_free_now; T1 activation_window/reactivated_expiry — consistent.
- T6 consumes T2 slots_status (created_by_id semantics) — consistent.
- T8 consumes T9 make_stars_invoice_link and T10 notify_admins_new_receipt before they exist. Ruling: API takes them as injected callables on app.state (`invoice_link_factory`, `receipt_notifier`); main.py wires real ones — keeps API testable — cost if wrong: small rewiring.
- T7 current_user consumes T2 upsert_user — consistent.
- T11 run_daily consumes T4 delete_museum — consistent.
- Ruling: Task 0 git init done in setup (repo created, .gitignore committed on main) — cost: none.
Task 0: complete (commits 61b2bb6..4841447, tests: bash -c 'cd backend && ../.venv/Scripts/python.exe -m pytest -q' → 1 passed in 0.00s)
Task 1: complete (commits f4f6d56..5450f7e, tests: bash -c 'cd backend && ../.venv/Scripts/python.exe -m pytest -q' → 8 passed in 0.01s)
Task 2: complete (commits 5450f7e..ac5bb70, tests: bash -c 'cd backend && ../.venv/Scripts/python.exe -m pytest -q' → 13 passed in 0.33s)
Task 2: Ruling: added User.blocked_bot + users.find_user(@username/id) now (needed by T10 admin & broadcast) — cost if wrong: unused column
Task 3: complete (commits ac5bb70..b88775f, tests: bash -c 'cd backend && PATH="/c/Users/User/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.2-full_build/bin:$PATH" ../.venv/Scripts/python.exe -m pytest -q' → 19 passed in 1.49s)
Task 3: Ruling: added probe_duration export + MAX_MUSIC_SECONDS=900 (music needs a cap; spec only caps bytes) — cost if wrong: long songs rejected
Task 4: complete (commits b88775f..0ba8ef7, tests: bash .superpowers/t.sh -q → 29 passed in 2.00s)
Task 4: Ruling: museum service funcs that touch files take `media_dir: Path` kwarg (plan signatures omitted it) — no global state — cost if wrong: one extra arg at call sites.
Task 4: Ruling: concurrency guard = count before processing + re-count after insert (delete & media_full if over) instead of BEGIN IMMEDIATE — works with async SQLAlchemy; SQLite serialises writers — cost if wrong: rare over-limit by one under heavy parallel upload.
Task 4: Ruling: settings field music_id maps to lock "music"; set_music_file clears music_id — cost: none.
Task 5: complete (commits 0ba8ef7..1455810, tests: bash .superpowers/t.sh -q → 45 passed in 2.54s)
Task 5: Ruling: ROOM may be bought for a draft too (not only active) — users filling >30 photos before first payment must not be blocked — cost if wrong: none.
Task 5: Ruling: open-order reuse: return an awaiting_review order regardless of method, or a pending one with the same method; other pending ones get new status "cancelled" — prevents double payment — cost: extra status value.
Task 5: Ruling: fulfilling MUSEUM on an already-paid museum (race) extends by 120d like REACTIVATE — user never loses money — cost: none.
Task 5: Ruling: attach_receipt takes media_dir; receipt stored as WebP under media/receipts (served via /media — reviewed in T7 for exposure).
Task 5: Ruling: attach_receipt(receipts_dir=...) — receipts stored outside public media dir (card details) — commit 2920b74
Task 6: complete (commits 2920b74..9f735f6, tests: bash .superpowers/t.sh -q → 51 passed in 2.65s)
Task 6: Ruling: a transfer link dies if the giver no longer owns the museum; added get_pending()/pending_transfer() helpers for bot preview & API — cost: none.
Task 7: complete (commits 9f735f6..83579c3, tests: bash .superpowers/t.sh -q → 62 passed in 2.90s)
Task 7: Ruling: create_app takes invoice_link_factory/receipt_notifier/clock kwargs (see pre-flight); routes commit explicitly instead of a commit-on-exit dependency — avoids FastAPI yield-dependency timing — cost: must remember commit in new routes.
Task 7: Ruling: Settings.receipts_dir = media_dir.parent/"receipts" (private), test_receipts_are_not_public.
Task 7: Ruling: added PUT voice/music + serialize.py shared shapes; upload size enforced while spooling (413 too_large).
Checkpoint review after T5 (74b3da8): fixed I1 receipt-on-deleted, I2 free stacking (SLOTS→not_needed, free REACTIVATE = max(exp, now+120d)), I4 duplicate_payment; minors fixed: unchanged locked values, free beats open order, naive open_at. Tests: tests/services/test_orders_review_fixes.py RED(8)→GREEN, suite 71/71.
Checkpoint: Ruling: delete_museum now rejects only 'pending' orders; 'awaiting_review' stays for admin refund — cost: admin sees orders for deleted museums.
FORWARD (T9): pre_checkout must refuse non-pending orders; successful_payment on duplicate_payment → refund_star_payment automatically.
FORWARD (T11): draft cleanup must skip museums that have paid or awaiting_review orders.
Checkpoint minor (deferred): files unlinked before commit (rollback leaves rows pointing at missing files).
Checkpoint minor (deferred): create_museum slot count race allows +1 under parallel creates.
Checkpoint minor (deferred): museum past expires_at stays editable until daily job marks it expired.
Task 8: complete (commits 74b3da8..94172ff, tests: bash .superpowers/t.sh -q → 79 passed in 3.47s)
Task 8: Ruling: owner gets full view of own draft/locked museum via public endpoint (preview); media files themselves are unguessable uuid URLs under /media — a leaked URL is viewable — cost if wrong: need signed URLs later.
Task 9: complete (commits 94172ff..d2a7f81, tests: bash .superpowers/t.sh -q → 92 passed in 5.65s)
Task 9: Ruling: duplicate/late Stars charges (duplicate_payment, museum_gone) are auto-refunded via refund_star_payment; pre_checkout refuses non-pending (covers cancelled orders) — cost: none.
Checkpoint review after T7 (8475932): fixed I1 ffmpeg playlist/SSRF (format whitelist + protocol_whitelist file; RED not observable on Windows — /etc/hosts absent — test kept for Linux), I2 body limit (BodyLimit ASGI wrapper, 411 without Content-Length, 413 over 60MB), I3 pixel cap 50MP before decode + to_thread + ffmpeg -t/timeout 180s + Semaphore(2), I4 SettingsIn/MediaPatch/Form validation → 400 bad_field. Tests: test_media_hardening.py + api/test_hardening.py RED(6)→GREEN, suite 102/102.
Checkpoint: Ruling: theme/mascot/opening_style/music_id validated as asset keys ^[a-z0-9_]{1,32}$ (exact lists come with plan 3) — cost: frontend may send unknown key that renders default.
Checkpoint: Ruling: bodies without Content-Length are refused (411) — browsers/Telegram WebView always send it — cost: chunked clients unsupported.
Checkpoint minor (deferred): optional_user upserts+commits on every authenticated request (SQLite write per GET).
Checkpoint minor (deferred): initData max age 24h (bearer replay window); duplicate query keys not rejected.
Checkpoint minor (deferred): limit races across parallel transactions (media +1, slots +1).
Task 10: complete (commits 8475932..ff17734, tests: bash .superpowers/t.sh -q → 114 passed in 6.95s)
Task 10: Ruling: review re-uses message.html_text when editing captions (user parts escaped at send) — cost: none.
Task 10: Ruling: rejected-receipt "resend" button opens webapp #/order/<code> (route to be built in plan 2) — cost: frontend must implement that route.
Task 10: Ruling: /bepul notifies the user; Stars /qaytar refuses non-paid/non-stars orders.
Checkpoint review after T9 (fbe0fa0): fixed I1 concurrent charges (atomic claim UPDATE + SQL increments), I2 refund_once (audit stars_refund / stars_refund_failed + admin alert), I3 atomic transfer accept, I4 HTML escaping (html_decoration.quote); minors fixed: cancelled-order Stars refunded, same-charge redelivery no-op, giver-notify guarded, deep-link regex + referrer must exist. Tests: tests/bot/test_payments_review_fixes.py RED(7)→GREEN, suite 122/122.
Checkpoint: Ruling: referral recorded only if referrer is a known user — cost: refs from users who never started the bot are dropped.
Checkpoint minor (deferred): pre_checkout does not re-check museum state (charged then auto-refunded).
Checkpoint minor (deferred): declining a transfer does not cancel it server-side nor notify giver.
Checkpoint review after T10 (c7ef936): fixed I1 review race (orders.claim_for_review → transient 'reviewing'), I2 post-commit side effects wrapped, I3 user told on museum_gone, I4 forward_origin, I5 strict /bepul days, I6/I7 broadcast retry + catch-all, I8 bulk blocked update, I9 /qaytar errors + "rights kept" notice; minors fixed: malformed callback data, callback filter on admin router, 16-digit cards. Tests: tests/bot/test_admin_review_fixes.py RED(9)→GREEN, suite 132/132.
Checkpoint: Ruling: Stars refund via /qaytar keeps granted rights; admin is told to adjust manually — spec says only "Stars qaytarish" — cost: admin must revoke by hand if wanted.
Checkpoint minor (deferred): broadcast runs inside the handler (long-running); no guard against two concurrent /xabar.
Checkpoint minor (deferred): receipt notifier failure (bad admin_chat_id) leaves order awaiting_review silently; /narx has no upper bound.
Task 11: complete (commits c7ef936..55b718e, tests: bash .superpowers/t.sh -q → 138 passed in 7.72s)
Task 11: Ruling: run_daily takes media_dir; drafts with paid/awaiting_review/reviewing orders are never auto-deleted (forward note from T5 review); a late first reminder sends only the closest threshold and marks both.
Task 11: Ruling: build_dispatcher detaches module-level routers so it can be built twice (tests) — cost: touches aiogram private _parent_router.
Task 11: Ruling: main.build() factored out for a wiring test; daily loop polls every 10 min, runs once at 03:00 Tashkent.
Final review (15b178d): verdict "with fixes". Fixed C1 docker perms (uid 1000 + chown doc; not unit-testable — Ruling), I2 payment_unhandled audit+alert, I3 reminder escaping, I4 reminders sent after commit (run_daily now commits), I5 notifier failure tolerated + /cheklar + required admin settings, I6 receipt revives cancelled card order. Tests: tests/test_final_review_fixes.py RED(6)→GREEN, suite 144/144.
Final: Ruling: run_daily commits its own transaction (needed to send after commit) — cost: callers can no longer batch it with other writes.
Final: Ruling: Docker data-permission fix verified by reading only; Docker not available on this Windows machine — cost: first deploy may still need a chown tweak.
Final: minor (deferred): no test for "room bought on handed-over museum lands on the museum".
Final: minor (deferred): non-ASCII hash in initData gives 500 instead of 401.
Final: minor (deferred): setting music_id does not clear an uploaded music_path file.
Final: minor (deferred): SIGTERM leaves polling/daily loop alive until docker kill (10 s).
Final: minor (deferred): daily job skipped if the process is down all of 03:00–03:59.
Final: minor (deferred): crafted "tr:ok" callback data raises ValueError.
Final: minor (deferred): museum_gone rejection writes no audit row.
Final: minor (deferred): __import__("pathlib") in main.build.
Final: minor (deferred): 50 MB upload copy runs on the event loop.
Final: recommendation: add Alembic migrations before plan 2 changes the schema.
