"""Reversible preview. Screen ID bookmarks survive .blend saves and reloads."""
import sys
import bpy
from bpy.app.handlers import persistent

KEY = '_ascii_render_viewport_state'
BACKUP_KEY = '_ascii_render_viewport_backup'
_owner = object()
_busy = False
_topology = None


def _records(screen):
    records = screen.get(KEY)
    # Deep-copy arrays too: replacing an IDProperty group invalidates its views.
    return records.to_dict() if records is not None else {}


def _write(screen, records):
    if records:
        if records != _records(screen):
            screen[KEY] = records
    elif KEY in screen:
        del screen[KEY]


def _spaces(screen):
    for area in screen.areas:
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                yield space


def _resolve(screen, record, loaded=False):
    # Live pointers survive splits/reordering; RNA paths locate serialized spaces.
    space = next((s for s in _spaces(screen) if str(s.as_pointer()) == record['space']), None)
    # Duplicating a window/workspace copies Screen bookmarks as well. Their
    # old pointers still belong to the source screen, but paths identify clones.
    cloned = space is None and any(str(s.as_pointer()) == record['space']
        for other in bpy.data.screens if other != screen for s in _spaces(other))
    if space is None and (loaded or cloned):
        try:
            candidate = screen.path_resolve(record['path'])
            if candidate.type == 'VIEW_3D':
                space = candidate
        except (ValueError, AttributeError):
            pass
    return space


def _rect(screen, space):
    area = next(a for a in screen.areas if any(s == space for s in a.spaces))
    return [area.x, area.y, area.width, area.height]


def _contains(parent, child):
    return (parent[0] <= child[0] and parent[1] <= child[1]
            and parent[0] + parent[2] >= child[0] + child[2]
            and parent[1] + parent[3] >= child[1] + child[3])


def _same_view(a, b):
    if a is None or b is None or a.region_3d is None or b.region_3d is None:
        return False
    return (a.shading.type == b.shading.type
            and tuple(a.region_3d.view_rotation) == tuple(b.region_3d.view_rotation)
            and tuple(a.region_3d.view_location) == tuple(b.region_3d.view_location)
            and a.region_3d.view_distance == b.region_3d.view_distance)


def _inherited(screen, scene, space, parents):
    rectangle = _rect(screen, space)
    for parent in parents:
        inside = 'rect' in parent and _contains(parent['rect'], rectangle)
        pending = rectangle[2:] == [0, 0] and _same_view(space, _resolve(screen, parent))
        if (parent['scene'] == scene.name and not parent.get('released', False)
                and space.shading.use_compositor == parent['assigned']
                and (inside or pending) and list(parent.get('rect', ())) != rectangle):
            return parent['original']
    return None


def _restore(space, record):
    if (space is not None and not record.get('released', False)
            and space.shading.use_compositor == record['assigned']):
        space.shading.use_compositor = record['original']


def restore(scene=None, *, loaded=False):
    # Adopt inherited spaces even if disable/remove beats their first event.
    if not _busy:
        sync_all(loaded=loaded)
    for screen in getattr(bpy.data, 'screens', ()):
        records = _records(screen)
        for key, record in list(records.items()):
            if scene is None or record['scene'] == scene.name:
                _restore(_resolve(screen, record, loaded), record)
                del records[key]
        _write(screen, records)
    for owner in getattr(bpy.data, 'scenes', ()):
        if (scene is None or owner == scene) and BACKUP_KEY in owner:
            del owner[BACKUP_KEY]


def _active(scene):
    from .compositor import effect_node
    return (hasattr(scene, 'ascii_render') and scene.ascii_render.enabled
            and getattr(scene.ascii_render, 'preview_in_viewport', False)
            and effect_node(scene) is not None)


