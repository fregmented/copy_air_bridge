# Repository Guidelines

## Project Overview

This project controls a Tuya IoT air conditioner locally through the TinyTuya
library and exposes it for use with a SmartThings Edge Driver.

- Server language: Python.
- Python package manager: uv.
- Deployment target: Docker.
- SmartThings Edge Driver language: Lua.
- Runtime configuration: store connection and device settings in
  `data/settings.yaml`.

## Expected Repository Structure

Keep the project organized around these responsibilities:

- `data/settings.yaml`: local runtime settings, Tuya credentials, device IDs,
  local keys, IP addresses, protocol versions, and any SmartThings bridge
  configuration needed at runtime.
- Python server code: local bridge/API implementation that talks to TinyTuya.
- Lua Edge Driver code: SmartThings Edge Driver implementation and capability
  mapping.
- Docker assets: Dockerfile and compose files for deployable runtime
  environments.

Do not commit real credentials, local keys, tokens, or private network details.
Prefer checked-in examples such as `data/settings.example.yaml` when defaults
or documentation are needed.

## Development Rules

- Use Python for server-side code.
- Use uv for dependency management, locking, and local execution.
- Use TinyTuya for Tuya device communication instead of custom Tuya protocol
  implementations.
- Use Lua for SmartThings Edge Driver code.
- Keep deployment reproducible with Docker.
- Treat `data/settings.yaml` as the primary source for environment-specific
  connection data.
- Keep Tuya data-point IDs and SmartThings capability mappings explicit and
  easy to audit.

## Tuya Air Conditioner Data Model

The device uses Tuya Things Data Model `modelId` `eh1sso`.

| DP ID | Code | Access | Type | Range / Unit | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | `switch` | rw | bool | - | Power switch |
| 2 | `temp_current` | ro | value | 10-45 C, step 1 | Current temperature |
| 5 | `temp_set` | rw | value | 16-32 C, step 1 | Target temperature |
| 7 | `mode` | rw | enum | `Auto`, `Colding`, `Dehmidify`, `Wind`, `Save` | Operating mode. Preserve vendor spelling unless a translation layer is explicitly added. |
| 9 | `fan_speed_enum` | rw | enum | `auto`, `low`, `middle`, `high` | Fan speed |
| 11 | `child_lock` | rw | bool | - | Child lock |
| 101 | `on_time` | rw | value | 0-24 H, step 1 | Start timer |
| 102 | `stop_time` | rw | value | 0-24 H, step 1 | Stop timer |
| 103 | `turbo` | rw | bool | - | Turbo mode |
| 104 | `sleepfunc` | rw | bool | - | Sleep mode |
| 105 | `swing1` | rw | enum | `stop`, `leftright`, `updown`, `all` | Swing mode |
| 106 | `light` | rw | bool | - | Display/light control |
| 107 | `currenterror` | ro | value | 0-99, step 1 | Current error code |
| 108 | `motiondetector` | ro | value | 0-1, step 1 | Motion detector state |
| 109 | `humidity` | ro | value | 0-100 %, step 1 | Current humidity |
| 110 | `humidityset` | rw | value | 35-70 %, step 5 | Target humidity |

## Implementation Notes

- Validate writable values against the model ranges before sending commands to
  TinyTuya.
- Read-only properties must not be exposed as writable SmartThings commands.
- Keep enum values exact when communicating with the Tuya device.
- If SmartThings capability names differ from Tuya codes, keep the translation
  in one clearly named mapping module/table.
- Prefer structured YAML parsing for settings instead of hand-written parsing.
- Add tests around data-point mapping, value validation, and command generation
  when implementing bridge behavior.

