#!/bin/bash
# Auto-update COVERAGE.md based on present spec-files
echo "# Specs Coverage" > backend/specs/COVERAGE.md
echo "" >> backend/specs/COVERAGE.md
echo "Auto-generated $(date +%Y-%m-%d). Re-run \`bash backend/specs/_gen-coverage.sh\`." >> backend/specs/COVERAGE.md
echo "" >> backend/specs/COVERAGE.md
echo "## Modules with spec.md" >> backend/specs/COVERAGE.md
ls backend/specs/*.md | grep -v COVERAGE | xargs -n1 basename | sed 's/.md$//' | while read m; do
  has_test=""
  if [ -f "backend/specs/test_$m.py" ]; then has_test="✓ test"; fi
  echo "- \`$m\` $has_test" >> backend/specs/COVERAGE.md
done
