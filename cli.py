# CLI
# Command-line interface for NOX_AI
# NOX_AI - placeholder

class CLI:
    """Command-line interface for NOX_AI"""
    
    def __init__(self):
        self.name = "CLI"
    
    async def run(self, task: dict) -> dict:
        raise NotImplementedError("Implement CLI.run()")
