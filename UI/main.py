import warnings
warnings.filterwarnings("ignore")

import sys
import os
import threading
import time
import uuid

# Ensure we can import from the backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".agents_DONTOUCH"))

# Import the backend early so if it wraps sys.stdout, it happens before rich captures it
from graph import workflow

from rich.console import Console
from rich.live import Live

from dashboard import build_dashboard
from state import UIState
from header import header

console = Console()
ui_state = UIState()

def run_agent(user_input, live):
    """Run the LangGraph agent in a background thread, streaming updates to the UI."""
    try:
        # Generate a fresh thread_id for each prompt so the graph starts clean
        thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        
        ui_state.add_log(f"Received: {user_input[:50]}...", style="dim")
        ui_state.add_log("Initializing agent graph...", style="yellow")
        live.update(build_dashboard(ui_state))
        
        inputs = {"user_request": user_input}
        
        for update in workflow.stream(inputs, config=thread_config, stream_mode="updates"):
            for node_name, node_state in update.items():
                ui_state.add_log(f"Completed node: {node_name}", style="bright_cyan")
                
                # Update workflow status based on nodes
                if node_name in ui_state.workflow_nodes:
                    ui_state.workflow_nodes[node_name] = "completed"
                    
                # Mark next steps as in progress
                if node_name == "intent": ui_state.workflow_nodes["planner"] = "in_progress"
                elif node_name == "planner": ui_state.workflow_nodes["research"] = "in_progress"
                elif node_name == "research": ui_state.workflow_nodes["coding"] = "in_progress"
                elif node_name == "coding": ui_state.workflow_nodes["execute"] = "in_progress"
                elif node_name == "execute": ui_state.workflow_nodes["verify"] = "in_progress"
                elif node_name == "verify": ui_state.workflow_nodes["final"] = "in_progress"
                
                live.update(build_dashboard(ui_state))
                
        ui_state.add_log("Workflow finished!", style="bold green")
        live.update(build_dashboard(ui_state))
        
    except Exception as e:
        ui_state.add_log(f"Error: {str(e)}", style="bold red")
        live.update(build_dashboard(ui_state))
    finally:
        ui_state.agent_done = True

def main():
    console.print(header())
    console.print("[dim]Welcome to Raman AGENT. Type your request below.[/dim]")
    console.print("[dim]Type [bold]/exit[/bold] to quit.[/dim]\n")
    
    while True:
        # Prompt for input (normal terminal, no Live screen)
        try:
            user_input = console.input("[bold cyan]> [/bold cyan]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[bold cyan]Goodbye![/bold cyan]")
            break
        
        user_input = user_input.strip()
        
        if not user_input:
            continue
            
        if user_input.lower() in ["/exit", "exit", "quit"]:
            console.print("[bold cyan]Goodbye![/bold cyan]")
            break
        
        # Reset state for a fresh run
        ui_state.reset()
        ui_state.add_log("Starting session...", style="green")
        ui_state.workflow_nodes["intent"] = "in_progress"
        
        # Run the Live dashboard while the agent works in the background
        try:
            with Live(build_dashboard(ui_state), refresh_per_second=10, screen=True) as live:
                agent_thread = threading.Thread(target=run_agent, args=(user_input, live), daemon=True)
                agent_thread.start()
                
                # Wait for the agent to finish (with a 10-minute safety timeout)
                timeout = 600  # 10 minutes max
                elapsed = 0
                while not ui_state.agent_done and elapsed < timeout:
                    time.sleep(0.1)
                    elapsed += 0.1
                
                if elapsed >= timeout:
                    ui_state.add_log("Timeout: Agent exceeded 10 minutes. Stopping.", style="bold red")
                    live.update(build_dashboard(ui_state))
                
                # Keep the dashboard on screen for 3 seconds so the user can read the final logs
                time.sleep(3)
        except KeyboardInterrupt:
            console.print("\n[yellow]Agent interrupted.[/yellow]")
        
        # After Live exits, we are back to the normal terminal
        console.print("[green]Task complete.[/green] Ready for next prompt.\n")

if __name__ == "__main__":
    main()