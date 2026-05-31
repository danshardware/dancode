---
name: new_agent
description: This helps you build a new agent for The Council. 
---

<!-- Tip: Use /create-prompt in chat to generate content with agent assistance -->

You will help to build an agent for The Council, which is this project. The Council is a multi-agent system that uses YAML to define agents. Documentation is in the `docs/` directory, specifically, `docs/how-to-create-agents.md`. Agent definitions are in `agents/*.yaml` and flows are defined in `flows/*.yaml`. 

Consider all user input before writing anything and ensure you go back and forth with the user to clarify requirements and constraints. Once you understand what you are building, generate the necessary YAML files for the agent definition and its main flow. Ensure the user tests the agent and validates the operation before considering the task done.