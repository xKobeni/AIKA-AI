from enum import Enum

class Action(Enum):
    
    CHAT = "chat"
    
    STORE_MEMORY = "store_memory"
    
    LIST_MEMORIES = "list_memories"
    
    SEARCH_MEMORY = "search_memory"
    
    DELETE_MEMORY = "delete_memory"
    
    USE_TOOL = "use_tool"
    NEW_SESSION = "new_session"
    LIST_SESSIONS = "list_sessions"
    RESUME_SESSION = "resume_session"
    DELETE_SESSION = "delete_session"
    CLEAR_CONVERSATION = "clear_conversation"
    
    PLAN_EXECUTION = "plan_execution"
    CONFIGURE = "configure"
    
    DELEGATE = "delegate"
    ORCHESTRATE = "orchestrate"