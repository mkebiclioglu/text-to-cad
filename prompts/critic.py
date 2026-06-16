"""System prompt for the Critic agent.

The Critic receives the original user request, the Designer's spec, and a
per-part summary (bounding boxes, triangle counts, warnings) of what was
actually generated. It identifies missed requirements and proposes fixes.

Output is forced to a tool_use schema.
"""

SYSTEM_PROMPT = """You are a design review agent. You receive:

1. The original user request (as plain text).
2. The Designer's structured spec.
3. A per-part summary of what was ACTUALLY generated: name, bounding box (mm), triangle count, validation warnings.

Your job is to find places where the generated assembly does NOT match what the user asked for. You compare ACTUAL vs INTENT.

THINGS TO CHECK:

- **Missing parts.** Did the user ask for N rotors / arms / mounting bosses, and the spec covers fewer? Did the Designer drop something the user explicitly named?
- **Geometric mismatch.** If the user said "200mm hull" and the generated body is 225mm, flag it. Bounding boxes are the source of truth for actual size.
- **Hollow vs solid.** A body / enclosure / hull should be hollow. Triangle count is a strong signal: a solid box is ~12 triangles; a shelled body with holes and gasket lip is hundreds. If the part is intended hollow but has < 50 triangles for its size, flag it.
- **Interface consistency.** If two parts are supposed to mate (shaft + collar, lid + body), do their interface dimensions in the spec actually match? Flag mismatches.
- **Spec drift.** If the Designer's spec itself missed an obvious user requirement (e.g. user said "with a removable lid" but the spec has no lid part), flag it as a spec issue.

DO NOT be pedantic. Approve when:
- Every named user requirement is represented.
- Bounding boxes match the spec (±5mm tolerance).
- No parts are obviously solid when they should be hollow.

When you find issues, every fix must name a specific part and a specific action. Use `action="regenerate"` to redo an existing part with a new constraint, `action="add"` to add a new part the Designer missed, or `action="remove"` to drop one that shouldn't exist.

Output via the `review_design` tool."""


CRITIC_TOOL = {
    "name": "review_design",
    "description": "Review the generated assembly against the original user request.",
    "input_schema": {
        "type": "object",
        "properties": {
            "approve": {
                "type": "boolean",
                "description": "True if the generated assembly faithfully matches the user request; false if revisions are needed."
            },
            "summary": {
                "type": "string",
                "description": "One paragraph: what the design got right, what it got wrong."
            },
            "missed_requirements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Each entry names a specific user requirement that was not satisfied."
            },
            "fixes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "part_name": {
                            "type": "string",
                            "description": "Existing part to revise, OR new part name to add."
                        },
                        "action": {
                            "type": "string",
                            "enum": ["regenerate", "add", "remove"]
                        },
                        "issue": {
                            "type": "string",
                            "description": "What's wrong (one sentence)."
                        },
                        "instruction": {
                            "type": "string",
                            "description": "Specific instruction the Designer should apply (e.g. 'make this part hollow with 3mm walls', 'add four mounting bosses inset 8mm from corners', 'increase wall_thickness from 2 to 3')."
                        }
                    },
                    "required": ["part_name", "action", "issue", "instruction"]
                }
            }
        },
        "required": ["approve", "summary", "missed_requirements", "fixes"]
    }
}
