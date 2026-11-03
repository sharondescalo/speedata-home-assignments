#!/bin/bash
# Generate user traffic for the SkyWatch service-health dashboard.
# Each city lookup hits the frontend at / and the backend at /api/weather.
# Health checks are not sent: those panels ignore /healthz and /readyz.
set -euo pipefail

base_url="${SKYWATCH_URL:-http://skywatch.test}"
requests="${REQUESTS:-40}"
pause="${PAUSE:-0.2}"

cities=(Haifa "Tel Aviv" London Tokyo "Nowhereville-xyz")

echo "Sending ${requests} lookups to ${base_url}"
echo "Watch http://grafana.skywatch.test/d/skywatch/skywatch"

frontend_ok=0
frontend_other=0
for ((i = 1; i <= requests; i++)); do
  city="${cities[$((i % ${#cities[@]}))]}"
  code="$(curl -sS -o /dev/null -w '%{http_code}' \
    -X POST "${base_url}/" \
    --data-urlencode "city=${city}" \
    -H 'Content-Type: application/x-www-form-urlencoded')"
  if [[ "${code}" == "200" ]]; then
    frontend_ok=$((frontend_ok + 1))
  else
    frontend_other=$((frontend_other + 1))
  fi
  printf '%s %s POST / city=%s\n' "${i}" "${code}" "${city}"
  sleep "${pause}"
done

echo "frontend 200=${frontend_ok} other=${frontend_other}"
echo "Backend /api/weather was called once per lookup. Unknown cities are 404 there."
echo "The 5xx stat stays empty unless Open-Meteo itself fails."
