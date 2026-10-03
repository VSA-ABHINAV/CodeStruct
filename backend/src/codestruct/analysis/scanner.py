"""Deterministic, non-following recursive Python source discovery."""

from __future__ import annotations

import os
import stat as stat_module
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from .diagnostics import SAFE_MESSAGES, DiagnosticCode, DiagnosticSeverity
from .models import ParserDiagnostic, ProjectScanResult, SourceFile, stable_id
from .policy import AnalysisPolicy

CancellationCheck = Callable[[], bool]


def derive_module_name(relative_path: str) -> str:
    """Derive an import-style module name from a normalized relative path."""

    path = PurePosixPath(relative_path)
    parts = list(path.parts)
    if not parts or path.suffix not in (".py", ".pyw", ".pyi"):
        raise ValueError("module paths must identify a .py, .pyw, or .pyi file")
    leaf = path.stem
    if leaf == "__init__":
        module_parts = parts[:-1]
    else:
        module_parts = [*parts[:-1], leaf]
    return ".".join(module_parts) if module_parts else "__root__"


def _diagnostic(
    code: DiagnosticCode,
    severity: DiagnosticSeverity,
    relative_path: str | None = None,
) -> ParserDiagnostic:
    return ParserDiagnostic(
        id=stable_id("diag", code.value, relative_path or ""),
        code=code,
        severity=severity,
        message=SAFE_MESSAGES[code],
        relative_path=relative_path,
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        normalized_path = os.path.normcase(os.fspath(path))
        normalized_root = os.path.normcase(os.fspath(root))
        return os.path.commonpath((normalized_path, normalized_root)) == normalized_root
    except ValueError:
        return False


def _is_reparse_stat(stat_result: os.stat_result) -> bool:
    flag = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return bool(flag and attributes & flag)


def _is_link_or_reparse(path: Path, stat_result: os.stat_result | None = None) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        return _is_reparse_stat(stat_result or path.lstat())
    except OSError:
        return False


def _has_link_component(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:] if path.anchor else path.parts:
        current = current / part
        try:
            if _is_link_or_reparse(current, current.lstat()):
                return True
        except OSError:
            return False
    return False


def _matches(relative_path: str, patterns: tuple[str, ...]) -> bool:
    path = PurePosixPath(relative_path)
    for pattern in patterns:
        normalized = pattern.replace("\\", "/")
        if path.match(normalized):
            return True
        if normalized.startswith("**/") and path.match(normalized[3:]):
            return True
    return False


def _excluded_by_name(path: PurePosixPath, policy: AnalysisPolicy) -> bool:
    folded_directories = {name.casefold() for name in policy.excluded_directories}
    folded_files = {name.casefold() for name in policy.excluded_file_names}
    return any(part.casefold() in folded_directories for part in path.parts[:-1]) or (
        path.name.casefold() in folded_files
        or path.suffix.casefold() in {".pem", ".key"}
    )


def _cancelled(check: CancellationCheck | None) -> bool:
    return bool(check and check())


def scan_project(
    project_root: str | os.PathLike[str],
    policy: AnalysisPolicy,
    cancellation_check: CancellationCheck | None = None,
) -> ProjectScanResult:
    """Discover safe regular Python files without reading their contents."""

    diagnostics: list[ParserDiagnostic] = []
    requested_root = Path(project_root)
    if _cancelled(cancellation_check):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.CANCELLATION_REQUESTED, DiagnosticSeverity.WARNING
            )
        )
        return ProjectScanResult(None, diagnostics=tuple(diagnostics), cancelled=True)

    try:
        canonical_root = requested_root.resolve(strict=True)
    except (OSError, RuntimeError):
        diagnostics.append(
            _diagnostic(DiagnosticCode.INVALID_PROJECT_ROOT, DiagnosticSeverity.ERROR)
        )
        return ProjectScanResult(None, diagnostics=tuple(diagnostics))

    if not canonical_root.is_dir():
        diagnostics.append(
            _diagnostic(DiagnosticCode.INVALID_PROJECT_ROOT, DiagnosticSeverity.ERROR)
        )
        return ProjectScanResult(canonical_root.name, diagnostics=tuple(diagnostics))

    if _has_link_component(requested_root.absolute()):
        diagnostics.append(
            _diagnostic(DiagnosticCode.PATH_LINK_SKIPPED, DiagnosticSeverity.ERROR)
        )
        return ProjectScanResult(canonical_root.name, diagnostics=tuple(diagnostics))

    if policy.authorized_roots:
        authorized = False
        for configured_root in policy.authorized_roots:
            try:
                canonical_authorized = Path(configured_root).resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if canonical_authorized.is_dir() and _is_within(
                canonical_root, canonical_authorized
            ):
                authorized = True
                break
        if not authorized:
            diagnostics.append(
                _diagnostic(DiagnosticCode.UNAUTHORIZED_ROOT, DiagnosticSeverity.ERROR)
            )
            return ProjectScanResult(
                canonical_root.name, diagnostics=tuple(diagnostics)
            )

    if policy.single_file_name:
        target_name = policy.single_file_name
        target_path = canonical_root / target_name
        try:
            target_stat = target_path.stat(follow_symlinks=False)
        except OSError:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.FILE_CHANGED_OR_MISSING,
                    DiagnosticSeverity.WARNING,
                    target_name,
                )
            )
            return ProjectScanResult(
                canonical_root.name,
                diagnostics=tuple(diagnostics),
            )

        if target_path.is_symlink() or _is_reparse_stat(target_stat):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.PATH_LINK_SKIPPED,
                    DiagnosticSeverity.WARNING,
                    target_name,
                )
            )
            return ProjectScanResult(
                canonical_root.name,
                diagnostics=tuple(diagnostics),
            )

        if not stat_module.S_ISREG(target_stat.st_mode):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_FILE,
                    DiagnosticSeverity.ERROR,
                    target_name,
                )
            )
            return ProjectScanResult(
                canonical_root.name,
                diagnostics=tuple(diagnostics),
            )

        target_entry = PurePosixPath(target_name)
        if target_entry.suffix not in (".py", ".pyw", ".pyi"):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_FILE,
                    DiagnosticSeverity.INFO,
                    target_name,
                )
            )
            return ProjectScanResult(
                canonical_root.name,
                diagnostics=tuple(diagnostics),
            )

        if target_stat.st_size > policy.max_file_size:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.FILE_TOO_LARGE,
                    DiagnosticSeverity.WARNING,
                    target_name,
                )
            )
            return ProjectScanResult(
                canonical_root.name,
                diagnostics=tuple(diagnostics),
                limit_reached=True,
            )

        source_file = SourceFile(
            id=stable_id("src", target_name),
            relative_path=target_name,
            module_name=derive_module_name(target_name),
            is_package=target_entry.name in ("__init__.py", "__init__.pyi"),
            size_bytes=target_stat.st_size,
            modified_ns=target_stat.st_mtime_ns,
            device=getattr(target_stat, "st_dev", None),
            inode=getattr(target_stat, "st_ino", None),
        )
        return ProjectScanResult(
            root_name=canonical_root.name,
            source_files=(source_file,),
            diagnostics=tuple(diagnostics),
            cancelled=False,
            limit_reached=False,
        )

    source_files: list[SourceFile] = []
    cancelled = False
    limit_reached = False

    def walk(directory: Path, depth: int) -> bool:
        nonlocal cancelled, limit_reached
        if _cancelled(cancellation_check):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.CANCELLATION_REQUESTED,
                    DiagnosticSeverity.WARNING,
                )
            )
            cancelled = True
            return False
        try:
            with os.scandir(directory) as scan:
                entries = sorted(
                    scan, key=lambda item: (item.name.casefold(), item.name)
                )
        except OSError:
            relative_directory = directory.relative_to(canonical_root).as_posix() or "."
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.FILE_READ_FAILURE,
                    DiagnosticSeverity.ERROR,
                    relative_directory,
                )
            )
            return True

        for entry in entries:
            if _cancelled(cancellation_check):
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.CANCELLATION_REQUESTED,
                        DiagnosticSeverity.WARNING,
                    )
                )
                cancelled = True
                return False

            entry_path = Path(entry.path)
            try:
                relative_path = entry_path.relative_to(canonical_root).as_posix()
            except ValueError:
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.PATH_TRAVERSAL_REJECTED,
                        DiagnosticSeverity.ERROR,
                    )
                )
                continue
            relative_entry = PurePosixPath(relative_path)

            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError:
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.FILE_CHANGED_OR_MISSING,
                        DiagnosticSeverity.WARNING,
                        relative_path,
                    )
                )
                continue

            if entry.is_symlink() or _is_reparse_stat(entry_stat):
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.PATH_LINK_SKIPPED,
                        DiagnosticSeverity.WARNING,
                        relative_path,
                    )
                )
                continue

            if entry.is_dir(follow_symlinks=False):
                if entry.name.casefold() in {
                    name.casefold() for name in policy.excluded_directories
                } or _matches(relative_path, policy.exclude_patterns):
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.PATH_EXCLUDED,
                            DiagnosticSeverity.INFO,
                            relative_path,
                        )
                    )
                    continue
                child_depth = depth + 1
                if child_depth > policy.max_depth:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.DEPTH_LIMIT_REACHED,
                            DiagnosticSeverity.WARNING,
                            relative_path,
                        )
                    )
                    limit_reached = True
                    continue
                if not walk(entry_path, child_depth):
                    return False
                continue

            if not stat_module.S_ISREG(entry_stat.st_mode):
                continue
            if _excluded_by_name(relative_entry, policy) or _matches(
                relative_path, policy.exclude_patterns
            ):
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.PATH_EXCLUDED,
                        DiagnosticSeverity.INFO,
                        relative_path,
                    )
                )
                continue
            if not _matches(relative_path, policy.include_patterns):
                continue
            if relative_entry.suffix not in (".py", ".pyw", ".pyi"):
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.UNSUPPORTED_FILE,
                        DiagnosticSeverity.INFO,
                        relative_path,
                    )
                )
                continue
            if len(source_files) >= policy.max_files:
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.FILE_COUNT_LIMIT_REACHED,
                        DiagnosticSeverity.WARNING,
                    )
                )
                limit_reached = True
                return False
            if entry_stat.st_size > policy.max_file_size:
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.FILE_TOO_LARGE,
                        DiagnosticSeverity.WARNING,
                        relative_path,
                    )
                )
                limit_reached = True
                continue
            source_files.append(
                SourceFile(
                    id=stable_id("src", relative_path),
                    relative_path=relative_path,
                    module_name=derive_module_name(relative_path),
                    is_package=relative_entry.name in ("__init__.py", "__init__.pyi"),
                    size_bytes=entry_stat.st_size,
                    modified_ns=entry_stat.st_mtime_ns,
                    device=getattr(entry_stat, "st_dev", None),
                    inode=getattr(entry_stat, "st_ino", None),
                )
            )
        return True

    walk(canonical_root, 0)
    ordered_files = tuple(sorted(source_files, key=lambda item: item.relative_path))
    return ProjectScanResult(
        root_name=canonical_root.name,
        source_files=ordered_files,
        diagnostics=tuple(diagnostics),
        cancelled=cancelled,
        limit_reached=limit_reached,
    )
