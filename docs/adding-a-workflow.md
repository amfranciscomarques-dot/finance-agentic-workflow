# Adding a workflow

A workflow is a LangGraph graph plus a small adapter the registry/CLI understand.
Here's the whole recipe.

## 1. Create the package

```
src/finance_workflow/workflows/my_workflow/
├── __init__.py     # the Workflow subclass
├── state.py        # TypedDict graph state
├── nodes.py        # node functions
├── graph.py        # build_graph()
├── prompts.py      # (if it uses the LLM)
└── schema.py       # (if it uses structured output)
```

## 2. Define the state

```python
# state.py
from typing import Any, TypedDict

class MyState(TypedDict, total=False):
    # inputs
    symbol: str
    use_llm: bool
    # gathered / derived
    data: dict[str, Any]
    result: str
```

> If two parallel nodes write the same key, add a reducer. The simplest design is
> to have each parallel node write a distinct key (see the equity-research graph).

## 3. Write nodes

Each node takes the state and returns a partial update:

```python
# nodes.py
def gather(state: MyState) -> dict:
    return {"data": MyProvider().get(state["symbol"])}

def analyze(state: MyState) -> dict:
    if state.get("use_llm"):
        from ...llm import get_llm
        ...  # call Claude (structured output recommended)
    return {"result": _fallback(state)}  # keep an offline path
```

Keep an offline/deterministic branch so the workflow runs without an API key.

## 4. Build the graph

```python
# graph.py
from langgraph.graph import END, START, StateGraph
from . import nodes
from .state import MyState

def build_graph():
    g = StateGraph(MyState)
    g.add_node("gather", nodes.gather)
    g.add_node("analyze", nodes.analyze)
    g.add_edge(START, "gather")
    g.add_edge("gather", "analyze")
    g.add_edge("analyze", END)
    return g.compile()
```

## 5. Implement the `Workflow` adapter

```python
# __init__.py
from typing import Any
from ...workflow import Workflow
from .graph import build_graph

class MyWorkflow(Workflow):
    name = "my-workflow"
    title = "My Workflow"
    description = "What it does, in one line."

    def build(self): return build_graph()

    def initial_state(self, symbol: str, offline: bool = False, **_: Any) -> dict:
        from ...llm import llm_available
        return {"symbol": symbol.upper(), "use_llm": llm_available() and not offline}

    def result_markdown(self, final_state: dict) -> str:
        return final_state.get("result", "")

    def metadata(self, final_state: dict) -> dict:
        return {"symbol": final_state.get("symbol")}
```

## 6. Register it

```python
# src/finance_workflow/workflows/__init__.py
from .my_workflow import MyWorkflow
registry.register(MyWorkflow())
```

Now it appears in `finwf list` and runs via `finwf run my-workflow --ticker ...`.

## 7. Test it

Add a `tests/test_my_workflow.py` that runs the graph in offline mode and asserts
on the result — mirror `tests/test_equity_research.py`.

## Tips

- **Reuse the data layer.** `MarketDataProvider`, `FundamentalsProvider`,
  `NewsProvider` already handle live+sample fallback.
- **Use structured output** (`with_structured_output(PydanticModel)`) whenever a
  later node needs typed fields.
- **Want a tool-calling agent instead of a DAG?** Bind the tools from
  `tools/langchain_tools.py` to `langgraph.prebuilt.create_react_agent(llm, TOOLS)`
  and wrap that as your `build()`.
