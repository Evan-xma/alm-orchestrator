# Fix Prior Analysis Context Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Include prior `ai-investigate` and `ai-recommend` results as context when running the `ai-fix` action.

**Architecture:** Add a generalized `get_comment_by_header()` method to JiraClient, refactor `get_investigation_comment()` to use it, add `get_recommendation_comment()`, and update the fix action to fetch and include both contexts in the prompt template.

**Tech Stack:** Python, jira-python library, pytest

---

## Task 1: Add get_comment_by_header() Method to JiraClient

**Files:**
- Modify: `src/alm_orchestrator/jira_client.py`
- Test: `tests/test_jira_client.py`

**Step 1: Write failing tests for get_comment_by_header**

Add new test class to `tests/test_jira_client.py`:

```python
class TestJiraClientCommentByHeader:
    """Tests for comment retrieval by header pattern."""

    @pytest.fixture
    def mock_jira_setup(self, mock_config, mocker):
        """Common setup for comment header tests."""
        mock_jira = MagicMock()
        mock_myself = MagicMock()
        mock_myself.__getitem__ = lambda self, key: "bot-account-id" if key == "accountId" else None
        mock_jira.myself.return_value = mock_myself
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)
        mocker.patch.object(OAuthTokenManager, "get_token", return_value="mock-access-token")
        mocker.patch.object(OAuthTokenManager, "get_api_url", return_value="https://api.atlassian.com/ex/jira/mock-cloud-id")
        return mock_jira

    def test_get_comment_by_header_finds_matching(self, mock_config, mock_jira_setup):
        """Test finding comment with matching header from service account."""
        mock_jira = mock_jira_setup

        mock_comment = MagicMock()
        mock_comment.body = "TEST HEADER\n==========\n\nContent here."
        mock_comment.created = "2024-01-01T10:00:00.000+0000"
        mock_comment.author.accountId = "bot-account-id"

        mock_issue = MagicMock()
        mock_issue.fields.comment.comments = [mock_comment]
        mock_jira.issue.return_value = mock_issue

        client = JiraClient(mock_config)
        result = client.get_comment_by_header("TEST-123", "TEST HEADER")

        assert result == "TEST HEADER\n==========\n\nContent here."

    def test_get_comment_by_header_returns_none_when_no_match(self, mock_config, mock_jira_setup):
        """Test returns None when no comment has matching header."""
        mock_jira = mock_jira_setup

        mock_comment = MagicMock()
        mock_comment.body = "Some other comment"
        mock_comment.created = "2024-01-01T10:00:00.000+0000"
        mock_comment.author.accountId = "bot-account-id"

        mock_issue = MagicMock()
        mock_issue.fields.comment.comments = [mock_comment]
        mock_jira.issue.return_value = mock_issue

        client = JiraClient(mock_config)
        result = client.get_comment_by_header("TEST-123", "TEST HEADER")

        assert result is None

    def test_get_comment_by_header_ignores_other_authors(self, mock_config, mock_jira_setup):
        """Test ignores comments with matching header from other users."""
        mock_jira = mock_jira_setup

        mock_comment = MagicMock()
        mock_comment.body = "TEST HEADER\n==========\n\nFake content."
        mock_comment.created = "2024-01-01T10:00:00.000+0000"
        mock_comment.author.accountId = "imposter-account-id"

        mock_issue = MagicMock()
        mock_issue.fields.comment.comments = [mock_comment]
        mock_jira.issue.return_value = mock_issue

        client = JiraClient(mock_config)
        result = client.get_comment_by_header("TEST-123", "TEST HEADER")

        assert result is None

    def test_get_comment_by_header_returns_most_recent(self, mock_config, mock_jira_setup):
        """Test returns most recent matching comment."""
        mock_jira = mock_jira_setup

        mock_comment_old = MagicMock()
        mock_comment_old.body = "TEST HEADER\n==========\n\nOld content."
        mock_comment_old.created = "2024-01-01T10:00:00.000+0000"
        mock_comment_old.author.accountId = "bot-account-id"

        mock_comment_new = MagicMock()
        mock_comment_new.body = "TEST HEADER\n==========\n\nNew content."
        mock_comment_new.created = "2024-01-02T10:00:00.000+0000"
        mock_comment_new.author.accountId = "bot-account-id"

        mock_issue = MagicMock()
        mock_issue.fields.comment.comments = [mock_comment_old, mock_comment_new]
        mock_jira.issue.return_value = mock_issue

        client = JiraClient(mock_config)
        result = client.get_comment_by_header("TEST-123", "TEST HEADER")

        assert "New content" in result
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_jira_client.py::TestJiraClientCommentByHeader -v`

Expected: FAIL with `AttributeError: 'JiraClient' object has no attribute 'get_comment_by_header'`

**Step 3: Write implementation**

