"""Out-of-sample test of the agents: does the AI team add anything the scorecard doesn't?

The model must not know what happened next. Claude Sonnet 4.5's training data ends in July
2025, so every 10-K filed from August 2025 on is unseen. The primary outcomes are what
happened to the business in the next two quarterly reports (margins, growth); stock returns
are secondary. Hypotheses and decision rules are fixed in PREREGISTRATION.md.

    python -m holdout prepare --sample 400   # sample + evidence packs (SEC data only, no API)
    python -m holdout run --dry-run          # whole pipeline with a stub model + cost estimate
    python -m holdout analyze --dry-run      # outcome pipeline on real SEC data, stub signals
    python -m holdout run --split dev        # real model on the dev split (iterate here)
    python -m holdout analyze --split dev
    python -m holdout run --split test       # once, after committing code + preregistration
    python -m holdout analyze --split test   # -> holdout/results/RESULTS_test.md
"""
