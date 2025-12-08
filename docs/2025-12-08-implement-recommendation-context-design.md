# Implement Action: Recommendation Context

## Overview

Add recommendation context to the `ai-implement` action, allowing feature implementations to use prior `ai-recommend` results.

## Changes

### implement.py

Add `_build_prior_analysis_section()` method:
- Call `jira_client.get_recommendation_comment(issue_key)`
- Return `## Recommended Approach\n\n<content>` when found
- Return empty string when not found
- Log "No recommendation comment found" when absent

In `execute()`:
- Call `_build_prior_analysis_section()` before template execution
- Pass `prior_analysis_section` in the template context

### prompts/implement.md

Add `{prior_analysis_section}` placeholder after the Description section:

```markdown
## Description
{issue_description}

{prior_analysis_section}

## Your Task
```

### Tests

1. Test with recommendation present - verify content appears in template context
2. Test with no recommendation - verify empty string passed, execution continues
3. Test section formatting - verify "## Recommended Approach" header included

### Documentation

Update `CLAUDE.md` action chaining table to include:

| Action | Uses Context From |
|--------|-------------------|
| `ai-implement` | `ai-recommend` results |

## Behavior

- Silent when no recommendation exists (logged only)
- Mirrors `ai-fix` pattern for consistency
- Only uses recommendation context (not investigation)
