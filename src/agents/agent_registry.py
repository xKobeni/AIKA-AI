import json
import logging
import os
from pathlib import Path

from agents.agent_profile import AgentProfile

logger = logging.getLogger(__name__)

DEFAULT_AGENT_ID = "aika"

PERSONAS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "personas"
)


class AgentRegistry:

    def __init__(self, data_path="data/agents.json"):
        self.agents = {}
        self.data_path = data_path
        self._ensure_default_agent()
        self._load_from_file()

    def _ensure_default_agent(self):
        aika_persona = os.path.join(PERSONAS_DIR, "aika.txt")
        default = AgentProfile(
            id=DEFAULT_AGENT_ID,
            name="AIKA",
            persona_path=aika_persona,
            model=None,
            allowed_tools=None,
            max_iterations=5,
            is_active=True,
            role="coordinator",
            delegates_to=["researcher", "planner", "writer"]
        )
        self.agents[DEFAULT_AGENT_ID] = default

        researcher_persona = os.path.join(PERSONAS_DIR, "researcher.txt")
        if os.path.exists(researcher_persona):
            self.agents["researcher"] = AgentProfile(
                id="researcher",
                name="Researcher",
                persona_path=researcher_persona,
                allowed_tools=["web_search", "web_crawl", "file_read", "file_search"],
                role="specialist",
                delegates_to=[]
            )

        planner_persona = os.path.join(PERSONAS_DIR, "planner.txt")
        if os.path.exists(planner_persona):
            self.agents["planner"] = AgentProfile(
                id="planner",
                name="Planner",
                persona_path=planner_persona,
                allowed_tools=["file_read", "file_search", "file_write"],
                role="specialist",
                delegates_to=[]
            )

        writer_persona = os.path.join(PERSONAS_DIR, "writer.txt")
        if os.path.exists(writer_persona):
            self.agents["writer"] = AgentProfile(
                id="writer",
                name="Writer",
                persona_path=writer_persona,
                allowed_tools=["file_write", "file_read", "file_edit"],
                role="specialist",
                delegates_to=[]
            )

    def _load_from_file(self):
        if not os.path.exists(self.data_path):
            return
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for agent_data in data.get("agents", []):
                profile = AgentProfile.from_dict(agent_data)
                if profile.id not in self.agents:
                    self.agents[profile.id] = profile
                else:
                    existing = self.agents[profile.id]
                    existing.name = profile.name
                    existing.persona_path = profile.persona_path
                    existing.model = profile.model
                    existing.allowed_tools = profile.allowed_tools
                    existing.max_iterations = profile.max_iterations
                    existing.is_active = profile.is_active
            logger.debug("Loaded agents from %s", self.data_path)
        except Exception as e:
            logger.warning("Failed to load agents from %s: %s", self.data_path, e)

    def _save_to_file(self):
        os.makedirs(os.path.dirname(self.data_path) or ".", exist_ok=True)
        data = {
            "agents": [p.to_dict() for p in self.agents.values()]
        }
        try:
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug("Saved agents to %s", self.data_path)
        except Exception as e:
            logger.warning("Failed to save agents to %s: %s", self.data_path, e)

    def register(self, profile):
        self.agents[profile.id] = profile
        self._save_to_file()
        return profile

    def get(self, agent_id):
        return self.agents.get(agent_id)

    def get_all(self):
        return list(self.agents.values())

    def get_active(self):
        return [a for a in self.agents.values() if a.is_active]

    def delete(self, agent_id):
        if agent_id == DEFAULT_AGENT_ID:
            return False
        if agent_id in self.agents:
            del self.agents[agent_id]
            self._save_to_file()
            return True
        return False

    def set_model(self, agent_id, model):
        profile = self.agents.get(agent_id)
        if not profile:
            return False
        profile.model = model
        self._save_to_file()
        return True

    def set_persona(self, agent_id, persona_path):
        profile = self.agents.get(agent_id)
        if not profile:
            return False
        profile.persona_path = persona_path
        self._save_to_file()
        return True

    def create_agent(
        self,
        agent_id,
        name,
        persona_path=None,
        model=None,
        allowed_tools=None,
        max_iterations=5
    ):
        if agent_id in self.agents:
            return None

        profile = AgentProfile(
            id=agent_id,
            name=name,
            persona_path=persona_path,
            model=model,
            allowed_tools=allowed_tools,
            max_iterations=max_iterations,
            is_active=True,
        )
        return self.register(profile)

    def load_personas_from_dir(self, directory=None):
        if directory is None:
            directory = PERSONAS_DIR
        if not os.path.isdir(directory):
            return
        for filename in os.listdir(directory):
            if filename.endswith(".txt"):
                agent_id = filename[:-4]
                persona_path = os.path.join(directory, filename)
                if agent_id not in self.agents:
                    profile = AgentProfile(
                        id=agent_id,
                        name=agent_id.replace("_", " ").title(),
                        persona_path=persona_path,
                    )
                    self.agents[agent_id] = profile
                    logger.debug("Discovered persona agent: %s", agent_id)
