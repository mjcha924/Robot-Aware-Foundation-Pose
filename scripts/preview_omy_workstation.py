"""Compose a static NVIDIA packing-table/OMY review scene; no task physics."""
import argparse
from pathlib import Path
import json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--headless', action='store_true')
parser.add_argument('--environment-usd')
parser.add_argument('--target-usd')
parser.add_argument('--background-config', type=Path)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--robot-usd', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
from isaacsim import SimulationApp
app = SimulationApp({'headless': args.headless, 'width': 1280, 'height': 720})
try:
    import omni.usd
    import omni.replicator.core as rep
    from pxr import UsdGeom, UsdLux, UsdShade, Sdf, Gf, Usd
    from omni.kit.viewport.utility import get_active_viewport
    import numpy as np
    from PIL import Image

    context = omni.usd.get_context()
    context.new_stage()
    stage = context.get_stage()
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    world = UsdGeom.Xform.Define(stage, '/World')
    stage.SetDefaultPrim(world.GetPrim())
    if args.environment_usd:
        environment = UsdGeom.Xform.Define(stage, '/World/Environment')
        environment.GetPrim().GetReferences().AddReference(args.environment_usd)
    else:
        settings = json.loads(args.background_config.read_text())['background'] if args.background_config else {}
        for name, position, size, color, roughness in [
            ('Floor', (0,0,-0.06), (12,12,0.12), settings.get('floor_color',[0.24,0.25,0.26]), settings.get('floor_roughness',0.72)),
            ('Wall', (0,2.8,2.5), (12,0.15,5), settings.get('wall_color',[0.70,0.68,0.64]), settings.get('wall_roughness',0.9)),
        ]:
            surface = UsdGeom.Cube.Define(stage, '/World/Background/' + name)
            surface.CreateSizeAttr(1)
            surface.AddTranslateOp().Set(Gf.Vec3d(*position))
            surface.AddScaleOp().Set(Gf.Vec3f(*size))
            material = UsdShade.Material.Define(stage, '/World/Looks/' + name)
            shader = UsdShade.Shader.Define(stage, str(material.GetPath()) + '/Shader')
            shader.CreateIdAttr('UsdPreviewSurface')
            shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
            shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(roughness)
            shader.CreateInput('metallic', Sdf.ValueTypeNames.Float).Set(0)
            material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
            UsdShade.MaterialBindingAPI.Apply(surface.GetPrim()).Bind(material)
    table = UsdGeom.Xform.Define(stage, '/World/PackingTable')
    table.GetPrim().GetReferences().AddReference('https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.2/Isaac/Props/PackingTable/packing_table.usd')
    # Upstream ROBOTIS also references this asset at unit scale in a metre stage.
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render'])
    bounds = {}
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh) or 'HeavyDuty' in prim.GetName():
            box = cache.ComputeWorldBound(prim).ComputeAlignedRange()
            bounds[str(prim.GetPath())] = [list(box.GetMin()), list(box.GetMax())]
    (args.output / 'table_bounds.json').write_text(json.dumps(bounds, indent=2))
    bench_path = '/World/PackingTable/SM_CratePacking_Table_A1/SM_HeavyDutyPackingTable_C02_01'
    bench = stage.GetPrimAtPath(bench_path)
    if not bench:
        raise RuntimeError('Expected NVIDIA bench prim is missing')
    bench_box = cache.ComputeWorldBound(bench).ComputeAlignedRange()
    height = bench_box.GetMax()[2]
    # Remove surrounding crates only in this composition; keep the source intact.
    group = stage.GetPrimAtPath('/World/PackingTable/SM_CratePacking_Table_A1')
    for child in group.GetChildren():
        if child.GetName() != 'SM_HeavyDutyPackingTable_C02_01':
            child.SetActive(False)
    container = stage.GetPrimAtPath('/World/PackingTable/container_h20')
    if container:
        container.SetActive(False)
    robot = UsdGeom.Xform.Define(stage, '/World/Robot')
    robot.GetPrim().GetReferences().AddReference(str(args.robot_usd.resolve()))
    robot.AddTranslateOp().Set(Gf.Vec3d(0, 0.12, height))
    if args.target_usd:
        target = UsdGeom.Xform.Define(stage, '/World/Target')
        visual = UsdGeom.Xform.Define(stage, '/World/Target/Asset')
        visual.GetPrim().GetReferences().AddReference(args.target_usd)
        target_box = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render']).ComputeWorldBound(visual.GetPrim()).ComputeAlignedRange()
        low, high = target_box.GetMin(), target_box.GetMax()
        target.AddTranslateOp().Set(Gf.Vec3d(0.22 - (low[0]+high[0])/2, -0.16 - (low[1]+high[1])/2, height - low[2] + 0.001))
        (args.output / 'target_inspection.json').write_text(json.dumps({'source': args.target_usd, 'size_stage_units': list(high-low), 'scale': 1, 'physics_validated': False}, indent=2))
    dome = UsdLux.DomeLight.Define(stage, '/World/Fill')
    dome.CreateIntensityAttr(1000)
    key = UsdLux.RectLight.Define(stage, '/World/Key')
    key.CreateIntensityAttr(1800)
    key.CreateWidthAttr(2)
    key.CreateHeightAttr(2)
    UsdGeom.Xformable(key).AddTranslateOp().Set(Gf.Vec3d(0, 0, 3))
    cameras = {
        'overview': ((3, -4, 2.7), (0, 0, height)),
        'sensor': ((1.25, -1.9, height + 1.0), (0, -0.1, height + 0.40)),
    }
    products = []
    for name, (eye, target) in cameras.items():
        camera = UsdGeom.Camera.Define(stage, '/World/' + name)
        transform = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*target), Gf.Vec3d(0, 0, 1)).GetInverse()
        UsdGeom.Xformable(camera).AddTransformOp().Set(transform)
        camera.CreateClippingRangeAttr(Gf.Vec2f(0.01, 100))
        camera.CreateFocalLengthAttr(24)
        product = rep.create.render_product(str(camera.GetPath()), (640, 480))
        annotator = rep.AnnotatorRegistry.get_annotator('rgb')
        annotator.attach(product)
        products.append((name, annotator))
    viewport = get_active_viewport()
    if viewport:
        viewport.camera_path = '/World/overview'
    for _ in range(60):
        app.update()
    rep.orchestrator.step(rt_subframes=8)
    for name, annotator in products:
        pixels = annotator.get_data()
        if pixels.size == 0:
            raise RuntimeError('Empty camera image: ' + name)
        Image.fromarray(pixels).save(args.output / (name + '.png'))
    stage.GetRootLayer().Export(str((args.output / 'workstation.usda').resolve()))
    print('PREVIEW_READY', str(args.output), 'bench_top', height, flush=True)
    if not args.headless:
        while app.is_running():
            app.update()
except Exception:
    import traceback
    traceback.print_exc()
    raise
finally:
    app.close()
