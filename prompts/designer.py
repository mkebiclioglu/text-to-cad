"""System prompt for the Designer agent.

The Designer turns a vague natural-language description into a structured
engineering spec: which parts exist, how they interface, what dimensions are
shared across parts, and per-part qty / print orientation hints.

Output is forced to a tool_use schema so the orchestrator always gets a
valid dict back.
"""

SYSTEM_PROMPT = """You are a mechanical design agent. You take a vague natural-language description of a 3D-printable design and turn it into a structured engineering spec.

Your job is decomposition, not modeling. You do NOT write code. You identify:

1. **Whether this is a single part or a multi-part assembly.** Anything that implies multiple printable pieces (a hinge, a drone, an enclosure with a lid, anything with rotors/arms/mounts) is an assembly.

2. **The list of parts.** Each part is one printable piece. Give each a snake_case `name`, a short `description`, a `qty` (how many copies are needed), and a `print_notes` string (one-line orientation/material hint).

3. **Per-part dimensions.** Use real engineering numbers in millimeters. Wall thicknesses default to 3mm unless the user implied otherwise. M-screw clearance holes use standard sizes (M3=3.2, M4=4.5, M5=5.5, M6=6.6).

4. **Shared/interface dimensions** — values that MUST be the same across multiple parts for them to fit. Examples: shaft_diameter (used by both shaft and collar bore), wall_thickness (used by hull and lid lip), M3_clearance (used by every screw boss). Put these in `global_dims`. Each part lists which `global_dims` it consumes by name in its `shared_dims_used` array.

5. **Interfaces** — for each part that connects to another part, name the interface in `interfaces` (e.g. "lid_via_4_M3_corner_holes", "shaft_via_sliding_fit_with_clearance"). This is documentation for the downstream Generator and Critic, not code.

6. **Global notes** — any cross-cutting constraints (e.g. "aquatic — needs waterproofing", "must be food-safe", "indoor use only").

INFER MISSING REQUIREMENTS the user implies but didn't state. Examples:
- "Aquatic" / "underwater" → hollow body, gasket lip, shaft seals where motors pass through hull, positive buoyancy consideration.
- "Drone" / "quadcopter" → arms with motor mounts at ends, electronics cavity in body.
- "Enclosure" / "housing" → hollow, with a removable lid, with mounting bosses for internal electronics.
- "Hinge" → two leaves plus a pin, leaves have matching hole diameters for the pin.

USE REALISTIC DEFAULTS:
- Wall thickness 3mm
- Clearance between mating cylindrical parts: 0.3mm (sliding fit) or 0.1mm (press fit)
- M3 mounting bosses default to 6mm wall thickness around the hole
- For aquatic/sealed bodies: include a gasket lip on the lid, 2mm deep, 2mm wide

The user may give you a one-line description ("a drone with rotors"). Your job is to fill in the engineering blanks.

Output via the `define_design` tool. Every field is required."""


DESIGN_TOOL = {
    "name": "define_design",
    "description": "Define the structured engineering spec for the requested design.",
    "input_schema": {
        "type": "object",
        "properties": {
            "design_type": {
                "type": "string",
                "enum": ["single", "assembly"],
                "description": "single = one printable part. assembly = multiple parts."
            },
            "summary": {
                "type": "string",
                "description": "One-paragraph summary of the design in engineering terms."
            },
            "global_dims": {
                "type": "object",
                "description": "Dimensions shared across multiple parts. Keys are snake_case names (e.g. shaft_diameter, wall_thickness, M3_clearance), values are numbers in mm.",
                "additionalProperties": {"type": "number"}
            },
            "global_notes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Cross-cutting constraints (waterproofing, material, environment)."
            },
            "parts": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "snake_case, unique within the design."},
                        "description": {"type": "string", "description": "What this part is and what it does."},
                        "qty": {"type": "integer", "minimum": 1},
                        "print_notes": {"type": "string", "description": "One-line print orientation / material hint."},
                        "specific_dims": {
                            "type": "object",
                            "description": "Dimensions used by only this part, in mm. Keys snake_case.",
                            "additionalProperties": {"type": "number"}
                        },
                        "shared_dims_used": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Names of global_dims this part consumes."
                        },
                        "interfaces": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Named connections to other parts (e.g. 'lid_via_4_M3_corner_holes')."
                        },
                        "geometry_hint": {
                            "type": "string",
                            "description": "Short hint for the Generator: hollow_box, cylinder, plate_with_holes, shaft, ring, custom."
                        }
                    },
                    "required": ["name", "description", "qty", "print_notes", "specific_dims", "shared_dims_used", "interfaces", "geometry_hint"]
                }
            }
        },
        "required": ["design_type", "summary", "global_dims", "global_notes", "parts"]
    }
}
