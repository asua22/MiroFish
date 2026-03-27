"""
OASIS Simulation Runner
Runs simulation in background and records each Agent's actions, supports real-time status monitoring
"""

import os
import sys
import json
import time
import asyncio
import threading
import subprocess
import signal
import atexit
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue

from ..config import Config
from ..utils.logger import get_logger
from .zep_graph_memory_updater import ZepGraphMemoryManager
from .simulation_ipc import SimulationIPCClient, CommandType, IPCResponse

logger = get_logger("mirofish.simulation_runner")

# Flag indicating whether cleanup function is registered
_cleanup_registered = False

# Platform detection
IS_WINDOWS = sys.platform == "win32"


class RunnerStatus(str, Enum):
    """Runner status"""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentAction:
    """Agent action record"""

    round_num: int
    timestamp: str
    platform: str  # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str  # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "result": self.result,
            "success": self.success,
        }


@dataclass
class RoundSummary:
    """Round summary"""

    round_num: int
    start_time: str
    end_time: Optional[str] = None
    simulated_hour: int = 0
    twitter_actions: int = 0
    reddit_actions: int = 0
    active_agents: List[int] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "simulated_hour": self.simulated_hour,
            "twitter_actions": self.twitter_actions,
            "reddit_actions": self.reddit_actions,
            "active_agents": self.active_agents,
            "actions_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
        }


@dataclass
class SimulationRunState:
    """Simulation running status (real-time)"""

    simulation_id: str
    runner_status: RunnerStatus = RunnerStatus.IDLE

    # Progress info
    current_round: int = 0
    total_rounds: int = 0
    simulated_hours: int = 0
    total_simulation_hours: int = 0

    # Independent round and simulation time per platform (for dual-platform parallel display)
    twitter_current_round: int = 0
    reddit_current_round: int = 0
    twitter_simulated_hours: int = 0
    reddit_simulated_hours: int = 0

    # Platform status
    twitter_running: bool = False
    reddit_running: bool = False
    twitter_actions_count: int = 0
    reddit_actions_count: int = 0

    # Platform completion status (detected via simulation_end events in actions.jsonl)
    twitter_completed: bool = False
    reddit_completed: bool = False

    # Round summary
    rounds: List[RoundSummary] = field(default_factory=list)

    # Recent actions (for frontend real-time display)
    recent_actions: List[AgentAction] = field(default_factory=list)
    max_recent_actions: int = 50

    # Timestamp
    started_at: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    # Error info
    error: Optional[str] = None

    # Process ID (for stopping)
    process_pid: Optional[int] = None

    # Auto-resume watchdog config
    auto_resume_count: int = 0       # How many times auto-resumed so far
    auto_resume_max: int = 3         # Max auto-resume attempts

    # Startup params stored for watchdog restarts
    startup_platform: str = "parallel"
    startup_max_rounds: Optional[int] = None
    startup_enable_graph_memory_update: bool = False
    startup_graph_id: Optional[str] = None

    def add_action(self, action: AgentAction):
        """Add action to recent actions list"""
        self.recent_actions.insert(0, action)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[: self.max_recent_actions]

        if action.platform == "twitter":
            self.twitter_actions_count += 1
        else:
            self.reddit_actions_count += 1

        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "runner_status": self.runner_status.value,
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "simulated_hours": self.simulated_hours,
            "total_simulation_hours": self.total_simulation_hours,
            "progress_percent": round(
                self.current_round / max(self.total_rounds, 1) * 100, 1
            ),
            # Independent round and time per platform
            "twitter_current_round": self.twitter_current_round,
            "reddit_current_round": self.reddit_current_round,
            "twitter_simulated_hours": self.twitter_simulated_hours,
            "reddit_simulated_hours": self.reddit_simulated_hours,
            "twitter_running": self.twitter_running,
            "reddit_running": self.reddit_running,
            "twitter_completed": self.twitter_completed,
            "reddit_completed": self.reddit_completed,
            "twitter_actions_count": self.twitter_actions_count,
            "reddit_actions_count": self.reddit_actions_count,
            "total_actions_count": self.twitter_actions_count
            + self.reddit_actions_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "process_pid": self.process_pid,
        }

    def to_detail_dict(self) -> Dict[str, Any]:
        """Contains detailed recent actions info"""
        result = self.to_dict()
        result["recent_actions"] = [a.to_dict() for a in self.recent_actions]
        result["rounds_count"] = len(self.rounds)
        return result


