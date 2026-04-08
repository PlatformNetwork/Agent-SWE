"""Agent-based complexity evaluator for SWE tasks.

Uses LLM with function calling to assess task complexity:
- Analyzes patch (lines changed, files modified)
- Analyzes tests and prompt
- REASONS about difficulty
- SUBMITS structured verdict
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ComplexityVerdict:
    """Verdict from complexity evaluation."""
    score: float  # 0.0 (trivial) to 1.0 (very complex)
    difficulty: str  # "easy", "medium", "hard"
    reasoning: str
    details: dict[str, Any] | None = None


@dataclass
class PatchAnalysis:
    """Analysis of the patch."""
    lines_added: int
    lines_removed: int
    lines_changed: int
    files_modified: int
    is_single_line: bool
    is_comment_only: bool
    is_doc_only: bool
    is_rename: bool
    change_types: list[str] = field(default_factory=list)


def analyze_patch(patch: str) -> PatchAnalysis:
    """Analyze patch complexity using diff parsing heuristics."""
    if not patch:
        return PatchAnalysis(
            lines_added=0, lines_removed=0, lines_changed=0,
            files_modified=0, is_single_line=True, is_comment_only=True,
            is_doc_only=True, is_rename=False, change_types=[]
        )
    
    lines = patch.split('\n')
    
    # Count added/removed lines (excluding headers)
    added = sum(1 for l in lines if l.startswith('+') and not l.startswith('+++'))
    removed = sum(1 for l in lines if l.startswith('-') and not l.startswith('---'))
    
    # Count files modified
    files = set()
    for l in lines:
        if l.startswith('+++ b/'):
            files.add(l[6:])
    files_modified = len(files)
    
    # Check if single line change
    is_single_line = added <= 1 and removed <= 1
    
    # Check if comment-only
    added_lines = [l[1:].strip() for l in lines if l.startswith('+') and not l.startswith('+++') and l[1:].strip()]
    is_comment_only = all(
        l.startswith('#') or l.startswith('//') or l.startswith('/*') or 
        l.startswith('*') or l.startswith('"""') or l.startswith("'''")
        for l in added_lines
    ) if added_lines else True
    
    # Check if rename-only
    is_rename = 'rename' in patch.lower() and added == removed
    
    # Detect change types
    change_types = []
    patch_lower = patch.lower()
    if 'def ' in patch or 'class ' in patch or 'if ' in patch or 'for ' in patch:
        change_types.append('logic')
    if 'test' in patch_lower or 'assert' in patch_lower:
        change_types.append('test')
    if 'import' in patch or 'require' in patch or 'from ' in patch:
        change_types.append('import')
    if 'config' in patch_lower or 'setting' in patch_lower:
        change_types.append('config')
    if 'doc' in patch_lower or 'comment' in patch_lower or 'readme' in patch_lower:
        change_types.append('doc')
    
    return PatchAnalysis(
        lines_added=added,
        lines_removed=removed,
        lines_changed=added + removed,
        files_modified=files_modified,
        is_single_line=is_single_line,
        is_comment_only=is_comment_only,
        is_doc_only=is_comment_only,
        is_rename=is_rename,
        change_types=change_types or ['unknown']
    )


# Tool schema for submit_verdict function
SUBMIT_VERDICT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "submit_verdict",
        "description": "Submit your complexity evaluation verdict. Call this AFTER reasoning about the task.",
        "parameters": {
            "type": "object",
            "properties": {
                "score": {
                    "type": "number",
                    "description": "Complexity score from 0.0 (trivial) to 1.0 (very complex)"
                },
                "difficulty": {
                    "type": "string",
                    "enum": ["easy", "medium", "hard"],
                    "description": "Difficulty category"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Detailed reasoning explaining the score"
                },
                "patch_amount": {
                    "type": "string",
                    "enum": ["single-line", "few-lines", "many-lines"],
                    "description": "Amount of code changed"
                },
                "logic_complexity": {
                    "type": "string",
                    "enum": ["trivial", "simple", "moderate", "complex"],
                    "description": "Complexity of the logic involved"
                },
                "context_needed": {
                    "type": "string",
                    "enum": ["minimal", "some", "significant"],
                    "description": "How much context understanding is needed"
                },
                "reject": {
                    "type": "boolean",
                    "description": "True if task should be rejected (too trivial/invalid)"
                },
                "reject_reason": {
                    "type": "string",
                    "description": "Reason for rejection if reject=true"
                }
            },
            "required": ["score", "difficulty", "reasoning"]
        }
    }
}


