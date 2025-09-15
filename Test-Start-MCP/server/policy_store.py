from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import fnmatch
from datetime import datetime, timezone, timedelta


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # Support 'Z' suffix and timezone-aware strings
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _is_under_root(p: Path, root: Path) -> bool:
    try:
        p_r = p.resolve()
        r_r = root.resolve()
        return r_r in p_r.parents or p_r == r_r
    except Exception:
        return False


@dataclass
class Caps:
    maxTimeoutMs: int = 90000
    maxBytes: int = 262144
    maxStdoutLines: int = 1500
    concurrency: int = 2


@dataclass
class Rule:
    id: str
    type: str  # 'path' | 'scope'
    path: Optional[str] = None
    scopeRoot: Optional[str] = None
    patterns: List[str] = field(default_factory=list)
    flagsAllowed: Optional[List[str]] = None
    flagsDenied: Optional[List[str]] = None
    caps: Optional[Caps] = None
    conditions: Optional[Dict[str, Any]] = None
    ttlSec: Optional[int] = None
    label: Optional[str] = None
    note: Optional[str] = None
    createdBy: Optional[str] = None
    createdAt: Optional[str] = None
    expiresAt: Optional[str] = None


@dataclass
class Overlay:
    sessionId: str
    profile: str
    expiresAt: Optional[str] = None


@dataclass
class Profile:
    caps: Caps
    flagsAllowed: List[str]


@dataclass
class PolicyState:
    version: int = 1
    rules: List[Rule] = field(default_factory=list)
    overlays: List[Overlay] = field(default_factory=list)
    profiles: Dict[str, Profile] = field(default_factory=dict)


def _to_caps(d: Optional[Dict[str, Any]]) -> Optional[Caps]:
    if not d:
        return None
    return Caps(
        maxTimeoutMs=int(d.get('maxTimeoutMs', 90000)),
        maxBytes=int(d.get('maxBytes', 262144)),
        maxStdoutLines=int(d.get('maxStdoutLines', 1500)),
        concurrency=int(d.get('concurrency', 2)),
    )


def load_state(fp: Path) -> PolicyState:
    try:
        if not fp.exists():
            return PolicyState()
        raw = json.loads(fp.read_text(encoding='utf-8'))
        rules = []
        for r in raw.get('rules', []):
            rules.append(Rule(
                id=str(r.get('id','')),
                type=str(r.get('type','path')),
                path=r.get('path'),
                scopeRoot=r.get('scopeRoot'),
                patterns=r.get('patterns') or [],
                flagsAllowed=r.get('flagsAllowed'),
                flagsDenied=r.get('flagsDenied'),
                caps=_to_caps(r.get('caps')),
                conditions=r.get('conditions'),
                ttlSec=r.get('ttlSec'),
                label=r.get('label'),
                note=r.get('note'),
                createdBy=r.get('createdBy'),
                createdAt=r.get('createdAt'),
                expiresAt=r.get('expiresAt'),
            ))
        overlays = [Overlay(**o) for o in raw.get('overlays', [])]
        profiles: Dict[str, Profile] = {}
        for name, p in (raw.get('profiles') or {}).items():
            profiles[name] = Profile(caps=_to_caps(p.get('caps')) or Caps(), flagsAllowed=p.get('flagsAllowed') or [])
        return PolicyState(version=int(raw.get('version', 1)), rules=rules, overlays=overlays, profiles=profiles)
    except Exception:
        return PolicyState()


