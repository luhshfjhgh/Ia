# ModelRegistry
# Registry of available LLM models
# NOX_AI - placeholder

class ModelRegistry:
    """Registry of available LLM models"""
    
    def __init__(self):
        self.name = "ModelRegistry"
    
    async def run(self, task: dict) -> dict:
        raise NotImplementedError("Implement ModelRegistry.run()")