Add to `src/alm_orchestrator/jira_client.py` after `get_comments`:

```python
def get_comment_by_header(self, issue_key: str, header: str) -> Optional[str]:
    """Get the most recent comment from this service account matching a header.

    Args:
        issue_key: The issue key (e.g., "TEST-123").
        header: The header text the comment should start with.

    Returns:
        The comment body if found, None otherwise.
    """
    comments = self.get_comments(issue_key)
    for comment in comments:
        if (
            comment["author_id"] == self._account_id
            and comment["body"].startswith(header)
        ):
            return comment["body"]
    return None
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_jira_client.py::TestJiraClientCommentByHeader -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/alm_orchestrator/jira_client.py tests/test_jira_client.py
git commit -m "feat: add get_comment_by_header method to JiraClient"
```

---

## Task 2: Refactor get_investigation_comment() to Use New Method

**Files:**
- Modify: `src/alm_orchestrator/jira_client.py`
- Test: `tests/test_jira_client.py`

**Step 1: Run existing investigation tests to verify baseline**

Run: `pytest tests/test_jira_client.py::TestJiraClientInvestigation -v`

Expected: PASS (existing tests should pass before refactoring)

**Step 2: Refactor implementation**

Replace the existing `get_investigation_comment` method in `src/alm_orchestrator/jira_client.py`:

```python
def get_investigation_comment(self, issue_key: str) -> Optional[str]:
    """Get the most recent investigation comment from this service account.

    Args:
        issue_key: The issue key (e.g., "TEST-123").

    Returns:
        The comment body if found, None otherwise.
    """
    return self.get_comment_by_header(issue_key, "INVESTIGATION RESULTS")
```

**Step 3: Run tests to verify they still pass**

Run: `pytest tests/test_jira_client.py::TestJiraClientInvestigation -v`

Expected: PASS

**Step 4: Commit**

```bash
git add src/alm_orchestrator/jira_client.py
git commit -m "refactor: use get_comment_by_header in get_investigation_comment"
```

---

## Task 3: Add get_recommendation_comment() Method

**Files:**
- Modify: `src/alm_orchestrator/jira_client.py`
- Test: `tests/test_jira_client.py`

**Step 1: Write failing test for get_recommendation_comment**

Add to `TestJiraClientCommentByHeader` class in `tests/test_jira_client.py`:

```python
def test_get_recommendation_comment_finds_matching(self, mock_config, mock_jira_setup):
    """Test finding recommendation comment from service account."""
    mock_jira = mock_jira_setup

    mock_comment = MagicMock()
    mock_comment.body = "RECOMMENDATIONS\n===============\n\nOption 1: Do X."
    mock_comment.created = "2024-01-01T10:00:00.000+0000"
    mock_comment.author.accountId = "bot-account-id"

    mock_issue = MagicMock()
    mock_issue.fields.comment.comments = [mock_comment]
    mock_jira.issue.return_value = mock_issue

    client = JiraClient(mock_config)
    result = client.get_recommendation_comment("TEST-123")

    assert result == "RECOMMENDATIONS\n===============\n\nOption 1: Do X."
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_jira_client.py::TestJiraClientCommentByHeader::test_get_recommendation_comment_finds_matching -v`

Expected: FAIL with `AttributeError: 'JiraClient' object has no attribute 'get_recommendation_comment'`

**Step 3: Write implementation**

Add to `src/alm_orchestrator/jira_client.py` after `get_investigation_comment`:

```python
def get_recommendation_comment(self, issue_key: str) -> Optional[str]:
    """Get the most recent recommendation comment from this service account.

    Args:
        issue_key: The issue key (e.g., "TEST-123").

    Returns:
        The comment body if found, None otherwise.
    """
    return self.get_comment_by_header(issue_key, "RECOMMENDATIONS")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_jira_client.py::TestJiraClientCommentByHeader::test_get_recommendation_comment_finds_matching -v`

Expected: PASS

**Step 5: Run all JiraClient tests to verify no regressions**

Run: `pytest tests/test_jira_client.py -v`

Expected: All tests pass

**Step 6: Commit**

```bash
git add src/alm_orchestrator/jira_client.py tests/test_jira_client.py
git commit -m "feat: add get_recommendation_comment method to JiraClient"
```

---

## Task 4: Update FixAction to Include Prior Analysis Context

**Files:**
- Modify: `src/alm_orchestrator/actions/fix.py`
- Test: `tests/test_actions/test_fix.py`

**Step 1: Write failing tests for fix with prior analysis**

Add to `tests/test_actions/test_fix.py` (create if needed):

