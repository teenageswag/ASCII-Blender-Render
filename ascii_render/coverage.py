"""Object and world masks from one shader AOV, without material duplication."""

import bpy
import sys
from bpy.app.handlers import persistent

AOV_NAME = 'ASCII_RenderMask'
EXCLUDE_KEY = '_ascii_render_exclude'
OWNED = 'ascii_render_mask_owned'
DEFAULT_SLOT = '_ascii_render_default_slot'
AOV_LAYERS = '_ascii_render_aov_layers'
DIFFUSE_LAYERS = '_ascii_render_diffuse_layers'
_busy = False
_pending = set()


def needs_mask(scene):
    return (scene.ascii_render.world_mode != 'ASCII'
            or any(obj.get(EXCLUDE_KEY, 0) for obj in scene.objects))


def _set(socket, value):
    if socket.default_value != value:
        socket.default_value = value


def _default_material():
    material = next((m for m in bpy.data.materials if m.get(OWNED) == 'default'), None)
    if material is None:
        material = bpy.data.materials.new('ASCII • Default Surface')
        material[OWNED] = 'default'
    return material


def _prepare_material(material):
    if material.library or material.node_tree is None:
        return
    tree = material.node_tree
    if any(n.get(OWNED) and n.type == 'OUTPUT_AOV' for n in tree.nodes):
        return
    attribute = tree.nodes.new('ShaderNodeAttribute')
    attribute.attribute_type = 'OBJECT'
    attribute.attribute_name = EXCLUDE_KEY
    attribute.label = 'ASCII: object exclusion'
    combine = tree.nodes.new('ShaderNodeCombineXYZ')
    combine.inputs['Y'].default_value = 1
    combine.label = 'ASCII: exclusion / surface coverage'
    output = tree.nodes.new('ShaderNodeOutputAOV')
    output.aov_name = AOV_NAME
    output.label = 'ASCII Render Mask'
    for index, node in enumerate((attribute, combine, output)):
        node[OWNED] = True
        node.location = (-600 + index * 220, -500)
    tree.links.new(attribute.outputs['Fac'], combine.inputs['X'])
    tree.links.new(combine.outputs[0], output.inputs['Color'])


def sync_scene(scene):
    """Prepare masks only for scenes that use object/world filtering."""
    global _busy
    from . import compositor
    if _busy or not hasattr(scene, 'ascii_render'):
        return
    effect = compositor.effect_node(scene)
    if effect is None:
        return
    if effect.node_tree.get('ascii_schema', 0) < compositor.SCHEMA:
        compositor.upgrade(scene)
        effect = compositor.effect_node(scene)
    active = needs_mask(scene)
    _set(effect.inputs['Use Object Mask'], float(active))
    analysis = scene.ascii_render.match_mode == 'SMART'
    diffuse = scene.ascii_render.color_source == 'DIFFUSE'
    if not diffuse and effect.inputs['Albedo'].is_linked:
        for link in list(effect.inputs['Albedo'].links):
            scene.compositing_node_group.links.remove(link)
    if not (active or analysis or diffuse):
        return
    _busy = True
    try:
        owned_layers = dict(scene.get(AOV_LAYERS, {}))
        diffuse_layers = dict(scene.get(DIFFUSE_LAYERS, {}))
        passes_changed = False
        for layer in scene.view_layers:
            if diffuse and not layer.use_pass_diffuse_color:
                layer.use_pass_diffuse_color = True
                diffuse_layers[layer.name] = True
                passes_changed = True
            if not any(a.name == AOV_NAME for a in layer.aovs):
                entry = layer.aovs.add()
                entry.name = AOV_NAME
                entry.type = 'COLOR'
                owned_layers[layer.name] = True
                passes_changed = True
            if layer.material_override:
                _prepare_material(layer.material_override)
        if owned_layers != dict(scene.get(AOV_LAYERS, {})):
            scene[AOV_LAYERS] = owned_layers
        if diffuse_layers != dict(scene.get(DIFFUSE_LAYERS, {})):
            scene[DIFFUSE_LAYERS] = diffuse_layers
        for obj in scene.objects:
            data = obj.data
            if data is None or not hasattr(data, 'materials'):
                continue
            if len(data.materials) == 0:
                if data.library:
                    continue
                data.materials.append(_default_material())
                data[DEFAULT_SLOT] = True
            for slot in obj.material_slots:
                if slot.material is None:
                    slot.material = _default_material()
                _prepare_material(slot.material)
        tree = scene.compositing_node_group
        source = next((n for n in tree.nodes if n.get(OWNED) == 'source'), None)
        if source is None:
            source = tree.nodes.new('CompositorNodeRLayers')
            source[OWNED] = 'source'
            source.label = 'ASCII: object / world mask'
            source.scene = scene
            source.location = (effect.location.x - 240, effect.location.y - 420)
            passes_changed = True
        requested = scene.ascii_render.mask_view_layer
        if requested not in scene.view_layers:
            main = next((n for n in tree.nodes if n.type == 'R_LAYERS'
                         and not n.get(OWNED) and (n.scene is None or n.scene == scene)), None)
            requested = main.layer if main and main.layer in scene.view_layers else scene.view_layers[0].name
        if source.layer != requested:
            source.layer = requested
            passes_changed = True
        if passes_changed:
            source.update()
        output = source.outputs.get(AOV_NAME)
        if output is not None:
            target = effect.inputs['Object Mask']
            if not target.is_linked or target.links[0].from_socket != output:
                tree.links.new(output, target)
        if diffuse and source.outputs.get('Diffuse Color') is not None:
            target = effect.inputs['Albedo']
            output = source.outputs['Diffuse Color']
            if not target.is_linked or target.links[0].from_socket != output:
                tree.links.new(output, target)
    finally:
        _busy = False


