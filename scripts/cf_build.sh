#!/usr/bin/env bash
# Cloudflare Pages / GitHub Actions build script (Linux).
# Configure the Pages build command as:  bash scripts/cf_build.sh
# and the output directory as:           dist
set -euo pipefail

python3 -m pip install --quiet holidays

python3 scripts/fetch_cache.py
python3 scripts/fetch_openholidays.py
python3 scripts/fetch_school.py
python3 scripts/fetch_lib.py
python3 scripts/assemble.py
python3 scripts/audit.py
python3 scripts/build_site.py \
  --site-url "${SITE_URL:-https://holidaykit.pages.dev}" \
  --contact-email "${CONTACT_EMAIL:-hello@example.com}" \
  --affiliate-url "${AFFILIATE_URL:-}" \
  --adsense-client "${ADSENSE_CLIENT:-}" \
  --google-site-verification "${GOOGLE_VERIFICATION:-}" \
  --indexnow-key "${INDEXNOW_KEY:-}"

echo "cf_build: dist ready"
