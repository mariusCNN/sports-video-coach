"""Plugins: what a sport (or any video domain) adds to the core.

A plugin is a `Plugin` object. The core finds plugins in three places, in this order:
  1. built in: the `generic` plugin (any sport, no computer vision: frame sheets -> agent review -> report);
  2. installed packages: entry points in the group `sports_video_coach.plugins` (`name = "pkg.module:PLUGIN"`);
  3. local folders: every `<dir>/<name>/__init__.py` defining `PLUGIN`, for each dir in $SVC_PLUGIN_PATH
     (os.pathsep-separated), `<workspace>/plugins` and `./plugins` (what `sports-video-coach new-plugin` writes).
A plugin that fails to load is reported by `errors()` and skipped; the others still load.

A unit is one folder the driver works on (a game, a training session, ...). It is owned by the plugin named in its
json `"plugin"` key, else by the first plugin with a `Kind` for that json file name whose `match` accepts the data.
"""
from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

GROUP = "sports_video_coach.plugins"


@dataclass
class Kind:
    """One kind of unit folder a plugin drives."""
    name: str                                   # "game", "training", "analysis", ...
    json: str                                   # the unit's json file name ("game.json")
    unit: str = ""                              # "module:Class", a pipeline.Unit subclass with load(folder)
    steps: str = ""                             # "module:NAME", the step table (list[pipeline.Step]); "" = not driven
    match: Callable[[dict], bool] | None = None  # does this json belong to this kind (e.g. kind == "training")
    driver: str | None = None                   # the plugin stage that drives it (None: the core `run`)
    levels: int = 0                             # a sub-report folder may sit this many levels below the json

    def unit_class(self):
        return _attr(self.unit)

    def step_table(self) -> list:
        return _attr(self.steps)


@dataclass
class Plugin:
    """What a plugin declares. Hooks are optional; the core works without them."""
    name: str
    summary: str                                # one line: what it analyses and delivers
    use_when: str = ""                          # one line for agents choosing a plugin
    stages: dict[str, tuple[str, str]] = field(default_factory=dict)   # stage -> (module, help)
    kinds: list[Kind] = field(default_factory=list)
    prompts: Path | None = None                 # writing guides and review briefs
    page: Any = None                            # render_html.PageHooks
    scenes: dict[str, Any] = field(default_factory=dict)              # film scene kind -> film.SceneKind
    film: Any = None                            # film.FilmHooks
    site: Any = None                            # publish.SiteHooks
    clip_windows: Callable[[Path], list[tuple[str, str]]] | None = None  # extra clip windows a page needs
    artifacts: dict[str, str] = field(default_factory=dict)           # extra artifact name -> help (steps tag it)
    claims: Callable[[str], bool] | None = None  # does this plugin take this target (e.g. a league url)
    version: str = ""


def _attr(ref: str):
    mod, _, name = ref.partition(":")
    return getattr(importlib.import_module(mod), name)


_CACHE: dict[str, Plugin] | None = None
_ERRORS: dict[str, str] = {}


def plugin_dirs() -> list[Path]:
    """Folders searched for local plugins."""
    from . import workspace
    dirs = [Path(p) for p in os.environ.get("SVC_PLUGIN_PATH", "").split(os.pathsep) if p]
    dirs += [workspace.root() / "plugins", Path.cwd() / "plugins"]
    out = []
    for d in dirs:
        d = d.expanduser().resolve()
        if d not in out and d.is_dir():
            out.append(d)
    return out


def _load_folder(folder: Path) -> Plugin:
    """Import <folder>/__init__.py as package `svc_plugin_<name>` and return its PLUGIN."""
    name = "svc_plugin_" + folder.name.replace("-", "_")
    if name in sys.modules:
        mod = sys.modules[name]
    else:
        spec = importlib.util.spec_from_file_location(name, folder / "__init__.py",
                                                      submodule_search_locations=[str(folder)])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            del sys.modules[name]
            raise
    p = getattr(mod, "PLUGIN", None)
    if not isinstance(p, Plugin):
        raise TypeError(f"{folder / '__init__.py'} defines no PLUGIN = Plugin(...)")
    return p


def _add(out: dict, where: str, load: Callable[[], Plugin]) -> None:
    try:
        p = load()
    except Exception as ex:  # a broken plugin must not take the others down
        _ERRORS[where] = f"{type(ex).__name__}: {ex}"
        return
    if p.name in out:
        _ERRORS[where] = f"plugin name {p.name!r} already loaded; skipped"
        return
    out[p.name] = p


def plugins(refresh: bool = False) -> dict[str, Plugin]:
    """Every loadable plugin by name (built-in first, then entry points, then local folders)."""
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    _ERRORS.clear()
    out: dict[str, Plugin] = {}
    _add(out, "builtin:generic", lambda: _attr("sports_video_coach.plugins.generic:PLUGIN"))
    for ep in sorted(importlib.metadata.entry_points(group=GROUP), key=lambda e: e.name):
        _add(out, f"entry point {ep.name} ({ep.value})", ep.load)
    for d in plugin_dirs():
        for f in sorted(d.iterdir()):
            if (f / "__init__.py").is_file():
                _add(out, f"folder {f}", lambda f=f: _load_folder(f))
    _CACHE = out
    return out


def errors() -> dict[str, str]:
    """Plugins that failed to load: where -> error (after `plugins()`)."""
    plugins()
    return dict(_ERRORS)


def get(name: str) -> Plugin:
    found = plugins()
    if name not in found:
        sys.exit(f"unknown plugin {name!r}; installed: {', '.join(found) or 'none'}")
    return found[name]


def json_names() -> list[tuple[str, int]]:
    """(json file name, levels) of every kind, in plugin order, each name once (largest levels wins)."""
    out: dict[str, int] = {}
    for p in plugins().values():
        for k in p.kinds:
            out[k.json] = max(out.get(k.json, 0), k.levels)
    return list(out.items())


def owner(folder: Path | str) -> tuple[Plugin, Kind, dict] | None:
    """(plugin, kind, json data) of the unit at `folder` (or the unit json above a sub-report); None when none."""
    from . import units
    path = units.unit_json(folder)
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf8"))
    data = data if isinstance(data, dict) else {}
    named = data.get("plugin")
    cands = [get(named)] if named else list(plugins().values())
    for p in cands:
        for k in p.kinds:
            if k.json == path.name and (k.match is None or k.match(data)):
                return p, k, data
    if named:
        sys.exit(f"{path}: plugin {named!r} has no kind for {path.name}")
    return None


def claimant(target: str) -> Plugin | None:
    """The first plugin whose `claims` accepts a target that is not a unit folder (e.g. a league url)."""
    for p in plugins().values():
        if p.claims and p.claims(target):
            return p
    return None
