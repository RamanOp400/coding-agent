from pydantic import BaseModel, Field
from typing import TypedDict, Literal, Annotated, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.types import interrupt, Command 
from langgraph.prebuilt import ToolNode, tools_condition
from agenti_main import llm
from tools import all_tools
from langgraph.checkpoint.memory import InMemorySaver
from prompt import *
# memory 
import operator
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def format_prompt(template: str, **kwargs) -> str:
    result = template
    for k, v in kwargs.items():
        result = result.replace(f"{{{k}}}", str(v))
    return result

# tool binding 
llm_invoke_tool = llm.bind_tools(all_tools)

class AgentState(TypedDict):
    user_request: str
    intent: dict                 # parsed goal, constraints, success criteria
    context: dict                # memory, repo facts, conventions
    plan: list[dict]             # ordered steps
    task_queue: list[dict]       # pending tasks
    current_task: Literal['research','coding']
    research_results: Annotated[Optional[list], operator.add] 
    code_changes: Optional[list[dict]] 
    merging_data: str 
    safety_flags: Literal['needs_human','execute']
    tool_results: list[dict]
    messages: Annotated[list[AnyMessage], add_messages]
    verification: Literal["success","failure"]
    error_analysis: str          # output from error_analyzer node
    review: str                  # output from review node
    reflection: str
    retry_local: Optional[bool]  # flag for local retry in reflection
    status: Literal['planning','running','review','done','failed']

class TaskQueue(BaseModel):
    task_type: Literal["research", "coding"]
    description: str = Field(..., description="write the task which you want to perform")

pydantic_output = llm.with_structured_output(TaskQueue)

def intent_analyzer(state: AgentState):
    response = llm.invoke(format_prompt(intention_analyzer, user_request=state['user_request']))
    result = response.content
    return {"intent": result}

def context_builder(state: AgentState):
     pass

def planner(state: AgentState):
    response = llm.invoke(format_prompt(planner_prompt, intent=state['intent'], context=state['user_request']))
    result = response.content
    return {"plan": result} 

def task_dispatcher(state: AgentState):
    result = pydantic_output.invoke(format_prompt(task_dispatcher_prompt, 
        User_paln=state.get('plan', ''), user_intend=state.get('intent', ''), user_input=state.get('user_request', ''),
        reflection=state.get('reflection', 'None'), task_queue=state.get('task_queue', 'None')))
    return {"task_queue": result.description, "current_task": result.task_type} 

def research(state: AgentState):
    response = llm.invoke(format_prompt(resercher_prompt, 
        intent=state.get('intent', ''), plan=state.get('plan', ''), task=state.get('task_queue', '')))
    result = response.content
    return {"research_results": [result]}  # list because research_results uses operator.add reducer
     
def coding(state: AgentState):
    response = llm.invoke(format_prompt(Coding_prompt, 
        intent=state.get('intent', ''), plan=state.get('plan', ''), task=state.get('task_queue', ''), 
        research=state.get('research_results', '')))
    result = response.content
    return {"code_changes": result}

def mergin_content(state: AgentState):
    context = {}
    if state.get('research_results'):
        context['research_results'] = state['research_results']
    if state.get('code_changes'):
        context['code_changes'] = state['code_changes']

    response = llm.invoke(format_prompt(meriging_agent, context=context))
    result = response.content
    return {"merging_data": result}

def safety_check(state: AgentState):
   
    response = llm.invoke(format_prompt(safty_check_prompt, context=state['merging_data']))
    result = response.content
    return {"safety_flags": result}
    
def human_checkpoint(state: AgentState):
    """Human-in-the-loop checkpoint using LangGraph's interrupt().
    
    Flow:
      1. mergin_content collects research_results + code_changes into one merged context.
      2. safety_check inspects the merged context and sets safety_flags.
      3. route_safety sends execution here ONLY when safety_flags == 'needs_human'.
      4. interrupt() pauses the graph and surfaces the merged context to the human.
      5. The human reviews and resumes with Command(resume="approve") or Command(resume="reject").
      6. This node then uses Command(goto=...) to route to 'execute' or 'planner'.
    """
  
    human_response = interrupt(
        # This value is surfaced to the caller (your app/UI) while the graph is paused
        {
            "question": "Please review the proposed changes before execution.",
            "merged_context": state.get("merging_data", ""),
            "safety_flags": state.get("safety_flags", ""),
        }
    )
    if human_response == "approve":
        return Command(goto="execute")
    else:
        return Command(goto="planner")

