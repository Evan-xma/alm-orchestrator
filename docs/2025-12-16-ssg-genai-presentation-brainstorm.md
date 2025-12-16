# SSG GenAI Presentation Brainstorm

**Date:** 2025-12-16
**Status:** Outline Complete

## Context

**Presenter:** Ron Starling, CTO Advisor at EY-Parthenon Software Strategy Group (SSG)

**Audience:**
- 5 CTO advisors (technical peers)
- ~24 Partners (client relationship managers)
- Various consultants and associates (junior diligence practitioners)
- All are diligence practitioners evaluating software companies for PE buyers

**Technical Level:** Medium — understand SDLC concepts (CI/CD, testing, deployment) at high level

**Goal:** Educate the team on what they need to know to evaluate AI adoption in target companies. Provide practical diligence questions they can use when evaluating SaaS companies.

## Key Insight

Most acquisition targets claim they're "using AI" because they have GitHub Copilot. They're unaware of the maturity gap:

| Level | Description | Example |
|-------|-------------|---------|
| **Level 1 — Assisted** | Autocomplete, line-by-line, developer-initiated | GitHub Copilot |
| **Level 2 — Agentic** | AI takes on tasks, multi-file changes, human reviews output | Claude Code, Cursor Agent |
| **Level 3 — Orchestrated** | AI integrated into ALM workflows, triggered by events | ALM Orchestrator |

## Final Direction: Combined Approach

Start with the maturity framework (2-3 slides), then present questions organized by theme with code snippets for credibility.

---

## Approach A: The Maturity Spectrum

**Slide 1: Title**
"Evaluating GenAI in the SDLC: A Maturity Framework for Diligence"

**Slide 2: The Question PE Buyers Are Asking**
"Is this company using AI effectively to build software?" — but most targets (and most diligence teams) lack a framework to answer this.

**Slide 3: The Three Levels**
- **Level 1 — Assisted**: Autocomplete tools (Copilot). Developer-initiated, line-by-line suggestions. Low ceiling.
- **Level 2 — Agentic**: AI takes on tasks (Claude Code, Cursor Agent). Multi-file changes, human reviews output.
- **Level 3 — Orchestrated**: AI integrated into ALM workflows. Triggered by events (Jira labels, PR creation). Human-in-the-loop at checkpoints.

**Slide 4: Why This Matters for Valuation**
Level 1 is table stakes. Level 2-3 adoption signals engineering leadership, velocity advantage, and scalability without linear headcount growth.

**Slide 5: Diligence Questions by Level**
3-4 questions to identify where a target falls. Green/red flag answers for each.

**Slide 6: Case Example — Level 3 in Practice**
Brief walkthrough of ALM Orchestrator: Jira label triggers AI investigation → AI recommends fix → AI implements with human approval → automated code/security review.

**Slide 7: Risks to Probe**
Security posture (prompt injection, secrets exposure), over-reliance, hallucination in production code.

**Slide 8: Summary & Takeaways**
The framework + 3 key questions to always ask.

---

## Approach B: The Diligence Question Bank

**Slide 1: Title**
"10 Questions to Evaluate GenAI Adoption in Software Targets"

**Slide 2: Why These Questions Matter**
Every target says they're "using AI." These questions separate marketing from reality and reveal actual maturity.

**Slide 3: Tooling Questions (2-3 questions)**
- "What AI coding tools are developers using?" → Red flag: "Copilot" and nothing else. Green flag: Multiple tools, agentic options.
- "How are these tools provisioned and governed?" → Red flag: Ad-hoc, individual licenses. Green flag: Centralized, usage tracked.

**Slide 4: Workflow Integration Questions (2-3 questions)**
- "At what points in your SDLC does AI assist?" → Red flag: Only code writing. Green flag: Code review, testing, documentation, investigation.
- "How do developers trigger AI assistance?" → Red flag: Manually in IDE only. Green flag: Automated triggers from tickets, PRs, CI.

