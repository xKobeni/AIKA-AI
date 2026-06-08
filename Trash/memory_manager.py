import json
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path("data/memories.json")
CONVERSATION_FILE = Path("data/conversations.json")

class MemoryManager:

    # -------------------
    # Memories
    # -------------------

    def load_memories(self):

        if not MEMORY_FILE.exists():
            return []

        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_memory(self, content, memory_type="fact"):

        memories = self.load_memories()

        memory_id = len(memories) + 1

        memories.append({
            "id": memory_id,
            "type": memory_type,
            "content": content,
            "created_at": datetime.now().isoformat()
        })

        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memories, f, indent=2)
    
    def delete_memory(self, memory_id):

        memories = self.load_memories()

        memories = [
            m for m in memories
            if m["id"] != memory_id
        ]

        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memories, f, indent=2)

    def search_memory(self, query):

        memories = self.load_memories()

        results = []

        for memory in memories:

            if query.lower() in memory["content"].lower():
                results.append(memory)

        return results

    # -------------------
    # Conversations
    # -------------------

    def load_conversations(self):

        if not CONVERSATION_FILE.exists():
            return []

        with open(CONVERSATION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_conversation(self, role, content):

        conversations = self.load_conversations()

        conversations.append({
            "role": role,
            "content": content
        })

        with open(CONVERSATION_FILE, "w", encoding="utf-8") as f:
            json.dump(conversations, f, indent=2)