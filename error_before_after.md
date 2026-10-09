BEFORE
- exact question/call: "What is the HRIS snapshot for Ghost Employee?"
- exact tool: hris_get_employee_snapshot
- exact arguments: {"employee_name": "Ghost Employee"}
- actual error/result: RuntimeError: No employee found with name: Ghost Employee
- behavior: the raw MCP stdio tool call failed at the server boundary and bubbled up as an unstructured exception; the Agent was not yet wrapping this failure into a recoverable observation.

AFTER
- exact SAME question/call: "What is the HRIS snapshot for Ghost Employee?"
- exact SAME tool: hris_get_employee_snapshot
- exact SAME arguments: {"employee_name": "Ghost Employee"}
- actual error/result: {'error': 'No employee found with name: Ghost Employee', 'recoverable': True, 'tool': 'hris_get_employee_snapshot', 'arguments': {'employee_name': 'Ghost Employee'}}
- behavior after recovery: the Agent catches the runtime error at the tool boundary, converts it into a structured error observation, and stops safely without fabricated success or a crash.

What changed
- The runtime call path still uses the same MCP tool and same arguments.
- The improvement is only in the Agent boundary: MCP failures are normalized into a structured, recoverable observation instead of escaping as an unhandled exception.
- This preserves the existing Agent loop while making the error explicit, inspectable, and safe to stop on.
