# TODO

## Required

- Phase 1 needs to loop on the planning until everytone agrees on the plan
- Phase 2 needs to have human in the loop
- Fix Phase 4 to be less LLM and more logic based
- Get rid of COUNCIL_DATA_DIR and rename to DANCODE_DATA_DIR which should sub in for the `~/.config/dancode`
- Running status absolutely needs to show what it's doing. a simple extrac olumn that shows the same info as the agent state will be fine.

## Bugs

- Token counts seem to go down. That's not possible. They can only go up. Ensure they are cumulative and showing in/out/cache
- Token counts should update as completion messages come in
- Creating all the council directories on start. 
- EVERY AGENT NEEDS A WAY TO BAIL IF IT GETS CONFUSED - Handled in the workflow block manager, inject a prompt that says "If you are blocked from doing your task and have no ability to rememdy this easily, respond with _YAML-SNIPPET_ to indicate that and tell the user what needs to happen to move forward
- Pause needs a timeout. If the current task takes longer than 10 seconds, it needs to force kill it, and ensure it's in a proper state (remove pending tool calls)

## nice to have

- Prompt caching
- Use the council as a library so I can dev in parallel