#!/usr/bin/env python3
"""Per-frame object visibility for analysis only (never a model input or gate).

visibility = visible-mask pixels / amodal GT silhouette pixels inside the image.
The amodal silhouette is rendered from the GT object pose on a padded canvas so
that truncation by the image border is reported separately (in_image_fraction)
instead of being counted as occlusion. Frames whose in-image silhouette is empty
have undefined visibility and are flagged.
"""
import argparse
import csv
import json
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'third_party/FoundationPose'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True, help='New CSV file')
    p.add_argument('--split', default='validation')
    a = p.parse_args()
    if a.output.exists(): p.error('output exists')
    import torch
    import nvdiffrast.torch as dr
    from PIL import Image
    from Utils import nvdiffrast_render, make_mesh_tensors
    from robot_conditioned_pose.omy_sequence import open_sequence
    snapshot = json.loads((ROOT / 'configs/omy_pilot_manifest_20261124.json').read_text())['sequences']
    names = sorted(n for n, r in snapshot.items() if r['split'] == a.split)
    glctx = dr.RasterizeCudaContext()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['sequence', 'frame', 'timestamp_s', 'visible_px', 'amodal_in_image_px', 'amodal_total_px',
                    'in_image_fraction', 'visibility', 'mask_outside_amodal_px', 'flag'])
        for name in names:
            seq = open_sequence(a.dataset / snapshot[name]['path'])
            H, W = 480, 640
            K = np.asarray(seq.K, dtype=np.float64).copy(); K[0, 2] += W; K[1, 2] += H  # 3x padded canvas
            mesh_tensors = make_mesh_tensors(seq.mesh)
            for i, frame in enumerate(seq.frames):
                pose = seq.target(i).float().cuda()[None]
                _, depth, _ = nvdiffrast_render(K=K, H=3 * H, W=3 * W, ob_in_cams=pose, glctx=glctx,
                                                mesh_tensors=mesh_tensors, output_size=(3 * H, 3 * W))
                amodal = (depth[0] > 0).cpu().numpy()
                inside = amodal[H:2 * H, W:2 * W]
                mask = np.asarray(Image.open(seq.path / 'masks' / (frame['frame_id'] + '.png'))) > 0
                total, in_img = int(amodal.sum()), int(inside.sum())
                visible = int((mask & inside).sum())
                flag = 'empty_in_image_silhouette' if in_img == 0 else ''
                w.writerow([name, i, f"{frame['timestamp_s']:.6f}", visible, in_img, total,
                            f'{in_img / total:.6f}' if total else '', f'{visible / in_img:.6f}' if in_img else '',
                            int((mask & ~inside).sum()), flag])
                torch.set_default_tensor_type('torch.FloatTensor')
            print(name, flush=True)


if __name__ == '__main__':
    main()
