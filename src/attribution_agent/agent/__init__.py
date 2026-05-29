"""The agent layer.

Three jobs, only one genuinely agentic (per the project's honest framing):
    reporting       scheduled: query views -> BoardPackData
    observations    scheduled LLM job: prose commentary on the numbers
    recommendations the actual agent: detect material changes, propose
                    guardrailed budget reallocations for human approval
"""