def cleanup_unused():
    """Remove owned shader nodes and empty-slot substitutes after the last use."""
    from .compositor import effect_node
    if any(effect_node(scene) and (needs_mask(scene) or scene.ascii_render.match_mode == 'SMART'
                                 or scene.ascii_render.color_source == 'DIFFUSE') for scene in bpy.data.scenes):
        return
    for material in bpy.data.materials:
        if material.library or not material.node_tree:
            continue
        for node in list(material.node_tree.nodes):
            if node.get(OWNED):
                material.node_tree.nodes.remove(node)
    seen = set()
    for obj in bpy.data.objects:
        data = obj.data
        if data is None or not hasattr(data, 'materials') or data.library or data.as_pointer() in seen:
            continue
        seen.add(data.as_pointer())
        if data.get(DEFAULT_SLOT):
            if len(data.materials) and data.materials[0] and data.materials[0].get(OWNED) == 'default':
                data.materials.pop(index=0)
            del data[DEFAULT_SLOT]
        for slot in obj.material_slots:
            if slot.material and slot.material.get(OWNED) == 'default':
                slot.material = None
    for scene in bpy.data.scenes:
        for layer in scene.view_layers:
            if scene.get(DIFFUSE_LAYERS, {}).get(layer.name):
                layer.use_pass_diffuse_color = False
            if scene.get(AOV_LAYERS, {}).get(layer.name):
                entry = next((a for a in layer.aovs if a.name == AOV_NAME), None)
                if entry:
                    layer.aovs.remove(entry)
        if AOV_LAYERS in scene:
            del scene[AOV_LAYERS]
        if DIFFUSE_LAYERS in scene:
            del scene[DIFFUSE_LAYERS]
    for material in list(bpy.data.materials):
        if material.get(OWNED) == 'default' and material.users == 0:
            bpy.data.materials.remove(material)


@persistent
def load_post(_):
    for scene in bpy.data.scenes:
        sync_scene(scene)


@persistent
def render_pre(scene, *_):
    sync_scene(scene)


def _flush():
    names = tuple(_pending)
    _pending.clear()
    for name in names:
        scene = bpy.data.scenes.get(name)
        if scene:
            sync_scene(scene)
    return None


@persistent
def depsgraph_update(scene, depsgraph):
    # Material assignments and newly created objects need an AOV too. UI updates
    # are deferred outside the dependency graph evaluation; rendering uses the
    # synchronous render_pre hook above.
    if _busy or bpy.app.background or not hasattr(scene, 'ascii_render'):
        return
    from .compositor import effect_node
    if not effect_node(scene) or not (needs_mask(scene) or scene.ascii_render.match_mode == 'SMART'):
        return
    if any(isinstance(update.id, (bpy.types.Object, bpy.types.Material,
                                 bpy.types.Mesh, bpy.types.Collection)) for update in depsgraph.updates):
        _pending.add(scene.name)
        if not bpy.app.timers.is_registered(_flush):
            bpy.app.timers.register(_flush, first_interval=0.25)


def register_handlers():
    for collection, callback in ((bpy.app.handlers.load_post, load_post),
                                 (bpy.app.handlers.render_pre, render_pre),
                                 (bpy.app.handlers.depsgraph_update_post, depsgraph_update)):
        if callback not in collection:
            collection.append(callback)


def unregister_handlers(*, all_copies=False):
    def owned(module):
        return (module == __name__ or all_copies and
                (module == 'ascii_render.coverage' or module.endswith('.ascii_render.coverage')))

    modules = [module for name, module in tuple(sys.modules.items())
               if owned(name) and module is not None]
    callbacks = []
    for collection in (bpy.app.handlers.load_post, bpy.app.handlers.render_pre,
                       bpy.app.handlers.depsgraph_update_post):
        for callback in list(collection):
            if (owned(getattr(callback, '__module__', ''))
                    and getattr(callback, '__name__', '') in {'load_post', 'render_pre', 'depsgraph_update'}):
                callbacks.append(callback)
                collection.remove(callback)
    flushes = {getattr(module, '_flush', None) for module in modules}
    flushes.update(getattr(callback, '__globals__', {}).get('_flush') for callback in callbacks)
    for flush in flushes:
        if flush is not None and bpy.app.timers.is_registered(flush):
            bpy.app.timers.unregister(flush)
    for module in modules:
        pending = getattr(module, '_pending', None)
        if pending is not None:
            pending.clear()
