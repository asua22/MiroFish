"""
Report Agent service
Uses LangChain + Zep to implement ReACT mode simulation report generation

Features:
1. Generates reports based on simulation requirements and Zep graph information
2. Plans outline structure first, then generates section by section
3. Uses ReACT multi-turn reasoning and reflection mode for each section
4. Supports user conversation, autonomously calling retrieval tools during conversation
"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .zep_tools import (
    ZepToolsService,
    SearchResult,
    InsightForgeResult,
    PanoramaResult,
    InterviewResult,
)

logger = get_logger("mirofish.report_agent")


class ReportLogger:
    """
    Report Agent detailed logger

    Generates an agent_log.jsonl file in the report folder, recording detailed actions at each step.
    Each line is a complete JSON object containing timestamp, action type, detailed content, etc.
    """

    def __init__(self, report_id: str):
        """
        Initialize the logger

        Args:
            report_id: Report ID used to determine log file path
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, "reports", report_id, "agent_log.jsonl"
        )
        self.start_time = datetime.now()
        self._ensure_log_file()

    def _ensure_log_file(self):
        """Ensure the directory where the log file is located exists"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)

    def _get_elapsed_time(self) -> float:
        """Get elapsed time since start (seconds)"""
        return (datetime.now() - self.start_time).total_seconds()

    def log(
        self,
        action: str,
        stage: str,
        details: Dict[str, Any],
        section_title: Optional[str] = None,
        section_index: Optional[int] = None,
    ):
        """
        Record a log entry

        Args:
            action: Action type, e.g., 'start', 'tool_call', 'llm_response', 'section_complete'
            stage: Current stage, e.g., 'planning', 'generating', 'completed'
            details: Detailed content dictionary, not truncated
            section_title: Current section title (optional)
            section_index: Current section index (optional)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(self._get_elapsed_time(), 2),
            "report_id": self.report_id,
            "action": action,
            "stage": stage,
            "section_title": section_title,
            "section_index": section_index,
            "details": details,
        }

        # Append to JSONL file
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    def log_start(self, simulation_id: str, graph_id: str, simulation_requirement: str):
        """Record the start of report generation"""
        self.log(
            action="report_start",
            stage="pending",
            details={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "simulation_requirement": simulation_requirement,
                "message": "Report generation task started",
            },
        )

    def log_planning_start(self):
        """Record the start of outline planning"""
        self.log(
            action="planning_start",
            stage="planning",
            details={"message": "Started planning report outline"},
        )

    def log_planning_context(self, context: Dict[str, Any]):
        """Record context information obtained during planning"""
        self.log(
            action="planning_context",
            stage="planning",
            details={
                "message": "Obtained simulation context information",
                "context": context,
            },
        )

    def log_planning_complete(self, outline_dict: Dict[str, Any]):
        """Record completion of outline planning"""
        self.log(
            action="planning_complete",
            stage="planning",
            details={"message": "Outline planning complete", "outline": outline_dict},
        )

    def log_section_start(self, section_title: str, section_index: int):
        """Record the start of section generation"""
        self.log(
            action="section_start",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={"message": f"Started generating section: {section_title}"},
        )

    def log_react_thought(
        self, section_title: str, section_index: int, iteration: int, thought: str
    ):
        """Record ReACT thought process"""
        self.log(
            action="react_thought",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "thought": thought,
                "message": f"ReACT thought iteration {iteration}",
            },
        )

    def log_tool_call(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        parameters: Dict[str, Any],
        iteration: int,
    ):
        """Record tool call"""
        self.log(
            action="tool_call",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "parameters": parameters,
                "message": f"Tool call: {tool_name}",
            },
        )

    def log_tool_result(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        result: str,
        iteration: int,
    ):
        """Record tool call result (full content, not truncated)"""
        self.log(
            action="tool_result",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "result": result,  # Full result, not truncated
                "result_length": len(result),
                "message": f"Tool {tool_name} returned result",
            },
        )

    def log_llm_response(
        self,
        section_title: str,
        section_index: int,
        response: str,
        iteration: int,
        has_tool_calls: bool,
        has_final_answer: bool,
    ):
        """Record LLM response (full content, not truncated)"""
        self.log(
            action="llm_response",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "response": response,  # Full response, not truncated
                "response_length": len(response),
                "has_tool_calls": has_tool_calls,
                "has_final_answer": has_final_answer,
                "message": f"LLM response (Tool calls: {has_tool_calls}, Final answer: {has_final_answer})",
            },
        )

    def log_section_content(
        self,
        section_title: str,
        section_index: int,
        content: str,
        tool_calls_count: int,
    ):
        """Record section content generation complete (only content, not representing whole section complete)"""
        self.log(
            action="section_content",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": content,  # Full content, not truncated
                "content_length": len(content),
                "tool_calls_count": tool_calls_count,
                "message": f"Section {section_title} content generation complete",
            },
        )

    def log_section_full_complete(
        self, section_title: str, section_index: int, full_content: str
    ):
        """
        Record section generation complete

        Frontend should listen to this log to determine if a section is truly complete and get the full content
        """
        self.log(
            action="section_complete",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": full_content,
                "content_length": len(full_content),
                "message": f"Section {section_title} generation complete",
            },
        )

    def log_report_complete(self, total_sections: int, total_time_seconds: float):
        """Record report generation complete"""
        self.log(
            action="report_complete",
            stage="completed",
            details={
                "total_sections": total_sections,
                "total_time_seconds": round(total_time_seconds, 2),
                "message": "Report generation complete",
            },
        )

    def log_error(self, error_message: str, stage: str, section_title: str = None):
        """Record error"""
        self.log(
            action="error",
            stage=stage,
            section_title=section_title,
            section_index=None,
            details={
                "error": error_message,
                "message": f"Error occurred: {error_message}",
            },
        )


class ReportConsoleLogger:
    """
    Report Agent console logger

    Writes console-style logs (INFO, WARNING, etc.) to a console_log.txt file in the report folder.
    These logs are different from agent_log.jsonl; they are plain text console output.
    """

    def __init__(self, report_id: str):
        """
        Initialize console logger

        Args:
            report_id: Report ID used to determine log file path
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, "reports", report_id, "console_log.txt"
        )
        self._ensure_log_file()
        self._file_handler = None
        self._setup_file_handler()

    def _ensure_log_file(self):
        """Ensure the directory where the log file is located exists"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)

    def _setup_file_handler(self):
        """Set up file handler to write logs to file simultaneously"""
        import logging

        # Create file handler
        self._file_handler = logging.FileHandler(
            self.log_file_path, mode="a", encoding="utf-8"
        )
        self._file_handler.setLevel(logging.INFO)

        # Use same concise format as console
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
        )
        self._file_handler.setFormatter(formatter)

        # Attach to report_agent related loggers
        loggers_to_attach = [
            "mirofish.report_agent",
            "mirofish.zep_tools",
        ]

        for logger_name in loggers_to_attach:
            target_logger = logging.getLogger(logger_name)
            # Avoid adding multiple times
            if self._file_handler not in target_logger.handlers:
                target_logger.addHandler(self._file_handler)

    def close(self):
        """Close file handler and remove from logger"""
        import logging

        if self._file_handler:
            loggers_to_detach = [
                "mirofish.report_agent",
                "mirofish.zep_tools",
            ]

            for logger_name in loggers_to_detach:
                target_logger = logging.getLogger(logger_name)
                if self._file_handler in target_logger.handlers:
                    target_logger.removeHandler(self._file_handler)

            self._file_handler.close()
            self._file_handler = None

    def __del__(self):
        """Ensure file handler is closed upon destruction"""
        self.close()


class ReportStatus(str, Enum):
    """Report status"""

    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """Report section"""

    title: str
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"title": self.title, "content": self.content}

    def to_markdown(self, level: int = 2) -> str:
        """Convert to Markdown format"""
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class ReportOutline:
    """Report outline"""

    title: str
    summary: str
    sections: List[ReportSection]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections],
        }

    def to_markdown(self) -> str:
        """Convert to Markdown format"""
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md