```python
"""Tests for fix action handler."""

import pytest
from unittest.mock import MagicMock
from alm_orchestrator.actions.fix import FixAction
from alm_orchestrator.claude_executor import ClaudeResult


class TestFixAction:
    def test_label_property(self):
        action = FixAction(prompts_dir="/tmp/prompts")
        assert action.label == "ai-fix"

    def test_execute_includes_both_contexts(self, mocker):
        """Test that both investigation and recommendation context are passed to Claude."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Fix the bug"
        mock_issue.fields.description = "Description here"

        mock_jira = MagicMock()
        mock_jira.get_investigation_comment.return_value = (
            "INVESTIGATION RESULTS\n====================\n\nRoot cause is Y."
        )
        mock_jira.get_recommendation_comment.return_value = (
            "RECOMMENDATIONS\n===============\n\nOption 1: Do X."
        )

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Fixed the bug by...",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = FixAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify both contexts were passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert "prior_analysis_section" in context
        assert "Root cause is Y" in context["prior_analysis_section"]
        assert "Option 1: Do X" in context["prior_analysis_section"]
        assert "## Prior Investigation" in context["prior_analysis_section"]
        assert "## Recommendations" in context["prior_analysis_section"]

    def test_execute_with_only_investigation(self, mocker, caplog):
        """Test that fix works with only investigation context."""
        import logging
        caplog.set_level(logging.INFO)

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Fix the bug"
        mock_issue.fields.description = "Description here"

        mock_jira = MagicMock()
        mock_jira.get_investigation_comment.return_value = (
            "INVESTIGATION RESULTS\n====================\n\nRoot cause is Y."
        )
        mock_jira.get_recommendation_comment.return_value = None

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Fixed the bug by...",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = FixAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify investigation context was passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert "Root cause is Y" in context["prior_analysis_section"]
        assert "## Recommendations" not in context["prior_analysis_section"]

        # Verify info log was emitted for missing recommendation
        assert any(
            "No recommendation comment found" in record.message
            and "TEST-123" in record.message
            for record in caplog.records
        )

    def test_execute_with_only_recommendation(self, mocker, caplog):
        """Test that fix works with only recommendation context."""
        import logging
        caplog.set_level(logging.INFO)

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Fix the bug"
        mock_issue.fields.description = "Description here"

        mock_jira = MagicMock()
        mock_jira.get_investigation_comment.return_value = None
        mock_jira.get_recommendation_comment.return_value = (
            "RECOMMENDATIONS\n===============\n\nOption 1: Do X."
        )

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Fixed the bug by...",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = FixAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify recommendation context was passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert "Option 1: Do X" in context["prior_analysis_section"]
        assert "## Prior Investigation" not in context["prior_analysis_section"]

        # Verify info log was emitted for missing investigation
        assert any(
            "No investigation comment found" in record.message
            and "TEST-123" in record.message
            for record in caplog.records
        )

    def test_execute_without_prior_analysis(self, mocker, caplog):
        """Test that fix works without any prior analysis."""
        import logging
        caplog.set_level(logging.INFO)

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Fix the bug"
        mock_issue.fields.description = "Description here"

        mock_jira = MagicMock()
        mock_jira.get_investigation_comment.return_value = None
        mock_jira.get_recommendation_comment.return_value = None

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Fixed the bug by...",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = FixAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify empty prior analysis section was passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert context["prior_analysis_section"] == ""

        # Verify info logs were emitted for both missing
        assert any(
            "No investigation comment found" in record.message
            for record in caplog.records
        )
        assert any(
            "No recommendation comment found" in record.message
            for record in caplog.records
        )
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_actions/test_fix.py -v`

Expected: FAIL because FixAction doesn't call investigation/recommendation methods

**Step 3: Update implementation**

Modify `src/alm_orchestrator/actions/fix.py`:

