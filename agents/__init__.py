# -*- coding: utf-8 -*-
"""
Atalhos de importação para compatibilidade reversa.
Permite que imports antigos como `from agents.global_memory import gm`
não quebrem mesmo que o arquivo real esteja em outro lugar.
"""
# Re-exports de compatibilidade
try:
    from memory.global_memory import gm
    from exports.project_exporter import export_project, list_exported_projects
    from core.orchestrator import orchestrator
except ImportError:
    pass