class SimulationRunner:
    """
    Simulation Runner

    Responsible for:
    1. Run OASIS simulation in background process
    2. Parse running logs, record each Agent's actions
    3. Provide real-time status query endpoint
    4. Support pause/stop/resume operations
    """

    # Running state storage directory
    RUN_STATE_DIR = os.path.join(os.path.dirname(__file__), "../../uploads/simulations")

    # Scripts directory
    SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "../../scripts")

    # Running state in memory
    _run_states: Dict[str, SimulationRunState] = {}
    _processes: Dict[str, subprocess.Popen] = {}
    _action_queues: Dict[str, Queue] = {}
    _monitor_threads: Dict[str, threading.Thread] = {}
    _stdout_files: Dict[str, Any] = {}  # Store stdout File handle
    _stderr_files: Dict[str, Any] = {}  # Store stderr File handle

    # Graph memory update config
    _graph_memory_enabled: Dict[str, bool] = {}  # simulation_id -> enabled

    @classmethod
    def _is_process_alive(cls, pid: int) -> bool:
        """Check if a process is still running by PID"""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    @classmethod
    def get_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """Get running status"""
        if simulation_id in cls._run_states:
            return cls._run_states[simulation_id]

        # TryFromFileload
        state = cls._load_run_state(simulation_id)
        if state:
            cls._run_states[simulation_id] = state
        return state

    @classmethod
    def _load_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """Load running state from file"""
        state_file = os.path.join(cls.RUN_STATE_DIR, simulation_id, "run_state.json")
        if not os.path.exists(state_file):
            return None

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            state = SimulationRunState(
                simulation_id=simulation_id,
                runner_status=RunnerStatus(data.get("runner_status", "idle")),
                current_round=data.get("current_round", 0),
                total_rounds=data.get("total_rounds", 0),
                simulated_hours=data.get("simulated_hours", 0),
                total_simulation_hours=data.get("total_simulation_hours", 0),
                # Independent round and time per platform
                twitter_current_round=data.get("twitter_current_round", 0),
                reddit_current_round=data.get("reddit_current_round", 0),
                twitter_simulated_hours=data.get("twitter_simulated_hours", 0),
                reddit_simulated_hours=data.get("reddit_simulated_hours", 0),
                twitter_running=data.get("twitter_running", False),
                reddit_running=data.get("reddit_running", False),
                twitter_completed=data.get("twitter_completed", False),
                reddit_completed=data.get("reddit_completed", False),
                twitter_actions_count=data.get("twitter_actions_count", 0),
                reddit_actions_count=data.get("reddit_actions_count", 0),
                started_at=data.get("started_at"),
                updated_at=data.get("updated_at", datetime.now().isoformat()),
                completed_at=data.get("completed_at"),
                error=data.get("error"),
                process_pid=data.get("process_pid"),
            )

            # load recentAction
            actions_data = data.get("recent_actions", [])
            for a in actions_data:
                state.recent_actions.append(
                    AgentAction(
                        round_num=a.get("round_num", 0),
                        timestamp=a.get("timestamp", ""),
                        platform=a.get("platform", ""),
                        agent_id=a.get("agent_id", 0),
                        agent_name=a.get("agent_name", ""),
                        action_type=a.get("action_type", ""),
                        action_args=a.get("action_args", {}),
                        result=a.get("result"),
                        success=a.get("success", True),
                    )
                )

            return state
        except Exception as e:
            logger.error(f"Failed to load running state: {str(e)}")
            return None

    @classmethod
    def _save_run_state(cls, state: SimulationRunState):
        """Save running state to file"""
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        state_file = os.path.join(sim_dir, "run_state.json")

        data = state.to_detail_dict()

        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        cls._run_states[state.simulation_id] = state

    @classmethod
    def start_simulation(
        cls,
        simulation_id: str,
        platform: str = "parallel",  # twitter / reddit / parallel
        max_rounds: int = None,  # Max simulation rounds(optional,Used to truncate too long simulation)
        enable_graph_memory_update: bool = False,  # Whether to update activity toZepGraph
        graph_id: str = None,  # ZepGraphID(Required when enabling graph update)
    ) -> SimulationRunState:
        """
        Start simulation

        Args:
            simulation_id: Simulation ID
            platform: runningPlatform (twitter/reddit/parallel)
            max_rounds: Max simulation rounds(optional,Used to truncate too long simulation)
            enable_graph_memory_update: Whether toAgentActivity dynamic update toZepGraph
            graph_id: ZepGraphID(Required when enabling graph update)

        Returns:
            SimulationRunState
        """
        # Check if already running
        existing = cls.get_run_state(simulation_id)
        if existing and existing.runner_status in [
            RunnerStatus.RUNNING,
            RunnerStatus.STARTING,
        ]:
            pid = existing.process_pid
            if pid and cls._is_process_alive(pid):
                raise ValueError(f"Simulation already running: {simulation_id}")
            else:
                # Stale state: process is dead but run_state was not updated
                logger.warning(
                    f"Stale run_state detected for {simulation_id} (pid={pid} is dead), cleaning up"
                )
                existing.runner_status = RunnerStatus.FAILED
                existing.error = "Process died unexpectedly (detected on restart)"
                existing.twitter_running = False
                existing.reddit_running = False
                cls._save_run_state(existing)

        # Load simulation config
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")

        if not os.path.exists(config_path):
            raise ValueError(
                f"Simulation config does not exist, please call /prepare endpoint first"
            )

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Initialize running state
        time_config = config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        total_rounds = int(total_hours * 60 / minutes_per_round)

        # If max_rounds specified, truncate
        if max_rounds is not None and max_rounds > 0:
            original_rounds = total_rounds
            total_rounds = min(total_rounds, max_rounds)
            if total_rounds < original_rounds:
                logger.info(
                    f"Rounds truncated: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})"
                )

        state = SimulationRunState(
            simulation_id=simulation_id,
            runner_status=RunnerStatus.STARTING,
            total_rounds=total_rounds,
            total_simulation_hours=total_hours,
            started_at=datetime.now().isoformat(),
            startup_platform=platform,
            startup_max_rounds=max_rounds,
            startup_enable_graph_memory_update=enable_graph_memory_update,
            startup_graph_id=graph_id,
        )

        cls._save_run_state(state)

        # If graph memory update enabled, create updater
        if enable_graph_memory_update:
            if not graph_id:
                raise ValueError(
                    "Must provide graph_id when enabling graph memory update"
                )

            try:
                ZepGraphMemoryManager.create_updater(simulation_id, graph_id)
                cls._graph_memory_enabled[simulation_id] = True
                logger.info(
                    f"Graph memory update enabled: simulation_id={simulation_id}, graph_id={graph_id}"
                )
            except Exception as e:
                logger.error(f"Failed to create graph memory updater: {e}")
                cls._graph_memory_enabled[simulation_id] = False
        else:
            cls._graph_memory_enabled[simulation_id] = False

        # Determine which script to run (scripts in backend/scripts/ directory)
        if platform == "twitter":
            script_name = "run_twitter_simulation.py"
            state.twitter_running = True
        elif platform == "reddit":
            script_name = "run_reddit_simulation.py"
            state.reddit_running = True
        else:
            script_name = "run_parallel_simulation.py"
            state.twitter_running = True
            state.reddit_running = True

        script_path = os.path.join(cls.SCRIPTS_DIR, script_name)

        if not os.path.exists(script_path):
            raise ValueError(f"Script doesn't exist: {script_path}")

        # Create action queue
        action_queue = Queue()
        cls._action_queues[simulation_id] = action_queue

        # Start simulationProcess
        try:
            # Build run command, use full path
            # New log structure:
            #   twitter/actions.jsonl - Twitter Actionlog
            #   reddit/actions.jsonl  - Reddit Actionlog
            #   simulation.log        - Main process log

            cmd = [
                sys.executable,  # Python interpreter
                script_path,
                "--config",
                config_path,  # Use full config file path
            ]

            # If max_rounds specified, add to command line args
            if max_rounds is not None and max_rounds > 0:
                cmd.extend(["--max-rounds", str(max_rounds)])

            # Create main log file to avoid stdout/stderr pipe buffer full causing process block
            main_log_path = os.path.join(sim_dir, "simulation.log")
            main_log_file = open(main_log_path, "w", encoding="utf-8")

            # Set subprocess environment, ensure UTF-8 encoding on Windows
            # This fixes third-party libraries (like OASIS) not specifying encoding when reading files
            env = os.environ.copy()
            env["PYTHONUTF8"] = (
                "1"  # Python 3.7+ Support,LetAll open() Default use UTF-8
            )
            env["PYTHONIOENCODING"] = "utf-8"  # Ensure stdout/stderr Use UTF-8

            # Set working directory to simulation directory (database etc files generated here)
            # Use start_new_session=True Create newProcess group,Ensure can via os.killpg terminateAllSubprocess
            process = subprocess.Popen(
                cmd,
                cwd=sim_dir,
                stdout=main_log_file,
                stderr=subprocess.STDOUT,  # stderr also write to sameFile
                text=True,
                encoding="utf-8",  # explicitSpecifyEncoding
                bufsize=1,
                env=env,  # pass with UTF-8 Set environment variables
                start_new_session=True,  # Create new process group, ensure server shutdown can terminate all related processes
            )

            # Save file handle for later closing
            cls._stdout_files[simulation_id] = main_log_file
            cls._stderr_files[simulation_id] = None  # No longer need separate stderr

            state.process_pid = process.pid
            state.runner_status = RunnerStatus.RUNNING
            cls._processes[simulation_id] = process
            cls._save_run_state(state)

            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=cls._monitor_simulation, args=(simulation_id,), daemon=True
            )
            monitor_thread.start()
            cls._monitor_threads[simulation_id] = monitor_thread

            logger.info(
                f"Simulation started successfully: {simulation_id}, pid={process.pid}, platform={platform}"
            )

        except Exception as e:
            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            cls._save_run_state(state)
            raise

        return state

    @classmethod
    def _monitor_simulation(cls, simulation_id: str):
        """Monitor simulation process, parse action logs"""
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)

        # New log structure:Platform-specific action logs
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")

        process = cls._processes.get(simulation_id)
        state = cls.get_run_state(simulation_id)

        if not process or not state:
            return

        twitter_position = 0
        reddit_position = 0

        try:
            while process.poll() is None:  # Process still running
                # Read Twitter Actionlog
                if os.path.exists(twitter_actions_log):
                    twitter_position = cls._read_action_log(
                        twitter_actions_log, twitter_position, state, "twitter"
                    )

                # Read Reddit Actionlog
                if os.path.exists(reddit_actions_log):
                    reddit_position = cls._read_action_log(
                        reddit_actions_log, reddit_position, state, "reddit"
                    )

                # Update status
                cls._save_run_state(state)
                time.sleep(2)

            # Process endedafter,Read logs one more time
            if os.path.exists(twitter_actions_log):
                cls._read_action_log(
                    twitter_actions_log, twitter_position, state, "twitter"
                )
            if os.path.exists(reddit_actions_log):
                cls._read_action_log(
                    reddit_actions_log, reddit_position, state, "reddit"
                )

            # Process ended
            exit_code = process.returncode

            if exit_code == 0:
                state.runner_status = RunnerStatus.COMPLETED
                state.completed_at = datetime.now().isoformat()
                state.twitter_running = False
                state.reddit_running = False
                logger.info(f"Simulation completed: {simulation_id}")
                cls._save_run_state(state)
            else:
                # Read last error from log
                main_log_path = os.path.join(sim_dir, "simulation.log")
                error_info = ""
                try:
                    if os.path.exists(main_log_path):
                        with open(main_log_path, "r", encoding="utf-8") as f:
                            error_info = f.read()[-2000:]
                except Exception:
                    pass

                # Auto-resume watchdog
                if state.auto_resume_count < state.auto_resume_max:
                    state.auto_resume_count += 1
                    logger.warning(
                        f"Simulation crashed (exit_code={exit_code}), "
                        f"auto-resuming ({state.auto_resume_count}/{state.auto_resume_max}): {simulation_id}"
                    )
                    state.runner_status = RunnerStatus.STARTING
                    state.twitter_running = False
                    state.reddit_running = False
                    cls._save_run_state(state)
                    try:
                        cls._relaunch_simulation(simulation_id, state)
                        return  # New monitor thread takes over
                    except Exception as relaunch_err:
                        logger.error(f"Auto-resume failed: {simulation_id}, error={relaunch_err}")
                        state.runner_status = RunnerStatus.FAILED
                        state.error = f"Auto-resume failed after crash (exit_code={exit_code}): {relaunch_err}"
                        cls._save_run_state(state)
                else:
                    state.runner_status = RunnerStatus.FAILED
                    state.error = f"Process exit code: {exit_code}, max auto-resumes ({state.auto_resume_max}) reached. Error: {error_info}"
                    state.twitter_running = False
                    state.reddit_running = False
                    logger.error(f"Simulation failed permanently: {simulation_id}, error={state.error}")
                    cls._save_run_state(state)

        except Exception as e:
            logger.error(
                f"Monitoring thread exception: {simulation_id}, error={str(e)}"
            )
            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            cls._save_run_state(state)

        finally:
            # Stop graph memory updater
            if cls._graph_memory_enabled.get(simulation_id, False):
                try:
                    ZepGraphMemoryManager.stop_updater(simulation_id)
                    logger.info(
                        f"Graph memory update stopped: simulation_id={simulation_id}"
                    )
                except Exception as e:
                    logger.error(f"Stop graph memory updaterFailed: {e}")
                cls._graph_memory_enabled.pop(simulation_id, None)

            # Clean process resources
            cls._processes.pop(simulation_id, None)
            cls._action_queues.pop(simulation_id, None)

            # Close log file handle
            if simulation_id in cls._stdout_files:
                try:
                    cls._stdout_files[simulation_id].close()
                except Exception:
                    pass
                cls._stdout_files.pop(simulation_id, None)
            if simulation_id in cls._stderr_files and cls._stderr_files[simulation_id]:
                try:
                    cls._stderr_files[simulation_id].close()
                except Exception:
                    pass
                cls._stderr_files.pop(simulation_id, None)

    @classmethod
    def _relaunch_simulation(cls, simulation_id: str, state: SimulationRunState):
        """Re-launch simulation process after a crash (used by auto-resume watchdog)"""
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")

        platform = state.startup_platform
        if platform == "twitter":
            script_name = "run_twitter_simulation.py"
            state.twitter_running = True
            state.reddit_running = False
        elif platform == "reddit":
            script_name = "run_reddit_simulation.py"
            state.twitter_running = False
            state.reddit_running = True
        else:
            script_name = "run_parallel_simulation.py"
            state.twitter_running = True
            state.reddit_running = True

        script_path = os.path.join(cls.SCRIPTS_DIR, script_name)
        if not os.path.exists(script_path):
            raise ValueError(f"Script not found: {script_path}")

        cmd = [sys.executable, script_path, "--config", config_path]
        if state.startup_max_rounds:
            cmd.extend(["--max-rounds", str(state.startup_max_rounds)])

        # Append to existing log so crash history is preserved
        main_log_path = os.path.join(sim_dir, "simulation.log")
        main_log_file = open(main_log_path, "a", encoding="utf-8")
        main_log_file.write(
            f"\n\n--- AUTO-RESUME attempt {state.auto_resume_count} at {datetime.now().isoformat()} ---\n\n"
        )

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        process = subprocess.Popen(
            cmd,
            cwd=sim_dir,
            stdout=main_log_file,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
            start_new_session=True,
        )

        cls._stdout_files[simulation_id] = main_log_file
        cls._stderr_files[simulation_id] = None
        cls._processes[simulation_id] = process

        state.process_pid = process.pid
        state.runner_status = RunnerStatus.RUNNING
        state.twitter_completed = False
        state.reddit_completed = False
        cls._save_run_state(state)

        action_queue = Queue()
        cls._action_queues[simulation_id] = action_queue

        monitor_thread = threading.Thread(
            target=cls._monitor_simulation, args=(simulation_id,), daemon=True
        )
        monitor_thread.start()
        cls._monitor_threads[simulation_id] = monitor_thread

        logger.info(
            f"Auto-resume launched: {simulation_id}, pid={process.pid}, "
            f"attempt={state.auto_resume_count}/{state.auto_resume_max}"
        )

    @classmethod
    def _read_action_log(
        cls, log_path: str, position: int, state: SimulationRunState, platform: str
    ) -> int:
        """
        Read action log file

        Args:
            log_path: logFilepath
            position: Last read position
            state: Running state object
            platform: Platform name (twitter/reddit)

        Returns:
            New read position
        """
        # Check if graph memory update enabled
        graph_memory_enabled = cls._graph_memory_enabled.get(state.simulation_id, False)
        graph_updater = None
        if graph_memory_enabled:
            graph_updater = ZepGraphMemoryManager.get_updater(state.simulation_id)

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                f.seek(position)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            action_data = json.loads(line)

                            # Process event type entries
                            if "event_type" in action_data:
                                event_type = action_data.get("event_type")

                                # Detect simulation_end event, mark platform completed
                                if event_type == "simulation_end":
                                    if platform == "twitter":
                                        state.twitter_completed = True
                                        state.twitter_running = False
                                        logger.info(
                                            f"Twitter simulation completed: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}"
                                        )
                                    elif platform == "reddit":
                                        state.reddit_completed = True
                                        state.reddit_running = False
                                        logger.info(
                                            f"Reddit simulation completed: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}"
                                        )

                                    # Check if all enabled platforms completed
                                    # If only running one platform, only check that platform
                                    # If running both platforms, need both to complete
                                    all_completed = cls._check_all_platforms_completed(
                                        state
                                    )
                                    if all_completed:
                                        state.runner_status = RunnerStatus.COMPLETED
                                        state.completed_at = datetime.now().isoformat()
                                        logger.info(
                                            f"All platforms simulation completed: {state.simulation_id}"
                                        )

                                # Update round info (from round_end event)
                                elif event_type == "round_end":
                                    round_num = action_data.get("round", 0)
                                    simulated_hours = action_data.get(
                                        "simulated_hours", 0
                                    )

                                    # Update independent round and time for each platform
                                    if platform == "twitter":
                                        if round_num > state.twitter_current_round:
                                            state.twitter_current_round = round_num
                                        state.twitter_simulated_hours = simulated_hours
                                    elif platform == "reddit":
                                        if round_num > state.reddit_current_round:
                                            state.reddit_current_round = round_num
                                        state.reddit_simulated_hours = simulated_hours

                                    # Overall round takes max of both platforms
                                    if round_num > state.current_round:
                                        state.current_round = round_num
                                    # Overall time takes max of both platforms
                                    state.simulated_hours = max(
                                        state.twitter_simulated_hours,
                                        state.reddit_simulated_hours,
                                    )

                                continue

                            action = AgentAction(
                                round_num=action_data.get("round", 0),
                                timestamp=action_data.get(
                                    "timestamp", datetime.now().isoformat()
                                ),
                                platform=platform,
                                agent_id=action_data.get("agent_id", 0),
                                agent_name=action_data.get("agent_name", ""),
                                action_type=action_data.get("action_type", ""),
                                action_args=action_data.get("action_args", {}),
                                result=action_data.get("result"),
                                success=action_data.get("success", True),
                            )
                            state.add_action(action)

                            # Update round
                            if (
                                action.round_num
                                and action.round_num > state.current_round
                            ):
                                state.current_round = action.round_num

                            # If graph memory update enabled, send activity to Zep
                            if graph_updater:
                                graph_updater.add_activity_from_dict(
                                    action_data, platform
                                )

                        except json.JSONDecodeError:
                            pass
                return f.tell()
        except Exception as e:
            logger.warning(f"Failed to read action log: {log_path}, error={e}")
            return position

    @classmethod
    def _check_all_platforms_completed(cls, state: SimulationRunState) -> bool:
        """
        Check if all enabled platforms completed simulation

        Check if platform enabled by checking if corresponding actions.jsonl exists

        Returns:
            True If all enabled platforms completed
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        twitter_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_log = os.path.join(sim_dir, "reddit", "actions.jsonl")

        # check whichPlatformenabled(Check by whether file exists)
        twitter_enabled = os.path.exists(twitter_log)
        reddit_enabled = os.path.exists(reddit_log)

        # If platform enabled but not completed, return False
        if twitter_enabled and not state.twitter_completed:
            return False
        if reddit_enabled and not state.reddit_completed:
            return False

        # At least one platform enabled and completed
        return twitter_enabled or reddit_enabled

    @classmethod
    def _terminate_process(
        cls, process: subprocess.Popen, simulation_id: str, timeout: int = 10
    ):
        """
        Cross-platform terminate process and its children

        Args:
            process: Process to terminate
            simulation_id: Simulation ID (for logging)
            timeout: Timeout to wait for process exit (seconds)
        """
        if IS_WINDOWS:
            # Windows: Use taskkill Command to terminate process tree
            # /F = Force terminate, /T = Terminate processtree(includeSubprocess)
            logger.info(
                f"Terminate process tree (Windows): simulation={simulation_id}, pid={process.pid}"
            )
            try:
                # Try graceful termination first
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T"],
                    capture_output=True,
                    timeout=5,
                )
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Force terminate
                    logger.warning(
                        f"Process not responding, force terminate: {simulation_id}"
                    )
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(process.pid), "/T"],
                        capture_output=True,
                        timeout=5,
                    )
                    process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"taskkill Failed,Try terminate: {e}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        else:
            # Unix: UseProcess groupterminate
            # Because used start_new_session=True,Process group ID Equals main process PID
            pgid = os.getpgid(process.pid)
            logger.info(
                f"Terminate process group (Unix): simulation={simulation_id}, pgid={pgid}"
            )

            # First send SIGTERM to entire process group
            os.killpg(pgid, signal.SIGTERM)

            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Such asIf timeoutWhenafternot ended yet,forceSend SIGKILL
                logger.warning(
                    f"Process group not responding to SIGTERM, force terminate: {simulation_id}"
                )
                os.killpg(pgid, signal.SIGKILL)
                process.wait(timeout=5)

    @classmethod
    def stop_simulation(cls, simulation_id: str) -> SimulationRunState:
        """Stop simulation"""
        state = cls.get_run_state(simulation_id)
        if not state:
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        if state.runner_status not in [RunnerStatus.RUNNING, RunnerStatus.PAUSED]:
            raise ValueError(
                f"Simulation not running: {simulation_id}, status={state.runner_status}"
            )

        state.runner_status = RunnerStatus.STOPPING
        cls._save_run_state(state)

        # Terminate process
        process = cls._processes.get(simulation_id)
        if process and process.poll() is None:
            try:
                cls._terminate_process(process, simulation_id)
            except ProcessLookupError:
                # ProcessalreadyalreadynotexistIn
                pass
            except Exception as e:
                logger.error(
                    f"Failed to terminate process group: {simulation_id}, error={e}"
                )
                # Fallback to direct process termination
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    process.kill()

        state.runner_status = RunnerStatus.STOPPED
        state.twitter_running = False
        state.reddit_running = False
        state.completed_at = datetime.now().isoformat()
        cls._save_run_state(state)

        # Stop graph memory updater
        if cls._graph_memory_enabled.get(simulation_id, False):
            try:
                ZepGraphMemoryManager.stop_updater(simulation_id)
                logger.info(
                    f"Graph memory update stopped: simulation_id={simulation_id}"
                )
            except Exception as e:
                logger.error(f"Stop graph memory updaterFailed: {e}")
            cls._graph_memory_enabled.pop(simulation_id, None)

        logger.info(f"Simulation stopped: {simulation_id}")
        return state

    @classmethod
    def _read_actions_from_file(
        cls,
        file_path: str,
        default_platform: Optional[str] = None,
        platform_filter: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None,
    ) -> List[AgentAction]:
        """
        Read actions from single action file

        Args:
            file_path: Action log file path
            default_platform: Default platform (used when action record has no platform field)
            platform_filter: Filter platform
            agent_id: Filter Agent ID
            round_num: Filter rounds
        """
        if not os.path.exists(file_path):
            return []

        actions = []

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)

                    # Skip non-action records (like simulation_start, round_start, round_end etc events)
                    if "event_type" in data:
                        continue

                    # Skip records without agent_id (non-Agent actions)
                    if "agent_id" not in data:
                        continue

                    # Get platform: prioritize record's platform, otherwise use default platform
                    record_platform = data.get("platform") or default_platform or ""

                    # Filter
                    if platform_filter and record_platform != platform_filter:
                        continue
                    if agent_id is not None and data.get("agent_id") != agent_id:
                        continue
                    if round_num is not None and data.get("round") != round_num:
                        continue

                    actions.append(
                        AgentAction(
                            round_num=data.get("round", 0),
                            timestamp=data.get("timestamp", ""),
                            platform=record_platform,
                            agent_id=data.get("agent_id", 0),
                            agent_name=data.get("agent_name", ""),
                            action_type=data.get("action_type", ""),
                            action_args=data.get("action_args", {}),
                            result=data.get("result"),
                            success=data.get("success", True),
                        )
                    )

                except json.JSONDecodeError:
                    continue

        return actions

    @classmethod
    def get_all_actions(
        cls,
        simulation_id: str,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None,
    ) -> List[AgentAction]:
        """
        Get complete action history for all platforms (no pagination limit)

        Args:
            simulation_id: Simulation ID
            platform: Filter platform(twitter/reddit)
            agent_id: Filter Agent
            round_num: Filter rounds

        Returns:
            completeActionList(byTimestampsort,newInbefore)
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        actions = []

        # Read Twitter ActionFile(Automatically set platform to twitter based on file path)
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        if not platform or platform == "twitter":
            actions.extend(
                cls._read_actions_from_file(
                    twitter_actions_log,
                    default_platform="twitter",  # Auto-fill platform field
                    platform_filter=platform,
                    agent_id=agent_id,
                    round_num=round_num,
                )
            )

        # Read Reddit ActionFile(Automatically set platform to reddit based on file path)
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        if not platform or platform == "reddit":
            actions.extend(
                cls._read_actions_from_file(
                    reddit_actions_log,
                    default_platform="reddit",  # Auto-fill platform field
                    platform_filter=platform,
                    agent_id=agent_id,
                    round_num=round_num,
                )
            )

        # If platform-specific files don't exist, try reading old single file format
        if not actions:
            actions_log = os.path.join(sim_dir, "actions.jsonl")
            actions = cls._read_actions_from_file(
                actions_log,
                default_platform=None,  # Old format files should have platform field
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num,
            )

        # byTimestampsort(newInbefore)
        actions.sort(key=lambda x: x.timestamp, reverse=True)

        return actions

    @classmethod
    def get_actions(
        cls,
        simulation_id: str,
        limit: int = 100,
        offset: int = 0,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None,
    ) -> List[AgentAction]:
        """
        Get action history (with pagination)

        Args:
            simulation_id: Simulation ID
            limit: Return count limit
            offset: Offset
            platform: Filter platform
            agent_id: Filter Agent
            round_num: Filter rounds

        Returns:
            ActionList
        """
        actions = cls.get_all_actions(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num,
        )

        # Pagination
        return actions[offset : offset + limit]

    @classmethod
    def get_timeline(
        cls, simulation_id: str, start_round: int = 0, end_round: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get simulation timeline (aggregated by round)

        Args:
            simulation_id: Simulation ID
            start_round: Start round
            end_round: End round

        Returns:
            Summary info per round
        """
        actions = cls.get_actions(simulation_id, limit=10000)

        # Group by round
        rounds: Dict[int, Dict[str, Any]] = {}

        for action in actions:
            round_num = action.round_num

            if round_num < start_round:
                continue
            if end_round is not None and round_num > end_round:
                continue

            if round_num not in rounds:
                rounds[round_num] = {
                    "round_num": round_num,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "active_agents": set(),
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }

            r = rounds[round_num]

            if action.platform == "twitter":
                r["twitter_actions"] += 1
            else:
                r["reddit_actions"] += 1

            r["active_agents"].add(action.agent_id)
            r["action_types"][action.action_type] = (
                r["action_types"].get(action.action_type, 0) + 1
            )
            r["last_action_time"] = action.timestamp

        # Convert to list
        result = []
        for round_num in sorted(rounds.keys()):
            r = rounds[round_num]
            result.append(
                {
                    "round_num": round_num,
                    "twitter_actions": r["twitter_actions"],
                    "reddit_actions": r["reddit_actions"],
                    "total_actions": r["twitter_actions"] + r["reddit_actions"],
                    "active_agents_count": len(r["active_agents"]),
                    "active_agents": list(r["active_agents"]),
                    "action_types": r["action_types"],
                    "first_action_time": r["first_action_time"],
                    "last_action_time": r["last_action_time"],
                }
            )

        return result

    @classmethod
    def get_agent_stats(cls, simulation_id: str) -> List[Dict[str, Any]]:
        """
        Get statistics for each Agent

        Returns:
            Agent stats list
        """
        actions = cls.get_actions(simulation_id, limit=10000)

        agent_stats: Dict[int, Dict[str, Any]] = {}

        for action in actions:
            agent_id = action.agent_id

            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": action.agent_name,
                    "total_actions": 0,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }

            stats = agent_stats[agent_id]
            stats["total_actions"] += 1

            if action.platform == "twitter":
                stats["twitter_actions"] += 1
            else:
                stats["reddit_actions"] += 1

            stats["action_types"][action.action_type] = (
                stats["action_types"].get(action.action_type, 0) + 1
            )
            stats["last_action_time"] = action.timestamp

        # Sort by total action count
        result = sorted(
            agent_stats.values(), key=lambda x: x["total_actions"], reverse=True
        )

        return result

    @classmethod
    def cleanup_simulation_logs(cls, simulation_id: str) -> Dict[str, Any]:
        """
        Clean simulation running logs (for forced restart simulation)

        Will delete following files:
        - run_state.json
        - twitter/actions.jsonl
        - reddit/actions.jsonl
        - simulation.log
        - stdout.log / stderr.log
        - twitter_simulation.db(Simulation database)
        - reddit_simulation.db(Simulation database)
        - env_status.json(Environment status)

        Note: will not delete config files (simulation_config.json) and profile files

        Args:
            simulation_id: Simulation ID

        Returns:
            Cleanup result info
        """
        import shutil

        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)

        if not os.path.exists(sim_dir):
            return {
                "success": True,
                "message": "Simulation directory doesn't exist, no need to clean",
            }

        cleaned_files = []
        errors = []

        # Files to delete (including database files)
        files_to_delete = [
            "run_state.json",
            "simulation.log",
            "stdout.log",
            "stderr.log",
            "twitter_simulation.db",  # Twitter platform database
            "reddit_simulation.db",  # Reddit platform database
            "env_status.json",  # Environment status file
        ]

        # need toDeleteDirectoryList(Contains action logs)
        dirs_to_clean = ["twitter", "reddit"]

        # DeleteFile
        for filename in files_to_delete:
            file_path = os.path.join(sim_dir, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    cleaned_files.append(filename)
                except Exception as e:
                    errors.append(f"Delete {filename} Failed: {str(e)}")

        # Clean platform directory action logs
        for dir_name in dirs_to_clean:
            dir_path = os.path.join(sim_dir, dir_name)
            if os.path.exists(dir_path):
                actions_file = os.path.join(dir_path, "actions.jsonl")
                if os.path.exists(actions_file):
                    try:
                        os.remove(actions_file)
                        cleaned_files.append(f"{dir_name}/actions.jsonl")
                    except Exception as e:
                        errors.append(
                            f"Delete {dir_name}/actions.jsonl Failed: {str(e)}"
                        )

        # cleanRunning state in memory
        if simulation_id in cls._run_states:
            del cls._run_states[simulation_id]

        logger.info(
            f"Simulation logs cleaned: {simulation_id}, DeleteFile: {cleaned_files}"
        )

        return {
            "success": len(errors) == 0,
            "cleaned_files": cleaned_files,
            "errors": errors if errors else None,
        }

    # Flag to prevent duplicate cleanup
    _cleanup_done = False

    @classmethod
    def cleanup_all_simulations(cls):
        """
        Clean all running simulation processes

        Called on server shutdown, ensure all child processes terminated
        """
        # Prevent duplicate cleanup
        if cls._cleanup_done:
            return
        cls._cleanup_done = True

        # Check if there's content to clean (avoid empty processes printing useless logs)
        has_processes = bool(cls._processes)
        has_updaters = bool(cls._graph_memory_enabled)

        if not has_processes and not has_updaters:
            return  # No content to clean, silently return

        logger.info("Cleaning all simulation processes...")

        # First stop all graph memory updaters (stop_all will print logs internally)
        try:
            ZepGraphMemoryManager.stop_all()
        except Exception as e:
            logger.error(f"Stop graph memory updaterFailed: {e}")
        cls._graph_memory_enabled.clear()

        # Copy dict to avoid modification during iteration
        processes = list(cls._processes.items())

        for simulation_id, process in processes:
            try:
                if process.poll() is None:  # Process still running
                    logger.info(
                        f"Terminate simulation process: {simulation_id}, pid={process.pid}"
                    )

                    try:
                        # Use cross-platform process termination method
                        cls._terminate_process(process, simulation_id, timeout=5)
                    except (ProcessLookupError, OSError):
                        # Process may not exist, try direct termination
                        try:
                            process.terminate()
                            process.wait(timeout=3)
                        except Exception:
                            process.kill()

                    # Update run_state.json
                    state = cls.get_run_state(simulation_id)
                    if state:
                        state.runner_status = RunnerStatus.STOPPED
                        state.twitter_running = False
                        state.reddit_running = False
                        state.completed_at = datetime.now().isoformat()
                        state.error = "Server shutdown, simulation terminated"
                        cls._save_run_state(state)

                    # Update simultaneously state.json,set statusIs stopped
                    try:
                        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
                        state_file = os.path.join(sim_dir, "state.json")
                        logger.info(f"Try to update state.json: {state_file}")
                        if os.path.exists(state_file):
                            with open(state_file, "r", encoding="utf-8") as f:
                                state_data = json.load(f)
                            state_data["status"] = "stopped"
                            state_data["updated_at"] = datetime.now().isoformat()
                            with open(state_file, "w", encoding="utf-8") as f:
                                json.dump(state_data, f, indent=2, ensure_ascii=False)
                            logger.info(
                                f"Updated state.json status to stopped: {simulation_id}"
                            )
                        else:
                            logger.warning(f"state.json doesn't exist: {state_file}")
                    except Exception as state_err:
                        logger.warning(
                            f"Failed to update state.json: {simulation_id}, error={state_err}"
                        )

            except Exception as e:
                logger.error(f"Failed to clean process: {simulation_id}, error={e}")

        # Clean file handles
        for simulation_id, file_handle in list(cls._stdout_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stdout_files.clear()

        for simulation_id, file_handle in list(cls._stderr_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stderr_files.clear()

        # Clean state in memory
        cls._processes.clear()
        cls._action_queues.clear()

        logger.info("SimulationProcesscleancomplete")

    @classmethod
    def register_cleanup(cls):
        """
        Register cleanup function

        In Flask Called on application start,Ensure cleanup all simulation processes on server shutdown
        """
        global _cleanup_registered

        if _cleanup_registered:
            return

        # Flask debug mode, only register in reloader subprocess (process actually running application)
        # WERKZEUG_RUN_MAIN=true represents reloader subprocess
        # If not debug mode, then no this environment variable, also need to register
        is_reloader_process = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
        is_debug_mode = (
            os.environ.get("FLASK_DEBUG") == "1"
            or os.environ.get("WERKZEUG_RUN_MAIN") is not None
        )

        # In debug mode, only register in reloader subprocess; non-debug always register in mode
        if is_debug_mode and not is_reloader_process:
            _cleanup_registered = True  # Mark registered, prevent subprocess again try
            return

        # Keep existing original signal handler
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)
        # SIGHUP Only in Unix SystemexistIn(macOS/Linux),Windows No
        original_sighup = None
        has_sighup = hasattr(signal, "SIGHUP")
        if has_sighup:
            original_sighup = signal.getsignal(signal.SIGHUP)

        def cleanup_handler(signum=None, frame=None):
            """Signal handler:FirstcleanSimulationProcess,Then call originalHandler"""
            # onlyhasInhasProcessneedneed tocleanWhenonly printlog
            if cls._processes or cls._graph_memory_enabled:
                logger.info(f"Received signal {signum},Start cleaning...")
            cls.cleanup_all_simulations()

            # Call original signal handler, let Flask normal exit
            try:
                if signum == signal.SIGINT and callable(original_sigint):
                    original_sigint(signum, frame)
                elif signum == signal.SIGTERM and callable(original_sigterm):
                    original_sigterm(signum, frame)
                elif has_sighup and signum == signal.SIGHUP:
                    # SIGHUP: Terminal closedWhenSend
                    if callable(original_sighup):
                        original_sighup(signum, frame)
                    else:
                        # default behaviorIs:Normal exit
                        sys.exit(0)
                else:
                    # Such asIf originalHandlernotcallable(Such as SIG_DFL),thenUsedefault behaviorIs
                    sys.exit(0)
            except KeyboardInterrupt:
                # Ignore expected KeyboardInterrupt
                pass
            except SystemExit:
                # werkzeug llama sys.exit(0) en su handler de SIGTERM, lo que lanza SystemExit.
                # Usamos os._exit() para salir inmediatamente sin pasar por atexit,
                # evitando el conflicto con logging.shutdown.
                os._exit(0)

        # Register atexit Handler(actionIsbackup)
        atexit.register(cls.cleanup_all_simulations)

        # Register signal handler(OnlyInmain threadin)
        try:
            # SIGTERM: kill Command default signal
            signal.signal(signal.SIGTERM, cleanup_handler)
            # SIGINT: Ctrl+C
            signal.signal(signal.SIGINT, cleanup_handler)
            # SIGHUP: Terminal closed(Only Unix System)
            if has_sighup:
                signal.signal(signal.SIGHUP, cleanup_handler)
        except ValueError:
            # Not in main thread, can only use atexit
            logger.warning(
                "Cannot register signal handler (not in main thread), only use atexit"
            )

        _cleanup_registered = True

    @classmethod
    def get_running_simulations(cls) -> List[str]:
        """
        GetAllingInrunningSimulation IDList
        """
        running = []
        for sim_id, process in cls._processes.items():
            if process.poll() is None:
                running.append(sim_id)
        return running

    # ============== Interview Feature ==============

    @classmethod
    def check_env_alive(cls, simulation_id: str) -> bool:
        """
        Check if simulation environment exists and is alive (can receive interview command)

        Args:
            simulation_id: Simulation ID

        Returns:
            True represents environment alive, False represents environment closed
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return False

        ipc_client = SimulationIPCClient(sim_dir)
        return ipc_client.check_env_alive()

    @classmethod
    def interview_agents_batch_simulated(
        cls,
        simulation_id: str,
        interviews: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        LLM-based fallback interview when the simulation environment is not running.

        Loads agent profiles from disk and uses the LLM to generate a simulated
        response that reflects the agent's persona, memories, and background.

        Args:
            simulation_id: Simulation ID (used to locate profile files)
            interviews: List of {"agent_id": int, "prompt": str}

        Returns:
            Same shape as SimulationRunner.interview_agents_batch:
            {
                "success": True,
                "simulated": True,
                "interviews_count": N,
                "result": {
                    "interviews_count": N,
                    "results": {
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit", "simulated": True},
                        ...
                    }
                }
            }
        """
        import csv
        from ..utils.llm_client import LLMClient

        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)

        # ── Load agent profiles ──────────────────────────────────────────────
        profiles: List[Dict[str, Any]] = []

        reddit_path = os.path.join(sim_dir, "reddit_profiles.json")
        twitter_path = os.path.join(sim_dir, "twitter_profiles.csv")

        if os.path.exists(reddit_path):
            try:
                with open(reddit_path, "r", encoding="utf-8") as f:
                    profiles = json.load(f)
                logger.info(
                    f"[SimulatedInterview] Loaded {len(profiles)} profiles from reddit_profiles.json"
                )
            except Exception as e:
                logger.warning(
                    f"[SimulatedInterview] Failed to read reddit_profiles.json: {e}"
                )

        if not profiles and os.path.exists(twitter_path):
            try:
                with open(twitter_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        profiles.append(
                            {
                                "realname": row.get("name", ""),
                                "username": row.get("username", ""),
                                "bio": row.get("description", ""),
                                "persona": row.get("user_char", ""),
                                "profession": "Unknown",
                            }
                        )
                logger.info(
                    f"[SimulatedInterview] Loaded {len(profiles)} profiles from twitter_profiles.csv"
                )
            except Exception as e:
                logger.warning(
                    f"[SimulatedInterview] Failed to read twitter_profiles.csv: {e}"
                )

        # ── Run LLM inference per agent ──────────────────────────────────────
        llm = LLMClient()
        results: Dict[str, Any] = {}

        for item in interviews:
            agent_id = item.get("agent_id", 0)
            prompt = item.get("prompt", "")

            # Fetch this agent's profile
            profile: Dict[str, Any] = {}
            if 0 <= agent_id < len(profiles):
                profile = profiles[agent_id]

            name = (
                profile.get("realname")
                or profile.get("username")
                or f"Agent_{agent_id}"
            )
            bio = profile.get("bio") or profile.get("description") or ""
            persona = profile.get("persona") or profile.get("user_char") or ""
            profession = profile.get("profession") or ""
            age = profile.get("age") or ""
            location = profile.get("location") or profile.get("country") or ""

            profile_parts = []
            if profession:
                profile_parts.append(f"Profession: {profession}")
            if age:
                profile_parts.append(f"Age: {age}")
            if location:
                profile_parts.append(f"Location: {location}")
            if bio:
                profile_parts.append(f"Bio: {bio}")
            if persona:
                profile_parts.append(f"Persona: {persona}")
            profile_text = (
                "\n".join(profile_parts) if profile_parts else "(No profile available)"
            )

            system_msg = (
                f"You are roleplaying as {name}, a simulation agent with the following profile:\n"
                f"{profile_text}\n\n"
                "Answer the following question in first person, in natural language, "
                "as this character would - based on their background, experiences, and personality. "
                "Be specific and concrete. Do not use headers or JSON. "
                "Answer in the same language as the question."
            )

            try:
                logger.info(
                    f"[SimulatedInterview] Generating LLM response for agent {agent_id} ({name})"
                )
                response_text = llm.chat(
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.8,
                    max_tokens=800,
                )
            except Exception as e:
                logger.error(
                    f"[SimulatedInterview] LLM call failed for agent {agent_id}: {e}"
                )
                response_text = f"(Simulated response unavailable: {e})"

            key = f"reddit_{agent_id}"
            results[key] = {
                "agent_id": agent_id,
                "response": response_text,
                "platform": "reddit",
                "simulated": True,
            }

        return {
            "success": True,
            "simulated": True,
            "interviews_count": len(interviews),
            "result": {
                "interviews_count": len(results),
                "results": results,
            },
        }

    @classmethod
    def get_env_status_detail(cls, simulation_id: str) -> Dict[str, Any]:
        """
        Get detailed simulation environment status info

        Args:
            simulation_id: Simulation ID

        Returns:
            Status detail dict,Contains status, twitter_available, reddit_available, timestamp
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        status_file = os.path.join(sim_dir, "env_status.json")

        default_status = {
            "status": "stopped",
            "twitter_available": False,
            "reddit_available": False,
            "timestamp": None,
        }

        if not os.path.exists(status_file):
            return default_status

        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status = json.load(f)
            return {
                "status": status.get("status", "stopped"),
                "twitter_available": status.get("twitter_available", False),
                "reddit_available": status.get("reddit_available", False),
                "timestamp": status.get("timestamp"),
            }
        except (json.JSONDecodeError, OSError):
            return default_status

    @classmethod
    def interview_agent(
        cls,
        simulation_id: str,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """
        Interview singleAgent

        Args:
            simulation_id: Simulation ID
            agent_id: Agent ID
            prompt: Interview question
            platform: SpecifyPlatform(optional)
                - "twitter": Only interviewTwitterPlatform
                - "reddit": Only interviewRedditPlatform
                - None: dualPlatformSimulationWhenInterview both platforms simultaneously,Return integrated result
            timeout: timeoutWhenWhenbetween(seconds)

        Returns:
            Interview result dict

        Raises:
            ValueError: Simulation does not existor environment notrunning
            TimeoutError: Wait response timeout
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(
                f"Simulation environment not running or closed,Cannot executeInterview: {simulation_id}"
            )

        logger.info(
            f"SendInterviewCommand: simulation_id={simulation_id}, agent_id={agent_id}, platform={platform}"
        )

        response = ipc_client.send_interview(
            agent_id=agent_id, prompt=prompt, platform=platform, timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "agent_id": agent_id,
                "prompt": prompt,
                "result": response.result,
                "timestamp": response.timestamp,
            }
        else:
            return {
                "success": False,
                "agent_id": agent_id,
                "prompt": prompt,
                "error": response.error,
                "timestamp": response.timestamp,
            }

    @classmethod
    def interview_agents_batch(
        cls,
        simulation_id: str,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0,
    ) -> Dict[str, Any]:
        """
        Batch interview multipleAgent

        Args:
            simulation_id: Simulation ID
            interviews: interviewList,each elementContains {"agent_id": int, "prompt": str, "platform": str(optional)}
            platform: defaultPlatform(optional,Will be by each interview itemplatformOverride)
                - "twitter": defaultOnly interviewTwitterPlatform
                - "reddit": defaultOnly interviewRedditPlatform
                - None: dualPlatformSimulationWheneachAgentInterview both platforms simultaneously
            timeout: timeoutWhenWhenbetween(seconds)

        Returns:
            batchInterview result dict

        Raises:
            ValueError: Simulation does not existor environment notrunning
            TimeoutError: Wait response timeout
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(
                f"Simulation environment not running or closed,Cannot executeInterview: {simulation_id}"
            )

        logger.info(
            f"SendbatchInterviewCommand: simulation_id={simulation_id}, count={len(interviews)}, platform={platform}"
        )

        response = ipc_client.send_batch_interview(
            interviews=interviews, platform=platform, timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "interviews_count": len(interviews),
                "result": response.result,
                "timestamp": response.timestamp,
            }
        else:
            return {
                "success": False,
                "interviews_count": len(interviews),
                "error": response.error,
                "timestamp": response.timestamp,
            }

    @classmethod
    def interview_all_agents(
        cls,
        simulation_id: str,
        prompt: str,
        platform: str = None,
        timeout: float = 180.0,
    ) -> Dict[str, Any]:
        """
        Interview allAgent(Global interview)

        Use same question to interview all in simulationAgent

        Args:
            simulation_id: Simulation ID
            prompt: Interview question(AllAgentUsesame question)
            platform: SpecifyPlatform(optional)
                - "twitter": Only interviewTwitterPlatform
                - "reddit": Only interviewRedditPlatform
                - None: dualPlatformSimulationWheneachAgentInterview both platforms simultaneously
            timeout: timeoutWhenWhenbetween(seconds)

        Returns:
            globalInterview result dict
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        # FromconfigFileGetAllAgentInfo
        config_path = os.path.join(sim_dir, "simulation_config.json")
        if not os.path.exists(config_path):
            raise ValueError(f"Simulation config does not exist: {simulation_id}")

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        agent_configs = config.get("agent_configs", [])
        if not agent_configs:
            raise ValueError(f"No in simulation configAgent: {simulation_id}")

        # buildbatchinterviewList
        interviews = []
        for agent_config in agent_configs:
            agent_id = agent_config.get("agent_id")
            if agent_id is not None:
                interviews.append({"agent_id": agent_id, "prompt": prompt})

        logger.info(
            f"Send globalInterviewCommand: simulation_id={simulation_id}, agent_count={len(interviews)}, platform={platform}"
        )

        return cls.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=interviews,
            platform=platform,
            timeout=timeout,
        )

    @classmethod
    def close_simulation_env(
        cls, simulation_id: str, timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Close simulation environment(butnotisStop simulationProcess)

        toSimulationSend shutdown environment command,make it exit gracefully from waitingCommandMode

        Args:
            simulation_id: Simulation ID
            timeout: timeoutWhenWhenbetween(seconds)

        Returns:
            Operation result dict
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            return {"success": True, "message": "Environment already closed"}

        logger.info(f"Send shutdown environment command: simulation_id={simulation_id}")

        try:
            response = ipc_client.send_close_env(timeout=timeout)

            return {
                "success": response.status.value == "completed",
                "message": "environmentcloseCommandalreadySend",
                "result": response.result,
                "timestamp": response.timestamp,
            }
        except TimeoutError:
            # Timeout may be because environment is closing
            return {
                "success": True,
                "message": "environmentcloseCommandalreadySend(Wait response timeout,Environment may beInclose)",
            }

    @classmethod
    def _get_interview_history_from_db(
        cls,
        db_path: str,
        platform_name: str,
        agent_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get from single databaseInterviewHistory"""
        import sqlite3

        if not os.path.exists(db_path):
            return []

        results = []

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            if agent_id is not None:
                cursor.execute(
                    """
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview' AND user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (agent_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview'
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )

            for user_id, info_json, created_at in cursor.fetchall():
                try:
                    info = json.loads(info_json) if info_json else {}
                except json.JSONDecodeError:
                    info = {"raw": info_json}

                results.append(
                    {
                        "agent_id": user_id,
                        "response": info.get("response", info),
                        "prompt": info.get("prompt", ""),
                        "timestamp": created_at,
                        "platform": platform_name,
                    }
                )

            conn.close()

        except Exception as e:
            logger.error(f"ReadInterviewHistory failed ({platform_name}): {e}")

        return results

    @classmethod
    def get_interview_history(
        cls,
        simulation_id: str,
        platform: str = None,
        agent_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        GetInterviewHistory(FromdatabaseRead)

        Args:
            simulation_id: Simulation ID
            platform: Platform type(reddit/twitter/None)
                - "reddit": onlyGetRedditPlatformHistory
                - "twitter": onlyGetTwitterPlatformHistory
                - None: Get all history of both platforms
            agent_id: SpecifyAgent ID(optional,onlyGetthisAgentHistory)
            limit: eachPlatformReturn count limit

        Returns:
            InterviewHistory record list
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)

        results = []

        # determineneed toqueryPlatform
        if platform in ("reddit", "twitter"):
            platforms = [platform]
        else:
            # If not specifiedplatformWhen,query bothPlatform
            platforms = ["twitter", "reddit"]

        for p in platforms:
            db_path = os.path.join(sim_dir, f"{p}_simulation.db")
            platform_results = cls._get_interview_history_from_db(
                db_path=db_path, platform_name=p, agent_id=agent_id, limit=limit
            )
            results.extend(platform_results)

        # Sort by time descending
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Such asIf querying multiplePlatform,Limit total
        if len(platforms) > 1 and len(results) > limit:
            results = results[:limit]

        return results
