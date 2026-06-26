from pydantic import BaseModel,Field
from prompt import planner_prompt
from typing import TypedDict, Literal, Annotated,Optional
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt,Command 
from langgraph.prebuilt import ToolNode,tools_condition
from agenti_main import llm
from tools import all_tools
from langgraph.checkpoint.memory import InMemorySaver
from prompt import *
# memeory 
import operator
# tool bindinding 
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
    merging_data : str 
    safety_flags: Literal['needs_human','execute']
    tool_results: list[dict]
    verification: Literal["success","failure"]
    reflection: str
    status: Literal['planning','running','review','done','failed']
class task_queuesss(BaseModel):
    task_type = Literal["research","coding"]
    description : str =Field(...,description="write the task which you want to perform")

pyadntic_output = llm.with_structured_output(task_queuesss)

def intent_analyzer(state: AgentState):
    response = llm.invoke(intent_analyzer(state['user_request']))
    result =  response.content
    return {"intent": result}
def context_builder(state: AgentState):
     pass
def planner(state: AgentState):
    response = llm.invoke(planner_prompt(state['intent'],state['user_request']))
    result =  response.content
    return {"plan": result} 
def task_dispatcher(state: AgentState):
    response = pyadntic_output.invoke(task_dispatcher_prompt(state['plan'],state['intent'],state['user_request']))
    result = response.content
    return {"task_queue": result.description,"current_task":result.task_type} 
def research(state: AgentState):
    response = llm.invoke(resercher_prompt(state["task_queue"]))
    result = response.content
    return {"research_results": result}
     
def coding(state: AgentState):
    response = llm.invoke(Coding_prompt(state["task_queue"]))
    result = response.content
    return {"code_changes": result}
def mergin_content(state:AgentState):
    context = {}
    if state['research_results']:
        context['research_results'] = state['research_results']
    if state['code_changes']:
        context['code_changes'] = state['code_changes']

    response = llm.invoke(mergin_content(context))
    result = response.content
    return {"merging_data": result}

def safety_check(state: AgentState):
    """Evaluates the merged execution context and decides if human approval is needed.
    Returns safety_flags: 'execute' (safe) or 'needs_human' (risky)."""
    response = llm.invoke(safty_check_prompt(state['merging_data']))
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
    response = llm.invoke(tool_executor_prompt(state['safety_flags']))
    return {'tool_results':response.content}
def verification(state: AgentState):
     response = llm.invoke(verifcation_prompt(state['tool_results']))
     return {"verification":response.content}
def error_analyzer(state: AgentState):
     response = llm.invoke(error_analysis_prompt(state['verification']))
     return {"error_analysis":response.content}
def review(state: AgentState):
    response = llm.invoke(review_prompt(state['verification']))
    result = response.content
    return {"review":result} 
def reflection(state: AgentState):
    context = {}
    if state['review']:
        context['review'] = state['review']
    if state['error_analysis']:
        context['error_analysis'] = state['error_analysis']
    response = llm.invoke(reflection_prompt(context))
    result = response.content
    return {"reflection":result}
      
def final_response(state: AgentState):
    response = llm.invoke(final_prompt(state['reflection']))
    result = response.content

    return {"status":result}
     
# conditional 
def route_task(state):
    t = state['current_task']
    return 'research' if t['type'] == 'research' else 'coding'

def route_safety(state):
    """Routes based on safety_flags set by the safety_check node."""
    return 'human' if state['safety_flags'] == 'needs_human' else 'execute'

def route_verification(state):
    return 'review' if state['verification']=="success" else 'error_analyzer'

def route_reflection(state):
    if state['status'] == 'failed' and state.get('retry_local'):
        return 'coding'        # minor fix, retry in place
    if state['status'] == 'failed':
        return 'planner'       # fundamental issue, re-plan
    if state['task_queue']:
        return 'task_queue'    # more work to do
    return 'final_response'    # done


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
g.add_edge('human', 'execute') 
g.add_conditional_edges('execute',tools_condition)
g.add_edge('tool_node', 'execute')
g.add_edge('execute', 'verify')
# verify branch
g.add_conditional_edges('verify', route_verification,
    {'review': 'review', 'error_analyzer': 'error_analyzer'})
g.add_edge('error_analyzer', 'reflect')
g.add_edge('review', 'reflect')

# reflection loop
g.add_conditional_edges('reflect', route_reflection,
    {'coding': 'coding', 'planner': 'planner',
     'task_queue': 'task_queue', 'final_response': 'final'})
g.add_edge('final', END)
memory = InMemorySaver()   
config = {"configurable": {"thread_id": "user-123"}}
workflow = g.compile(checkpointer=memory)

inputs = {"user_request": "write a code to add two numbers"}
for output in workflow.stream(inputs, config=config, stream_mode="values"):
    print(output)