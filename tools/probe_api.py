import bpy

print('VERSION', bpy.app.version_string)
scene = bpy.context.scene
print('SCENE_COMPOSITING', [(p.identifier, p.type) for p in scene.bl_rna.properties if 'compos' in p.identifier or 'node' in p.identifier])
tree = bpy.data.node_groups.new('ASCII API probe', 'CompositorNodeTree')
for node_type in ('NodeGroupInput', 'NodeGroupOutput', 'CompositorNodeRLayers', 'CompositorNodeImageCoordinates', 'CompositorNodeImageInfo', 'CompositorNodeMapUV', 'CompositorNodePixelate', 'CompositorNodeBlur', 'CompositorNodeFilter', 'CompositorNodeRGBToBW', 'ShaderNodeMath', 'ShaderNodeSeparateXYZ', 'ShaderNodeCombineXYZ', 'ShaderNodeMix', 'ShaderNodeVectorMath', 'CompositorNodeSetAlpha', 'CompositorNodeImage', 'CompositorNodeSeparateColor', 'CompositorNodeCombineColor'):
    try:
        node = tree.nodes.new(node_type)
        print('NODE', node_type, 'IN', [(s.name, s.bl_idname, str(getattr(s, 'default_value', ''))) for s in node.inputs], 'OUT', [s.name for s in node.outputs])
        print('PROPS', [(p.identifier, p.type, [i.identifier for i in p.enum_items] if p.type == 'ENUM' else '') for p in node.bl_rna.properties if not p.is_readonly and p.identifier not in bpy.types.Node.bl_rna.properties and not p.identifier.startswith('bl_')])
    except Exception as e:
        print('UNSUPPORTED', node_type, str(e))
print('RENDER_PROPS', [(p.identifier, p.type) for p in scene.render.bl_rna.properties if 'compos' in p.identifier])
print('SHADING_PROPS', [(p.identifier, p.type) for p in bpy.types.View3DShading.bl_rna.properties if 'compos' in p.identifier])
print('EXTENSION', bpy.utils.extension_path_user)
