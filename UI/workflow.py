from rich.table import Table
from rich.panel import Panel

def workflow(ui_state=None):
    table = Table(expand=True, box=None, padding=(1, 1))
    
    table.add_column("STEP", style="bold purple", justify="center", width=6)
    table.add_column("TASK", style="white")
    table.add_column("STATUS", justify="right")

    if not ui_state:
        from state import UIState
        ui_state = UIState()

    def get_status_ui(status_string):
        if status_string == "completed":
            return "[green]✔ Completed[/green]"
        elif status_string == "in_progress":
            return "[bold bright_cyan]▶ In Progress[/bold bright_cyan]"
        else:
            return "[dim]○ Pending[/dim]"

    table.add_row("1", "Intent Analysis", get_status_ui(ui_state.workflow_nodes.get("intent", "pending")))
    table.add_row("2", "Planning", get_status_ui(ui_state.workflow_nodes.get("planner", "pending")))
    table.add_row("3", "Research", get_status_ui(ui_state.workflow_nodes.get("research", "pending")))
    table.add_row("4", "Generate Code", get_status_ui(ui_state.workflow_nodes.get("coding", "pending")))
    table.add_row("5", "Execute Tools", get_status_ui(ui_state.workflow_nodes.get("execute", "pending")))
    table.add_row("6", "Review & Verify", get_status_ui(ui_state.workflow_nodes.get("verify", "pending")))
    table.add_row("7", "Finalize", get_status_ui(ui_state.workflow_nodes.get("final", "pending")))

    return Panel(
        table, 
        title="[bold purple]⚙ WORKFLOW[/bold purple]", 
        title_align="left", 
        border_style="purple"
    )
