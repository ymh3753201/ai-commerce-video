#!/usr/bin/env python3
"""Validate, normalize, and stitch generated MP4 clips into a final video."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from _common import ScriptError, media_summary, require_ffmpeg, sha256_file, verify_media_file


def collect_clips(project_dir: Path, explicit: list[str]) -> list[Path]:
    if explicit:
        clips = [Path(item).expanduser().resolve() for item in explicit]
    else:
        clips = sorted((project_dir / "clips").glob("shot_*.mp4"))
    missing = [str(path) for path in clips if not path.exists()]
    if missing:
        raise ScriptError(f"Missing clips: {missing}")
    if not clips:
        raise ScriptError("No clips found")
    return clips


def parse_fps(value: str | None) -> int:
    if not value:
        return 30
    try:
        if "/" in value:
            num, den = value.split("/", 1)
            return max(1, round(float(num) / float(den)))
        return max(1, round(float(value)))
    except (TypeError, ValueError, ZeroDivisionError):
        return 30


def resolve_target(clips: list[Path], target_resolution: str | None, target_fps: int | None) -> tuple[int, int, int]:
    first = media_summary(clips[0])
    video = first.get("video") or {}
    if target_resolution:
        width_s, height_s = target_resolution.lower().split("x", 1)
        width, height = int(width_s), int(height_s)
    else:
        width = int(video.get("width") or 720)
        height = int(video.get("height") or 1280)
    fps = int(target_fps or parse_fps(video.get("fps")))
    return width, height, fps


def concat_escape(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")


def write_concat_list(path: Path, clips: list[Path]) -> None:
    path.write_text("".join(f"file '{concat_escape(clip)}'\n" for clip in clips), encoding="utf-8")


def run(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        raise ScriptError(f"Command failed: {' '.join(cmd)}\n{exc.stderr[-1200:]}") from exc


def normalize_clip(src: Path, dest: Path, width: int, height: int, fps: int, crf: int, preset: str, require_audio: bool) -> dict:
    summary = media_summary(src)
    has_audio = bool(summary.get("has_audio"))
    if require_audio and not has_audio:
        raise ScriptError(
            f"Required commerce speech audio is missing from {src}; refusing to synthesize silence and call it valid"
        )
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1,fps={fps},format=yuv420p"
    )
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if not has_audio:
        duration = max(float(summary.get("duration_seconds") or 0), 0.1)
        cmd.extend(["-f", "lavfi", "-t", f"{duration:.3f}", "-i", "anullsrc=r=48000:cl=stereo"])
    cmd.extend(["-map", "0:v:0"])
    if has_audio:
        cmd.extend(["-map", "0:a:0"])
    else:
        cmd.extend(["-map", "1:a:0"])
    cmd.extend([
        "-vf", vf,
        "-r", str(fps),
        "-vsync", "cfr",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-af", "aresample=48000:first_pts=0,asetpts=PTS-STARTPTS",
        "-c:a", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",
        str(dest),
    ])
    run(cmd)
    return verify_media_file(dest, require_audio=require_audio)


def concat_with_single_audio_encode(clips: list[Path], concat_list: Path, output: Path) -> None:
    write_concat_list(concat_list, clips)
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-map", "0:v:0", "-map", "0:a:0",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        str(output),
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True, help="Project folder containing clips/")
    parser.add_argument("--clips", nargs="*", default=[], help="Explicit MP4 clips in order")
    parser.add_argument("--output", help="Final MP4 path")
    parser.add_argument("--target-resolution", help="Normalize to WIDTHxHEIGHT, e.g. 720x1280")
    parser.add_argument("--target-fps", type=int, default=30, help="Normalize to this constant frame rate")
    parser.add_argument("--crf", type=int, default=18, help="H.264 CRF for normalization")
    parser.add_argument("--preset", default="medium", help="FFmpeg libx264 preset")
    parser.add_argument("--no-normalize", action="store_true", help="Skip normalization and only concat-copy compatible clips")
    parser.add_argument("--require-audio", action="store_true", help="Require audio stream in final output")
    parser.add_argument("--dry-run", action="store_true", help="Probe clips and create concat list only; do not render")
    args = parser.parse_args()

    try:
        require_ffmpeg()
        project_dir = Path(args.project_dir).expanduser().resolve()
        clips = collect_clips(project_dir, args.clips)
        output = Path(args.output).expanduser().resolve() if args.output else project_dir / "final.mp4"
        concat_list = project_dir / "concat-list.txt"
        temp_dir = project_dir / ".stitch_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        width, height, fps = resolve_target(clips, args.target_resolution, args.target_fps)
        input_summaries = [media_summary(clip) for clip in clips]
        report = {
            "clips": [str(clip) for clip in clips],
            "clip_sha256": [sha256_file(clip) for clip in clips],
            "input_media": input_summaries,
            "concat_list": str(concat_list),
            "output": str(output),
            "target": {"width": width, "height": height, "fps": fps, "codec": "libx264", "audio_codec": "aac", "audio_sample_rate": 48000},
            "normalized": not args.no_normalize,
            "dry_run": args.dry_run,
            "audio_boundary_policy": "preserve_incoming_first_phoneme_no_fade_or_crossfade",
            "per_clip_fades_applied": False,
            "crossfade_applied": False,
            "intermediate_audio_codec": "pcm_s16le",
            "single_final_aac_encode": True,
        }
        cumulative = 0.0
        boundaries = []
        for summary in input_summaries[:-1]:
            cumulative += float(summary.get("duration_seconds") or 0)
            boundaries.append(round(cumulative, 3))
        report["boundary_seconds"] = boundaries
        write_concat_list(concat_list, clips)
        if args.dry_run:
            print(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
            return 0

        output.parent.mkdir(parents=True, exist_ok=True)
        if args.no_normalize:
            if len(clips) == 1:
                shutil.copy2(clips[0], output)
                report["single_final_aac_encode"] = False
            else:
                concat_with_single_audio_encode(clips, concat_list, output)
        else:
            normalized: list[Path] = []
            normalized_reports = []
            for index, clip in enumerate(clips, start=1):
                dest = temp_dir / f"norm_{index:04d}.mkv"
                normalized_reports.append(normalize_clip(clip, dest, width, height, fps, args.crf, args.preset, require_audio=args.require_audio))
                normalized.append(dest)
            norm_concat_list = temp_dir / "concat-normalized.txt"
            concat_with_single_audio_encode(normalized, norm_concat_list, output)
            report["normalized_media"] = normalized_reports
            report["normalized_concat_list"] = str(norm_concat_list)

        media = verify_media_file(output, require_audio=args.require_audio)
        report["final_media"] = media
        report["output_sha256"] = sha256_file(output)
        report_file = output.with_suffix(".stitch-report.json")
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, **report, "report_file": str(report_file)}, ensure_ascii=False, indent=2))
        return 0
    except (ScriptError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
