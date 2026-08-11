# Image generation adapter contract

The asset pipeline owns editorial intent, character continuity, local paths,
file validation, and deck finalization. It does not import a provider SDK or
know a model name. Imagen, Nano Banana, OpenAI image tools, and future
providers are adapters behind the same JSON protocol.

## Protocol

An adapter is an executable that reads one JSON object from stdin and writes
one JSON object to stdout. It must not print logs to stdout; diagnostics belong
on stderr. The pipeline starts it with the run directory as the working
directory, so all request and response paths are relative to that run.

Capability request:

```json
{
  "protocol": "handdrawn-image/v1",
  "operation": "capabilities"
}
```

Capability response:

```json
{
  "protocol": "handdrawn-image/v1",
  "status": "ok",
  "capabilities": {
    "generate": true,
    "reference_images": true,
    "native_alpha": false
  },
  "provider": "provider-name",
  "model": "runtime-selected-model"
}
```

Generation request:

```json
{
  "protocol": "handdrawn-image/v1",
  "operation": "generate_with_references",
  "job_id": "s03-begin-with-fear",
  "kind": "scene_illustration",
  "prompt_spec": {
    "use_case": "illustration-story",
    "primary_request": "one concrete scene",
    "input_images": [
      {"path": "character/anchor.png", "role": "character_identity"}
    ],
    "text_verbatim": "",
    "constraints": ["no embedded text"]
  },
  "references": ["character/anchor.png"],
  "output": {
    "path": ".asset-staging-job/scene.png",
    "final_path": "illustrations/03-begin-with-fear.png",
    "format": "png"
  },
  "requirements": {
    "generate": true,
    "reference_images": true
  }
}
```

The adapter writes the final raster file to `output.path`. The core then
validates and copies it to `output.final_path`; an adapter must never write
outside the run directory.

Success response:

```json
{
  "protocol": "handdrawn-image/v1",
  "status": "ok",
  "provider": "provider-name",
  "model": "runtime-selected-model",
  "request_id": "optional-provider-request-id"
}
```

Failure response:

```json
{
  "protocol": "handdrawn-image/v1",
  "status": "error",
  "error": "human-readable reason"
}
```

The core requires `reference_images` for every scene job. It must stop before
spending a request when the selected provider cannot accept the locked anchor.
`native_alpha` is optional: the renderer can use the existing multiply blend
or the local chroma-key conversion when native transparency is unavailable.

## Provider mapping

The adapter, not the deck, translates the neutral `prompt_spec` and reference
roles into provider-specific request fields. A Google Imagen adapter can map
the anchor to its reference-image input; a Nano Banana adapter can map the same
anchor to its image-conditioned input. Their model IDs, credentials, endpoint
versions, and safety settings stay in adapter-local configuration or the
runtime environment.

Do not put provider keys, absolute paths, base64 payloads, or provider-specific
request JSON in `deck.json`, `asset-plan.json`, or the shared bundle.

## Host-native image tools

When the host exposes an image tool that cannot be called as a subprocess, the
agent executes each pending job using the same `prompt_spec` and `references`,
saves the selected result into a workspace-local file, and imports it with:

```sh
python scripts/asset_pipeline.py accept \
  output/<slug>/asset-plan.json \
  character-anchor \
  /path/to/generated-anchor.png
```

The agent repeats this for the scene jobs. Once all jobs are accepted, the
pipeline finalizes `deck.json` and writes `asset-manifest.json`.

## Text policy

The default is no embedded text in any language. Do not ask the image model to
render Korean, English, labels, numbers, logos, or watermarks. Visible copy is
HTML/CSS text. Empty books, cards, signs, letters, and nameplates are allowed
as visual objects; their copy is rendered by the deck.
