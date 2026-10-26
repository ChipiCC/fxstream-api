---
description: Run the full definition of done (lint + mypy + tests)
---

Run the full check for this repository:

```
mise run check
```

Fix any failures. Do not weaken Ruff, mypy, or the coverage threshold
(`fail_under` in pyproject.toml) to make it pass — fix the code instead.
