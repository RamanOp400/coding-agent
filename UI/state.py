class UIState:
    def __init__(self):
        self.logs = []
        self.workflow_nodes = {
            "intent": "pending",
            "planner": "pending",
            "research": "pending",
            "coding": "pending",
            "execute": "pending",
            "verify": "pending",
            "final": "pending"
        }
        self.agent_done = False

    def add_log(self, text, style="white"):
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append((f"[{timestamp}] {text}\n", style))

    def reset(self):
        """Reset state for a new prompt, just like starting fresh."""
        self.logs = []
        self.workflow_nodes = {
            "intent": "pending",
            "planner": "pending",
            "research": "pending",
            "coding": "pending",
            "execute": "pending",
            "verify": "pending",
            "final": "pending"
        }
        self.agent_done = False