@dataclass
class Report:
    """Full report"""

    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: ReportStatus
    outline: Optional[ReportOutline] = None
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "status": self.status.value,
            "outline": self.outline.to_dict() if self.outline else None,
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════
# Prompt Template Constants
# ═══════════════════════════════════════════════════════════════

# ── Tool Descriptions ──

TOOL_DESC_INSIGHT_FORGE = """\
【Deep Insight Retrieval - Powerful Retrieval Tool】
This is our powerful retrieval function designed for deep analysis. It will:
1. Automatically break your query into multiple sub-questions
2. Retrieve information from the simulation graph from multiple dimensions
3. Integrate results from semantic search, entity analysis, and relationship chain tracing
4. Return the most comprehensive and in-depth retrieval content

【Use Cases】
- Need deep analysis of a specific topic
- Need to understand multiple aspects of an event
- Need to obtain rich source material to support report sections

【Returns】
- Relevant facts (direct quotes possible)
- Core entity insights
- Relationship chain analysis"""

TOOL_DESC_PANORAMA_SEARCH = """\
【Breadth Search - Full View Retrieval】
This tool is used to get a complete view of simulation results, especially suitable for understanding the evolution process of an event. It will:
1. Retrieve all relevant nodes and relationships
2. Distinguish between currently effective facts and historical/expired facts
3. Help you understand how public opinion evolves

【Use Cases】
- Need to understand the full development trajectory of an event
- Need to compare public opinion changes across different stages
- Need comprehensive entity and relationship information

【Returns】
- Currently effective facts (latest simulation results)
- Historical/expired facts (evolution records)
- All involved entities"""

TOOL_DESC_QUICK_SEARCH = """\
【Simple Search - Quick Retrieval】
Lightweight quick retrieval tool, suitable for simple, direct information queries.

【Use Cases】
- Need quick lookups for specific information
- Need to verify a specific fact
- Simple information retrieval

【Returns】
- List of facts most relevant to the query"""

TOOL_DESC_INTERVIEW_AGENTS = """\
【Deep Interview - Real Agent Interview (Dual Platform)】
Calls the OASIS simulation environment's interview API to conduct real interviews with running simulation Agents!
This is not an LLM simulation, but a call to the real interview interface to obtain original answers from the simulated Agents.
Defaults to interviewing on both Twitter and Reddit simultaneously to get a more comprehensive view.

Workflow:
1. Automatically read persona files to understand all simulated Agents
2. Intelligently select Agents most relevant to the interview topic (e.g., student, media, official, etc.)
3. Automatically generate interview questions
4. Call /api/simulation/interview/batch interface for real interviews on both platforms
5. Integrate all interview results to provide multi-perspective analysis

【Use Cases】
- Need to understand opinions on an event from different role perspectives (How do students see it? Media? Officials?)
- Need to collect multiple opinions and stances
- Need to obtain real answers from simulated Agents (from OASIS simulation environment)
- Want the report to be more vivid, including "interview records"

【Returns】
- Identity information of interviewed Agents
- Interview responses from Agents on Twitter and Reddit
- Key quotes (direct quotes possible)
- Interview summaries and opinion comparisons

【Important】 The OASIS simulation environment must be running to use this feature!"""

# ── Outline Planning Prompt ──

PLAN_SYSTEM_PROMPT = """\
You are an expert in writing "Future Prediction Reports" with a "God's-eye view" of the simulation world-you can observe the behaviors, statements, and interactions of every Agent in the simulation.

[Core Philosophy]
We have constructed a simulation world and injected specific "simulation requirements" as variables. The evolutionary results of the simulation world are a prediction of what might happen in the future. You are observing not "experimental data," but a "future preview."

[Your Task]
Write a "Future Prediction Report" answering:
1. Under the conditions we set, what happens in the future?
2. How do various Agents (groups) react and act?
3. What future trends and risks does this simulation reveal?

[Report Positioning]
- ✅ This is a simulation-based future prediction report, revealing "If this happens, what will the future be like"
- ✅ Focus on predictive results: event trajectory, group reactions, emergent phenomena, potential risks
- ✅ Agent behaviors and statements in the simulation world are predictions of future human behavior
- ❌ Not an analysis of the current real-world situation
- ❌ Not a generic summary of public opinion

[Section Constraints]
- Minimum 2 sections, maximum 5 sections
- No subsections; write content directly in each section
- Be concise, focus on core predictive findings

Please output the report outline in JSON format as follows:
{
    "title": "Report Title",
    "summary": "Report summary (one sentence summarizing core predictive findings)",
    "sections": [
        {
            "title": "Section Title",
            "description": "Section content description"
        }
    ]
}

Note: The sections array must have at least 2 and at most 5 elements!"""

PLAN_USER_PROMPT_TEMPLATE = """\
[Simulation Scenario Setup]
Variables injected into the simulation world (simulation requirements): {simulation_requirement}

[Simulation World Scale]
- Number of entities participating in the simulation: {total_nodes}
- Number of relationships generated between entities: {total_edges}
- Entity type distribution: {entity_types}
- Number of active Agents: {total_entities}

[Sample of Future Facts Predicted by Simulation]
{related_facts_json}

Please examine this future preview with a "God's-eye view":
1. Under the conditions we set, what state does the future present?
2. How did various crowds (Agents) react and act?
3. What future trends does this simulation reveal worth noting?

Design the most appropriate report section structure based on the predicted results.

[Reminder] Report section count: Minimum 2, maximum 5, be concise and focus on core predictive findings."""

# ── Section Generation Prompt ──

SECTION_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert in writing "Future Prediction Reports" and are currently writing a section of the report.

Report Title: {report_title}
Report Summary: {report_summary}
Prediction Scenario (simulation requirements): {simulation_requirement}

Currently Writing Section: {section_title}

================================================================
[Core Philosophy]
================================================================

The simulation world is a preview of the future. We have injected specific conditions (simulation requirements) into the simulation world. The behaviors and interactions of Agents in the simulation are predictions of future human behavior.

Your task is to:
- Reveal what happens in the future under the set conditions
- Predict how various crowds (Agents) react and act
- Discover future trends, risks, and opportunities worthy of note

❌ Do not write an analysis of the current real-world situation
✅ Focus on "what the future will be like"-simulation results are the predicted future

================================================================
[Most Important Rules - Must be followed]
================================================================

1. [Must use tools to observe the simulation world]
   - You are observing the future preview with a "God's-eye view"
   - All content must come from events and Agent statements/behaviors in the simulation world
   - Do not use your own knowledge to write report content
   - Use tools at least 3 times per section (at most 5 times) to observe the simulation world, which represents the future

2. [Must quote original Agent statements/behaviors]
   - Agent statements and behaviors are predictions of future human behavior
   - Use quote format in the report to display these predictions, for example:
     > "Some groups will say: original content..."
   - These quotes are core evidence for the simulation predictions

3. [Language Consistency - Quoted content must be translated into report language]
   - Tool results may contain English, Chinese, or mixed content
   - If the simulation requirements and original materials are in English, the report must be written entirely in English
   - When quoting English or mixed-language content returned by tools, you must ensure the quoted part is also in English
   - Maintain the original meaning and ensure natural phrasing
   - This rule applies to both main text and quoted blocks (> format)

4. [Faithfully present prediction results]
   - Report content must reflect simulation results representing the future in the simulation world
   - Do not add information that does not exist in the simulation
   - If information on a certain aspect is insufficient, state it truthfully

================================================================
[⚠️ Formatting Specifications - Extremely Important!]
================================================================