def sync_all(*, loaded=False):
    global _busy
    if _busy or not hasattr(bpy.data, 'screens'):
        return
    _busy = True
    try:
        visible = {}
        for manager in bpy.data.window_managers:
            for window in manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        space = area.spaces.active
                        visible[space.as_pointer()] = (window.scene, window.screen, space)
        # Fullscreen moves a space into a temporary Screen, which is destroyed
        # on exit. A per-space Scene backup survives that deletion, including
        # when preview was first enabled while already in fullscreen.
        for scene, screen, space in visible.values():
            key = str(space.as_pointer())
            records = _records(screen)
            if key in records:
                continue
            backup = scene.get(BACKUP_KEY, {}).get(key)
            if backup is not None:
                record = backup.to_dict()
                record['path'] = space.path_from_id()
                records[key] = record
                _write(screen, records)
        provenance = {screen.as_pointer(): list(_records(screen).values()) for screen in bpy.data.screens}
        for screen in bpy.data.screens:
            migrated = {}
            for record in _records(screen).values():
                space = _resolve(screen, record, loaded)
                if space is None:
                    continue  # Never transfer a closed space's ownership to a new one.
                scene = bpy.data.scenes.get(record['scene'])
                current = visible.get(space.as_pointer())
                if scene is None or not _active(scene) or current and current[0] != scene:
                    _restore(space, record)
                    continue
                if space.shading.use_compositor != record['assigned']:
                    record['released'] = True  # Respect manual edits until the next toggle.
                record['space'], record['path'] = str(space.as_pointer()), space.path_from_id()
                record['rect'] = _rect(screen, space)
                migrated[record['space']] = record
            _write(screen, migrated)
        for scene, screen, space in visible.values():
            inherited = _inherited(screen, scene, space, provenance[screen.as_pointer()])
            if not _active(scene):
                # A user may disable preview before a new split's first event.
                if inherited is not None:
                    space.shading.use_compositor = inherited
                continue
            records = _records(screen)
            key = str(space.as_pointer())
            record = records.get(key)
            if record is None:
                previous = space.shading.use_compositor
                rectangle = _rect(screen, space)
                # A split inherits ALWAYS from its parent. Its original value
                # comes from the parent's pre-split bookmark, not that copy.
                if inherited is not None:
                    previous = inherited
                record = dict(space=key, path=space.path_from_id(), scene=scene.name,
                              original=previous, rect=rectangle,
                              assigned=scene.ascii_render.preview_mode, released=False)
            if not record['released']:
                record['assigned'] = scene.ascii_render.preview_mode
                space.shading.use_compositor = record['assigned']
            records[key] = record
            _write(screen, records)
        backups = {}
        for screen in bpy.data.screens:
            for key, record in _records(screen).items():
                backups.setdefault(record['scene'], {})[key] = record
        for scene in bpy.data.scenes:
            records = backups.get(scene.name, {})
            if records:
                old = scene.get(BACKUP_KEY)
                if old is None or old.to_dict() != records:
                    scene[BACKUP_KEY] = records
            elif BACKUP_KEY in scene:
                del scene[BACKUP_KEY]
        if any(_active(s) for s in bpy.data.scenes) and not bpy.app.timers.is_registered(_watch):
            bpy.app.timers.register(_watch, first_interval=0.75)
    finally:
        _busy = False


def _inventory():
    return tuple((w.as_pointer(), w.scene.as_pointer(), w.screen.as_pointer(),
                  tuple((a.as_pointer(), a.type, a.spaces.active.as_pointer()) for a in w.screen.areas))
                 for m in bpy.data.window_managers for w in m.windows)


def _watch():
    # RNA misses some splits/new windows. Check only topology at most every
    # 0.75 seconds while preview is on, never per redraw or depsgraph update.
    global _topology
    topology = _inventory()
    if topology != _topology:
        _topology = topology
        sync_all()
    return 0.75 if any(_active(s) for s in bpy.data.scenes) else None


def _changed():
    sync_all()


def _subscribe():
    bpy.msgbus.clear_by_owner(_owner)
    for owner, prop in ((bpy.types.Window, 'workspace'), (bpy.types.Window, 'screen'),
                        (bpy.types.Window, 'scene'), (bpy.types.Area, 'type'),
                        (bpy.types.View3DShading, 'use_compositor')):
        bpy.msgbus.subscribe_rna(key=(owner, prop), owner=_owner, args=(), notify=_changed)


@persistent
def load_pre(_):
    restore()


@persistent
def load_post(_):
    _subscribe()
    sync_all(loaded=True)


@persistent
def undo_post(_):
    sync_all(loaded=True)


def register_handlers():
    _subscribe()
    for collection, callback in ((bpy.app.handlers.load_pre, load_pre),
                                 (bpy.app.handlers.load_post, load_post),
                                 (bpy.app.handlers.undo_post, undo_post),
                                 (bpy.app.handlers.redo_post, undo_post)):
        if callback not in collection:
            collection.append(callback)


def unregister_handlers(*, all_copies=False):
    def owned(name):
        return name == __name__ or all_copies and (name == 'ascii_render.viewport' or name.endswith('.ascii_render.viewport'))
    restore()
    for collection in (bpy.app.handlers.load_pre, bpy.app.handlers.load_post,
                       bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        for callback in list(collection):
            if owned(getattr(callback, '__module__', '')):
                collection.remove(callback)
    for name, module in tuple(sys.modules.items()):
        if module is not None and owned(name):
            owner = getattr(module, '_owner', None)
            if owner is not None:
                bpy.msgbus.clear_by_owner(owner)
            watch = getattr(module, '_watch', None)
            if watch is not None and bpy.app.timers.is_registered(watch):
                bpy.app.timers.unregister(watch)
