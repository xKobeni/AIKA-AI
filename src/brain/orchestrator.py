import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from brain.shared_context import SharedContext
from brain.agent_message import AgentMessage

logger = logging.getLogger(__name__)

TEAM_DONE_MARKER = "[TEAM_DONE]"
MAX_TEAM_TURNS = 10


class Orchestrator:

    def __init__(self, agent_registry, agent_loop, llm=None, max_workers=4):
        self.agent_registry = agent_registry
        self.agent_loop = agent_loop
        self.llm = llm
        self.max_workers = max_workers
        self._active_teams = {}

    def delegate(self, from_agent_id, task, target_agent_id, shared_context=None):
        if shared_context is None:
            shared_context = SharedContext()

        target_profile = self.agent_registry.get(target_agent_id)
        if not target_profile:
            return f"Agent '{target_agent_id}' not found."

        shared_context.set("task", task, agent_id=from_agent_id)
        shared_context.set("delegated_by", from_agent_id, agent_id=from_agent_id)

        logger.info("Delegation: %s -> %s | task=%s", from_agent_id, target_agent_id, task[:50])

        result = self.agent_loop.run(task, agent_id=target_agent_id)

        shared_context.set("result", result, agent_id=target_agent_id)

        message = AgentMessage.result(
            from_agent=target_agent_id,
            to_agent=from_agent_id,
            result_data=result
        )

        return result

    def run_chain(self, agent_ids, initial_input, shared_context=None):
        if shared_context is None:
            shared_context = SharedContext()

        shared_context.set("task", initial_input, agent_id="orchestrator")
        current_input = initial_input
        results = []

        logger.info("Chain started: %s | task=%s", " -> ".join(agent_ids), initial_input[:50])

        for i, agent_id in enumerate(agent_ids):
            profile = self.agent_registry.get(agent_id)
            if not profile:
                results.append({"agent": agent_id, "error": f"Agent '{agent_id}' not found."})
                continue

            logger.info("Chain step %d/%d: %s", i + 1, len(agent_ids), agent_id)

            result = self.agent_loop.run(current_input, agent_id=agent_id)

            shared_context.set(f"chain_step_{i}", result, agent_id=agent_id)
            shared_context.set("last_result", result, agent_id=agent_id)

            results.append({"agent": agent_id, "result": result})

            current_input = f"Previous result from {agent_id}:\n{result}\n\nContinue with the next step."

        final_result = results[-1]["result"] if results and "result" in results[-1] else ""
        shared_context.set("chain_result", final_result, agent_id="orchestrator")

        logger.info("Chain completed: %d steps", len(results))

        return final_result

    def run_parallel(self, agent_ids, input_task, shared_context=None):
        if shared_context is None:
            shared_context = SharedContext()

        shared_context.set("task", input_task, agent_id="orchestrator")

        logger.info("Parallel started: %s | task=%s", ", ".join(agent_ids), input_task[:50])

        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_agent = {
                executor.submit(self.agent_loop.run, input_task, agent_id=agent_id): agent_id
                for agent_id in agent_ids
                if self.agent_registry.get(agent_id)
            }

            for future in as_completed(future_to_agent):
                agent_id = future_to_agent[future]
                try:
                    result = future.result()
                    results[agent_id] = result
                    shared_context.set(f"parallel_{agent_id}", result, agent_id=agent_id)
                except Exception as e:
                    results[agent_id] = f"Error: {e}"
                    logger.warning("Parallel agent %s failed: %s", agent_id, e)

        logger.info("Parallel completed: %d agents", len(results))

        return results

    def run_team(self, agent_ids, task, shared_context=None, max_turns=MAX_TEAM_TURNS):
        if shared_context is None:
            shared_context = SharedContext()

        shared_context.set("task", task, agent_id="orchestrator")
        shared_context.set("team_agents", agent_ids, agent_id="orchestrator")
        shared_context.set("turn", 0, agent_id="orchestrator")

        team_id = f"team_{datetime.now().strftime('%H%M%S')}"
        self._active_teams[team_id] = {
            "agents": agent_ids,
            "task": task,
            "status": "running",
            "turns": 0
        }

        logger.info("Team started: %s | task=%s | max_turns=%d",
                     ", ".join(agent_ids), task[:50], max_turns)

        turn = 0
        contributions = []
        team_done = False

        while turn < max_turns and not team_done:
            shared_context.set("turn", turn, agent_id="orchestrator")

            for agent_id in agent_ids:
                profile = self.agent_registry.get(agent_id)
                if not profile:
                    continue

                team_context = self._build_team_context(
                    agent_id, agent_ids, task, contributions, turn, shared_context
                )

                result = self.agent_loop.run(team_context, agent_id=agent_id)

                contribution = {
                    "agent": agent_id,
                    "turn": turn,
                    "result": result
                }
                contributions.append(contribution)
                shared_context.set(f"turn_{turn}_{agent_id}", result, agent_id=agent_id)

                if TEAM_DONE_MARKER in str(result):
                    team_done = True
                    break

            turn += 1

        final_result = self._assemble_team_result(contributions, shared_context)
        shared_context.set("team_result", final_result, agent_id="orchestrator")

        self._active_teams[team_id]["status"] = "completed"
        self._active_teams[team_id]["turns"] = turn

        logger.info("Team completed: %d turns, %d contributions", turn, len(contributions))

        return final_result

    def _build_team_context(self, current_agent, all_agents, task, contributions, turn, shared_context):
        parts = [
            f"You are part of a team working on: {task}",
            f"Team members: {', '.join(all_agents)}",
            f"Current turn: {turn + 1}",
            "",
            "Your role is to contribute to this task based on your expertise.",
            "Read the shared context for previous contributions from other agents.",
            "When the task is fully complete, end your response with [TEAM_DONE].",
            "",
            "Previous contributions:"
        ]

        if contributions:
            for c in contributions[-5:]:
                parts.append(f"  [{c['agent']}]: {c['result'][:200]}")
        else:
            parts.append("  (No contributions yet - you're starting!)")

        parts.append("")
        parts.append("Your contribution:")

        return "\n".join(parts)

    def _assemble_team_result(self, contributions, shared_context):
        if not contributions:
            return "Team produced no contributions."

        parts = []
        for c in contributions:
            parts.append(f"[{c['agent']}]: {c['result']}")

        return "\n\n".join(parts)

    def get_team_status(self, team_id=None):
        if team_id:
            return self._active_teams.get(team_id)
        return dict(self._active_teams)
