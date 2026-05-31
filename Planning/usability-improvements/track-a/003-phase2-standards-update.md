# Task 003 — Strengthen Phase 2 (Jank) + Phase 3 (Refine) with coding standards

**Track A — can run in parallel with 001 and 002**

## Overview

After task 002 wires `coding_standards` into shared state, the Phase 2 and Phase 3
flow prompts need to reference it.

**Phase 2 change**: Add a new "Coding Standards Compliance" section to the audit prompt
that explicitly checks the plan against `{{state.coding_standards}}`.

**Phase 3 change**: Add a brief reminder to verify that the final plan satisfies
the coding standards, referencing `{{state.coding_standards}}`.

## Files Changed

- `flows/phase2_jank.yaml`
- `flows/phase3_refine.yaml`

## Type Contracts

No new functions. YAML-only changes.

## Workflow

### Part 1 — flows/phase2_jank.yaml

1. Open `flows/phase2_jank.yaml`.

2. Find the line:
   ```
         ### Convention Violations
         Check against AGENTS_MD conventions: {{state.agents_md}}
   ```

3. Replace that section with:
   ```yaml
         ### Convention Violations
         Check against AGENTS_MD conventions: {{state.agents_md}}

         ### Coding Standards Compliance
         The following coding standards MUST be satisfied by every plan.
         For each standard below, check every task file and flag any task
         that would produce code violating the standard.

         {{state.coding_standards}}

         For each violation found:
           RISK: Coding Standards
           LOCATION: <file> → <section>
           PROBLEM: which standard is violated and how
           FIX: exact edit to the plan that ensures the coding model will comply
   ```

   The indentation must match the surrounding YAML (8 spaces, since this is inside
   the `system_prompt: |` block of the `audit` block).

### Part 2 — flows/phase3_refine.yaml

1. Open `flows/phase3_refine.yaml`.

2. Find the line that ends the numbered list (the last numbered item before the
   `Start by listing files` instruction):
   ```
         6. Verify that the README.md execution map is still accurate after any additions.
              Update it if needed.
   ```

3. After item 6, add a new item 7:
   ```yaml
         7. Cross-check the completed plan against the coding standards below.
            For any task whose "Workflow" or "Type Contracts" would produce code that
            violates a standard, add a note in the relevant section.
            Do not rewrite the whole task — a single-sentence note is sufficient.

            Coding standards to enforce:
            {{state.coding_standards}}
   ```

4. Do not alter any transitions, tool lists, or block structure. Only the system_prompt
   text changes.

## Acceptance Criteria

```bash
# Verify the new placeholders are present in both files
grep -c "coding_standards" flows/phase2_jank.yaml
# Expected: 1

grep -c "coding_standards" flows/phase3_refine.yaml
# Expected: 1
```

```python
# Verify YAML still parses cleanly
import yaml
with open("flows/phase2_jank.yaml") as f:
    data = yaml.safe_load(f)
assert data["id"] == "phase2_jank"

with open("flows/phase3_refine.yaml") as f:
    data = yaml.safe_load(f)
assert data["id"] == "phase3_refine"
```

## Testing Plan

File: `tests/unit/test_flow_yaml_validity.py` (create if absent)

```python
def test_phase2_jank_yaml_valid():
    """flows/phase2_jank.yaml parses as valid YAML and contains coding_standards ref."""
    import yaml
    from pathlib import Path
    text = (Path(__file__).parent.parent.parent / "flows" / "phase2_jank.yaml").read_text()
    data = yaml.safe_load(text)
    assert data["id"] == "phase2_jank"
    assert "coding_standards" in text


def test_phase3_refine_yaml_valid():
    """flows/phase3_refine.yaml parses as valid YAML and contains coding_standards ref."""
    import yaml
    from pathlib import Path
    text = (Path(__file__).parent.parent.parent / "flows" / "phase3_refine.yaml").read_text()
    data = yaml.safe_load(text)
    assert data["id"] == "phase3_refine"
    assert "coding_standards" in text
```