class ComplexityEvaluator:
    """
    Agent-based complexity evaluator using LLM function calling.
    
    Evaluates task complexity by:
    1. Analyzing patch (lines, files, change types)
    2. Analyzing tests and prompt
    3. Using LLM to REASON about difficulty
    4. Enforcing structured SUBMIT_VERDICT output
    """
    
    # Complexity thresholds
    EASY_THRESHOLD = 0.35
    MEDIUM_THRESHOLD = 0.65
    
    # Minimum score to accept task
    MIN_ACCEPTABLE_SCORE = 0.25
    
    def __init__(
        self,
        model: str = "moonshotai/kimi-k2.5:nitro",
        api_key: str | None = None,
        api_base: str = "https://openrouter.ai/api/v1"
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.api_base = api_base
    
    def evaluate(
        self,
        patch: str,
        tests: list[str],
        prompt: str,
        repo_context: dict[str, Any] | None = None
    ) -> ComplexityVerdict:
        """
        Evaluate task complexity using agentic reasoning.
        
        Args:
            patch: The unified diff patch
            tests: List of test commands
            prompt: Task description
            repo_context: Additional repo info (language, stars, etc.)
        
        Returns:
            ComplexityVerdict with score, difficulty, and reasoning
        """
        from openai import OpenAI
        
        # Analyze patch first
        patch_analysis = analyze_patch(patch)
        
        # Quick rejection for obvious trivial cases
        if patch_analysis.is_single_line and not patch_analysis.change_types:
            return ComplexityVerdict(
                score=0.1,
                difficulty="easy",
                reasoning="Single-line change with no logic modification",
                details={"reject": True, "reject_reason": "Trivial single-line change"}
            )
        
        if patch_analysis.is_comment_only:
            return ComplexityVerdict(
                score=0.05,
                difficulty="easy",
                reasoning="Comment/documentation-only change",
                details={"reject": True, "reject_reason": "Comment-only change"}
            )
        
        if patch_analysis.is_rename:
            return ComplexityVerdict(
                score=0.1,
                difficulty="easy",
                reasoning="Rename-only change",
                details={"reject": True, "reject_reason": "Rename-only change"}
            )
        
        # Build evaluation prompt
        system_prompt = """You are a complexity evaluator for software engineering tasks.

Your job is to assess how difficult a coding task is by analyzing:
1. The patch (what changes are needed)
2. The tests (what behavior must be understood)
3. The prompt (what the agent is asked to do)

REASON through each aspect carefully:
- Is this a typo fix? (score: 0.1)
- Is this a single config line? (score: 0.15)
- Does it require understanding existing code? (score: +0.2)
- Does it require multi-file changes? (score: +0.15)
- Does it require complex logic? (score: +0.2)
- Does it require understanding domain concepts? (score: +0.1)

Scoring guide:
- 0.0-0.25: Trivial (typo, single config, rename) → REJECT
- 0.25-0.4: Easy but acceptable (simple logic fix)
- 0.4-0.6: Medium (multiple functions, some reasoning)
- 0.6-0.8: Hard (cross-file changes, complex logic)
- 0.8-1.0: Very Hard (architectural, complex bugs)

You MUST call the submit_verdict function with your analysis."""

        user_prompt = f"""
## Task Prompt
{prompt}

## Patch Analysis
- Lines added: {patch_analysis.lines_added}
- Lines removed: {patch_analysis.lines_removed}
- Files modified: {patch_analysis.files_modified}
- Is single-line: {patch_analysis.is_single_line}
- Is comment-only: {patch_analysis.is_comment_only}
- Change types: {patch_analysis.change_types}

## Actual Patch
```diff
{patch[:3000]}
```

## Tests to Pass
{chr(10).join(f"- {t}" for t in tests) if tests else "No specific tests"}

## Repository Context
{json.dumps(repo_context, indent=2) if repo_context else "Not provided"}

REASON about the complexity:
1. What kind of change is this?
2. How much code context is needed?
3. What makes this easy or hard?
4. Should this task be rejected as too trivial?

Then SUBMIT your verdict using the submit_verdict function.
"""

        client = OpenAI(
            base_url=self.api_base,
            api_key=self.api_key
        )
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt.strip()},
                    {"role": "user", "content": user_prompt.strip()}
                ],
                tools=[SUBMIT_VERDICT_SCHEMA],
                tool_choice={"type": "function", "function": {"name": "submit_verdict"}},
                temperature=0.3,
                max_tokens=1000
            )
            
            # Extract function call
            if response.choices and response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                verdict_data = json.loads(tool_call.function.arguments)
                
                return ComplexityVerdict(
                    score=verdict_data.get("score", 0.5),
                    difficulty=verdict_data.get("difficulty", "medium"),
                    reasoning=verdict_data.get("reasoning", "No reasoning provided"),
                    details={
                        "patch_amount": verdict_data.get("patch_amount"),
                        "logic_complexity": verdict_data.get("logic_complexity"),
                        "context_needed": verdict_data.get("context_needed"),
                        "reject": verdict_data.get("reject", False),
                        "reject_reason": verdict_data.get("reject_reason")
                    }
                )
            
            # Fallback: calculate score from patch analysis
            fallback_score = min(0.5, patch_analysis.lines_changed / 50)
            if patch_analysis.lines_changed <= 2:
                fallback_score = 0.15
            elif patch_analysis.lines_changed <= 10:
                fallback_score = 0.35
            elif patch_analysis.lines_changed <= 30:
                fallback_score = 0.55
            else:
                fallback_score = 0.75
            
            return ComplexityVerdict(
                score=fallback_score,
                difficulty="easy" if fallback_score < 0.4 else ("medium" if fallback_score < 0.65 else "hard"),
                reasoning=f"Fallback score based on patch analysis: {patch_analysis.lines_changed} lines changed, {patch_analysis.files_modified} files",
                details={"fallback": True}
            )
            
        except Exception as e:
            logger.error(f"Error evaluating complexity: {e}")
            return ComplexityVerdict(
                score=0.5,
                difficulty="medium",
                reasoning=f"Error during evaluation: {str(e)}",
                details={"error": str(e)}
            )
    
    def should_accept(self, verdict: ComplexityVerdict) -> tuple[bool, str]:
        """
        Check if task should be accepted based on verdict.
        
        Returns:
            (accept: bool, reason: str)
        """
        if verdict.details and verdict.details.get("reject"):
            return False, verdict.details.get("reject_reason", "Rejected by evaluator")
        
        if verdict.score < self.MIN_ACCEPTABLE_SCORE:
            return False, f"Score {verdict.score:.2f} below minimum {self.MIN_ACCEPTABLE_SCORE}"
        
        return True, f"Score: {verdict.score:.2f}, Difficulty: {verdict.difficulty}"