def tool_executor(state: AgentState):
    # Retrieve previous tool messages if we are in a tool loop
    msgs = state.get('messages', [])
    sys_msg = format_prompt(tool_executor_prompt, context=state['merging_data'])
    
    if not msgs:
        messages_to_invoke = [("user", sys_msg)]
    else:
        # Re-invoke LLM with the context + tool history
        messages_to_invoke = [("user", sys_msg)] + msgs
        
    response = llm_invoke_tool.invoke(messages_to_invoke)
    
    # Store a string representation for the verify node
    history_str = response.content if response.content else str(response.tool_calls)
    
    return {'messages': [response], 'tool_results': [{'output': history_str}]}

def verification(state: AgentState):
     response = llm.invoke(format_prompt(verifcation_prompt, 
        task=state.get('task_queue', ''), tool_results=state.get('tool_results', '')))
     return {"verification": response.content}

def error_analyzer(state: AgentState):
     response = llm.invoke(format_prompt(error_analysis_prompt, 
        task=state.get('task_queue', ''), tool_results=state.get('tool_results', ''), verification=state.get('verification', '')))
     return {"error_analysis": response.content}

def review(state: AgentState):
    response = llm.invoke(format_prompt(review_prompt, 
        task=state.get('task_queue', ''), code=state.get('merging_data', ''), verification=state.get('verification', '')))
    result = response.content
    return {"review": result} 

def reflection(state: AgentState):
    feedback = state.get('error_analysis') if state.get('verification') == 'failure' else state.get('review')
    response = llm.invoke(format_prompt(reflection_prompt, 
        task=state.get('task_queue', ''), plan=state.get('plan', ''), feedback=feedback))
    result = response.content
    return {"reflection": result}
      
def final_response(state: AgentState):
    response = llm.invoke(format_prompt(final_prompt, context=state['reflection']))
    result = response.content
    return {"status": result}
     
# conditional 
def route_task(state):
    return state['current_task']

def route_safety(state):
    """Routes based on safety_flags set by the safety_check node."""
    return 'human' if state['safety_flags'] == 'needs_human' else 'execute'

def route_verification(state):
    return 'review' if state['verification'] == "success" else 'error_analyzer'

def route_reflection(state):
    status = state.get('status', '').strip().lower()
    if 'retry_task' in status:
        return 'coding'
    if 'replan' in status:
        return 'planner'
    if 'next_task' in status:
        return 'task_queue'
    return 'done'


g = StateGraph(AgentState)

# nodes
g.add_node('intent', intent_analyzer)
g.add_node('context', context_builder)
g.add_node('planner', planner)
g.add_node('task_queue', task_dispatcher)
g.add_node('research', research)
g.add_node('coding', coding)
g.add_node('merge', mergin_content)   # merges research + coding results into one context
g.add_node('safety', safety_check)
g.add_node('human', human_checkpoint)
g.add_node('execute', tool_executor)
tool_node = ToolNode(all_tools)
g.add_node("tool_node", tool_node)
g.add_node('verify', verification)
g.add_node('error_analyzer', error_analyzer)
g.add_node('review', review)
g.add_node('reflect', reflection)
g.add_node('final', final_response)

# linear spine
g.add_edge(START, 'intent')
g.add_edge('intent', 'context')
g.add_edge('context', 'planner')
g.add_edge('planner', 'task_queue')

# task routing
g.add_conditional_edges('task_queue', route_task,
    {'research': 'research', 'coding': 'coding'})
# after research/coding → merge results into unified context → then safety check
g.add_edge('research', 'merge')
g.add_edge('coding', 'merge')
g.add_edge('merge', 'safety')

# safety + execution
g.add_conditional_edges('safety', route_safety,
    {'human': 'human', 'execute': 'execute'})

g.add_conditional_edges('execute', tools_condition,
    {"tools": "tool_node", "__end__": "verify"})
g.add_edge('tool_node', 'execute')

# verify branch
g.add_conditional_edges('verify', route_verification,
    {'review': 'review', 'error_analyzer': 'error_analyzer'})
g.add_edge('error_analyzer', 'reflect')
g.add_edge('review', 'reflect')

# reflection loop
g.add_edge('reflect', 'final')
g.add_conditional_edges('final', route_reflection,
    {'coding': 'coding', 'planner': 'planner',
     'task_queue': 'task_queue', 'done': END})
memory = InMemorySaver()   
config = {"configurable": {"thread_id": "user-123"}}
workflow = g.compile(checkpointer=memory)

inputs = {"user_request": "make a folder named 'quadratic_project' and inside of that folder make a file named 'solver.py', and inside of that file write python code to solve a quadratic equation. Make sure to use tools to create the folder and file."}
for output in workflow.stream(inputs, config=config, stream_mode="values"):
    print(output)