[One section = Minimum content unit]
- Each section is the smallest block unit of the report
- ❌ Do not use any Markdown headers (#, ##, ###, ####, etc.) within sections
- ❌ Do not add section main headers at the beginning of content
- ✅ Section titles are added automatically by the system; you only need to write pure body content
- ✅ Use **bold text**, paragraph separation, quotes, and lists to organize content, but do not use headers

[Correct Example]
```
This section analyzes the public opinion propagation trend of the event. Through deep analysis of simulation data, we found...

**Initial Explosion Stage**

Weibo, as the first scene of public opinion, assumed the core function of information initiation:

> "Weibo contributed 68% of the initial buzz..."

**Emotional Amplification Stage**

The Douyin platform further amplified the event's influence:

- Strong visual impact
- High emotional resonance
```

[Incorrect Example]
```
## Executive Summary          ← Incorrect! Do not add any headers
### I. Initial Stage           ← Incorrect! Do not use ### for subsections
#### 1.1 Detailed Analysis    ← Incorrect! Do not use #### for fine-grained sections

This section analyzes...
```

================================================================
[Available Retrieval Tools] (Use 3-5 times per section)
================================================================

{tools_description}

[Tool Usage Suggestions - Please mix different tools, do not use only one]
- insight_forge: Deep analysis, automatically decomposes questions and performs multi-dimensional retrieval of facts and relationships
- panorama_search: Wide-angle panorama search, understand event overview, timeline, and evolutionary process
- quick_search: Quickly verify a specific piece of information
- interview_agents: Interview simulation Agents, obtain first-person viewpoints and real reactions from different roles

================================================================
[Workflow]
================================================================

Each time you reply, you can only do one of the following two things (cannot do both):

Option A - Call tool:
Output your thought, then call a tool in the following format:
<tool_call>
{{"name": "Tool Name", "parameters": {{"parameter_name": "parameter_value"}}}}
</tool_call>
The system will execute the tool and return the results to you. You cannot and should not write tool results yourself.

Option B - Output final content:
When you have obtained sufficient information through tools, output the section content starting with "Final Answer:".

⚠️ Strictly prohibited:
- Do not include both tool calls and Final Answer in one reply
- Do not fabricate tool return results (Observation); all tool results are injected by the system
- At most one tool call per reply

================================================================
[Section Content Requirements]
================================================================

1. Content must be based on simulation data retrieved by tools
2. Quote original text extensively to demonstrate simulation effects
3. Use Markdown format (but no headers allowed):
   - Use **bold text** to mark key points (replacing subsections)
   - Use lists (-, 1., 2., 3.) to organize points
   - Use empty lines to separate paragraphs
   - ❌ Do not use #, ##, ###, #### or any header syntax
4. [Quote format specifications - Must be standalone paragraphs]
   Quotes must be standalone paragraphs, with an empty line before and after, and cannot be mixed into paragraphs:

   ✅ Correct format:
   ```
   The school's response was considered lacking in substance.

   > "The school's coping mode appeared rigid and slow in the ever-changing social media environment."

   This evaluation reflects general public dissatisfaction.
   ```

   ❌ Incorrect format:
   ```
   The school's response was considered lacking in substance. > "The school's coping mode..." This evaluation reflects...
   ```
5. Maintain logical coherence with other sections
6. [Avoid repetition] Carefully read the completed section content below, do not repeat the same information
7. [Re-emphasize] Do not add any headers! Use **bold text** to replace subsection titles"""

SECTION_USER_PROMPT_TEMPLATE = """\
Completed section content (please read carefully to avoid repetition):
{previous_content}

================================================================
[Current Task] Writing Section: {section_title}
================================================================

[Important Reminder]
1. Carefully read the completed sections above, avoid repeating the same content!
2. Must call tools to obtain simulation data before starting
3. Please mix different tools, do not use only one
4. Report content must come from retrieval results, do not use your own knowledge

[⚠️ Formatting Warning - Must be followed]
- ❌ Do not write any headers (#, ##, ###, #### are not allowed)
- ❌ Do not write "{section_title}" as the beginning
- ✅ Section titles are automatically added by the system
- ✅ Write body text directly, use **bold text** to replace subsection titles

Please start:
1. First, Think (Thought) about what information is needed for this section
2. Then, call a tool (Action) to obtain simulation data
3. After collecting sufficient information, output Final Answer (pure body text, no headers)"""


# ── ReACT Loop Message Templates ──

REACT_OBSERVATION_TEMPLATE = """\
Observation:

=== Tool {tool_name} returned ===
{result}

================================================================
Tool calls count {tool_calls_count}/{max_tool_calls} (Used: {used_tools_str}){unused_hint}
- If information is sufficient: output section content starting with "Final Answer:" (must quote the original text above)
- If more information is needed: call a tool to continue retrieval
================================================================"""

REACT_INSUFFICIENT_TOOLS_MSG = (
    "[Note] You only called tools {tool_calls_count} times, at least {min_tool_calls} are required. "
    "Please call tools again to retrieve more simulation data before outputting Final Answer. {unused_hint}"
)

REACT_INSUFFICIENT_TOOLS_MSG_ALT = (
    "Currently called {tool_calls_count} times, at least {min_tool_calls} times required. "
    "Please call tools to retrieve simulation data. {unused_hint}"
)

REACT_TOOL_LIMIT_MSG = (
    "Tool call limit reached ({tool_calls_count}/{max_tool_calls}), no more tool calls allowed. "
    'Please immediately output section content starting with "Final Answer:" based on the information already retrieved.'
)

REACT_UNUSED_TOOLS_HINT = "\n💡 You haven't used: {unused_list}, it is recommended to try different tools to obtain information from multiple perspectives"

REACT_FORCE_FINAL_MSG = "Tool call limit reached, please directly output Final Answer: and generate section content."

# ── Chat Prompt ──

CHAT_SYSTEM_PROMPT_TEMPLATE = """\
You are a concise and efficient simulation prediction assistant.

[Background]
Prediction condition: {simulation_requirement}

[Generated Analysis Report]
{report_content}

[Rules]
1. Prioritize answering based on the report content above
2. Answer questions directly, avoid long-winded reasoning
3. Only call tools to retrieve more data if the report content is insufficient
4. Answers should be concise, clear, and organized

[Available Tools] (Use only when necessary, at most 1-2 times)
{tools_description}

[Tool Call Format]
<tool_call>
{{"name": "Tool Name", "parameters": {{"parameter_name": "parameter_value"}}}}
</tool_call>

[Answer Style]
- Concise and direct, avoid lengthy explanations
- Use > format to quote key content
- Give conclusions first, then explain reasons"""

CHAT_OBSERVATION_SUFFIX = "\n\nPlease answer the question concisely."


# ═══════════════════════════════════════════════════════════════
# ReportAgent Main Class
# ═══════════════════════════════════════════════════════════════


class ReportAgent:
    """
    Report Agent - Simulation Report Generation Agent

    Uses ReACT (Reasoning + Acting) mode:
    1. Planning phase: Analyze simulation requirements, plan report outline structure
    2. Generation phase: Generate content section by section, each section can call tools multiple times to obtain information
    3. Reflection phase: Check content completeness and accuracy
    """

    MAX_TOOL_CALLS_PER_SECTION = 5

    MAX_REFLECTION_ROUNDS = 3

    MAX_TOOL_CALLS_PER_CHAT = 2

    def __init__(
        self,
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        zep_tools: Optional[ZepToolsService] = None,
    ):
        """
        Initialize Report Agent

        Args:
            graph_id: Graph ID
            simulation_id: Simulation ID
            simulation_requirement: Simulation requirement description
            llm_client: LLM client (optional)
            zep_tools: Zep tools service (optional)
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement

        self.llm = llm_client or LLMClient()
        self.zep_tools = zep_tools or ZepToolsService()

        self.tools = self._define_tools()

        self.report_logger: Optional[ReportLogger] = None
        self.console_logger: Optional[ReportConsoleLogger] = None

        logger.info(
            f"ReportAgent initialized: graph_id={graph_id}, simulation_id={simulation_id}"
        )

    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define available tools"""
        return {
            "insight_forge": {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": "The question or topic you want to analyze in depth",
                    "report_context": "Current report section context (optional, helps generate more precise sub-questions)",
                },
            },
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "Search query for relevance ranking",
                    "include_expired": "Whether to include expired/historical content (default True)",
                },
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "Search query string",
                    "limit": "Number of results to return (optional, default 10)",
                },
            },
            "interview_agents": {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "Interview topic or requirement description (e.g., 'Understand student opinions about dormitory formaldehyde incident')",
                    "max_agents": "Maximum number of agents to interview (optional, default 5, max 10)",
                },
            },
        }

    def _execute_tool(
        self, tool_name: str, parameters: Dict[str, Any], report_context: str = ""
    ) -> str:
        """
        Execute tool call

        Args:
            tool_name: Tool name
            parameters: Tool parameters
            report_context: Report context (for InsightForge)

        Returns:
            Tool execution result (text format)
        """
        logger.info(f"Executing tool: {tool_name}, parameters: {parameters}")

        try:
            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.zep_tools.insight_forge(
                    graph_id=self.graph_id,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx,
                )
                return result.to_text()

            elif tool_name == "panorama_search":
                # Breadth search - Get full picture
                query = parameters.get("query", "")
                include_expired = parameters.get("include_expired", True)
                if isinstance(include_expired, str):
                    include_expired = include_expired.lower() in ["true", "1", "yes"]
                result = self.zep_tools.panorama_search(
                    graph_id=self.graph_id, query=query, include_expired=include_expired
                )
                return result.to_text()

            elif tool_name == "quick_search":
                # Simple search - Quick retrieval
                query = parameters.get("query", "")
                limit = parameters.get("limit", 10)
                if isinstance(limit, str):
                    limit = int(limit)
                result = self.zep_tools.quick_search(
                    graph_id=self.graph_id, query=query, limit=limit
                )
                return result.to_text()

            elif tool_name == "interview_agents":
                # Deep interview - Call real OASIS interview API to get simulated Agent responses (dual platform)
                interview_topic = parameters.get(
                    "interview_topic", parameters.get("query", "")
                )
                max_agents = parameters.get("max_agents", 5)
                if isinstance(max_agents, str):
                    max_agents = int(max_agents)
                max_agents = min(max_agents, 10)
                result = self.zep_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents,
                )
                return result.to_text()

            # ========== Backward compatibility - old tools (internally redirect to new tools) ==========

            elif tool_name == "search_graph":
                # Redirect to quick_search
                logger.info("search_graph redirected to quick_search")
                return self._execute_tool("quick_search", parameters, report_context)

            elif tool_name == "get_graph_statistics":
                result = self.zep_tools.get_graph_statistics(self.graph_id)
                return json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.zep_tools.get_entity_summary(
                    graph_id=self.graph_id, entity_name=entity_name
                )
                return json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "get_simulation_context":
                # Redirect to insight_forge, as it is more powerful
                logger.info("get_simulation_context redirected to insight_forge")
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool(
                    "insight_forge", {"query": query}, report_context
                )

            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.zep_tools.get_entities_by_type(
                    graph_id=self.graph_id, entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                return json.dumps(result, ensure_ascii=False, indent=2)

            else:
                return f"Unknown tool: {tool_name}. Please use one of: insight_forge, panorama_search, quick_search"

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}, error: {str(e)}")
            return f"Tool execution failed: {str(e)}"

    # Valid tool names set, used for bare JSON fallback parsing validation
    VALID_TOOL_NAMES = {
        "insight_forge",
        "panorama_search",
        "quick_search",
        "interview_agents",
    }

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls from LLM response

        Supported formats (by priority):
        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        2. Bare JSON (the entire response or a single line is a tool call JSON)
        """
        tool_calls = []

        # Format 1: XML style (standard format)
        xml_pattern = r"<tool_call>\s*(\{.*?\})\s*</tool_call>"
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            try:
                call_data = json.loads(match.group(1))
                # Normalize key names: "tool" → "name", "params" → "parameters"
                if "tool" in call_data and "name" not in call_data:
                    call_data["name"] = call_data.pop("tool")
                if "params" in call_data and "parameters" not in call_data:
                    call_data["parameters"] = call_data.pop("params")
                if "name" in call_data:
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls

        # Format 2: Fallback - LLM directly outputs bare JSON (without <tool_call> tags)
        # Only try when format 1 doesn't match, to avoid mis-matching JSON in the body
        stripped = response.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                call_data = json.loads(stripped)
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
                    return tool_calls
            except json.JSONDecodeError:
                pass

        # Response may contain thought text + bare JSON, try to extract the last JSON object
        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """Validate if the parsed JSON is a valid tool call"""
        # Support both {"name": ..., "parameters": ...} and {"tool": ..., "params": ...} key names
        tool_name = data.get("name") or data.get("tool")
        if tool_name and tool_name in self.VALID_TOOL_NAMES:
            # Normalize key names to name / parameters
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False

    def _get_tools_description(self) -> str:
        """Generate tool description text"""
        desc_parts = ["Available tools:"]
        for name, tool in self.tools.items():
            params_desc = ", ".join(
                [f"{k}: {v}" for k, v in tool["parameters"].items()]
            )
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  Parameters: {params_desc}")
        return "\n".join(desc_parts)

    def plan_outline(
        self, progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        Plan report outline

        Use LLM to analyze simulation requirements and plan the report outline structure

        Args:
            progress_callback: Progress callback function

        Returns:
            ReportOutline: Report outline
        """
        logger.info("Starting report outline planning...")

        if progress_callback:
            progress_callback("planning", 0, "Analyzing simulation requirements...")

        # First get simulation context (may fail if Zep graph doesn't exist)
        try:
            context = self.zep_tools.get_simulation_context(
                graph_id=self.graph_id, simulation_requirement=self.simulation_requirement
            )
        except Exception as ctx_err:
            logger.warning(f"Could not fetch simulation context (graph may not exist in Zep): {ctx_err}")
            context = {"graph_statistics": {}, "related_facts": [], "entities": [], "total_entities": 0}

        if progress_callback:
            progress_callback("planning", 30, "Generating report outline...")

        system_prompt = PLAN_SYSTEM_PROMPT
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get("graph_statistics", {}).get("total_nodes", 0),
            total_edges=context.get("graph_statistics", {}).get("total_edges", 0),
            entity_types=list(
                context.get("graph_statistics", {}).get("entity_types", {}).keys()
            ),
            total_entities=context.get("total_entities", 0),
            related_facts_json=json.dumps(
                context.get("related_facts", [])[:10], ensure_ascii=False, indent=2
            ),
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )

            if progress_callback:
                progress_callback("planning", 80, "Parsing outline structure...")

            # Parse outline
            sections = []
            for section_data in response.get("sections", []):
                sections.append(
                    ReportSection(title=section_data.get("title", ""), content="")
                )

            outline = ReportOutline(
                title=response.get("title", "Simulation Analysis Report"),
                summary=response.get("summary", ""),
                sections=sections,
            )

            if progress_callback:
                progress_callback("planning", 100, "Outline planning complete")

            logger.info(f"Outline planning completed: {len(sections)} sections")
            return outline
        except Exception as e:
            logger.error(f"Outline planning failed: {str(e)}")
            # Return default outline (3 sections, as fallback)
            return ReportOutline(
                title="Future Prediction Report",
                summary="Future trends and risk analysis based on simulation predictions",
                sections=[
                    ReportSection(title="Prediction Scenario and Core Findings"),
                    ReportSection(title="Crowd Behavior Prediction Analysis"),
                    ReportSection(title="Trend Outlook and Risk Warnings"),
                ],
            )

    def _generate_section_react(
        self,
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0,
    ) -> str:
        """
        Generate single section content using ReACT mode

        ReACT loop:
        1. Thought - Analyze what information is needed
        2. Action - Call tool to obtain information
        3. Observation - Analyze tool return results
        4. Repeat until information is sufficient or max iterations reached
        5. Final Answer - Generate section content

        Args:
            section: Section to generate
            outline: Complete outline
            previous_sections: Content of previous sections (for coherence)
            progress_callback: Progress callback
            section_index: Section index (for logging)

        Returns:
            Section content (Markdown format)
        """
        logger.info(f"Generating section using ReACT: {section.title}")

        # Log section start
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)

        system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            report_title=outline.title,
            report_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            section_title=section.title,
            tools_description=self._get_tools_description(),
        )

        # Build user prompt - pass max 4000 characters per completed section
        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                # Max 4000 characters per section
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "(This is the first section)"

        user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # ReACT loop
        tool_calls_count = 0
        max_iterations = 5  # Max iterations
        min_tool_calls = 3  # Minimum tool calls
        conflict_retries = (
            0  # Consecutive conflicts where tool call and Final Answer appear together
        )
        used_tools = set()  # Track tool names that have been called
        all_tools = {
            "insight_forge",
            "panorama_search",
            "quick_search",
            "interview_agents",
        }

        # Report context, used for InsightForge's sub-question generation
        report_context = f"Section title: {section.title}\nSimulation requirement: {self.simulation_requirement}"

        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating",
                    int((iteration / max_iterations) * 100),
                    f"Deep retrieval and writing ({tool_calls_count}/{self.MAX_TOOL_CALLS_PER_SECTION})",
                )

            # Call LLM
            response = self.llm.chat(
                messages=messages, temperature=0.5, max_tokens=4096
            )

            # Check if LLM response is None (API exception or empty content)
            if response is None:
                logger.warning(
                    f"Section {section.title} iteration {iteration + 1}: LLM returned None"
                )
                # If there are remaining iterations, add message and retry
                if iteration < max_iterations - 1:
                    messages.append(
                        {"role": "assistant", "content": "(Empty response)"}
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": "Please continue generating content.",
                        }
                    )
                    continue
                # Last iteration also returns None, break loop and force completion
                break

            logger.debug(f"LLM response: {response[:200]}...")

            # Parse once, reuse results
            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            # ── Conflict handling: LLM outputs both tool call and Final Answer ──
            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    f"Section {section.title} iteration {iteration + 1}: "
                    f"LLM output both tool call and Final Answer (conflict #{conflict_retries})"
                )

                if conflict_retries <= 2:
                    # First two times: discard this response, require LLM to reply again
                    messages.append({"role": "assistant", "content": response})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "[Format Error] You included both tool call and Final Answer in one reply, which is not allowed.\n"
                                "Each reply can only do one of the following:\n"
                                "- Call a tool (output a <tool_call> block, do not write Final Answer)\n"
                                "- Output final content (start with 'Final Answer:', do not include <tool_call>)\n"
                                "Please reply again, only do one thing."
                            ),
                        }
                    )
                    continue
                else:
                    # Third time: degrade, truncate to first tool call, force execution
                    logger.warning(
                        f"Section {section.title}: {conflict_retries} consecutive conflicts, "
                        "degrading to truncate and execute first tool call"
                    )
                    first_tool_end = response.find("</tool_call>")
                    if first_tool_end != -1:
                        response = response[: first_tool_end + len("</tool_call>")]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            # Log LLM response
            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer,
                )

            # ── Case 1: LLM output Final Answer ──
            if has_final_answer:
                # Insufficient tool calls, reject and require continuing to call tools
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": response})
                    unused_tools = all_tools - used_tools
                    unused_hint = (
                        f"(These tools haven't been used yet, recommend trying them: {', '.join(unused_tools)})"
                        if unused_tools
                        else ""
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                                tool_calls_count=tool_calls_count,
                                min_tool_calls=min_tool_calls,
                                unused_hint=unused_hint,
                            ),
                        }
                    )
                    continue

                # Normal end
                final_answer = response.split("Final Answer:")[-1].strip()
                logger.info(
                    f"Section {section.title} generation complete (tool calls: {tool_calls_count})"
                )

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count,
                    )
                return final_answer

            # ── Case 2: LLM tries to call tool ──
            if has_tool_calls:
                # Tool quota exhausted → explicitly inform, require Final Answer output
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    messages.append({"role": "assistant", "content": response})
                    messages.append(
                        {
                            "role": "user",
                            "content": REACT_TOOL_LIMIT_MSG.format(
                                tool_calls_count=tool_calls_count,
                                max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                            ),
                        }
                    )
                    continue

                # Only execute the first tool call
                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(
                        f"LLM attempted to call {len(tool_calls)} tools, executing only the first one: {call.get('name', call.get('tool', 'Unknown'))}"
                    )

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call.get("name", call.get("tool", "Unknown")),
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1,
                    )

                result = self._execute_tool(
                    call.get("name", call.get("tool", "Unknown")),
                    call.get("parameters", {}),
                    report_context=report_context,
                )

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call.get("name", call.get("tool", "Unknown")),
                        result=result,
                        iteration=iteration + 1,
                    )

                tool_calls_count += 1
                used_tools.add(call.get("name", call.get("tool", "Unknown")))

                # Build unused tools hint
                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(
                        unused_list=",".join(unused_tools)
                    )

                messages.append({"role": "assistant", "content": response})
                messages.append(
                    {
                        "role": "user",
                        "content": REACT_OBSERVATION_TEMPLATE.format(
                            tool_name=call.get("name", call.get("tool", "Unknown")),
                            result=result,
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                            used_tools_str=", ".join(used_tools) if used_tools else "none",
                            unused_hint=unused_hint,
                        ),
                    }
                )
                continue

            # ── Case 3: Neither tool call nor Final Answer ──
            messages.append({"role": "assistant", "content": response})

            if tool_calls_count < min_tool_calls:
                # Insufficient tool calls, recommend unused tools
                unused_tools = all_tools - used_tools
                unused_hint = (
                    f"(These tools haven't been used yet, recommend trying them: {', '.join(unused_tools)})"
                    if unused_tools
                    else ""
                )

                messages.append(
                    {
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    }
                )
                continue

            # Tool calls sufficient, LLM output content but without "Final Answer:" prefix
            # Directly use this content as final answer, no more spinning
            logger.info(
                f"Section {section.title} did not detect 'Final Answer:' prefix, directly adopting LLM output as final content (tool calls: {tool_calls_count})"
            )
            final_answer = response.strip()

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count,
                )
            return final_answer

        # Reached max iterations, force generate content
        logger.warning(
            f"Section {section.title} reached max iterations, forcing generation"
        )
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})

        response = self.llm.chat(messages=messages, temperature=0.5, max_tokens=4096)

        # Check if LLM returns None during forced completion
        if response is None:
            logger.error(
                f"Section {section.title} LLM returned None during forced completion, using default error message"
            )
            final_answer = f"(Section generation failed: LLM returned empty response, please retry later)"
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response

        # Log section content generation complete
        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count,
            )

        return final_answer

    def generate_report(
        self,
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None,
        resume: bool = False,
    ) -> Report:
        """
        Generate complete report (section-by-section real-time output)

        Each section is saved immediately after generation, no need to wait for the entire report.
        File structure:
        reports/{report_id}/
            meta.json       - Report metadata
            outline.json    - Report outline
            progress.json   - Generation progress
            section_01.md   - Section 1
            section_02.md   - Section 2
            ...
            full_report.md  - Complete report

        Args:
            progress_callback: Progress callback function (stage, progress, message)
            report_id: Report ID (optional, auto-generated if not provided)

        Returns:
            Report: Complete report
        """
        import uuid

        # If no report_id is provided, auto-generate
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()

        # On resume: load existing report to preserve created_at etc.
        if resume:
            existing = ReportManager.get_report(report_id)
            if existing:
                report = existing
                report.status = ReportStatus.GENERATING
                report.error = None
            else:
                report = Report(
                    report_id=report_id,
                    simulation_id=self.simulation_id,
                    graph_id=self.graph_id,
                    simulation_requirement=self.simulation_requirement,
                    status=ReportStatus.GENERATING,
                    created_at=datetime.now().isoformat(),
                )
        else:
            report = Report(
                report_id=report_id,
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement,
                status=ReportStatus.PENDING,
                created_at=datetime.now().isoformat(),
            )

        # Completed section titles list (for progress tracking)
        completed_section_titles = []

        try:
            # Initialize: Create report folder and save initial state
            ReportManager._ensure_report_folder(report_id)

            # Loggers append to existing files naturally (mode="a")
            self.report_logger = ReportLogger(report_id)
            self.console_logger = ReportConsoleLogger(report_id)

            if resume:
                # Log resume event (appends to existing agent_log.jsonl)
                self.report_logger.log(
                    action="resume_start",
                    stage="generating",
                    details={"message": "Resuming report generation from last checkpoint"},
                )
                logger.info(f"Resuming report: {report_id}")

                # Load existing outline - no planning needed
                outline = ReportManager.load_outline(report_id)
                if not outline:
                    raise ValueError(
                        f"Cannot resume report {report_id}: outline.json not found. "
                        "Please generate a new report."
                    )
                report.outline = outline
                logger.info(f"Loaded outline: {len(outline.sections)} sections")
            else:
                self.report_logger.log_start(
                    simulation_id=self.simulation_id,
                    graph_id=self.graph_id,
                    simulation_requirement=self.simulation_requirement,
                )

                ReportManager.update_progress(
                    report_id, "pending", 0, "Initializing report...", completed_sections=[]
                )
                ReportManager.save_report(report)

                # Phase 1: Plan outline
                report.status = ReportStatus.PLANNING
                ReportManager.update_progress(
                    report_id,
                    "planning",
                    5,
                    "Starting to plan report outline...",
                    completed_sections=[],
                )

                self.report_logger.log_planning_start()

                if progress_callback:
                    progress_callback("planning", 0, "Starting to plan report outline...")

                outline = self.plan_outline(
                    progress_callback=lambda stage, prog, msg: (
                        progress_callback(stage, prog // 5, msg)
                        if progress_callback
                        else None
                    )
                )
                report.outline = outline

                self.report_logger.log_planning_complete(outline.to_dict())

                ReportManager.save_outline(report_id, outline)
                ReportManager.update_progress(
                    report_id,
                    "planning",
                    15,
                    f"Outline planning complete, {len(outline.sections)} sections",
                    completed_sections=[],
                )
                ReportManager.save_report(report)
                logger.info(f"Outline saved to file: {report_id}/outline.json")

            # Phase 2: Generate section by section (save each section)
            report.status = ReportStatus.GENERATING

            total_sections = len(outline.sections)
            generated_sections = []  # Save content for context

            for i, section in enumerate(outline.sections):
                section_num = i + 1
                section_path = ReportManager._get_section_path(report_id, section_num)
                base_progress = 20 + int((i / total_sections) * 70)

                # On resume: skip already saved sections, load their content for context
                if resume and os.path.exists(section_path):
                    with open(section_path, "r", encoding="utf-8") as f:
                        existing_content = f.read()
                    generated_sections.append(existing_content)
                    completed_section_titles.append(section.title)
                    logger.info(f"Skipping already completed section {section_num}: {section.title}")
                    continue

                # Update progress
                ReportManager.update_progress(
                    report_id,
                    "generating",
                    base_progress,
                    f"Generating section: {section.title} ({section_num}/{total_sections})",
                    current_section=section.title,
                    completed_sections=completed_section_titles,
                )

                if progress_callback:
                    progress_callback(
                        "generating",
                        base_progress,
                        f"Generating section: {section.title} ({section_num}/{total_sections})",
                    )

                # Generate main section content
                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg: (
                        progress_callback(
                            stage, base_progress + int(prog * 0.7 / total_sections), msg
                        )
                        if progress_callback
                        else None
                    ),
                    section_index=section_num,
                )

                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                # Save section
                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                # Log section complete
                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip(),
                    )

                logger.info(f"Section saved: {report_id}/section_{section_num:02d}.md")

                # Update progress
                ReportManager.update_progress(
                    report_id,
                    "generating",
                    base_progress + int(70 / total_sections),
                    f"Section {section.title} complete",
                    current_section=None,
                    completed_sections=completed_section_titles,
                )

            # Phase 3: Assemble complete report
            if progress_callback:
                progress_callback("generating", 95, "Assembling full report...")

            ReportManager.update_progress(
                report_id,
                "generating",
                95,
                "Assembling full report...",
                completed_sections=completed_section_titles,
            )

            # Use ReportManager to assemble full report
            report.markdown_content = ReportManager.assemble_full_report(
                report_id, outline
            )
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()

            # Calculate total time
            total_time_seconds = (datetime.now() - start_time).total_seconds()

            # Log report complete
            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections, total_time_seconds=total_time_seconds
                )

            # Save final report
            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id,
                "completed",
                100,
                "Report generation complete",
                completed_sections=completed_section_titles,
            )

            if progress_callback:
                progress_callback("completed", 100, "Report generation complete")

            logger.info(f"Report generation complete: {report_id}")

            # Close console logger
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report

        except Exception as e:
            import traceback
            logger.error(f"Report generation failed: {str(e)}\n{traceback.format_exc()}")
            report.status = ReportStatus.FAILED
            report.error = str(e)

            # Log error
            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")

            # Save failed status
            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id,
                    "failed",
                    -1,
                    f"Report generation failed: {str(e)}",
                    completed_sections=completed_section_titles,
                )
            except Exception:
                pass  # Ignore save failure errors

            # Close console logger
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report

    def chat(
        self, message: str, chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Chat with Report Agent

        During conversation, Agent can autonomously call retrieval tools to answer questions

        Args:
            message: User message
            chat_history: Chat history

        Returns:
            {
                "response": "Agent response",
                "tool_calls": [list of called tools],
                "sources": [information sources]
            }
        """
        logger.info(f"Report Agent chat: {message[:50]}...")

        chat_history = chat_history or []

        # Get generated report content
        report_content = ""
        try:
            report = ReportManager.get_report_by_simulation(self.simulation_id)
            if report and report.markdown_content:
                # Limit report length to avoid too long context
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [Report content truncated] ..."
        except Exception as e:
            logger.warning(f"Failed to get report content: {e}")

        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "(No report yet)",
            tools_description=self._get_tools_description(),
        )

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        # Add history
        for h in chat_history[-10:]:  # Limit history length
            messages.append(h)

        # Add user message
        messages.append({"role": "user", "content": message})

        # ReACT loop (simplified)
        tool_calls_made = []
        max_iterations = 2  # Reduce iteration rounds

        for iteration in range(max_iterations):
            response = self.llm.chat(messages=messages, temperature=0.5)

            # Parse tool calls
            tool_calls = self._parse_tool_calls(response)

            if not tool_calls:
                # No tool calls, directly return response
                clean_response = re.sub(
                    r"<tool_call>.*?</tool_call>", "", response, flags=re.DOTALL
                )
                clean_response = re.sub(r"\[TOOL_CALL\].*?\)", "", clean_response)

                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [
                        tc.get("parameters", {}).get("query", "")
                        for tc in tool_calls_made
                    ],
                }

            # Execute tool calls (limit quantity)
            tool_results = []
            for call in tool_calls[:1]:  # Max 1 tool call per round
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                tool_name_c = call.get("name") or call.get("tool", "Unknown")
                result = self._execute_tool(tool_name_c, call.get("parameters", {}))
                tool_results.append(
                    {
                        "tool": tool_name_c,
                        "result": result[:1500],  # Limit result length
                    }
                )
                tool_calls_made.append(call)

            # Add results to messages
            messages.append({"role": "assistant", "content": response})
            observation = "\n".join(
                [f"[{r['tool']} result]\n{r['result']}" for r in tool_results]
            )
            messages.append(
                {"role": "user", "content": observation + CHAT_OBSERVATION_SUFFIX}
            )

        # Reached max iterations, get final response
        final_response = self.llm.chat(messages=messages, temperature=0.5)

        # Clean response
        clean_response = re.sub(
            r"<tool_call>.*?</tool_call>", "", final_response, flags=re.DOTALL
        )
        clean_response = re.sub(r"\[TOOL_CALL\].*?\)", "", clean_response)

        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [
                tc.get("parameters", {}).get("query", "") for tc in tool_calls_made
            ],
        }


