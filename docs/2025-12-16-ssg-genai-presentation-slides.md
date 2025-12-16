# Evaluating GenAI in the SDLC
## A Maturity Framework for Diligence

**Presenter:** Ron Starling, CTO Advisor
**Group:** EY-Parthenon Software Strategy Group

---

## Slide 1: Title

# Evaluating GenAI in the SDLC
### A Maturity Framework for Diligence

Ron Starling | CTO Advisor | Software Strategy Group

---

## Slide 2: The Question PE Buyers Are Asking

> "Is this company using AI effectively to build software?"

**The problem:** Most targets claim they're "using AI" — but we lack a framework to assess it.

**The opportunity:** Structured diligence questions reveal actual maturity vs. marketing.

---

## Slide 3: The Three Levels of AI Adoption

| Level | Name | Description | Example |
|-------|------|-------------|---------|
| **1** | Assisted | Autocomplete, line-by-line, developer-initiated | GitHub Copilot |
| **2** | Agentic | AI takes on tasks, multi-file changes, human reviews output | Cursor, Windsurf, agentic IDEs |
| **3** | Orchestrated | AI integrated into ALM workflows, triggered by events | Jira, Git, TCM + AI integration |

**Key insight:** Most targets are at Level 1 and don't know it.

---

## Slide 4: Why This Matters for Valuation

| Level | Valuation Signal | OSM Proposal |
|-------|------------------|--------------|
| **Level 1** | Table stakes — no differentiation | 2-3 |
| **Level 2** | Engineering leadership, velocity advantage | 3-4 |
| **Level 3** | Scalability without linear headcount growth | 4-5 |

**Diligence implication:** Level 2-3 adoption signals a more capital-efficient engineering organization.

---

## Slide 5: Tooling Questions

### What to Ask

1. **"What AI coding tools are developers using?"**
   - ⚠️ Watch: "Copilot" and nothing else
   - 🟢 Green flag: Multiple tools, agentic options mentioned

2. **"How are these tools provisioned and governed?"**
   - 🔴 Red flag: Ad-hoc, individual licenses, no visibility
   - 🟢 Green flag: Centralized provisioning, usage tracked

**Takeaway:** Copilot is baseline — agentic tooling signals velocity ambition.

---

## Slide 6: Workflow Integration Questions

### What to Ask

3. **"At what points in your SDLC does AI assist?"**
   - 🔴 Red flag: Only code writing
   - 🟢 Green flag: Code review, spec/plan writing, test case writing, test automation, defect analysis, documentation, investigation

4. **"How do developers trigger AI assistance?"**
   - 🔴 Red flag: Manually in IDE only
   - 🟢 Green flag: Automated triggers from tickets, PRs, CI

### What Level 3 Looks Like: Integration Triggers

| Source | Trigger Mechanism | AI Action |
|--------|-------------------|-----------|
| **Jira** | Label added, status transition, automation rule | Defect root cause analysis, recommend implementation/fix options |
| **GitHub** | PR opened, comment, check run, webhook | Code review, security review, fix |
| **CI/CD** | Build failure, test failure, quality gate | Root cause analysis, test case assessment, auto-fix PR |
| **Security** | SAST/DAST finding, CVE alert | Vulnerability triage, recommend remediation |

**Takeaway:** Breadth of AI integration signals organizational maturity — narrow usage just shifts the bottleneck.

---

## Slide 7: Human-in-the-Loop Questions

### What to Ask

5. **"What's your code review process before merge?"**
   - 🔴 Red flag: No formal process
   - ⚠️ Watch: Peer review only
   - 🟢 Green flag: Two reviews required — one human, one AI agent

6. **"What's your rollback story for AI-generated changes?"**
   - 🔴 Red flag: Blank stare
   - 🟢 Green flag: Same as any other code (git revert, feature flags)

### What Level 3 Looks Like

```
PR #847: Fix null pointer in payment service
──────────────────────────────────────────
Created by:     ai-agent
Triggered by:   Jira PROJ-1234 [ai-fix]
Reviews:        ✓ @ai-code-review (AI)
                ✓ @jsmith (human)
CI Status:      ✓ tests passing
Merge:          Approved by @jsmith
```

**Takeaway:** AI review multiplies human reviewer productivity — broader coverage, same accountability.

---

## Slide 8: Security Questions

