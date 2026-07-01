from rich.layout import Layout
from header import header
from workflow import workflow
from logs import logs

def build_dashboard(ui_state=None):
    layout = Layout()

    # Simple 2-section vertical split: Header on top, Main body below
    layout.split_column(
        Layout(name="header", size=6),
        Layout(name="main")
    )

    # Split the main body left and right
    layout["main"].split_row(
        Layout(name="workflow", ratio=1),
        Layout(name="logs", ratio=1)
    )

    # Assign the 3 components
    layout["header"].update(header())
    layout["workflow"].update(workflow(ui_state))
    layout["logs"].update(logs(ui_state))

    return layout
