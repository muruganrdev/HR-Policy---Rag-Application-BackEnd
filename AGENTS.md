# Agent Instructions for HR Policy RAG Codebase

Welcome to the HR Policy RAG repository.

## Mandatory Rule Before Modifying the Application

Before exploring the repository or implementing any code changes:

1. **Read `docs/COPILOT_PROJECT_CONTEXT.md` first.**
   This document records the actual architecture, request flows, role access controls, registered tools, test locations, and known constraints of this project.
2. **Inspect only the necessary files** required for the specific task at hand. Do not scan the entire codebase repeatedly.
3. **Preserve the Agent-First Architecture:**
   - The Agent (`app/agent.py` in single mode, `app/multi_agent/orchestrator.py` in multi mode) is the main entry point for all questions.
   - Never reintroduce Direct RAG as a competing top-level path that bypasses the Agent. RAG is exposed as an internal retrieval capability via `lookup_policy` or `PolicyRetrievalSpecialist`.
4. **Preserve Least-Privilege Role Authorization:**
   - Always enforce access boundaries in `app/security.py`. Never treat client-supplied parameters as proof of identity without authenticated principal validation.
   - Do not weaken privacy protections for employee-specific private data (salaries, leave balances, personalized dispositions).
5. **Update `docs/COPILOT_PROJECT_CONTEXT.md` after completing any implementation task:**
   - Record modified files and rationale.
   - Record actual test commands executed and their real results.
   - Never claim a test passed unless it was actually executed.
