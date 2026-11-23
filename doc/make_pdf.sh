#!/usr/bin/env bash
# Build Proposal.pdf from Proposal.md: pandoc (Markdown -> HTML) + headless Chromium via Playwright (HTML -> PDF).
# Requires: pandoc, node with the 'playwright' package and its Chromium.
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
pandoc Proposal.md -f gfm -t html5 -s --metadata title="sky130_cm_ip__ginkgo_hall proposal" \
  --css doc/proposal.css --embed-resources --resource-path=. -o "$tmp/Proposal.html"
# drop pandoc's generated title block; the document's own H1 is the title
python3 -c "import re,sys; p=sys.argv[1]; s=open(p).read(); open(p,'w').write(re.sub(r'<header id=\"title-block-header\">.*?</header>','',s,flags=re.S))" "$tmp/Proposal.html"
HTML="$tmp/Proposal.html" OUT="$PWD/Proposal.pdf" node -e '
const {chromium} = require("playwright");
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto("file://" + process.env.HTML);
  await p.pdf({path: process.env.OUT, format: "A4", printBackground: true, displayHeaderFooter: true,
    headerTemplate: "<span></span>",
    footerTemplate: "<div style=\"font-size:7pt;width:100%;text-align:center;color:#666\">sky130_cm_ip__ginkgo_hall — Proposal — <span class=pageNumber></span>/<span class=totalPages></span></div>",
    margin: {top: "16mm", bottom: "16mm", left: "14mm", right: "14mm"}});
  await b.close();
})();'
rm -rf "$tmp"
echo "wrote Proposal.pdf"
