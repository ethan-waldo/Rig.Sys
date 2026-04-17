# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial release of the project.
- Added `UnrealControlRigExport` module to export Maya rig metadata/FBX and generate an Unreal Python Control Rig build script.
- Extended Unreal export manifest with custom control attributes, constraints, and connection metadata for parity-focused reconstruction.
- Added rig-logic utility node capture and IK/FK switch system extraction to the Unreal export manifest.

### Changed

- Updated package Python requirement to `>=3.10` for modern Maya compatibility.
- Improved export path resolution so directory outputs correctly include module-specific file extensions.
- Extended generated Unreal script to apply best-effort reconstruction for custom attrs and parent constraints, and persist richer metadata on the Control Rig asset.
- Extended generated Unreal script metadata persistence with `rig_logic_nodes` and `ik_fk_systems` payloads, and added best-effort IK/FK visibility reconstruction hooks.

[unreleased]: https://github.com/olivierlacan/keep-a-changelog/compare/v1.1.1...HEAD