class ReportManager:
    """
    Report Manager

    Responsible for report persistence storage and retrieval

    File structure (section-by-section output):
    reports/
      {report_id}/
        meta.json          - Report metadata and status
        outline.json       - Report outline
        progress.json      - Generation progress
        section_01.md      - Section 1
        section_02.md      - Section 2
        ...
        full_report.md     - Complete report
    """

    # Report storage directory
    REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, "reports")

    @classmethod
    def _ensure_reports_dir(cls):
        """Ensure report root directory exists"""
        os.makedirs(cls.REPORTS_DIR, exist_ok=True)

    @classmethod
    def _get_report_folder(cls, report_id: str) -> str:
        """Get report folder path"""
        return os.path.join(cls.REPORTS_DIR, report_id)

    @classmethod
    def _ensure_report_folder(cls, report_id: str) -> str:
        """Ensure report folder exists and return path"""
        folder = cls._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        return folder

    @classmethod
    def _get_report_path(cls, report_id: str) -> str:
        """Get report metadata file path"""
        return os.path.join(cls._get_report_folder(report_id), "meta.json")

    @classmethod
    def _get_report_markdown_path(cls, report_id: str) -> str:
        """Get complete report Markdown file path"""
        return os.path.join(cls._get_report_folder(report_id), "full_report.md")

    @classmethod
    def _get_outline_path(cls, report_id: str) -> str:
        """Get outline file path"""
        return os.path.join(cls._get_report_folder(report_id), "outline.json")

    @classmethod
    def _get_progress_path(cls, report_id: str) -> str:
        """Get progress file path"""
        return os.path.join(cls._get_report_folder(report_id), "progress.json")

    @classmethod
    def _get_section_path(cls, report_id: str, section_index: int) -> str:
        """Get section Markdown file path"""
        return os.path.join(
            cls._get_report_folder(report_id), f"section_{section_index:02d}.md"
        )

    @classmethod
    def _get_agent_log_path(cls, report_id: str) -> str:
        """Get Agent log file path"""
        return os.path.join(cls._get_report_folder(report_id), "agent_log.jsonl")

    @classmethod
    def _get_console_log_path(cls, report_id: str) -> str:
        """Get console log file path"""
        return os.path.join(cls._get_report_folder(report_id), "console_log.txt")

    @classmethod
    def get_console_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Get console log content

        This is the console output log during report generation (INFO, WARNING, etc.),
        different from the structured logs in agent_log.jsonl.

        Args:
            report_id: Report ID
            from_line: Start from which line (for incremental fetch, 0 means from the beginning)

        Returns:
            {
                "logs": [list of log lines],
                "total_lines": total lines,
                "from_line": starting line number,
                "has_more": whether there are more logs
            }
        """
        log_path = cls._get_console_log_path(report_id)

        if not os.path.exists(log_path):
            return {"logs": [], "total_lines": 0, "from_line": 0, "has_more": False}

        logs = []
        total_lines = 0

        with open(log_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    # Keep original log line, remove trailing newline
                    logs.append(line.rstrip("\n\r"))

        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False,  # Read to end
        }

    @classmethod
    def get_console_log_stream(cls, report_id: str) -> List[str]:
        """
        Get complete console log (get all at once)

        Args:
            report_id: Report ID

        Returns:
            List of log lines
        """
        result = cls.get_console_log(report_id, from_line=0)
        return result["logs"]

    @classmethod
    def get_agent_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Get Agent log content

        Args:
            report_id: Report ID
            from_line: Start from which line (for incremental fetch, 0 means from the beginning)

        Returns:
            {
                "logs": [list of log entries],
                "total_lines": total lines,
                "from_line": starting line number,
                "has_more": whether there are more logs
            }
        """
        log_path = cls._get_agent_log_path(report_id)

        if not os.path.exists(log_path):
            return {"logs": [], "total_lines": 0, "from_line": 0, "has_more": False}

        logs = []
        total_lines = 0

        with open(log_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # Skip lines that fail to parse
                        continue

        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False,  # Read to end
        }

    @classmethod
    def get_agent_log_stream(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Get complete Agent log (for getting all at once)

        Args:
            report_id: Report ID

        Returns:
            List of log entries
        """
        result = cls.get_agent_log(report_id, from_line=0)
        return result["logs"]

    @classmethod
    def load_outline(cls, report_id: str) -> Optional[ReportOutline]:
        """Load outline from outline.json, returns None if not found"""
        path = cls._get_outline_path(report_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        sections = [
            ReportSection(title=s["title"], content=s.get("content", ""))
            for s in data.get("sections", [])
        ]
        return ReportOutline(
            title=data["title"],
            summary=data["summary"],
            sections=sections,
        )

    @classmethod
    def save_outline(cls, report_id: str, outline: ReportOutline) -> None:
        """
        Save report outline

        Called immediately after planning phase completes
        """
        cls._ensure_report_folder(report_id)

        with open(cls._get_outline_path(report_id), "w", encoding="utf-8") as f:
            json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"Outline saved: {report_id}")

    @classmethod
    def save_section(
        cls, report_id: str, section_index: int, section: ReportSection
    ) -> str:
        """
        Save single section

        Called immediately after each section is generated, implementing section-by-section output

        Args:
            report_id: Report ID
            section_index: Section index (starts from 1)
            section: Section object

        Returns:
            Saved file path
        """
        cls._ensure_report_folder(report_id)

        # Build section Markdown content - clean possible duplicate titles
        cleaned_content = cls._clean_section_content(section.content, section.title)
        md_content = f"## {section.title}\n\n"
        if cleaned_content:
            md_content += f"{cleaned_content}\n\n"

        # Save file
        file_suffix = f"section_{section_index:02d}.md"
        file_path = os.path.join(cls._get_report_folder(report_id), file_suffix)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"Section saved: {report_id}/{file_suffix}")
        return file_path

    @classmethod
    def _clean_section_content(cls, content: str, section_title: str) -> str:
        """
        Clean section content

        1. Remove Markdown heading lines at the beginning that duplicate the section title
        2. Convert all ### and below level headings to bold text

        Args:
            content: Original content
            section_title: Section title

        Returns:
            Cleaned content
        """
        import re

        if not content:
            return content

        content = content.strip()
        lines = content.split("\n")
        cleaned_lines = []
        skip_next_empty = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check if it's a Markdown heading line
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)

            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2).strip()

                # Check if it's a duplicate heading with section title (skip duplicates within first 5 lines)
                if i < 5:
                    if title_text == section_title or title_text.replace(
                        " ", ""
                    ) == section_title.replace(" ", ""):
                        skip_next_empty = True
                        continue

                # Convert all heading levels (#, ##, ###, ####, etc.) to bold
                # Because section titles are added by the system, there should be no headings in content
                cleaned_lines.append(f"**{title_text}**")
                cleaned_lines.append("")  # Add empty line
                continue

            # If previous line was a skipped heading and current line is empty, also skip
            if skip_next_empty and stripped == "":
                skip_next_empty = False
                continue

            skip_next_empty = False
            cleaned_lines.append(line)

        # Remove leading empty lines
        while cleaned_lines and cleaned_lines[0].strip() == "":
            cleaned_lines.pop(0)

        # Remove leading separators
        while cleaned_lines and cleaned_lines[0].strip() in ["---", "***", "___"]:
            cleaned_lines.pop(0)
            # Also remove empty lines after separator
            while cleaned_lines and cleaned_lines[0].strip() == "":
                cleaned_lines.pop(0)

        return "\n".join(cleaned_lines)

    @classmethod
    def update_progress(
        cls,
        report_id: str,
        status: str,
        progress: int,
        message: str,
        current_section: str = None,
        completed_sections: List[str] = None,
    ) -> None:
        """
        Update report generation progress

        Frontend can get real-time progress by reading progress.json
        """
        cls._ensure_report_folder(report_id)

        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "current_section": current_section,
            "completed_sections": completed_sections or [],
            "updated_at": datetime.now().isoformat(),
        }

        with open(cls._get_progress_path(report_id), "w", encoding="utf-8") as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)

    @classmethod
    def get_progress(cls, report_id: str) -> Optional[Dict[str, Any]]:
        """Get report generation progress"""
        path = cls._get_progress_path(report_id)

        if not os.path.exists(path):
            return None

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def get_generated_sections(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Get list of generated sections

        Returns information of all saved section files
        """
        folder = cls._get_report_folder(report_id)

        if not os.path.exists(folder):
            return []

        sections = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith("section_") and filename.endswith(".md"):
                file_path = os.path.join(folder, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Parse section index from filename
                parts = filename.replace(".md", "").split("_")
                section_index = int(parts[1])

                sections.append(
                    {
                        "filename": filename,
                        "section_index": section_index,
                        "content": content,
                    }
                )

        return sections

    @classmethod
    def assemble_full_report(cls, report_id: str, outline: ReportOutline) -> str:
        """
        Assemble complete report

        Assemble complete report from saved section files and clean titles
        """
        folder = cls._get_report_folder(report_id)

        # Build report header
        md_content = f"# {outline.title}\n\n"
        md_content += f"> {outline.summary}\n\n"
        md_content += f"---\n\n"

        # Read all section files in order
        sections = cls.get_generated_sections(report_id)
        for section_info in sections:
            md_content += section_info["content"]

        # Post-process: clean title issues in the entire report
        md_content = cls._post_process_report(md_content, outline)

        # Save complete report
        full_path = cls._get_report_markdown_path(report_id)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"Complete report assembled: {report_id}")
        return md_content

    @classmethod
    def _post_process_report(cls, content: str, outline: ReportOutline) -> str:
        """
        Post-process report content

        1. Remove duplicate titles
        2. Keep report main title (#) and section titles (##), remove other level headings (###, ####, etc.)
        3. Clean up extra empty lines and separators

        Args:
            content: Original report content
            outline: Report outline

        Returns:
            Processed content
        """
        import re

        lines = content.split("\n")
        processed_lines = []
        prev_was_heading = False

        # Collect all section titles from outline
        section_titles = set()
        for section in outline.sections:
            section_titles.add(section.title)

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Check if it's a heading line
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)

            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                # Check if it's a duplicate heading (same content appears within 5 consecutive lines)
                is_duplicate = False
                for j in range(max(0, len(processed_lines) - 5), len(processed_lines)):
                    prev_line = processed_lines[j].strip()
                    prev_match = re.match(r"^(#{1,6})\s+(.+)$", prev_line)
                    if prev_match:
                        prev_title = prev_match.group(2).strip()
                        if prev_title == title:
                            is_duplicate = True
                            break

                if is_duplicate:
                    # Skip duplicate heading and empty lines after it
                    i += 1
                    while i < len(lines) and lines[i].strip() == "":
                        i += 1
                    continue

                # Heading level handling:
                # - # (level=1) only keep report main title
                # - ## (level=2) keep section title
                # - ### and below (level>=3) convert to bold text

                if level == 1:
                    if title == outline.title:
                        # Keep report main title
                        processed_lines.append(line)
                        prev_was_heading = True
                    elif title in section_titles:
                        # Section title incorrectly used #, correct to ##
                        processed_lines.append(f"## {title}")
                        prev_was_heading = True
                    else:
                        # Other level 1 headings convert to bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                elif level == 2:
                    if title in section_titles or title == outline.title:
                        # Keep section title
                        processed_lines.append(line)
                        prev_was_heading = True
                    else:
                        # Non-section level 2 headings convert to bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                else:
                    # ### and below level headings convert to bold text
                    processed_lines.append(f"**{title}**")
                    processed_lines.append("")
                    prev_was_heading = False

                i += 1
                continue

            elif stripped == "---" and prev_was_heading:
                # Skip separator immediately after heading
                i += 1
                continue

            elif stripped == "" and prev_was_heading:
                # Only keep one empty line after heading
                if processed_lines and processed_lines[-1].strip() != "":
                    processed_lines.append(line)
                prev_was_heading = False

            else:
                processed_lines.append(line)
                prev_was_heading = False

            i += 1

        # Clean up consecutive multiple empty lines (keep at most 2)
        result_lines = []
        empty_count = 0
        for line in processed_lines:
            if line.strip() == "":
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)

        return "\n".join(result_lines)

    @classmethod
    def save_report(cls, report: Report) -> None:
        """Save report metadata and complete report"""
        cls._ensure_report_folder(report.report_id)

        # Save metadata JSON
        with open(cls._get_report_path(report.report_id), "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

        # Save outline
        if report.outline:
            cls.save_outline(report.report_id, report.outline)

        # Save complete Markdown report
        if report.markdown_content:
            with open(
                cls._get_report_markdown_path(report.report_id), "w", encoding="utf-8"
            ) as f:
                f.write(report.markdown_content)

        logger.info(f"Report saved: {report.report_id}")

    @classmethod
    def get_report(cls, report_id: str) -> Optional[Report]:
        """Get report"""
        path = cls._get_report_path(report_id)

        if not os.path.exists(path):
            # Backward compatibility: check files stored directly in reports directory
            old_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
            if os.path.exists(old_path):
                path = old_path
            else:
                return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Rebuild Report object
        outline = None
        if data.get("outline"):
            outline_data = data["outline"]
            sections = []
            for s in outline_data.get("sections", []):
                sections.append(
                    ReportSection(title=s["title"], content=s.get("content", ""))
                )
            outline = ReportOutline(
                title=outline_data["title"],
                summary=outline_data["summary"],
                sections=sections,
            )

        # If markdown_content is empty, try reading from full_report.md
        markdown_content = data.get("markdown_content", "")
        if not markdown_content:
            full_report_path = cls._get_report_markdown_path(report_id)
            if os.path.exists(full_report_path):
                with open(full_report_path, "r", encoding="utf-8") as f:
                    markdown_content = f.read()

        return Report(
            report_id=data["report_id"],
            simulation_id=data["simulation_id"],
            graph_id=data["graph_id"],
            simulation_requirement=data["simulation_requirement"],
            status=ReportStatus(data["status"]),
            outline=outline,
            markdown_content=markdown_content,
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at", ""),
            error=data.get("error"),
        )

    @classmethod
    def get_report_by_simulation(cls, simulation_id: str) -> Optional[Report]:
        """Get report by simulation ID"""
        cls._ensure_reports_dir()

        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # New format: folder
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report and report.simulation_id == simulation_id:
                    return report
            # Backward compatibility: JSON file
            elif item.endswith(".json"):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report and report.simulation_id == simulation_id:
                    return report

        return None

    @classmethod
    def list_reports(
        cls, simulation_id: Optional[str] = None, limit: int = 50
    ) -> List[Report]:
        """List reports"""
        cls._ensure_reports_dir()

        reports = []
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # New format: folder
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
            # Backward compatibility: JSON file
            elif item.endswith(".json"):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)

        # Sort by creation time in reverse order
        reports.sort(key=lambda r: r.created_at, reverse=True)

        return reports[:limit]

    @classmethod
    def delete_report(cls, report_id: str) -> bool:
        """Delete report (entire folder)"""
        import shutil

        folder_path = cls._get_report_folder(report_id)

        # New format: delete entire folder
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            logger.info(f"Report folder deleted: {report_id}")
            return True

        # Backward compatibility: delete individual files
        deleted = False
        old_json_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
        old_md_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.md")

        if os.path.exists(old_json_path):
            os.remove(old_json_path)
            deleted = True
        if os.path.exists(old_md_path):
            os.remove(old_md_path)
            deleted = True

        return deleted