def save_state(fp: Path, state: PolicyState) -> None:
    try:
        fp.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {
            'version': state.version,
            'rules': [r.__dict__ for r in state.rules],
            'overlays': [o.__dict__ for o in state.overlays],
            'profiles': {k: {'caps': v.caps.__dict__ if v.caps else {}, 'flagsAllowed': v.flagsAllowed} for k, v in state.profiles.items()},
        }
        fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def evaluate_preflight(path: str, args: Optional[List[str]], session_id: Optional[str], agent_name: Optional[str], agent_version: Optional[str],
                       allowed_root: Path, flags_global: List[str], state: Optional[PolicyState]) -> Tuple[bool, Optional[Dict[str, Any]], List[str], List[Dict[str,str]]]:
    """Evaluate preflight policy.
    - Enforces boundary: path must be under allowed_root and exist as a file.
    - Merges overlays (session profile) → rule match (path or scope+patterns).
    - Intersects allowed flags with global flags; respects flagsDenied.
    - Returns (allowed, matchedRule, reasons, suggestions).
    """
    reasons: List[str] = []
    suggestions: List[Dict[str, str]] = []
    matched_rule_dict: Optional[Dict[str, Any]] = None
    args = list(args or [])

    try:
        p = Path(path).resolve()
    except Exception:
        return False, None, ['invalid_path'], []

    # Boundary checks
    if not _is_under_root(p, allowed_root):
        reasons.append('outside_allowed_root')
    if not p.exists() or not p.is_file():
        reasons.append('path_not_found')

    # Effective allowed flags start with global
    effective_allowed_flags = set(flags_global)

    # Overlay profile (highest priority)
    st = state or PolicyState()
    overlay = None
    if session_id:
        now = datetime.now(timezone.utc)
        for o in st.overlays:
            if o.sessionId == session_id:
                exp = _parse_iso(o.expiresAt)
                if exp is None or exp > now:
                    overlay = o
                    break
        if overlay and overlay.profile in st.profiles:
            prof = st.profiles[overlay.profile]
            if prof.flagsAllowed:
                effective_allowed_flags = effective_allowed_flags.intersection(set(prof.flagsAllowed))

    # Select best matching rule (first match)
    def rule_valid(r: Rule) -> bool:
        exp = _parse_iso(r.expiresAt)
        return (exp is None) or (exp > datetime.now(timezone.utc))

    matched_rule = None
    for r in (st.rules or []):
        if not rule_valid(r):
            continue
        if r.type == 'path' and r.path:
            try:
                if Path(r.path).resolve() == p:
                    matched_rule = r
                    break
            except Exception:
                continue
        elif r.type == 'scope' and r.scopeRoot and r.patterns:
            try:
                root = Path(r.scopeRoot).resolve()
                if _is_under_root(p, root):
                    rel = str(p.relative_to(root))
                    if any(fnmatch.fnmatch(rel, pat) for pat in r.patterns):
                        matched_rule = r
                        break
            except Exception:
                continue

    # Merge rule flags if present
    if matched_rule:
        if matched_rule.flagsAllowed:
            effective_allowed_flags = effective_allowed_flags.intersection(set(matched_rule.flagsAllowed))
        if matched_rule.flagsDenied:
            # Denied flags take precedence: remove them from allowed
            effective_allowed_flags = effective_allowed_flags.difference(set(matched_rule.flagsDenied))
        matched_rule_dict = matched_rule.__dict__.copy()

    # Flag validation (only check --flags; positional unsupported)
    bad_flags: List[str] = []
    for a in args:
        if a.startswith('--') and a not in effective_allowed_flags:
            bad_flags.append(a)
    if bad_flags:
        reasons.append('disallowed_flags: ' + ','.join(bad_flags))

    # Suggestions
    try:
        suggestions.append({'type': 'scope', 'value': str(p.parent), 'comment': 'Use project scope root'})
        suggestions.append({'type': 'pattern', 'value': p.name, 'comment': 'Use runner basename'})
    except Exception:
        pass

    allowed = len(reasons) == 0
    return allowed, matched_rule_dict, reasons, suggestions


def effective_caps_for(path: str, session_id: Optional[str], allowed_root: Path, state: Optional[PolicyState]) -> Optional[Caps]:
    """Compute effective caps given session overlay and matching rule.
    Priority: overlay profile caps (if present) combined with matched rule caps (min for each field).
    Returns a Caps or None if no caps are defined anywhere.
    """
    st = state or PolicyState()
    try:
        p = Path(path).resolve()
    except Exception:
        return None
    if not _is_under_root(p, allowed_root):
        return None

    # Overlay caps
    overlay_caps: Optional[Caps] = None
    if session_id:
        now = datetime.now(timezone.utc)
        for o in st.overlays:
            if o.sessionId == session_id:
                exp = _parse_iso(o.expiresAt)
                if exp is None or exp > now:
                    prof = st.profiles.get(o.profile)
                    if prof and prof.caps:
                        overlay_caps = prof.caps
                    break

    # Matched rule caps
    rule_caps: Optional[Caps] = None
    matched: Optional[Rule] = None
    for r in (st.rules or []):
        exp = _parse_iso(r.expiresAt)
        if exp is not None and exp <= datetime.now(timezone.utc):
            continue
        try:
            if r.type == 'path' and r.path and Path(r.path).resolve() == p:
                matched = r
                break
            if r.type == 'scope' and r.scopeRoot and r.patterns:
                root = Path(r.scopeRoot).resolve()
                if _is_under_root(p, root):
                    rel = str(p.relative_to(root))
                    if any(fnmatch.fnmatch(rel, pat) for pat in r.patterns):
                        matched = r
                        break
        except Exception:
            continue
    if matched and matched.caps:
        rule_caps = matched.caps

    if not overlay_caps and not rule_caps:
        return None

    # Merge (min of present fields)
    def min_or(a: Optional[int], b: Optional[int], default: Optional[int]) -> Optional[int]:
        vals = [v for v in (a, b) if isinstance(v, int)]
        if not vals:
            return default
        return min(vals)

    return Caps(
        maxTimeoutMs=min_or(getattr(overlay_caps, 'maxTimeoutMs', None), getattr(rule_caps, 'maxTimeoutMs', None), getattr(overlay_caps or rule_caps, 'maxTimeoutMs', 90000)),
        maxBytes=min_or(getattr(overlay_caps, 'maxBytes', None), getattr(rule_caps, 'maxBytes', None), getattr(overlay_caps or rule_caps, 'maxBytes', 262144)),
        maxStdoutLines=min_or(getattr(overlay_caps, 'maxStdoutLines', None), getattr(rule_caps, 'maxStdoutLines', None), getattr(overlay_caps or rule_caps, 'maxStdoutLines', 1500)),
        concurrency=min_or(getattr(overlay_caps, 'concurrency', None), getattr(rule_caps, 'concurrency', None), getattr(overlay_caps or rule_caps, 'concurrency', 2)) or 1,
    )
