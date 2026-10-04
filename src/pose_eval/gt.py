"""Locate the ground-truth pose file of each frame in a YCBInEOAT scene."""


def gt_pose_paths(scene_dir):
    """Map frame id -> annotated pose file.

    Some sequences name poses after the frame id (cracker_box_reorient), others by index
    (mustard0: 0000000.txt, ...). Names are used when they match the frame ids; otherwise the
    i-th pose file belongs to the i-th frame in sorted order, which needs equal counts.
    """
    from pathlib import Path

    scene = Path(scene_dir)
    frame_ids = sorted(p.stem for p in (scene / "rgb").glob("*.png"))
    pose_files = sorted((scene / "annotated_poses").glob("*.txt"))
    by_name = {p.stem: p for p in pose_files}
    if all(frame_id in by_name for frame_id in frame_ids):
        return {frame_id: by_name[frame_id] for frame_id in frame_ids}
    if len(pose_files) != len(frame_ids):
        raise ValueError(f"{len(frame_ids)} frames but {len(pose_files)} pose files, and names do not match")
    return dict(zip(frame_ids, pose_files))
