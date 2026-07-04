import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SharedContext:

    def __init__(self):
        self._data = {}
        self._agent_results = {}
        self._lock = threading.Lock()

    def set(self, key, value, agent_id=None):
        with self._lock:
            self._data[key] = value
            if agent_id:
                if agent_id not in self._agent_results:
                    self._agent_results[agent_id] = []
                self._agent_results[agent_id].append({
                    "key": key,
                    "value": value,
                    "timestamp": datetime.now().isoformat()
                })
            logger.debug("SharedContext.set: %s = %s (agent=%s)", key, str(value)[:50], agent_id)

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def get_all(self):
        with self._lock:
            return dict(self._data)

    def get_agent_results(self, agent_id):
        with self._lock:
            return list(self._agent_results.get(agent_id, []))

    def clear(self):
        with self._lock:
            self._data.clear()
            self._agent_results.clear()

    def __repr__(self):
        with self._lock:
            return f"SharedContext({len(self._data)} keys, {len(self._agent_results)} agents)"
