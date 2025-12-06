"""Tests for PR extraction utility."""

import pytest

from alm_orchestrator.utils.pr_extraction import extract_pr_number, find_pr_in_texts


class TestExtractPrNumber:
    """Tests for extract_pr_number function."""

    def test_extracts_from_github_url(self):
        text = "See https://github.com/owner/repo/pull/42 for details"
        assert extract_pr_number(text) == 42

    def test_extracts_from_pr_hash_format(self):
        text = "PR #123"
        assert extract_pr_number(text) == 123

    def test_extracts_from_pr_colon_format(self):
        text = "PR: 456"
        assert extract_pr_number(text) == 456

    def test_extracts_from_pull_request_format(self):
        text = "Pull Request: #789"
        assert extract_pr_number(text) == 789

    def test_case_insensitive(self):
        text = "pr #42"
        assert extract_pr_number(text) == 42

    def test_returns_none_when_no_pr(self):
        text = "No PR reference here"
        assert extract_pr_number(text) is None

    def test_returns_none_for_empty_string(self):
        assert extract_pr_number("") is None


class TestFindPrInTexts:
    """Tests for find_pr_in_texts function."""

    def test_finds_pr_in_description_only(self):
        result = find_pr_in_texts("PR #42", [])
        assert result == 42

    def test_finds_pr_in_comments_only(self):
        result = find_pr_in_texts("No PR here", ["PR #42"])
        assert result == 42

    def test_description_takes_priority(self):
        result = find_pr_in_texts("PR #1", ["PR #2", "PR #3"])
        assert result == 1

    def test_newest_comment_wins(self):
        # Comments are pre-sorted newest-first by caller
        result = find_pr_in_texts("No PR", ["PR #99", "PR #1"])
        assert result == 99

    def test_returns_none_when_no_pr_anywhere(self):
        result = find_pr_in_texts("Nothing", ["Also nothing", "Still nothing"])
        assert result is None

    def test_returns_none_for_empty_inputs(self):
        result = find_pr_in_texts("", [])
        assert result is None
