from pyfiglet import Figlet
from rich.align import Align
from rich.panel import Panel

def header():
    # Use the font and text you specified
    fig = Figlet(font="ansi_shadow")
    title = f"[bold bright_cyan]{fig.renderText('Raman AGENT')}[/bold bright_cyan]"
    
    # Just center the big text perfectly
    content = Align.center(title )
    
    return Panel(content, border_style="cyan",    subtitle = "[dim]Your AI Pair Programmer[/dim]"
)
