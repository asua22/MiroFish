"""
Simulation Config Intelligent Generator
Uses LLM to automatically generate detailed simulation parameters based on simulation requirements, document content, and graph information.
Achieves full automation, no need for manual parameter setting.

Adopts a step-by-step generation strategy to prevent failure caused by generating overly long content at once:
1. Generate time configuration
2. Generate event configuration
3. Generate agent configuration in batches
4. Generate platform configuration
"""

import json
import math
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger("mirofish.simulation_config")

# 中国作息时间配置（已废弃，改为动态检测）
# CHINA_TIMEZONE_CONFIG = {
#     # ... (省略)
# }


@dataclass
class AgentActivityConfig:
    """Individual agent's activity configuration"""

    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str

    # Activity level (0.0-1.0)
    activity_level: float = 0.5  # Overall activity

    # Posting frequency (expected posts per hour)
    posts_per_hour: float = 1.0
    comments_per_hour: float = 2.0

    # Active hours (24-hour format, 0-23)
    active_hours: List[int] = field(default_factory=lambda: list(range(8, 23)))

    # Response speed (delay in response to hot events, unit: simulation minutes)
    response_delay_min: int = 5
    response_delay_max: int = 60

    # Sentiment bias (-1.0 to 1.0, negative to positive)
    sentiment_bias: float = 0.0

    # Stance (attitude towards specific topics)
    stance: str = "neutral"  # supportive, opposing, neutral, observer

    # Influence weight (determines probability of being seen by other agents)
    influence_weight: float = 1.0


