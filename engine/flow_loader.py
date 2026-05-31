"""Flow loader — parses a flow YAML file into a runnable PocketFlow Flow."""

from __future__ import annotations

import sys
import os
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pocketflow import Flow, Node
from engine.block import make_block, BaseBlock


class _EndNode(Node):
    """Silent terminal node — has no successors so PocketFlow stops without warning."""
    def prep(self, shared): return None
    def exec(self, prep_res): return None
    def post(self, shared, prep_res, exec_res): return "end"

def load_flow(flow_path: str | Path) -> tuple[Flow, dict, dict[str, BaseBlock]]:
    """
    Load a flow YAML and return (PocketFlow Flow, raw flow_config dict, block_instances dict).

    The YAML must have:
        id:     str
        start:  block_id
        blocks:
            <block_id>:
                type: llm | guardrail | tool_call | checkpoint | human_input
                transitions:
                    <action>: <block_id> | END
                ... (block-type specific fields)

    Transitions mapped to "END" (or absent) cause the flow to terminate naturally.
    """
    path = Path(flow_path)
    with path.open(encoding="utf-8") as fh:
        flow_config: dict = yaml.safe_load(fh)

    blocks_config: dict = flow_config.get("blocks", {})

    # Instantiate all blocks first so we can wire them in a second pass
    block_instances: dict[str, BaseBlock] = {}
    for block_id, block_cfg in blocks_config.items():
        block_instances[block_id] = make_block(block_id, block_cfg)

# Shared silent end sentinel — routes every explicit END transition through it
    # so PocketFlow terminates without emitting a "Flow ends" warning.
    end_sentinel = _EndNode()

    # Wire transitions
    for block_id, block_cfg in blocks_config.items():
        node = block_instances[block_id]
        for action, target in block_cfg.get("transitions", {}).items():
            if not target or target.upper() == "END":
                node.next(end_sentinel, action)  # silent terminal
            else:
                if target not in block_instances:
                    raise ValueError(
                        f"Flow '{flow_config.get('id')}': block '{block_id}' "
                        f"transition '{action}' points to unknown block '{target}'"
                    )
                node.next(block_instances[target], action)

    start_id = flow_config.get("start")
    if start_id not in block_instances:
        raise ValueError(
            f"Flow '{flow_config.get('id')}': start block '{start_id}' not found"
        )

    flow = Flow(start=block_instances[start_id])
    return flow, flow_config, block_instances
