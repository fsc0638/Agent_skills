---
name: mcp-python-executor
provider: mcp
version: 1.0.0
runtime_requirements: []
description: >
  Powerful Python execution tool. MANDATORY: Do not just provide code in text; always use this tool to actually execute the code when the user requests a calculation, verification, or script run. 
  The LLM (Brain) must provide raw Python code. Use this as your primary way to interact with the system logic.
parameters:
  type: object
  properties:
    code:
      type: string
      description: The full Python code to execute. Use print() to see output.
  required: [code]
---

# MCP Python Executor

## Description
This skill acts as a direct link between the LLM's reasoning and actual execution.
The LLM can write a script to solve the user's problem, and this tool will run it.

## How to use
- **code (string)**: The full Python code to execute.
  - Use `print()` to output results – they will be returned to the LLM.
  - Access to standard libraries is allowed.