| Data & Secrets | Permissions & Detection |
|----------------|------------------------|
| 7. **"How do you prevent AI from leaking secrets?"** | 10. **"What permissions does the AI have?"** |
| 🔴 "We trust the tool" | 🔴 Developer-level access to everything |
| 🟢 Sandboxing, secrets scanning on output | 🟢 Scoped to task, sandboxed filesystem/network |
| | |
| 8. **"What data is sent to AI providers?"** | 11. **"How do you detect AI-introduced vulnerabilities?"** |
| 🔴 "Don't know" | 🔴 "Same as regular code review" |
| 🟢 Clear policy, no customer data without approval | 🟢 Automated security scans, specific review protocols |
| | |
| 9. **"How do you protect against prompt injection?"** | |
| 🔴 "What's prompt injection?" | |
| 🟢 Input/output separation, output validation, limited blast radius | |

### What Good Looks Like

**Output Scanning:** Scan AI output for secrets before use
```python
CREDENTIAL_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",                         # AWS Access Key
    r"-----BEGIN .* PRIVATE KEY-----",            # Private keys
    r"eyJ[a-zA-Z0-9_-]*\.eyJ.*\.[a-zA-Z0-9_-]*",  # JWTs
]

def has_high_entropy_strings(text: str) -> bool:
    """Detect random-looking strings (possible secrets)."""
    for word in re.findall(r"[a-zA-Z0-9_\-]{20,}", text):
        if shannon_entropy(word) > 4.5:
            return True
    return False
```

**Agent Isolation & Sandboxing:** Run agent in separate process with restricted permissions
```json
{ "allow": ["Read(**)", "Glob(**)"], "deny": ["Write(**)", "Bash(curl:*)", "Read(.env*)"] }
```
```python
result = subprocess.run(["ai-agent", "-p", prompt], cwd=work_dir, capture_output=True, timeout=600)
```

---

## Slide 9: Measurement Questions

### What to Ask

12. **"How do you measure AI's impact on velocity?"**
    - 🔴 Red flag: Anecdotes ("developers love it")
    - 🟢 Green flag: Metrics (cycle time, PR throughput, defect rates)

13. **"What's the adoption rate across teams?"**
    - 🔴 Red flag: "A few power users"
    - 🟢 Green flag: Org-wide rollout with training

---

## Slide 10: Red Flags & Green Flags Summary

| Area | 🔴 Red Flag | 🟢 Green Flag |
|------|-------------|---------------|
| **Tooling** | Copilot only, ad-hoc licenses | Multiple tools, centralized |
| **Workflow** | Manual IDE only | Automated triggers, multi-stage |
| **Human-in-Loop** | No formal review | Defined approval gates |
| **Security** | "We trust the tool" | Sandboxing, permission scoping |
| **Secrets** | No policy | Explicit blocking, scanning |
| **Measurement** | Anecdotes | Quantified velocity metrics |

---

## Slide 11: Key Takeaways

### The Framework
- **Level 1 (Assisted)** → Table stakes, no moat
- **Level 2 (Agentic)** → Engineering advantage
- **Level 3 (Orchestrated)** → Scalable automation

### The Three Questions That Reveal the Most
1. "At what points in your SDLC does AI assist?" (workflow maturity)
2. "What permissions does the AI have?" (security posture)
3. "How do you measure AI's impact?" (organizational maturity)

### The Bottom Line
Companies that can't articulate their AI strategy beyond "we use Copilot" are at Level 1 — and that's increasingly insufficient.

---

## Appendix: Supporting Resources

- **LinkedIn Article:** [The Prompt Injection Problem Isn't Filtering—It's Architecture](https://www.linkedin.com/pulse/prompt-injection-problem-isnt-filtering-its-ron-starling-xggoc)

- **Three-Pillar Defense Framework:**
  1. **Architecture** — Treat LLM as function, not agent
  2. **Containment** — OS-level sandboxes, fresh environment per task
  3. **Detection** — Structured prompts, output validation, denial logging

---

## Speaker Notes

### Timing Guide (15-20 min total)
- Slides 1-4 (Framework): 4-5 min
- Slides 5-7 (Workflow/Human-in-Loop): 4-5 min
- Slides 8-9 (Security): 4-5 min
- Slides 10-12 (Measurement/Summary): 3-4 min

### Key Points to Emphasize
- The gap between Level 1 and Level 2-3 is significant and most targets don't know it
- Code snippets are from a working implementation, not hypothetical
- Security questions are the most differentiating — most targets haven't thought about prompt injection
- The framework gives Partners a vocabulary for discussing AI maturity with clients
