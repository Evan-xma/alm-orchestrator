"""Utility functions for extracting PR references from text."""

import re
from typing import List, Optional


def extract_pr_number(text: str) -> Optional[int]:
    """Extract PR number from a single text string.

    Looks for patterns like:
    - PR: https://github.com/owner/repo/pull/42
    - Pull Request: #42
    - PR #42

    Args:
        text: Text to search for PR reference.

    Returns:
        PR number if found, None otherwise.
    """
    patterns = [
        r"github\.com/[^/]+/[^/]+/pull/(\d+)",
        r"PR[:\s#]+(\d+)",
        r"Pull Request[:\s#]+(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def find_pr_in_texts(description: str, comments: List[str]) -> Optional[int]:
    """Find PR number, checking description first, then comments.

    Args:
        description: Issue description text.
        comments: List of comment bodies, sorted newest-first.

    Returns:
        PR number if found, None otherwise.
    """
    pr_number = extract_pr_number(description)
    if pr_number:
        return pr_number

    for comment in comments:
        pr_number = extract_pr_number(comment)
        if pr_number:
            return pr_number

    return None
