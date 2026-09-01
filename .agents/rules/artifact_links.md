---
description: Always format artifact links using canonical file paths (file:///home/vscode/.gemini/antigravity-cli/brain/<conversation_id>/<file>.md) for reliable Cmd+Click editor navigation.
globs: ["**/*"]
always_on: true
---

# Artifact Link Formatting Rule

When referencing artifacts (plans, walkthroughs, reports) in chat responses:

1. **Canonical `.brain` Links**:
   - Format links using the absolute file URI `file:///home/vscode/.gemini/antigravity-cli/brain/<conversation_id>/<filename>.md`.

2. **Cmd+Click Compatibility**:
   - Markdown links formatted with the full `file:///` path resolve cleanly inside VS Code without broken `~` prefixing.