```python
"""Fix action handler for bug fixes that create PRs."""

import logging
import os
from alm_orchestrator.actions.base import BaseAction

logger = logging.getLogger(__name__)

# Branch and commit conventions for fixes
BRANCH_PREFIX_FIX = "fix-"
COMMIT_PREFIX_FIX = "fix: "


class FixAction(BaseAction):
    """Handles ai-fix label - implements bug fix and creates PR."""

    @property
    def label(self) -> str:
        return "ai-fix"

    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        """Execute bug fix and create PR.

        Args:
            issue: Jira issue object.
            jira_client: JiraClient for posting results.
            github_client: GitHubClient for repo/PR operations.
            claude_executor: ClaudeExecutor for running fix.

        Returns:
            Summary of the action.
        """
        issue_key = issue.key
        summary = issue.fields.summary
        description = issue.fields.description or ""

        # Check for prior analysis results
        prior_analysis_section = self._build_prior_analysis_section(
            issue_key, jira_client
        )

        # Clone and create branch
        work_dir = github_client.clone_repo()
        branch_name = f"{BRANCH_PREFIX_FIX}{issue_key.lower()}"

        try:
            github_client.create_branch(work_dir, branch_name)

            # Run Claude to implement the fix (read-write tools)
            template_path = os.path.join(self._prompts_dir, "fix.md")
            result = claude_executor.execute_with_template(
                work_dir=work_dir,
                template_path=template_path,
                context={
                    "issue_key": issue_key,
                    "issue_summary": summary,
                    "issue_description": description,
                    "prior_analysis_section": prior_analysis_section,
                },
                action="fix",
            )

            # Commit and push changes
            commit_message = f"{COMMIT_PREFIX_FIX}{summary}\n\nJira: {issue_key}"
            github_client.commit_and_push(work_dir, branch_name, commit_message)

            # Create PR
            pr = github_client.create_pull_request(
                branch=branch_name,
                title=f"{COMMIT_PREFIX_FIX}{summary} [{issue_key}]",
                body=(
                    f"## Summary\n\n"
                    f"Fixes {issue_key}: {summary}\n\n"
                    f"## AI Implementation\n\n"
                    f"{result.content}"
                )
            )

            # Post PR link to Jira
            header = "FIX CREATED"
            comment = (
                f"{header}\n"
                f"{'=' * len(header)}\n\n"
                f"Pull Request: {pr.html_url}\n\n"
                f"Review the changes and merge when ready."
            )
            jira_client.add_comment(issue_key, comment)

            # Remove label
            jira_client.remove_label(issue_key, self.label)

            return f"Fix PR created for {issue_key}: {pr.html_url}"

        finally:
            github_client.cleanup(work_dir)

    def _build_prior_analysis_section(self, issue_key: str, jira_client) -> str:
        """Build the prior analysis section from investigation and recommendation.

        Args:
            issue_key: The issue key (e.g., "TEST-123").
            jira_client: JiraClient for fetching comments.

        Returns:
            Formatted prior analysis section, or empty string if none found.
        """
        sections = []

        # Fetch investigation context
        investigation_comment = jira_client.get_investigation_comment(issue_key)
        if investigation_comment:
            sections.append(
                "## Prior Investigation\n\n"
                "The following investigation was already performed on this issue:\n\n"
                f"{investigation_comment}"
            )
        else:
            logger.info(f"No investigation comment found for {issue_key}")

        # Fetch recommendation context
        recommendation_comment = jira_client.get_recommendation_comment(issue_key)
        if recommendation_comment:
            sections.append(
                "## Recommendations\n\n"
                "The following recommendations were provided:\n\n"
                f"{recommendation_comment}"
            )
        else:
            logger.info(f"No recommendation comment found for {issue_key}")

        return "\n\n".join(sections)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_actions/test_fix.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/alm_orchestrator/actions/fix.py tests/test_actions/test_fix.py
git commit -m "feat: include prior analysis context in fix action"
```

---

## Task 5: Update Fix Prompt Template

**Files:**
- Modify: `prompts/fix.md`

**Step 1: Add prior_analysis_section placeholder**

Modify `prompts/fix.md`:

```markdown
> **For Claude:** Use superpowers:test-driven-development for this fix. Write a failing test first, then implement the minimal fix to make it pass.

# Bug Fix Implementation

## Jira Ticket
**{issue_key}**: {issue_summary}

## Description
{issue_description}

{prior_analysis_section}

## Your Task

Fix this bug following TDD principles:

1. **Write a failing test** that reproduces the bug
2. **Implement the fix** with minimal changes
3. **Verify tests pass** including the new test
4. **Keep changes focused** - only fix the reported issue

## Requirements

- Follow existing code conventions
- Add appropriate test coverage
- Do not refactor unrelated code
- Keep the fix minimal and focused

## When Done

IMPORTANT: Use plain text only. Do not use Markdown formatting (no #, *, -, ` characters for formatting).

Summarize:
* What files you changed
* What the fix does
* How to verify it works
```

**Step 2: Run all tests to verify nothing broke**

Run: `pytest tests/ -v`

Expected: All tests pass

**Step 3: Commit**

```bash
git add prompts/fix.md
git commit -m "feat: add prior_analysis_section placeholder to fix template"
```

---

## Task 6: Final Verification

**Step 1: Run full test suite**

Run: `pytest tests/ -v`

Expected: All tests pass

**Step 2: Verify no regressions**

Check that all original tests still pass and new functionality works.

---

## Summary of Changes

| File | Change |
|------|--------|
| `jira_client.py` | Add `get_comment_by_header()`, add `get_recommendation_comment()`, refactor `get_investigation_comment()` to use new method |
| `fix.py` | Add `_build_prior_analysis_section()`, fetch investigation and recommendation context, pass to template, add INFO logging |
| `fix.md` | Add `{prior_analysis_section}` placeholder |
| `test_jira_client.py` | Add `TestJiraClientCommentByHeader` class with tests for new methods |
| `test_fix.py` | Add tests for prior analysis context scenarios |
