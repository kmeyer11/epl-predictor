#!/bin/sh
# Container entry point: refresh the predictions now and then daily at
# REFRESH_AT (UTC), and serve the dashboard on PORT.
#
# The default 06:00 UTC is before the earliest Premier League kickoff, so
# `predict` saves every day's bets before the matches start.
set -u

PORT="${PORT:-8010}"
REFRESH_AT="${REFRESH_AT:-06:00}"

refresh_loop() {
    while true; do
        echo "[$(date -u '+%F %T')] daily refresh starting"
        python -m epl_predictor.cli daily || echo "[$(date -u '+%F %T')] daily refresh had errors"
        next=$(date -u -d "tomorrow $REFRESH_AT" +%s)
        echo "[$(date -u '+%F %T')] next refresh at $(date -u -d "@$next" '+%F %T') UTC"
        sleep $((next - $(date -u +%s)))
    done
}

refresh_loop &
exec python -m http.server "$PORT" --directory site
