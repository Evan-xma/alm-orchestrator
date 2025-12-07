# Security Review

## Pull Request
**{pr_title}**

{pr_description}

## Changed Files
Review ONLY these files that were modified in the pull request:
{changed_files}

## Your Task

Read each of the files listed above and perform a security-focused review checking for:

1. **Injection vulnerabilities** - SQL, command, XSS, etc.
2. **Authentication/Authorization** - Proper access controls?
3. **Sensitive data handling** - Secrets, PII, logging
4. **Input validation** - All inputs properly validated?
5. **Dependencies** - Known vulnerable dependencies?
6. **OWASP Top 10** - Any of the common vulnerabilities?

Consider the PR description when evaluating security implications of the changes.

IMPORTANT: Only review the files listed above. Do not review other files in the repository.

## Output Format

IMPORTANT: Use plain text only. Do not use Markdown formatting (no #, *, -, ` characters for formatting).

SUMMARY
[Overall security assessment]

HIGH PRIORITY FINDINGS
[Security issues that must be fixed - include severity and remediation]

LOW PRIORITY FINDINGS
[Minor security improvements]

SECURITY RECOMMENDATIONS
[General hardening suggestions]
