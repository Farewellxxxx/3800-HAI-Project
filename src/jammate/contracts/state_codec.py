"""JSON Schema for the versioned wire view of the existing JamState."""
from __future__ import annotations

import json
from functools import lru_cache
from jsonschema import Draft202012Validator
from .input_event import _json_values, input_event_schema


def state_schema():
    def obj(properties):
        return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}
    text = {"type": "string", "minLength": 1}
    integer = {"type": "integer", "minimum": 0}
    score = {"type": "number", "minimum": 0, "maximum": 1}
    boolean = {"type": "boolean"}
    notes = {"type": "array", "items": obj({
        "pitch": {"type": "integer", "minimum": 0, "maximum": 127},
        "start": {"type": "number", "minimum": 0}, "duration": {"type": "number", "exclusiveMinimum": 0},
        "velocity": {"type": "integer", "minimum": 0, "maximum": 127}, "instrument": text,
    })}
    input_defs = input_event_schema()["$defs"]
    rhythm = input_defs["rhythmPayload"]["properties"]["rhythm"]
    # Localize the only reference used by the reused input rhythm shape.
    rhythm = json.loads(json.dumps(rhythm).replace('"#/$defs/score"', '"#/$defs/unit"'))
    free_rhythm = obj({**input_defs["freeRhythmHits"]["properties"],
                       "audio_duration_s": input_defs["freeRhythmPayload"]["properties"]["audio_duration_s"],
                       "start_bar": {"type": ["integer", "null"], "minimum": 0}})
    rhythm_context = {"$ref": "#/$defs/rhythmContext"}
    legacy_rhythm = {"$ref": "#/$defs/legacyRhythm"}
    result = obj({
        "schema_version": {"enum": ["1.0.0", "1.1.0"]}, "session_id": text, "state_version": integer,
        "transport": obj({"tempo_bpm": {"type": "number", "minimum": 60, "maximum": 180}, "playing": boolean,
                          "bar": integer, "beat": {"type": "number", "minimum": 0, "exclusiveMaximum": 4}, "next_bar": integer}),
        "harmony": obj({"key": {"anyOf": [{"type": "null"}, obj({"tonic": {"type": "integer", "minimum": 0, "maximum": 11}, "mode": {"enum": ["major", "minor"]}})]}, "progression_variant": integer}),
        "form": obj({"section": text, "bars_elapsed": integer}),
        "feel": obj({"energy": {"type": "integer", "minimum": 0, "maximum": 3}, "density": score, "brightness": score, "tension": score, "tags": {"type": "array", "items": text}}),
        "motifs": obj({"current_id": {"type": ["string", "null"]}, "last_user": notes, "last_ai": notes,
                       "items": {"type": "array", "items": obj({"motif_id": text, "owner": {"enum": ["user", "ai"]}, "source_event_ids": {"type": "array", "uniqueItems": True, "items": text}, "notes": notes})}}),
        "arrangement": obj({"layers": {"type": "array", "minItems": 4, "maxItems": 4, "items": obj({"name": {"enum": ["drums", "bass", "keys", "lead"]}, "active": boolean, "level": score, "density": score, "role": text})}}),
        "interaction": obj({"strategy": {"enum": ["LISTEN", "FOLLOW", "RESPOND", "INITIATE"]}, "initiative": score,
                            "current_lead": {"enum": ["user", "ai", None]}, "user_active": boolean, "awaiting_user": boolean, "last_feedback": {"type": ["string", "null"]}}),
        "rhythm": {"anyOf": [{"type": "null"}, rhythm_context]}, "rhythm_mode": {"enum": ["follow", "vary", "simplify"]},
        "rhythm_sources": {"type": "array", "items": obj({"event_id": text, "context": rhythm_context})},
    })
    result.update({"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "JamMate JamState 1.0.0 / 1.1.0",
                   "$defs": {"unit": score, "legacyRhythm": rhythm,
                             "rhythmContext": {"anyOf": [legacy_rhythm, free_rhythm]}},
                   "if": {"properties": {"schema_version": {"const": "1.0.0"}}},
                   "then": {"properties": {"rhythm": {"anyOf": [{"type": "null"}, legacy_rhythm]},
                                           "rhythm_sources": {"items": {"properties": {"context": legacy_rhythm}}}}}})
    return result


@lru_cache(maxsize=1)
def _validator():
    schema = state_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_state(data):
    _json_values(data)
    error = next(_validator().iter_errors(json.loads(json.dumps(data, allow_nan=False))), None)
    if error:
        raise ValueError(f"JamState {'.'.join(map(str, error.absolute_path))}: {error.message}")
