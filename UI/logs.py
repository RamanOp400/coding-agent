from rich.panel import Panel
from rich.text import Text

def logs(ui_state=None):
    text = Text()
    
    if ui_state and ui_state.logs:
        # Show only the last 15 logs to prevent overflowing the panel
        display_logs = ui_state.logs[-15:]
        for msg, style in display_logs:
            text.append(msg, style=style)
    else:
        text.append("Waiting for agent to start...\n", style="dim")

    return Panel(
        text, 
        title="[bold yellow]>_ LIVE LOGS[/bold yellow]", 
        title_align="left", 
        border_style="yellow",
        padding=(1, 2)
    )
