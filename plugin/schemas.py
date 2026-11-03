"""Tool schemas — what the LLM sees."""

STATUS = {
    "name": "voxmetrica_status",
    "description": (
        "VoxMetrica system status: seal health, enrolled speakers, embed backend, data root. "
        "Use when diagnosing voice biometrics or after setup."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

WHOAMI = {
    "name": "voxmetrica_whoami",
    "description": (
        "Return the current speaker claim for this session, or identify from an audio file path. "
        "Use when the user asks who VoxMetrica thinks is speaking."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "audio_path": {
                "type": "string",
                "description": "Optional path to a wav/ogg/flac/mp3 file to identify",
            },
            "session_id": {
                "type": "string",
                "description": "Optional session id for claim lookup",
            },
        },
        "required": [],
    },
}

LIST = {
    "name": "voxmetrica_list",
    "description": "List enrolled VoxMetrica speakers (not root control-plane details).",
    "parameters": {"type": "object", "properties": {}, "required": []},
}

ENROLL = {
    "name": "voxmetrica_enroll",
    "description": (
        "ROOT ONLY. Enroll a new speaker from one or more audio file paths, "
        "or enroll root voice (as_root_voice=true). Copies a capability template "
        "as starting memory for that biometric (full-adult, limited-child, guest-default)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "speaker_id": {
                "type": "string",
                "description": "Stable id, e.g. adult1, alex (ignored if as_root_voice)",
            },
            "display_name": {"type": "string", "description": "Human name"},
            "audio_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Paths to enrollment audio clips",
            },
            "template": {
                "type": "string",
                "description": "Optional template: full-adult | limited-child | guest-default",
            },
            "as_root_voice": {
                "type": "boolean",
                "description": "If true, store embeddings under root control plane",
            },
            "discord_user_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional Discord user id bindings",
            },
            "is_root_claim": {
                "type": "boolean",
                "description": "Set true only when current speaker claim is root",
            },
            "local_cli": {
                "type": "boolean",
                "description": "Set true for host recovery CLI path",
            },
        },
        "required": ["display_name", "audio_paths"],
    },
}

DELETE = {
    "name": "voxmetrica_delete",
    "description": "ROOT ONLY. Delete an enrolled speaker and their capability memory.",
    "parameters": {
        "type": "object",
        "properties": {
            "speaker_id": {"type": "string"},
            "is_root_claim": {"type": "boolean"},
            "local_cli": {"type": "boolean"},
        },
        "required": ["speaker_id"],
    },
}

GET_CAPS = {
    "name": "voxmetrica_get_capabilities",
    "description": (
        "Read capability memory for a speaker_id (what that biometric may access). "
        "Root can read anyone; others should only request self."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "speaker_id": {"type": "string", "description": "Speaker id or 'guest'"},
        },
        "required": ["speaker_id"],
    },
}

SET_CAPS = {
    "name": "voxmetrica_set_capabilities",
    "description": (
        "ROOT ONLY. Update which resources a biometric is allowed. "
        "Provide template name, or a full capabilities object, or path to YAML."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "speaker_id": {"type": "string"},
            "template": {
                "type": "string",
                "description": "full-adult | limited-child | guest-default",
            },
            "capabilities": {
                "type": "object",
                "description": "Full capabilities document to write",
            },
            "caps_yaml_path": {
                "type": "string",
                "description": "Path to a capabilities YAML file to load",
            },
            "is_root_claim": {"type": "boolean"},
            "local_cli": {"type": "boolean"},
        },
        "required": ["speaker_id"],
    },
}

CHECK = {
    "name": "voxmetrica_check",
    "description": (
        "Check whether a speaker is allowed a resource (tools|toolsets|paths|memory_scopes|home)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "speaker_id": {"type": "string"},
            "kind": {
                "type": "string",
                "description": "tools | toolsets | paths | memory_scopes | home",
            },
            "name": {
                "type": "string",
                "description": "Resource name e.g. terminal, web_search, /home/shared/private",
            },
        },
        "required": ["speaker_id", "kind", "name"],
    },
}

CLARIFY_RESOLVE = {
    "name": "voxmetrica_clarify_resolve",
    "description": (
        "Resolve a pending gray-zone identity: choice is a candidate speaker_id or 'guest'. "
        "Binds the session claim; optional template adapt on confirm."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "choice": {"type": "string", "description": "speaker_id from candidates, or guest"},
            "adapt": {"type": "boolean", "description": "Append query emb on confirm (default true)"},
        },
        "required": ["choice"],
    },
}

ADAPT = {
    "name": "voxmetrica_adapt",
    "description": "ROOT ONLY. Append a confirmed embedding from audio for a speaker (template adaptation).",
    "parameters": {
        "type": "object",
        "properties": {
            "speaker_id": {"type": "string"},
            "audio_path": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["speaker_id", "audio_path"],
    },
}

SYNC_EXPORT = {
    "name": "voxmetrica_sync_export",
    "description": "ROOT ONLY. Export gallery signatures as voxmetrica-sync-v1 to a directory path.",
    "parameters": {
        "type": "object",
        "properties": {"dest": {"type": "string", "description": "Destination directory"}},
        "required": ["dest"],
    },
}

SYNC_IMPORT = {
    "name": "voxmetrica_sync_import",
    "description": "ROOT ONLY. Import a voxmetrica-sync-v1 package (embeddings+meta+caps).",
    "parameters": {
        "type": "object",
        "properties": {"src": {"type": "string", "description": "Package directory"}},
        "required": ["src"],
    },
}
