---
description: Always format artifact links using workspace-relative or workspace file paths (file:///workspaces/hebras-ai/.brain/<conversation_id>/<file>.md) for reliable Cmd+Click editor navigation.
globs: ["**/*"]
always_on: true
---

# Artifact Link Formatting Rule

When referencing artifacts (plans, walkthroughs, reports) in chat responses:

1. **Workspace `.brain` Links**:
   - Format links using the workspace symlink `file:///workspaces/hebras-ai/.brain/<conversation_id>/<filename>.md`.
   - Alternatively, display the raw path `~/.gemini/antigravity-cli/brain/<conversation_id>/<filename>.md`.

2. **Cmd+Click Compatibility**:
   - Markdown links formatted as `file:///workspaces/hebras-ai/.brain/<conversation_id>/<filename>.md` resolve cleanly inside VS Code without broken `~` prefixing.
