# SDD ledger — plan: docs/superpowers/plans/2026-10-25-sahifa-1b-account-museums.md
Mode: inline; final review at end. Base: bac65f0
Pre-flight: T4 consumes T1 verify_media/media_secret and T3 TgFetcher — consistent. T5 implements T2/T3 callables.
Task 1: complete (commits bac65f0..d3b0a71, tests: bash .superpowers/t.sh -q → 149 passed in 7.99s)
Task 2: complete (commits d3b0a71..a803c18, tests: bash .superpowers/t.sh -q → 158 passed in 8.07s)
Task 3: complete (commits d3b0a71..a803c18, tests: bash .superpowers/t.sh -q → 158 passed in 8.17s)
Task 2/3: Ruling: implemented in one commit (same file); create_app tg hooks default to a 'not configured' error so older callers keep working — cost: none. Proxy loads whole file in memory (<=20MB, 4 concurrent) and has no Range support — cost: video seeking re-downloads.
Task 4: complete (commits a803c18..19236d2, tests: bash .superpowers/t.sh -q → 163 passed in 8.72s)
Task 4: Ruling: all tokens verified before any Telegram fetch or disk write; on failure delete_museum removes files and the transaction rolls back — cost: none. Audio tokens rejected as wall items (bad_format).
Task 5: complete (commits 19236d2..3828b7d, tests: bash .superpowers/t.sh -q → 170 passed in 8.86s)
Task 5: Ruling: files sent as documents (no Telegram recompression); BadRequest on send also maps to start_bot (chat not found) — cost: other bad requests reported as start_bot.
Final review (639793b): verdict "No" → fixed C1 content-type detection, I2 Range/206, I3 RetryAfter + telegram_unavailable 503, I4 SAHIFA_MEDIA_SECRET (media_key), I5 per-IP rate limit 120/min (view-token expiry not added — Ruling), I6 pre-count limits + adopt_image/adopt_video (no re-encode; RED for byte-equality not observed — Pillow re-encode was deterministic — kept as guard). Tests: tests/test_review_1b_fixes.py RED(7)→GREEN, suite 178/178.
Final: Ruling: tokens stay non-expiring (CloudStorage holds them forever); exposure bounded by per-IP rate limit — cost: a leaked link stays viewable.
Final: minor (deferred): CRLF/LF churn — add .gitattributes (* text=auto eol=lf) and renormalise.
Final: minor (deferred): empty media_dir/<id>/ directory left after failed import/delete.
Final: minor (deferred): routes_tgmedia imports private _spooled from routes_museums.
Final: minor (deferred): wiring test checks only callable names.
