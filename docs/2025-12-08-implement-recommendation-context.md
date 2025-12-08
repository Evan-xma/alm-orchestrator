# Implement Action: Recommendation Context Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add recommendation context to the `ai-implement` action so feature implementations can use prior `ai-recommend` results.

**Architecture:** Fetch recommendation comment from Jira using existing `get_recommendation_comment()` method. Format with "## Recommended Approach" header and inject into template via `{prior_analysis_section}` placeholder.

**Tech Stack:** Python, pytest, Jira API (via existing JiraClient)

---

## Task 1: Add Test for Recommendation Context Present

**Files:**
- Create: `tests/test_actions/test_implement.py`

**Step 1: Write the failing test**

```python
"""Tests for implement action handler."""

import pytest
from unittest.mock import MagicMock
from alm_orchestrator.actions.implement import ImplementAction
from alm_orchestrator.claude_executor import ClaudeResult


class TestImplementAction:
    def test_execute_includes_recommendation_context(self, mocker):
        """Test that recommendation context is passed to Claude."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Add user dashboard"
        mock_issue.fields.description = "Create a dashboard for users"

        mock_jira = MagicMock()
        mock_jira.get_recommendation_comment.return_value = (
            "RECOMMENDATIONS\n===============\n\nOption 1: Use React components."
        )

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Implemented dashboard",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = ImplementAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify recommendation context was passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert "prior_analysis_section" in context
        assert "Option 1: Use React components" in context["prior_analysis_section"]
        assert "## Recommended Approach" in context["prior_analysis_section"]
```

**Step 2: Run test to verify it fails**

Run: `cd /home/ronstarling/repos/alm-orchestrator/.worktrees/implement-recommend-context && source .venv/bin/activate && pytest tests/test_actions/test_implement.py::TestImplementAction::test_execute_includes_recommendation_context -v`

Expected: FAIL with KeyError or assertion error (prior_analysis_section not in context)

**Step 3: Commit test**

```bash
git add tests/test_actions/test_implement.py
git commit -m "test: add test for implement recommendation context"
```

---

## Task 2: Add Test for No Recommendation (Silent)

**Files:**
- Modify: `tests/test_actions/test_implement.py`

**Step 1: Add the failing test**

```python
    def test_execute_without_recommendation(self, mocker, caplog):
        """Test that implement works without recommendation context."""
        import logging
        caplog.set_level(logging.INFO)

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Add user dashboard"
        mock_issue.fields.description = "Create a dashboard for users"

        mock_jira = MagicMock()
        mock_jira.get_recommendation_comment.return_value = None

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Implemented dashboard",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = ImplementAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify empty prior analysis section was passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert context["prior_analysis_section"] == ""

        # Verify info log was emitted
        assert any(
            "No recommendation comment found" in record.message
            and "TEST-123" in record.message
            for record in caplog.records
        )
```

**Step 2: Run test to verify it fails**

Run: `cd /home/ronstarling/repos/alm-orchestrator/.worktrees/implement-recommend-context && source .venv/bin/activate && pytest tests/test_actions/test_implement.py::TestImplementAction::test_execute_without_recommendation -v`

Expected: FAIL (prior_analysis_section not in context or no log emitted)

**Step 3: Commit test**

```bash
git add tests/test_actions/test_implement.py
git commit -m "test: add test for implement without recommendation"
```

---

## Task 3: Implement _build_prior_analysis_section Method

**Files:**
- Modify: `src/alm_orchestrator/actions/implement.py`

**Step 1: Add logging import and method**

Add at top of file after existing imports:

```python
import logging

logger = logging.getLogger(__name__)
```

Add method to `ImplementAction` class after `execute` method:

```python
    def _build_prior_analysis_section(self, issue_key: str, jira_client) -> str:
        """Build the prior analysis section from recommendation.

        Args:
            issue_key: The issue key (e.g., "TEST-123").
            jira_client: JiraClient for fetching comments.

        Returns:
            Formatted prior analysis section, or empty string if none found.
        """
        recommendation_comment = jira_client.get_recommendation_comment(issue_key)
        if recommendation_comment:
            return (
                "## Recommended Approach\n\n"
                f"{recommendation_comment}"
            )
        else:
            logger.info(f"No recommendation comment found for {issue_key}")
            return ""
```

**Step 2: Update execute method to call _build_prior_analysis_section**

In the `execute` method, add after line `description = issue.fields.description or ""`:

```python
        # Check for prior analysis results
        prior_analysis_section = self._build_prior_analysis_section(
            issue_key, jira_client
        )
```

Update the `context` dict in `execute_with_template` call to include:

```python
                context={
                    "issue_key": issue_key,
                    "issue_summary": summary,
                    "issue_description": description,
                    "prior_analysis_section": prior_analysis_section,
                },
```

**Step 3: Run tests to verify they pass**

Run: `cd /home/ronstarling/repos/alm-orchestrator/.worktrees/implement-recommend-context && source .venv/bin/activate && pytest tests/test_actions/test_implement.py -v`

Expected: PASS (both tests)

**Step 4: Commit implementation**

```bash
git add src/alm_orchestrator/actions/implement.py
git commit -m "feat: add recommendation context to implement action"
```

---

## Task 4: Update Prompt Template

**Files:**
- Modify: `prompts/implement.md`

**Step 1: Add placeholder to template**

Current template has:

```markdown
## Description
{issue_description}

## Your Task
```

Change to:

```markdown
## Description
{issue_description}

{prior_analysis_section}

## Your Task
```

**Step 2: Run all tests to verify nothing broke**

Run: `cd /home/ronstarling/repos/alm-orchestrator/.worktrees/implement-recommend-context && source .venv/bin/activate && pytest tests/ -v`

Expected: All 109+ tests PASS

**Step 3: Commit template change**

```bash
git add prompts/implement.md
git commit -m "feat: add prior_analysis_section placeholder to implement template"
```

---

## Task 5: Update Documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update action chaining table**

Find the "Action Chaining" section and update the table to include:

```markdown
| Action | Uses Context From |
|--------|-------------------|
| `ai-recommend` | `ai-investigate` results |
| `ai-fix` | `ai-investigate` and `ai-recommend` results |
| `ai-implement` | `ai-recommend` results |
```

**Step 2: Run tests one final time**

Run: `cd /home/ronstarling/repos/alm-orchestrator/.worktrees/implement-recommend-context && source .venv/bin/activate && pytest tests/ -v`

Expected: All tests PASS

**Step 3: Commit documentation**

```bash
git add CLAUDE.md
git commit -m "docs: add implement action to chaining table"
```

---

## Task 6: Final Verification

**Step 1: Run full test suite**

Run: `cd /home/ronstarling/repos/alm-orchestrator/.worktrees/implement-recommend-context && source .venv/bin/activate && pytest tests/ -v`

Expected: All tests PASS (109+ tests)

**Step 2: Review all commits**

Run: `git log --oneline main..HEAD`

Expected commits:
1. `test: add test for implement recommendation context`
2. `test: add test for implement without recommendation`
3. `feat: add recommendation context to implement action`
4. `feat: add prior_analysis_section placeholder to implement template`
5. `docs: add implement action to chaining table`