@dataclass
class TimeSimulationConfig:
    """Time simulation configuration (based on typical daily schedules)"""

    # Total simulation duration (hours)
    total_simulation_hours: int = 72  # Default 72 hours (3 days)

    # Time per round (simulation minutes) - Default 60 minutes (1 hour), speeds up time flow
    minutes_per_round: int = 60

    # Range of active agents per hour
    agents_per_hour_min: int = 5
    agents_per_hour_max: int = 20

    # Peak hours (19:00 - 22:00, most active time)
    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5

    # Off-peak hours (00:00 - 05:00, almost no activity)
    off_peak_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.05  # Extremely low activity at night

    # Morning hours
    morning_hours: List[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.4

    # Work hours
    work_hours: List[int] = field(
        default_factory=lambda: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    )
    work_activity_multiplier: float = 0.7


@dataclass
class EventConfig:
    """Event configuration"""

    # Initial events (triggered at the start of simulation)
    initial_posts: List[Dict[str, Any]] = field(default_factory=list)

    # Scheduled events (triggered at specific times)
    scheduled_events: List[Dict[str, Any]] = field(default_factory=list)

    # Hot topic keywords
    hot_topics: List[str] = field(default_factory=list)

    # Public opinion guidance direction
    narrative_direction: str = ""


@dataclass
class PlatformConfig:
    """Platform-specific configuration"""

    platform: str  # twitter or reddit

    # Recommendation algorithm weights
    recency_weight: float = 0.4  # Time freshness
    popularity_weight: float = 0.3  # Popularity
    relevance_weight: float = 0.3  # Relevance

    # Viral propagation threshold (amount of interaction before spreading)
    viral_threshold: int = 10

    # Echo chamber effect strength (degree of similar views clustering)
    echo_chamber_strength: float = 0.5


@dataclass
class SimulationParameters:
    """Complete simulation parameter configuration"""

    # Basic information
    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str

    # Time configuration
    time_config: TimeSimulationConfig = field(default_factory=TimeSimulationConfig)

    # Agent configuration list
    agent_configs: List[AgentActivityConfig] = field(default_factory=list)

    # Event configuration
    event_config: EventConfig = field(default_factory=EventConfig)

    # Platform configuration
    twitter_config: Optional[PlatformConfig] = None
    reddit_config: Optional[PlatformConfig] = None

    # LLM configuration
    llm_model: str = ""
    llm_base_url: str = ""

    # Generation metadata
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_reasoning: str = ""  # LLM reasoning explanation

    def to_dict(self) -> Dict[str, Any]:
        """Converts to dictionary"""
        time_dict = asdict(self.time_config)
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "time_config": time_dict,
            "agent_configs": [asdict(a) for a in self.agent_configs],
            "event_config": asdict(self.event_config),
            "twitter_config": asdict(self.twitter_config)
            if self.twitter_config
            else None,
            "reddit_config": asdict(self.reddit_config) if self.reddit_config else None,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
            "generation_reasoning": self.generation_reasoning,
        }

    def to_json(self, indent: int = 2) -> str:
        """Converts to JSON string"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class SimulationConfigGenerator:
    """
    Simulation Configuration Intelligent Generator

    Uses LLM to analyze simulation requirements, document content, and graph entity information,
    automatically generating optimal simulation parameter configurations.

    Adopts a step-by-step generation strategy:
    1. Generate time configuration and event configuration (lightweight)
    2. Generate agent configuration in batches (10-20 per batch)
    3. Generate platform configuration
    """

    # Maximum context character count
    MAX_CONTEXT_LENGTH = 50000
    # Number of agents to generate per batch
    AGENTS_PER_BATCH = 15

    # Context truncation lengths for each step (character count)
    TIME_CONFIG_CONTEXT_LENGTH = 10000  # Time configuration
    EVENT_CONFIG_CONTEXT_LENGTH = 8000  # Event configuration
    ENTITY_SUMMARY_LENGTH = 300  # Entity summary
    AGENT_SUMMARY_LENGTH = 300  # Entity summary in agent config
    ENTITIES_PER_TYPE_DISPLAY = 20  # Number of entities displayed per type

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        """
        Intelligently generates complete simulation configuration (step-by-step)

        Args:
            simulation_id: Simulation ID
            project_id: Project ID
            graph_id: Graph ID
            simulation_requirement: Simulation requirement description
            document_text: Original document content
            entities: Filtered entity list
            enable_twitter: Whether to enable Twitter
            enable_reddit: Whether to enable Reddit
            progress_callback: Progress callback function (current_step, total_steps, message)

        Returns:
            SimulationParameters: Complete simulation parameters
        """
        logger.info(
            f"Starting intelligent simulation config generation: simulation_id={simulation_id}, entities={len(entities)}"
        )

        # Calculate total steps
        num_batches = math.ceil(len(entities) / self.AGENTS_PER_BATCH)
        total_steps = (
            3 + num_batches
        )  # Time config + Event config + N batches of Agents + Platform config
        current_step = 0

        def report_progress(step: int, message: str):
            nonlocal current_step
            current_step = step
            if progress_callback:
                progress_callback(step, total_steps, message)
            logger.info(f"[{step}/{total_steps}] {message}")

        # 1. Build basic context information
        context = self._build_context(
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            entities=entities,
        )

        reasoning_parts = []

        # ========== Step 1: Generate time configuration ==========
        report_progress(1, "Generating time configuration...")
        num_entities = len(entities)
        time_config_result = self._generate_time_config(context, num_entities)
        time_config = self._parse_time_config(time_config_result, num_entities)
        reasoning_parts.append(
            f"Time configuration: {time_config_result.get('reasoning', 'Success')}"
        )

        # ========== Step 2: Generate event configuration ==========
        report_progress(2, "Generating event configuration and hot topics...")
        event_config_result = self._generate_event_config(
            context, simulation_requirement, entities
        )
        event_config = self._parse_event_config(event_config_result)
        reasoning_parts.append(
            f"Event configuration: {event_config_result.get('reasoning', 'Success')}"
        )

        # ========== Step 3-N: Generate agent configuration in batches ==========
        all_agent_configs = []
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.AGENTS_PER_BATCH
            end_idx = min(start_idx + self.AGENTS_PER_BATCH, len(entities))
            batch_entities = entities[start_idx:end_idx]

            report_progress(
                3 + batch_idx,
                f"Generating agent configuration ({start_idx + 1}-{end_idx}/{len(entities)})...",
            )

            batch_configs = self._generate_agent_configs_batch(
                context=context,
                entities=batch_entities,
                start_idx=start_idx,
                simulation_requirement=simulation_requirement,
            )
            all_agent_configs.extend(batch_configs)

        reasoning_parts.append(
            f"Agent configuration: Successfully generated {len(all_agent_configs)}"
        )

        # ========== Assign initial post agents ==========
        logger.info("Assigning appropriate publisher agents to initial posts...")
        event_config = self._assign_initial_post_agents(event_config, all_agent_configs)
        assigned_count = len(
            [
                p
                for p in event_config.initial_posts
                if p.get("poster_agent_id") is not None
            ]
        )
        reasoning_parts.append(
            f"Initial post assignment: {assigned_count} posts assigned to publishers"
        )

        # ========== Last step: Generate platform configuration ==========
        report_progress(total_steps, "Generating platform configuration...")
        twitter_config = None
        reddit_config = None

        if enable_twitter:
            twitter_config = PlatformConfig(
                platform="twitter",
                recency_weight=0.4,
                popularity_weight=0.3,
                relevance_weight=0.3,
                viral_threshold=10,
                echo_chamber_strength=0.5,
            )

        if enable_reddit:
            reddit_config = PlatformConfig(
                platform="reddit",
                recency_weight=0.3,
                popularity_weight=0.4,
                relevance_weight=0.3,
                viral_threshold=15,
                echo_chamber_strength=0.6,
            )

        # Build final parameters
        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=time_config,
            agent_configs=all_agent_configs,
            event_config=event_config,
            twitter_config=twitter_config,
            reddit_config=reddit_config,
            llm_model=self.model_name,
            llm_base_url=self.base_url,
            generation_reasoning=" | ".join(reasoning_parts),
        )

        logger.info(
            f"Simulation configuration generation complete: {len(params.agent_configs)} agent configurations"
        )

        return params

    def _build_context(
        self,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
    ) -> str:
        """Builds LLM context, truncated to maximum length"""

        # Entity summary
        entity_summary = self._summarize_entities(entities)

        # Build context
        context_parts = [
            f"## Simulation Requirements\n{simulation_requirement}",
            f"\n## Entity Information ({len(entities)} items)\n{entity_summary}",
        ]

        current_length = sum(len(p) for p in context_parts)
        remaining_length = (
            self.MAX_CONTEXT_LENGTH - current_length - 500
        )  # Leave 500 character buffer

        if remaining_length > 0 and document_text:
            doc_text = document_text[:remaining_length]
            if len(document_text) > remaining_length:
                doc_text += "\n...(Document truncated)"
            context_parts.append(f"\n## Original Document Content\n{doc_text}")

        return "\n".join(context_parts)

    def _summarize_entities(self, entities: List[EntityNode]) -> str:
        """Generates entity summary"""
        lines = []

        # Group by type
        by_type: Dict[str, List[EntityNode]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e)

        for entity_type, type_entities in by_type.items():
            lines.append(f"\n### {entity_type} ({len(type_entities)} items)")
            # Use configured display count and summary length
            display_count = self.ENTITIES_PER_TYPE_DISPLAY
            summary_len = self.ENTITY_SUMMARY_LENGTH
            for e in type_entities[:display_count]:
                summary_preview = (
                    (e.summary[:summary_len] + "...")
                    if len(e.summary) > summary_len
                    else e.summary
                )
                lines.append(f"- {e.name}: {summary_preview}")
            if len(type_entities) > display_count:
                lines.append(f"  ... and {len(type_entities) - display_count} more")

        return "\n".join(lines)

    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """LLM call with retry, includes JSON repair logic"""
        import re

        max_attempts = 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7
                    - (attempt * 0.1),  # Lower temperature on each retry
                )

                content = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason

                # Check if truncated
                if finish_reason == "length":
                    logger.warning(f"LLM output truncated (attempt {attempt + 1})")
                    content = self._fix_truncated_json(content)

                # Attempt JSON parsing
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"JSON parsing failed (attempt {attempt + 1}): {str(e)[:80]}"
                    )

                    # Attempt to fix JSON
                    fixed = self._try_fix_config_json(content)
                    if fixed:
                        return fixed

                    last_error = e

            except Exception as e:
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}): {str(e)[:80]}"
                )
                last_error = e
                import time

                time.sleep(2 * (attempt + 1))

        raise last_error or Exception("LLM call failed")

    def _fix_truncated_json(self, content: str) -> str:
        """Fixes truncated JSON"""
        content = content.strip()

        # Calculate unclosed braces/brackets
        open_braces = content.count("{") - content.count("}")
        open_brackets = content.count("[") - content.count("]")

        # Check for unclosed string
        if content and content[-1] not in '",}]':
            content += '"'

        # Close braces
        content += "]" * open_brackets
        content += "}" * open_braces

        return content

    def _try_fix_config_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Attempts to fix configuration JSON"""
        import re

        # Fix truncation
        content = self._fix_truncated_json(content)

        # Extract JSON part
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            json_str = json_match.group()

            # Remove newlines in strings
            def fix_string(match):
                s = match.group(0)
                s = s.replace("\n", " ").replace("\r", " ")
                s = re.sub(r"\s+", " ", s)
                return s

            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string, json_str)

            try:
                return json.loads(json_str)
            except:
                # Remove control characters
                json_str = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", json_str)
                json_str = re.sub(r"\s+", " ", json_str)
                try:
                    return json.loads(json_str)
                except:
                    pass

        return None

    def _generate_time_config(self, context: str, num_entities: int) -> Dict[str, Any]:
        """Generates time configuration"""
        # Use configured context truncation length
        context_truncated = context[: self.TIME_CONFIG_CONTEXT_LENGTH]

        # Calculate maximum allowed value (90% of agent count)
        max_agents_allowed = max(1, int(num_entities * 0.9))

        prompt = f"""Based on the following simulation requirements, generate time simulation configuration.

{context_truncated}

## Task
Please generate JSON for time configuration.

### Basic Principles (for reference, adapt to the event and participating group):
- Detect the timezone/cultural context from the input and adapt the activity schedule.
- Generally: low activity in early morning, gradual increase in morning, moderate in work hours, peak in evening.
- **Important**: The following example values are for reference only. Adjust time periods based on the event nature and participant group characteristics.
  - Example: Student group peak might be late night (21-23); Media is active all day; Official institutions active only during work hours.
  - Example: Sudden hot events might lead to late-night activity, shortening off_peak_hours.

### Return JSON Format (no markdown)
Example:
{{
    "total_simulation_hours": 72,
    "minutes_per_round": 60,
    "agents_per_hour_min": 5,
    "agents_per_hour_max": 50,
    "peak_hours": [19, 20, 21, 22],
    "off_peak_hours": [0, 1, 2, 3, 4, 5],
    "morning_hours": [6, 7, 8],
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    "reasoning": "Explanation for this time configuration"
}}

Field Explanation:
- total_simulation_hours (int): Total simulation hours (24-168).
- minutes_per_round (int): Minutes per round (30-120).
- agents_per_hour_min (int): Min agents active per hour (1-{max_agents_allowed}).
- agents_per_hour_max (int): Max agents active per hour (1-{max_agents_allowed}).
- peak_hours (int array): Peak hours, adjust based on participants.
- off_peak_hours (int array): Off-peak hours.
- morning_hours (int array): Morning hours.
- work_hours (int array): Work hours.
- reasoning (string): Explanation."""

        system_prompt = "You are a social media simulation expert. Return pure JSON. Adapt timezone and cultural context based on input."

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"Time config LLM generation failed: {e}, using default")
            return self._get_default_time_config(num_entities)

    def _get_default_time_config(self, num_entities: int) -> Dict[str, Any]:
        """Gets default time configuration (daily routine)"""
        return {
            "total_simulation_hours": 72,
            "minutes_per_round": 60,  # 1 hour per round, accelerates time flow
            "agents_per_hour_min": max(1, num_entities // 15),
            "agents_per_hour_max": max(5, num_entities // 5),
            "peak_hours": [19, 20, 21, 22],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
            "morning_hours": [6, 7, 8],
            "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "reasoning": "Using default daily routine configuration (1 hour per round)",
        }

    def _parse_time_config(
        self, result: Dict[str, Any], num_entities: int
    ) -> TimeSimulationConfig:
        """Parses time configuration result and validates agents_per_hour values"""
        # Get raw values
        agents_per_hour_min = result.get(
            "agents_per_hour_min", max(1, num_entities // 15)
        )
        agents_per_hour_max = result.get(
            "agents_per_hour_max", max(5, num_entities // 5)
        )

        # Validate and fix: ensure not exceeding total agent count
        if agents_per_hour_min > num_entities:
            logger.warning(
                f"agents_per_hour_min ({agents_per_hour_min}) exceeds total Agent count ({num_entities}), fixed"
            )
            agents_per_hour_min = max(1, num_entities // 10)

        if agents_per_hour_max > num_entities:
            logger.warning(
                f"agents_per_hour_max ({agents_per_hour_max}) exceeds total Agent count ({num_entities}), fixed"
            )
            agents_per_hour_max = max(agents_per_hour_min + 1, num_entities // 2)

        # Ensure min < max
        if agents_per_hour_min >= agents_per_hour_max:
            agents_per_hour_min = max(1, agents_per_hour_max // 2)
            logger.warning(
                f"agents_per_hour_min >= max, fixed to {agents_per_hour_min}"
            )

        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get(
                "minutes_per_round", 60
            ),  # Default 1 hour per round
            agents_per_hour_min=agents_per_hour_min,
            agents_per_hour_max=agents_per_hour_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            off_peak_activity_multiplier=0.05,  # Almost no activity at night
            morning_hours=result.get("morning_hours", [6, 7, 8]),
            morning_activity_multiplier=0.4,
            work_hours=result.get("work_hours", list(range(9, 19))),
            work_activity_multiplier=0.7,
            peak_activity_multiplier=1.5,
        )

    def _generate_event_config(
        self, context: str, simulation_requirement: str, entities: List[EntityNode]
    ) -> Dict[str, Any]:
        """Generates event configuration"""

        # Get available entity type list for LLM reference
        entity_types_available = list(
            set(e.get_entity_type() or "Unknown" for e in entities)
        )

        # List representative entity names for each type
        type_examples = {}
        for e in entities:
            etype = e.get_entity_type() or "Unknown"
            if etype not in type_examples:
                type_examples[etype] = []
            if len(type_examples[etype]) < 3:
                type_examples[etype].append(e.name)

        type_info = "\n".join(
            [f"- {t}: {', '.join(examples)}" for t, examples in type_examples.items()]
        )

        # Use configured context truncation length
        context_truncated = context[: self.EVENT_CONFIG_CONTEXT_LENGTH]

        prompt = f"""Based on the following simulation requirements, generate event configuration.

Simulation requirements: {simulation_requirement}

{context_truncated}

## Available entity types and examples
{type_info}

## Task
Generate event configuration JSON:
- Extract hot topic keywords
- Describe public opinion development direction
- Design initial post content, **every post must specify poster_type (publisher type)**

**Important**: poster_type must be selected from the "Available entity types" above, so that the initial post can be assigned to the appropriate Agent.
Example: Official statements should be published by Official/University type, news by MediaOutlet, student opinions by Student.

Return JSON format (no markdown):
{{
    "hot_topics": ["Keyword1", "Keyword2", ...],
    "narrative_direction": "<description of public opinion development>",
    "initial_posts": [
        {{"content": "Post content", "poster_type": "Entity type (must match available types)"}},
        ...
    ],
    "reasoning": "<brief explanation>"
}}"""

        system_prompt = "You are a public opinion analysis expert. Return pure JSON. Note poster_type must accurately match available entity types."

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"Event config LLM generation failed: {e}, using default")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
                "reasoning": "Using default configuration",
            }

    def _parse_event_config(self, result: Dict[str, Any]) -> EventConfig:
        """Parses event configuration result"""
        return EventConfig(
            initial_posts=result.get("initial_posts", []),
            scheduled_events=[],
            hot_topics=result.get("hot_topics", []),
            narrative_direction=result.get("narrative_direction", ""),
        )

    def _assign_initial_post_agents(
        self, event_config: EventConfig, agent_configs: List[AgentActivityConfig]
    ) -> EventConfig:
        """
        Assigns appropriate publisher Agent to initial posts

        Matches most suitable agent_id based on each post's poster_type
        """
        if not event_config.initial_posts:
            return event_config

        # Build agent index by entity type
        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for agent in agent_configs:
            etype = agent.entity_type.lower()
            if etype not in agents_by_type:
                agents_by_type[etype] = []
            agents_by_type[etype].append(agent)

        # Type alias mapping (handles different formats LLM might output)
        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
        }

        # Track used agent index per type to avoid reusing the same agent
        used_indices: Dict[str, int] = {}

        updated_posts = []
        for post in event_config.initial_posts:
            poster_type = post.get("poster_type", "").lower()
            content = post.get("content", "")

            # Attempt to find matching agent
            matched_agent_id = None

            # 1. Direct match
            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used_indices.get(poster_type, 0) % len(agents)
                matched_agent_id = agents[idx].agent_id
                used_indices[poster_type] = idx + 1
            else:
                # 2. Match using aliases
                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used_indices.get(alias, 0) % len(agents)
                                matched_agent_id = agents[idx].agent_id
                                used_indices[alias] = idx + 1
                                break
                    if matched_agent_id is not None:
                        break

            # 3. If still not found, use highest influence agent
            if matched_agent_id is None:
                logger.warning(
                    f"No matching Agent found for type '{poster_type}', using highest influence Agent"
                )
                if agent_configs:
                    # Sort by influence and select highest
                    sorted_agents = sorted(
                        agent_configs, key=lambda a: a.influence_weight, reverse=True
                    )
                    matched_agent_id = sorted_agents[0].agent_id
                else:
                    matched_agent_id = 0

            updated_posts.append(
                {
                    "content": content,
                    "poster_type": post.get("poster_type", "Unknown"),
                    "poster_agent_id": matched_agent_id,
                }
            )

            logger.info(
                f"Initial post assignment: poster_type='{poster_type}' -> agent_id={matched_agent_id}"
            )

        event_config.initial_posts = updated_posts
        return event_config

    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str,
    ) -> List[AgentActivityConfig]:
        """Generates agent configuration in batches"""

        # Build entity info
        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for i, e in enumerate(entities):
            entity_list.append(
                {
                    "agent_id": start_idx + i,
                    "entity_name": e.name,
                    "entity_type": e.get_entity_type() or "Unknown",
                    "summary": e.summary[:summary_len] if e.summary else "",
                }
            )

        prompt = f"""Based on the following information, generate social media activity configuration for each entity.

Simulation requirement: {simulation_requirement}

## Entity List
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## Task
Generate activity configuration for each entity, note:
- **Time must align with daily routines**: Almost no activity between 0-5 AM, most active between 7-10 PM.
- **Official institutions** (University/GovernmentAgency): Low activity(0.1-0.3), active during work hours(9-17), slow response(60-240 minutes), high influence(2.5-3.0).
- **Media** (MediaOutlet): Medium activity(0.4-0.6), active all day(8-23), fast response(5-30 minutes), high influence(2.0-2.5).
- **Individuals** (Student/Person/Alumni): High activity(0.6-0.9), primarily evening activity(18-23), fast response(1-15 minutes), low influence(0.8-1.2).
- **Public figures/Experts**: Medium activity(0.4-0.6), medium-high influence(1.5-2.0).

Return JSON format (no markdown):
{{
    "agent_configs": [
        {{
            "agent_id": <must match input>,
            "activity_level": <0.0-1.0>,
            "posts_per_hour": <posting frequency>,
            "comments_per_hour": <comment frequency>,
            "active_hours": [<list of active hours, consider daily routines>],
            "response_delay_min": <min response delay in minutes>,
            "response_delay_max": <max response delay in minutes>,
            "sentiment_bias": <-1.0 to 1.0>,
            "stance": "<supportive/opposing/neutral/observer>",
            "influence_weight": <influence weight>
        }},
        ...
    ]
}}"""

        system_prompt = "You are a social media behavior analysis expert. Return pure JSON, configuration must fit daily routines."

        try:
            result = self._call_llm_with_retry(prompt, system_prompt)
            llm_configs = {
                cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])
            }
        except Exception as e:
            logger.warning(
                f"Agent config batch LLM generation failed: {e}, using rule-based generation"
            )
            llm_configs = {}

        # Build AgentActivityConfig objects
        configs = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_configs.get(agent_id, {})

            # If LLM didn't generate it, use rule-based generation
            if not cfg:
                cfg = self._generate_agent_config_by_rule(entity)

            config = AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                activity_level=cfg.get("activity_level", 0.5),
                posts_per_hour=cfg.get("posts_per_hour", 0.5),
                comments_per_hour=cfg.get("comments_per_hour", 1.0),
                active_hours=cfg.get("active_hours", list(range(9, 23))),
                response_delay_min=cfg.get("response_delay_min", 5),
                response_delay_max=cfg.get("response_delay_max", 60),
                sentiment_bias=cfg.get("sentiment_bias", 0.0),
                stance=cfg.get("stance", "neutral"),
                influence_weight=cfg.get("influence_weight", 1.0),
            )
            configs.append(config)

        return configs

    def _generate_agent_config_by_rule(self, entity: EntityNode) -> Dict[str, Any]:
        """Generates single agent configuration based on rules (dynamically adjusted according to entity type)"""
        entity_type = (entity.get_entity_type() or "Unknown").lower()

        # Basic rules: provide default configuration based on entity type
        if entity_type in ["university", "governmentagency", "ngo"]:
            return {
                "activity_level": 0.2,
                "posts_per_hour": 0.1,
                "comments_per_hour": 0.05,
                "active_hours": list(range(9, 18)),
                "response_delay_min": 60,
                "response_delay_max": 240,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 3.0,
            }
        elif entity_type in ["mediaoutlet"]:
            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.8,
                "comments_per_hour": 0.3,
                "active_hours": list(range(7, 24)),
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "observer",
                "influence_weight": 2.5,
            }
        elif entity_type in ["professor", "expert", "official"]:
            return {
                "activity_level": 0.4,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.5,
                "active_hours": list(range(8, 22)),
                "response_delay_min": 15,
                "response_delay_max": 90,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 2.0,
            }
        else:
            # Default persona
            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.6,
                "active_hours": list(range(8, 23)),
                "response_delay_min": 5,
                "response_delay_max": 60,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0,
            }

    def _parse_time_config(
        self, result: Dict[str, Any], num_entities: int
    ) -> TimeSimulationConfig:
        """解析时间配置结果，并验证agents_per_hour值不超过总agent数"""
        # 获取原始值
        agents_per_hour_min = result.get(
            "agents_per_hour_min", max(1, num_entities // 15)
        )
        agents_per_hour_max = result.get(
            "agents_per_hour_max", max(5, num_entities // 5)
        )

        # 验证并修正：确保不超过总agent数
        if agents_per_hour_min > num_entities:
            logger.warning(
                f"agents_per_hour_min ({agents_per_hour_min}) exceeds total Agent count ({num_entities}), fixed"
            )
            agents_per_hour_min = max(1, num_entities // 10)

        if agents_per_hour_max > num_entities:
            logger.warning(
                f"agents_per_hour_max ({agents_per_hour_max}) exceeds total Agent count ({num_entities}), fixed"
            )
            agents_per_hour_max = max(agents_per_hour_min + 1, num_entities // 2)

        # 确保 min < max
        if agents_per_hour_min >= agents_per_hour_max:
            agents_per_hour_min = max(1, agents_per_hour_max // 2)
            logger.warning(
                f"agents_per_hour_min >= max，已修正为 {agents_per_hour_min}"
            )

        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get("minutes_per_round", 60),  # 默认每轮1小时
            agents_per_hour_min=agents_per_hour_min,
            agents_per_hour_max=agents_per_hour_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            off_peak_activity_multiplier=0.05,  # 凌晨几乎无人
            morning_hours=result.get("morning_hours", [6, 7, 8]),
            morning_activity_multiplier=0.4,
            work_hours=result.get("work_hours", list(range(9, 19))),
            work_activity_multiplier=0.7,
            peak_activity_multiplier=1.5,
        )

    def _generate_event_config(
        self, context: str, simulation_requirement: str, entities: List[EntityNode]
    ) -> Dict[str, Any]:
        """生成事件配置"""

        # 获取可用的实体类型列表，供 LLM 参考
        entity_types_available = list(
            set(e.get_entity_type() or "Unknown" for e in entities)
        )

        # 为每种类型列出代表性实体名称
        type_examples = {}
        for e in entities:
            etype = e.get_entity_type() or "Unknown"
            if etype not in type_examples:
                type_examples[etype] = []
            if len(type_examples[etype]) < 3:
                type_examples[etype].append(e.name)

        type_info = "\n".join(
            [f"- {t}: {', '.join(examples)}" for t, examples in type_examples.items()]
        )

        # 使用配置的上下文截断长度
        context_truncated = context[: self.EVENT_CONFIG_CONTEXT_LENGTH]

        prompt = f"""基于以下模拟需求，生成事件配置。

模拟需求: {simulation_requirement}

{context_truncated}

## 可用实体类型及示例
{type_info}

## 任务
请生成事件配置JSON：
- 提取热点话题关键词
- 描述舆论发展方向
- 设计初始帖子内容，**每个帖子必须指定 poster_type（发布者类型）**

**重要**: poster_type 必须从上面的"可用实体类型"中选择，这样初始帖子才能分配给合适的 Agent 发布。
例如：官方声明应由 Official/University 类型发布，新闻由 MediaOutlet 发布，学生观点由 Student 发布。

返回JSON格式（不要markdown）：
{{
    "hot_topics": ["关键词1", "关键词2", ...],
    "narrative_direction": "<舆论发展方向描述>",
    "initial_posts": [
        {{"content": "帖子内容", "poster_type": "实体类型（必须从可用类型中选择）"}},
        ...
    ],
    "reasoning": "<简要说明>"
}}"""

        system_prompt = "你是舆论分析专家。返回纯JSON格式。注意 poster_type 必须精确匹配可用实体类型。"

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"事件配置LLM生成失败: {e}, 使用默认配置")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
                "reasoning": "使用默认配置",
            }

    def _parse_event_config(self, result: Dict[str, Any]) -> EventConfig:
        """解析事件配置结果"""
        return EventConfig(
            initial_posts=result.get("initial_posts", []),
            scheduled_events=[],
            hot_topics=result.get("hot_topics", []),
            narrative_direction=result.get("narrative_direction", ""),
        )

    def _assign_initial_post_agents(
        self, event_config: EventConfig, agent_configs: List[AgentActivityConfig]
    ) -> EventConfig:
        """
        为初始帖子分配合适的发布者 Agent

        根据每个帖子的 poster_type 匹配最合适的 agent_id
        """
        if not event_config.initial_posts:
            return event_config

        # 按实体类型建立 agent 索引
        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for agent in agent_configs:
            etype = agent.entity_type.lower()
            if etype not in agents_by_type:
                agents_by_type[etype] = []
            agents_by_type[etype].append(agent)

        # 类型映射表（处理 LLM 可能输出的不同格式）
        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
        }

        # 记录每种类型已使用的 agent 索引，避免重复使用同一个 agent
        used_indices: Dict[str, int] = {}

        updated_posts = []
        for post in event_config.initial_posts:
            poster_type = post.get("poster_type", "").lower()
            content = post.get("content", "")

            # 尝试找到匹配的 agent
            matched_agent_id = None

            # 1. 直接匹配
            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used_indices.get(poster_type, 0) % len(agents)
                matched_agent_id = agents[idx].agent_id
                used_indices[poster_type] = idx + 1
            else:
                # 2. 使用别名匹配
                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used_indices.get(alias, 0) % len(agents)
                                matched_agent_id = agents[idx].agent_id
                                used_indices[alias] = idx + 1
                                break
                    if matched_agent_id is not None:
                        break

            # 3. 如果仍未找到，使用影响力最高的 agent
            if matched_agent_id is None:
                logger.warning(
                    f"未找到类型 '{poster_type}' 的匹配 Agent，使用影响力最高的 Agent"
                )
                if agent_configs:
                    # 按影响力排序，选择影响力最高的
                    sorted_agents = sorted(
                        agent_configs, key=lambda a: a.influence_weight, reverse=True
                    )
                    matched_agent_id = sorted_agents[0].agent_id
                else:
                    matched_agent_id = 0

            updated_posts.append(
                {
                    "content": content,
                    "poster_type": post.get("poster_type", "Unknown"),
                    "poster_agent_id": matched_agent_id,
                }
            )

            logger.info(
                f"初始帖子分配: poster_type='{poster_type}' -> agent_id={matched_agent_id}"
            )

        event_config.initial_posts = updated_posts
        return event_config

    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str,
    ) -> List[AgentActivityConfig]:
        """分批生成Agent配置"""

        # 构建实体信息（使用配置的摘要长度）
        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for i, e in enumerate(entities):
            entity_list.append(
                {
                    "agent_id": start_idx + i,
                    "entity_name": e.name,
                    "entity_type": e.get_entity_type() or "Unknown",
                    "summary": e.summary[:summary_len] if e.summary else "",
                }
            )

        prompt = f"""基于以下信息，为每个实体生成社交媒体活动配置。

模拟需求: {simulation_requirement}

## 实体列表
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## 任务
为每个实体生成活动配置，注意：
- **时间符合中国人作息**：凌晨0-5点几乎不活动，晚间19-22点最活跃
- **官方机构**（University/GovernmentAgency）：活跃度低(0.1-0.3)，工作时间(9-17)活动，响应慢(60-240分钟)，影响力高(2.5-3.0)
- **媒体**（MediaOutlet）：活跃度中(0.4-0.6)，全天活动(8-23)，响应快(5-30分钟)，影响力高(2.0-2.5)
- **个人**（Student/Person/Alumni）：活跃度高(0.6-0.9)，主要晚间活动(18-23)，响应快(1-15分钟)，影响力低(0.8-1.2)
- **公众人物/专家**：活跃度中(0.4-0.6)，影响力中高(1.5-2.0)

返回JSON格式（不要markdown）：
{{
    "agent_configs": [
        {{
            "agent_id": <必须与输入一致>,
            "activity_level": <0.0-1.0>,
            "posts_per_hour": <发帖频率>,
            "comments_per_hour": <评论频率>,
            "active_hours": [<活跃小时列表，考虑中国人作息>],
            "response_delay_min": <最小响应延迟分钟>,
            "response_delay_max": <最大响应延迟分钟>,
            "sentiment_bias": <-1.0到1.0>,
            "stance": "<supportive/opposing/neutral/observer>",
            "influence_weight": <影响力权重>
        }},
        ...
    ]
}}"""

        system_prompt = (
            "你是社交媒体行为分析专家。返回纯JSON，配置需符合中国人作息习惯。"
        )

        try:
            result = self._call_llm_with_retry(prompt, system_prompt)
            llm_configs = {
                cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])
            }
        except Exception as e:
            logger.warning(f"Agent配置批次LLM生成失败: {e}, 使用规则生成")
            llm_configs = {}

        # 构建AgentActivityConfig对象
        configs = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_configs.get(agent_id, {})

            # 如果LLM没有生成，使用规则生成
            if not cfg:
                cfg = self._generate_agent_config_by_rule(entity)

            config = AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                activity_level=cfg.get("activity_level", 0.5),
                posts_per_hour=cfg.get("posts_per_hour", 0.5),
                comments_per_hour=cfg.get("comments_per_hour", 1.0),
                active_hours=cfg.get("active_hours", list(range(9, 23))),
                response_delay_min=cfg.get("response_delay_min", 5),
                response_delay_max=cfg.get("response_delay_max", 60),
                sentiment_bias=cfg.get("sentiment_bias", 0.0),
                stance=cfg.get("stance", "neutral"),
                influence_weight=cfg.get("influence_weight", 1.0),
            )
            configs.append(config)

        return configs

    def _generate_agent_config_by_rule(self, entity: EntityNode) -> Dict[str, Any]:
        """基于规则生成单个Agent配置（根据实体类型动态调整）"""
        entity_type = (entity.get_entity_type() or "Unknown").lower()

        # 基础规则：根据实体类型提供默认配置，后续由 ContextDetector 或 LLM 进行动态调整
        # 这些规则旨在提供一个合理的初始值，而非死板的固定值
        if entity_type in ["university", "governmentagency", "ngo"]:
            return {
                "activity_level": 0.2,
                "posts_per_hour": 0.1,
                "comments_per_hour": 0.05,
                "active_hours": list(range(9, 18)),
                "response_delay_min": 60,
                "response_delay_max": 240,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 3.0,
            }
        elif entity_type in ["mediaoutlet"]:
            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.8,
                "comments_per_hour": 0.3,
                "active_hours": list(range(7, 24)),
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "observer",
                "influence_weight": 2.5,
            }
        elif entity_type in ["professor", "expert", "official"]:
            return {
                "activity_level": 0.4,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.5,
                "active_hours": list(range(8, 22)),
                "response_delay_min": 15,
                "response_delay_max": 90,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 2.0,
            }
        else:
            # 默认人设
            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.6,
                "active_hours": list(range(8, 23)),
                "response_delay_min": 5,
                "response_delay_max": 60,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0,
            }