*Snippet: Label-to-action mapping*
```python
# Labels trigger specific AI workflows
| ai-investigate | Root cause analysis     |
| ai-fix         | Bug fix implementation  |
| ai-code-review | Automated code review   |
```

**Slide 5: Human-in-the-Loop Questions (2-3 questions)**
- "Who reviews AI-generated code before merge?" → Red flag: No formal process. Green flag: Defined approval gates.
- "What's your rollback story for AI-generated changes?" → Red flag: Blank stare. Green flag: Same as any other code.

*Snippet: The approval flow*
```
Jira ticket + label
    → AI investigates (read-only)
    → AI recommends approach
    → Human approves
    → AI implements + creates PR
    → Human merges
```

**Slide 6: Security & Risk Questions (5 questions)**

- "How do you prevent AI from leaking secrets or credentials?" → Red flag: "We trust the tool." Green flag: Sandboxing, secrets scanning on output.
- "What data is sent to AI providers, and how is it classified?" → Red flag: Don't know. Green flag: Clear policy, no customer data or source code without approval.
- "How do you protect against prompt injection when AI processes untrusted input?" → Red flag: "What's prompt injection?" Green flag: Input/output separation, output validation, limited blast radius.
- "What permissions does the AI have in your environment?" → Red flag: Developer-level access to everything. Green flag: Scoped to task, sandboxed filesystem/network.
- "How do you detect if AI-generated code introduces vulnerabilities?" → Red flag: "Same as regular code review." Green flag: Automated security scans on AI-generated changes, specific review protocols.

*Snippet 1: Agent launched in isolated working directory*
```python
result = subprocess.run(
    ["claude", "-p", prompt, "--output-format", "json"],
    cwd=work_dir,        # Restricted to cloned repo
    capture_output=True,
    timeout=self._timeout,
)
```

*Snippet 2: Read-only sandbox for investigation (can't modify code)*
```json
{
  "permissions": {
    "allow": ["Read(**)", "Glob(**)", "Grep(**)", "Bash(git log:*)"],
    "deny": ["Write(**)", "Edit(**)", "WebFetch", "Bash(curl:*)"]
  }
}
```

*Snippet 3: Read-write sandbox for fixes (still no network egress)*
```json
{
  "permissions": {
    "allow": ["Read(**)", "Write(**)", "Edit(**)", "Bash(pytest:*)"],
    "deny": ["Bash(curl:*)", "Bash(wget:*)", "Bash(ssh:*)"]
  }
}
```

*Snippet 4: Secrets blocked in all profiles*
```json
"deny": [
  "Read(.env)", "Read(.env.*)", "Read(**/.env)", "Read(**/.env.*)"
]
```

**Slide 7: Measurement Questions**
- "How do you measure AI's impact on velocity?" → Red flag: Anecdotes. Green flag: Metrics (cycle time, PR throughput, defect rates).

**Slide 8: Red Flags & Green Flags Summary**
One-page cheat sheet: What good looks like vs. warning signs.

---

## Supporting Materials

**LinkedIn Article:** [The Prompt Injection Problem Isn't Filtering—It's Architecture](https://www.linkedin.com/pulse/prompt-injection-problem-isnt-filtering-its-ron-starling-xggoc)

**Three-Pillar Defense Framework (from article):**
1. **Architecture**: Treat LLM as deterministic function, not autonomous agent. Hardwired orchestrator controls integrations.
2. **Containment**: OS-level sandboxes, restricted filesystem/network, fresh environment per invocation.
3. **Detection**: Structured prompts with boundaries, output validation, permission denial logging.

**ALM Orchestrator Project:** Working Level-3 implementation demonstrating all concepts.

---

## Next Steps

1. Choose final approach (A, B, or combined)
2. Build slide deck
3. Add code snippets and diagrams
4. Rehearse with timing (target: 15-20 minutes for 5-10 slides)
