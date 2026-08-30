#!/usr/bin/env python3
"""Regression tests for the guarded ai-commerce-video production core."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT
SCRIPTS = SKILL / "scripts"
CONFIG = SKILL / "assets" / "templates" / "model-config.example.json"
sys.path.insert(0, str(SCRIPTS))


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key in {
            "AI_COMMERCE_VIDEO_API_KEY",
            "AI_COMMERCE_VIDEO_MIKUAPI_KEY",
            "AI_COMMERCE_VIDEO_119337_KEY",
            "AI_COMMERCE_VIDEO_BASE_URL",
            "AI_COMMERCE_VIDEO_MODEL",
            "AI_COMMERCE_VIDEO_PROXY_URL",
            "AI_COMMERCE_VIDEO_ENV_FILE",
            "YUNWU_API_KEY",
            "XAI_API_KEY",
            "FAL_KEY",
        } or key.startswith("AI_COMMERCE_VIDEO_MODEL_") or key.startswith("AI_COMMERCE_VIDEO_BASE_URL_"):
            env.pop(key, None)
    env["AI_COMMERCE_VIDEO_ENV_FILE"] = str(ROOT / ".nonexistent-test-env")
    env["AI_COMMERCE_VIDEO_DISABLE_KEYCHAIN"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_cmd(args: list[str], expect_ok: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    command_env = clean_env()
    if env:
        command_env.update(env)
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=command_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if expect_ok and result.returncode != 0:
        raise AssertionError(
            f"Command failed: {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    if not expect_ok and result.returncode == 0:
        raise AssertionError(
            f"Command unexpectedly passed: {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def make_test_video(
    path: Path,
    *,
    size: str = "320x240",
    fps: int = 24,
    duration: float = 1.0,
    color: str = "red",
    audio: bool = True,
) -> None:
    if not shutil.which("ffmpeg"):
        raise unittest.SkipTest("ffmpeg is required for media tests")
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={size}:r={fps}:d={duration}",
    ]
    if audio:
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:sample_rate=48000:duration={duration}",
                "-shortest",
            ]
        )
    cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])
    if audio:
        cmd.extend(["-c:a", "aac", "-ar", "48000", "-ac", "2"])
    cmd.extend(["-movflags", "+faststart", str(path)])
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)


class ProductionCoreTests(unittest.TestCase):
    def prepare_project(
        self,
        tmp_path: Path,
        *,
        duration: int = 25,
        subtitle_choice: str = "disabled",
        subtitle_file: Path | None = None,
        spoken_script: str | None = None,
    ) -> tuple[dict, Path]:
        product = tmp_path / "product.png"
        product.write_bytes(b"\x89PNG\r\n\x1a\n")
        command = [
            "python3",
            str(SCRIPTS / "prepare_project.py"),
            "--name",
            "Production Core",
            "--project-root",
            str(tmp_path / "projects"),
            "--product-image",
            str(product),
            "--model-key",
            "grok_video_15",
            "--video-source-image",
            str(product),
            "--duration",
            str(duration),
            "--platform",
            "douyin",
            "--placement",
            "in_feed",
            "--spoken-script",
            spoken_script or "还在为普通水杯容易漏水而烦恼吗？这款密封杯采用可靠杯盖结构，通勤放包里更安心。现在点击商品入口，查看适合你的颜色。",
            "--prompt",
            "A professional presenter demonstrates the approved leak-resistant travel cup in a clean studio.",
            "--subtitle-choice",
            subtitle_choice,
        ]
        if subtitle_choice == "enabled":
            command.extend(["--subtitle-request-source", "user_plan_confirmation"])
        if subtitle_file:
            command.extend(["--subtitle-file", str(subtitle_file)])
        result = run_cmd(command)
        data = json.loads(result.stdout)
        plan_path = Path(data["plan"])
        return json.loads(plan_path.read_text(encoding="utf-8")), plan_path

    def test_25_second_plan_uses_15_and_10_legal_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, _ = self.prepare_project(Path(tmp), duration=25)
            self.assertEqual(plan["duration_plan"]["request_durations_seconds"], [15, 10])
            self.assertEqual([shot["duration_seconds"] for shot in plan["shots"]], [15, 10])
            self.assertTrue(
                all(shot["duration_seconds"] in {4, 6, 8, 10, 12, 15} for shot in plan["shots"])
            )
            self.assertEqual(plan["production_contract"]["base_request_count"], 2)
            self.assertEqual(plan["production_contract"]["approved_paid_cap"], 2)
            self.assertEqual(plan["platform_contract"]["rules_version"], "2026-07-15")
            self.assertEqual(plan["platform_contract"]["verified_at"], "2026-07-15")
            self.assertEqual(plan["platform_contract"]["source_reference"], "references/platform-requirements.md")
            model_contract = plan["model_capability_contract"]
            self.assertEqual(model_contract["official_model_family"], "grok-imagine-video-1.5")
            self.assertEqual(model_contract["provider_model_alias"], "grok-imagine-video-1.5")
            self.assertEqual(model_contract["allowed_duration_seconds"], list(range(1, 16)))

    def test_each_segment_has_unique_script_and_stitch_safe_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, _ = self.prepare_project(Path(tmp), duration=25)
            shots = plan["shots"]
            self.assertNotEqual(shots[0]["spoken_script"], shots[1]["spoken_script"])
            self.assertTrue(shots[0]["script_boundary"]["stitch_safe"])
            self.assertTrue(shots[0]["spoken_script"].endswith(("。", "！", "？", ".", "!", "?")))
            self.assertNotEqual(shots[0]["prompt"], shots[1]["prompt"])
            self.assertEqual(plan["continuity_plan"]["mode"], "planned_cut")
            self.assertTrue(plan["duration_plan_digest"])

    def test_overlong_spoken_script_is_blocked_before_paid_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = None
            with self.assertRaises(AssertionError) as ctx:
                self.prepare_project(
                    Path(tmp),
                    duration=15,
                    spoken_script=(
                        "这款商品拥有非常丰富的第一项功能说明和完整使用场景。"
                        "接下来继续详细介绍第二项功能、第三项功能、材料、尺寸、颜色、价格以及所有优惠信息。"
                        "最后还要补充售后服务、物流安排、适用人群、注意事项并邀请大家立即进入商品页面完成购买。"
                    ),
                )
            result = str(ctx.exception).lower()
            self.assertIn("speech capacity", result)

    def test_provider_prompt_and_payload_never_include_subtitles(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, plan_path = self.prepare_project(Path(tmp), duration=15, subtitle_choice="enabled")
            for shot in plan["shots"]:
                lower_prompt = shot["prompt"].lower()
                self.assertNotIn("captions match", lower_prompt)
                self.assertNotIn("readable captions", lower_prompt)
                self.assertNotIn("keep product, subtitles", lower_prompt)
                for forbidden in ("subtitle", "caption", "srt", "vtt", "lower third", "text overlay", "字幕"):
                    self.assertNotIn(forbidden, lower_prompt)
                self.assertIn("no newly generated written", lower_prompt)
            dry_run = run_cmd(
                [
                    "python3",
                    str(SCRIPTS / "generate_video.py"),
                    "--plan",
                    str(plan_path),
                    "--config",
                    str(CONFIG),
                    "--dry-run",
                ]
            )
            result = json.loads(dry_run.stdout)["results"][0]
            record = json.loads(Path(result["request_file"]).read_text(encoding="utf-8"))
            self.assertFalse(record["asset_trace"]["subtitle_included_in_payload"])
            self.assertTrue(record["asset_trace"]["no_generated_overlay_text_requested"])
            forbidden = {"subtitle", "subtitles", "srt", "vtt", "captions"}
            self.assertFalse(forbidden.intersection(record["payload"]))

    def test_generation_blocks_manually_injected_provider_subtitle_instruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, plan_path = self.prepare_project(Path(tmp), duration=15)
            plan["shots"][0]["prompt"] += " Add readable subtitles and a lower third."
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "generate_video.py"),
                "--plan", str(plan_path), "--config", str(CONFIG), "--dry-run",
            ], expect_ok=False)
            self.assertIn("forbidden subtitle", result.stdout.lower())

    def test_local_subtitle_contract_is_strict_and_zero_paid(self):
        subtitle_policy = importlib.import_module("subtitle_policy")
        enabled = {
            "enabled": True,
            "request_source": "user_plan_confirmation",
            "confirmation_status": "confirmed",
            "provider_policy": "never_send",
            "render_policy": "postproduction_burn_only",
            "paid_api_call": False,
        }
        self.assertTrue(subtitle_policy.is_confirmed_postproduction_subtitle_plan(enabled))
        self.assertEqual(subtitle_policy.enabled_subtitle_contract_errors(enabled), [])
        for field, bad_value in {
            "request_source": "default",
            "confirmation_status": "pending",
            "provider_policy": "provider_caption",
            "render_policy": "provider_render",
            "paid_api_call": True,
            "subtitle_included_in_payload": True,
        }.items():
            invalid = dict(enabled)
            invalid[field] = bad_value
            self.assertFalse(subtitle_policy.is_confirmed_postproduction_subtitle_plan(invalid), field)

    def test_confirmed_srt_is_copied_locally_and_never_sent_to_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_srt = tmp_path / "approved.srt"
            source_srt.write_text("1\n00:00:00,000 --> 00:00:02,000\n密封通勤杯\n", encoding="utf-8")
            plan, plan_path = self.prepare_project(
                tmp_path,
                duration=15,
                subtitle_choice="enabled",
                subtitle_file=source_srt,
            )
            subtitle_plan = plan["subtitle_plan"]
            copied = Path(subtitle_plan["input_subtitle"]["value"])
            self.assertEqual(subtitle_plan["timing_source"], "provided_srt")
            self.assertTrue(copied.is_file())
            self.assertNotEqual(copied.resolve(), source_srt.resolve())
            self.assertFalse(subtitle_plan["subtitle_included_in_payload"])
            run_cmd([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(plan_path), "--config", str(CONFIG),
            ])
            contract = json.loads((plan_path.parent / "production-contract.json").read_text(encoding="utf-8"))
            subtitle_fingerprints = [
                item for item in contract["asset_fingerprints"] if item.get("role") == "approved_subtitle"
            ]
            self.assertEqual(len(subtitle_fingerprints), 1)
            self.assertTrue(subtitle_fingerprints[0]["sha256"])

    def test_provided_srt_local_postproduction_has_zero_provider_or_paid_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_srt = tmp_path / "approved.srt"
            source_srt.write_text("1\n00:00:00,000 --> 00:00:01,500\n密封通勤杯\n", encoding="utf-8")
            plan, plan_path = self.prepare_project(
                tmp_path,
                duration=15,
                subtitle_choice="enabled",
                subtitle_file=source_srt,
            )
            clean_video = plan_path.parent / "final.mp4"
            make_test_video(clean_video, duration=2.0, audio=True)
            subtitle_result = run_cmd([
                "python3", str(SCRIPTS / "generate_subtitles.py"),
                "--plan", str(plan_path), "--video", str(clean_video),
            ])
            subtitle_audit = json.loads(subtitle_result.stdout)
            self.assertFalse(subtitle_audit["provider_payload_used"])
            self.assertFalse(subtitle_audit["paid_api_call"])
            burn_result = run_cmd([
                "python3", str(SCRIPTS / "burn_subtitles.py"),
                "--plan", str(plan_path), "--video", str(clean_video),
                "--srt", subtitle_audit["subtitle"],
                "--output", str(plan_path.parent / "final.captioned.mp4"),
                "--dry-run",
            ])
            burn_audit = json.loads(burn_result.stdout)
            self.assertFalse(burn_audit["provider_payload_used"])
            self.assertFalse(burn_audit["paid_api_call"])

    def test_model_config_rejects_non_discrete_or_out_of_range_duration_slots(self):
        validate_config = importlib.import_module("validate_config")
        base = {
            "provider": "test",
            "base_url": "https://example.invalid/v1",
            "generation_path": "/video/generations",
            "model": "test-video",
            "min_duration_seconds": 4,
            "max_duration_seconds": 15,
            "default_duration_seconds": 15,
            "allowed_duration_seconds": [4, 6, 8, 10, 12, 15],
        }
        self.assertEqual(validate_config.validate_model(base), [])
        duplicate = dict(base, allowed_duration_seconds=[4, 6, 6, 15])
        self.assertTrue(any("allowed_duration_seconds" in issue for issue in validate_config.validate_model(duplicate)))
        outside = dict(base, allowed_duration_seconds=[4, 6, 16])
        self.assertTrue(any("allowed_duration_seconds" in issue for issue in validate_config.validate_model(outside)))
        missing_default = dict(base, allowed_duration_seconds=[4, 6, 8, 10, 12])
        self.assertTrue(any("default_duration_seconds" in issue for issue in validate_config.validate_model(missing_default)))

    def test_grok_config_distinguishes_provider_alias_and_cost_contract(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        model = config["models"]["grok_video_15"]
        self.assertEqual(model["official_model_family"], "grok-imagine-video-1.5")
        self.assertEqual(model["provider_model_alias"], model["model"])
        self.assertEqual(model["billing_unit"], "provider_defined")
        self.assertEqual(model["cost_guard_unit"], "provider_submission")
        self.assertEqual(model["max_paid_submissions_per_shot"], 1)
        self.assertEqual(model["provider_overlay_text_policy"], "forbid_generated_written_elements")

    def test_paid_contract_has_no_repair_reserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, _ = self.prepare_project(Path(tmp), duration=30)
            contract = plan["production_contract"]
            self.assertEqual(contract["base_request_count"], 2)
            self.assertEqual(contract["approved_paid_cap"], 2)
            self.assertEqual(contract["repair_reserve"], 0)
            self.assertEqual(contract["per_shot_repair_limit"], 0)
            self.assertEqual(contract["max_generated_seconds"], 30)

    def test_duplicate_submission_is_blocked_but_resume_is_allowed(self):
        workflow = importlib.import_module("_workflow")
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            shots = [{"id": "shot_01", "duration_seconds": 15}]
            ledger = workflow.load_or_create_jobs(project_dir, shots, approved_paid_cap=1)
            self.assertEqual(workflow.record_submission_attempt(project_dir, ledger, "shot_01"), 1)
            workflow.transition_job(
                project_dir,
                ledger,
                "shot_01",
                "submitted",
                request_id="request-1",
            )
            self.assertEqual(workflow.pollable_request_id(ledger, "shot_01"), "request-1")
            with self.assertRaises(Exception):
                workflow.record_submission_attempt(project_dir, ledger, "shot_01")

    def test_preflight_creates_immutable_contract_without_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, plan_path = self.prepare_project(Path(tmp), duration=25)
            result = run_cmd(
                [
                    "python3",
                    str(SCRIPTS / "preflight_project.py"),
                    "--plan",
                    str(plan_path),
                    "--config",
                    str(CONFIG),
                ]
            )
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"])
            self.assertEqual(report["dry_run_request_count"], 2)
            self.assertEqual(report["expected_paid_requests"], 2)
            self.assertFalse(report["paid_api_call"])
            contract = json.loads(Path(report["contract_file"]).read_text(encoding="utf-8"))
            self.assertEqual(contract["approved_paid_cap"], 2)
            self.assertEqual(contract["repair_reserve"], 0)
            self.assertEqual(contract["duration_plan_digest"], plan["duration_plan_digest"])
            self.assertFalse((plan_path.parent / "jobs.json").exists())

    def test_preflight_defers_missing_optional_subtitle_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, plan_path = self.prepare_project(Path(tmp), duration=15, subtitle_choice="enabled")
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["subtitle_plan"]["lexical_source"], "final_audio_transcript")
            plan["subtitle_plan"]["request_source"] = "default"
            plan["subtitle_plan"]["whisper_executable"] = str(Path(tmp) / "missing-whisper-cli")
            plan["subtitle_plan"]["whisper_model"] = str(Path(tmp) / "missing-whisper-model.bin")
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(plan_path), "--config", str(CONFIG),
            ])
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"])
            self.assertTrue(report["paid_generation_allowed"])
            self.assertTrue(report["subtitle_postproduction_deferred"])
            self.assertTrue(any("whisper" in item.lower() for item in report["subtitle_postproduction_warnings"]))
            self.assertTrue(any("request_source" in item for item in report["subtitle_postproduction_warnings"]))

    def test_platform_validator_blocks_illegal_slot_and_provider_subtitle_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, plan_path = self.prepare_project(Path(tmp), duration=15)
            plan["shots"][0]["duration_seconds"] = 16
            plan["subtitle_plan"]["subtitle_included_in_payload"] = True
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "validate_platform_plan.py"),
                "--plan", str(plan_path), "--config", str(CONFIG),
            ], expect_ok=False)
            text = result.stdout.lower()
            self.assertIn("legal request duration", text)
            self.assertIn("subtitle_included_in_payload", text)

    def test_preflight_itself_blocks_illegal_request_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, plan_path = self.prepare_project(Path(tmp), duration=15)
            plan["shots"][0]["duration_seconds"] = 16
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(plan_path), "--config", str(CONFIG),
            ], expect_ok=False)
            self.assertIn("legal request duration", result.stdout.lower())
            self.assertFalse((plan_path.parent / "production-contract.json").exists())

    def test_preflight_blocks_legal_but_unplanned_duration_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, plan_path = self.prepare_project(Path(tmp), duration=15)
            plan["shots"][0]["duration_seconds"] = 12
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(plan_path), "--config", str(CONFIG),
            ], expect_ok=False)
            self.assertIn("duration_plan", result.stdout.lower())
            self.assertFalse((plan_path.parent / "production-contract.json").exists())

    def test_workflow_confirm_binds_contract_and_creates_base_only_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, plan_path = self.prepare_project(Path(tmp), duration=30)
            run_cmd(
                [
                    "python3",
                    str(SCRIPTS / "preflight_project.py"),
                    "--plan",
                    str(plan_path),
                    "--config",
                    str(CONFIG),
                ]
            )
            result = run_cmd(
                [
                    "python3",
                    str(SCRIPTS / "workflow_engine.py"),
                    "--project-dir",
                    str(plan_path.parent),
                    "confirm",
                    "--approved-by",
                    "offline-test",
                ]
            )
            data = json.loads(result.stdout)
            self.assertTrue(data["ok"])
            confirmation = json.loads((plan_path.parent / "video-confirmation.json").read_text(encoding="utf-8"))
            jobs = json.loads((plan_path.parent / "jobs.json").read_text(encoding="utf-8"))
            self.assertTrue(confirmation["plan_confirmed"])
            self.assertTrue(confirmation["image_assets_confirmed"])
            self.assertTrue(confirmation["video_generation_confirmed"])
            self.assertTrue(confirmation["paid_video_authorized"])
            self.assertEqual(confirmation["approved_paid_cap"], 2)
            self.assertEqual(jobs["approved_paid_cap"], 2)
            self.assertEqual(jobs["paid_submission_attempts"], 0)

    def test_workflow_requires_audio_for_spoken_selling_unless_platform_forbids_audio(self):
        workflow_engine = importlib.import_module("workflow_engine")
        spoken = {
            "creative_contract": {"speaker_mode": "digital-human-spoken"},
            "audio_contract": {"speech_required": True},
            "platform_contract": {"audio_policy": "recommended_with_captions"},
        }
        no_speech_with_sound = {
            "creative_contract": {"speaker_mode": "no-speech"},
            "audio_contract": {"speech_required": False},
            "sound_design_contract": {"non_speech_required": True},
            "platform_contract": {"audio_policy": "recommended_with_captions"},
        }
        no_audio = {
            "creative_contract": {"speaker_mode": "silent-captions"},
            "audio_contract": {"speech_required": False},
            "sound_design_contract": {"non_speech_required": False},
            "platform_contract": {"audio_policy": "no_audio"},
        }
        self.assertTrue(workflow_engine.plan_requires_audio(spoken))
        self.assertTrue(workflow_engine.plan_requires_audio(no_speech_with_sound))
        self.assertFalse(workflow_engine.plan_requires_audio(no_audio))

    def test_workflow_submit_posts_each_shot_at_most_once(self):
        class SubmitHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/v1/models":
                    self.send_error(404)
                    return
                self.server.get_count += 1
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"data": [{"id": "grok-imagine-video-1.5"}]}).encode("utf-8"))

            def do_POST(self):
                self.server.post_count += 1
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"data": {"task_id": "request-1"}}).encode("utf-8"))

            def log_message(self, format, *args):
                return

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            server = HTTPServer(("127.0.0.1", 0), SubmitHandler)
            server.post_count = 0
            server.get_count = 0
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config_data = json.loads(CONFIG.read_text(encoding="utf-8"))
                config_data["models"]["grok_video_15"]["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
                config_path = tmp_path / "local-config.json"
                config_path.write_text(json.dumps(config_data), encoding="utf-8")
                _, plan_path = self.prepare_project(tmp_path, duration=15)
                run_cmd([
                    "python3", str(SCRIPTS / "preflight_project.py"),
                    "--plan", str(plan_path), "--config", str(config_path),
                ])
                run_cmd([
                    "python3", str(SCRIPTS / "workflow_engine.py"),
                    "--project-dir", str(plan_path.parent), "confirm", "--approved-by", "offline-test",
                ])
                env = {"AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key"}
                first = run_cmd([
                    "python3", str(SCRIPTS / "workflow_engine.py"),
                    "--project-dir", str(plan_path.parent), "submit", "--config", str(config_path),
                ], env=env)
                self.assertTrue(json.loads(first.stdout)["ok"])
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                request_file = Path(plan["shots"][0]["request_file"])
                first_request_record = request_file.read_bytes()
                second = run_cmd([
                    "python3", str(SCRIPTS / "workflow_engine.py"),
                    "--project-dir", str(plan_path.parent), "submit", "--config", str(config_path),
                ], expect_ok=False, env=env)
                self.assertIn("second paid submission", second.stdout.lower())
                self.assertEqual(server.post_count, 1)
                self.assertEqual(server.get_count, 1)
                self.assertEqual(request_file.read_bytes(), first_request_record)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_direct_manual_confirmation_cannot_bypass_guarded_paid_workflow(self):
        class CountingHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.server.post_count += 1
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"data": {"task_id": "unsafe-request"}}).encode("utf-8"))

            def log_message(self, format, *args):
                return

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            server = HTTPServer(("127.0.0.1", 0), CountingHandler)
            server.post_count = 0
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config_data = json.loads(CONFIG.read_text(encoding="utf-8"))
                config_data["models"]["grok_video_15"]["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
                config_path = tmp_path / "local-config.json"
                config_path.write_text(json.dumps(config_data), encoding="utf-8")
                _, plan_path = self.prepare_project(tmp_path, duration=15)

                result = run_cmd([
                    "python3", str(SCRIPTS / "generate_video.py"),
                    "--plan", str(plan_path),
                    "--config", str(config_path),
                    "--confirmed",
                ], expect_ok=False, env={"AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key"})

                self.assertIn("guarded paid workflow", result.stdout.lower())
                self.assertEqual(server.post_count, 0)
                self.assertFalse((plan_path.parent / "jobs.json").exists())
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_poll_refuses_to_forward_provider_key_to_foreign_response_host(self):
        class CredentialTrapHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.get_count += 1
                self.server.authorization = self.headers.get("Authorization")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "COMPLETED"}).encode("utf-8"))

            def log_message(self, format, *args):
                return

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trap = HTTPServer(("127.0.0.1", 0), CredentialTrapHandler)
            trap.get_count = 0
            trap.authorization = None
            thread = threading.Thread(target=trap.serve_forever, daemon=True)
            thread.start()
            try:
                config_data = json.loads(CONFIG.read_text(encoding="utf-8"))
                config_data["models"]["grok_video_15"]["base_url"] = "http://provider.invalid/v1"
                config_path = tmp_path / "local-config.json"
                config_path.write_text(json.dumps(config_data), encoding="utf-8")
                request_file = tmp_path / "requests" / "shot_01_request.json"
                request_file.parent.mkdir()
                request_file.write_text(json.dumps({
                    "shot_id": "shot_01",
                    "model_key": "grok_video_15",
                    "submit_url": "http://provider.invalid/v1/videos/generations",
                    "response": {
                        "request_id": "request-1",
                        "status_url": f"http://127.0.0.1:{trap.server_port}/steal",
                    },
                }), encoding="utf-8")

                result = run_cmd([
                    "python3", str(SCRIPTS / "poll_video.py"),
                    "--request-file", str(request_file),
                    "--config", str(config_path),
                    "--timeout", "1",
                    "--interval", "0",
                ], expect_ok=False, env={"AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key"})

                self.assertIn("refusing to send provider credentials", result.stdout.lower())
                self.assertEqual(trap.get_count, 0)
                self.assertIsNone(trap.authorization)
            finally:
                trap.shutdown()
                thread.join(timeout=5)
                trap.server_close()

    def test_paid_submit_blocks_network_route_drift_after_readiness(self):
        class ReadyHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"data": [{"id": "grok-imagine-video-1.5"}]}).encode("utf-8"))

            def do_POST(self):
                self.server.post_count += 1
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"request_id": "unexpected"}).encode("utf-8"))

            def log_message(self, format, *args):
                return

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            server = HTTPServer(("127.0.0.1", 0), ReadyHandler)
            server.post_count = 0
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config_data = json.loads(CONFIG.read_text(encoding="utf-8"))
                config_data["models"]["grok_video_15"]["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
                config_path = tmp_path / "local-config.json"
                config_path.write_text(json.dumps(config_data), encoding="utf-8")
                _, plan_path = self.prepare_project(tmp_path, duration=15)
                run_cmd([
                    "python3", str(SCRIPTS / "preflight_project.py"),
                    "--plan", str(plan_path), "--config", str(config_path),
                ])
                run_cmd([
                    "python3", str(SCRIPTS / "workflow_engine.py"),
                    "--project-dir", str(plan_path.parent), "confirm", "--approved-by", "offline-test",
                ])
                env = {"AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key"}
                run_cmd([
                    "python3", str(SCRIPTS / "check_provider_readiness.py"),
                    "--project-dir", str(plan_path.parent), "--config", str(config_path),
                    "--model-key", "grok_video_15",
                ], env=env)
                result = run_cmd([
                    "python3", str(SCRIPTS / "generate_video.py"),
                    "--plan", str(plan_path), "--config", str(config_path),
                    "--confirmation-file", str(plan_path.parent / "video-confirmation.json"),
                    "--readiness-file", str(plan_path.parent / "provider-readiness.json"),
                    "--max-paid-submissions", "1",
                ], expect_ok=False, env={
                    **env,
                    "AI_COMMERCE_VIDEO_PROXY_URL": "http://127.0.0.1:1",
                })
                self.assertIn("network route changed", result.stdout.lower())
                self.assertEqual(server.post_count, 0)
                jobs = json.loads((plan_path.parent / "jobs.json").read_text(encoding="utf-8"))
                self.assertEqual(jobs["paid_submission_attempts"], 0)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_workflow_submit_blocks_payload_contract_drift_before_http_post(self):
        class CountingHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/v1/models":
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"data": [{"id": "grok-imagine-video-1.5"}]}).encode("utf-8"))

            def do_POST(self):
                self.server.post_count += 1
                self.send_response(500)
                self.end_headers()

            def log_message(self, format, *args):
                return

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            server = HTTPServer(("127.0.0.1", 0), CountingHandler)
            server.post_count = 0
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config_data = json.loads(CONFIG.read_text(encoding="utf-8"))
                model = config_data["models"]["grok_video_15"]
                model["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
                config_path = tmp_path / "local-config.json"
                config_path.write_text(json.dumps(config_data), encoding="utf-8")
                _, plan_path = self.prepare_project(tmp_path, duration=15)
                run_cmd([
                    "python3", str(SCRIPTS / "preflight_project.py"),
                    "--plan", str(plan_path), "--config", str(config_path),
                ])
                run_cmd([
                    "python3", str(SCRIPTS / "workflow_engine.py"),
                    "--project-dir", str(plan_path.parent), "confirm", "--approved-by", "offline-test",
                ])

                model["source_image_field"] = "image_urls"
                model["source_payload_format"] = "url_array"
                config_path.write_text(json.dumps(config_data), encoding="utf-8")
                result = run_cmd([
                    "python3", str(SCRIPTS / "workflow_engine.py"),
                    "--project-dir", str(plan_path.parent), "submit", "--config", str(config_path),
                ], expect_ok=False, env={"AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key"})
                self.assertIn("drifted from preflight", result.stdout.lower())
                self.assertEqual(server.post_count, 0)
                jobs = json.loads((plan_path.parent / "jobs.json").read_text(encoding="utf-8"))
                self.assertEqual(jobs["paid_submission_attempts"], 0)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_workflow_region_403_blocks_before_paid_attempt_and_keeps_confirmation(self):
        class RegionBlockedHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.get_count += 1
                self.send_response(403)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("<html><title>访问受限</title><body>当前地区暂不提供服务</body></html>".encode("utf-8"))

            def do_POST(self):
                self.server.post_count += 1
                self.send_response(500)
                self.end_headers()

            def log_message(self, format, *args):
                return

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            server = HTTPServer(("127.0.0.1", 0), RegionBlockedHandler)
            server.get_count = 0
            server.post_count = 0
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config_data = json.loads(CONFIG.read_text(encoding="utf-8"))
                config_data["models"]["grok_video_15"]["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
                config_path = tmp_path / "local-config.json"
                config_path.write_text(json.dumps(config_data), encoding="utf-8")
                _, plan_path = self.prepare_project(tmp_path, duration=15)
                run_cmd([
                    "python3", str(SCRIPTS / "preflight_project.py"),
                    "--plan", str(plan_path), "--config", str(config_path),
                ])
                run_cmd([
                    "python3", str(SCRIPTS / "workflow_engine.py"),
                    "--project-dir", str(plan_path.parent), "confirm", "--approved-by", "offline-test",
                ])
                result = run_cmd([
                    "python3", str(SCRIPTS / "workflow_engine.py"),
                    "--project-dir", str(plan_path.parent), "submit", "--config", str(config_path),
                ], expect_ok=False, env={"AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key"})
                data = json.loads(result.stdout)
                self.assertFalse(data["ok"])
                self.assertEqual(data["stage"], "provider_readiness")
                self.assertFalse(data["paid_api_call"])
                self.assertTrue(data["authorization_preserved"])
                self.assertFalse(data["reconfirmation_required"])
                self.assertEqual(server.get_count, 1)
                self.assertEqual(server.post_count, 0)
                jobs = json.loads((plan_path.parent / "jobs.json").read_text(encoding="utf-8"))
                self.assertEqual(jobs["paid_submission_attempts"], 0)
                self.assertTrue((plan_path.parent / "video-confirmation.json").exists())
                readiness = json.loads((plan_path.parent / "provider-readiness.json").read_text(encoding="utf-8"))
                self.assertEqual(readiness["status"], "blocked")
                self.assertEqual(readiness["error_code"], "region_restricted")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_provider_readiness_uses_skill_proxy_without_changing_system_proxy(self):
        class ProxyHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.get_count += 1
                self.server.request_path = self.path
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"data": [{"id": "grok-imagine-video-1.5"}]}).encode("utf-8"))

            def log_message(self, format, *args):
                return

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            server = HTTPServer(("127.0.0.1", 0), ProxyHandler)
            server.get_count = 0
            server.request_path = ""
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config_data = json.loads(CONFIG.read_text(encoding="utf-8"))
                config_data["models"]["grok_video_15"]["base_url"] = "http://provider.invalid/v1"
                config_path = tmp_path / "proxy-config.json"
                config_path.write_text(json.dumps(config_data), encoding="utf-8")
                project_dir = tmp_path / "project"
                project_dir.mkdir()
                result = run_cmd([
                    "python3", str(SCRIPTS / "check_provider_readiness.py"),
                    "--project-dir", str(project_dir),
                    "--config", str(config_path),
                    "--model-key", "grok_video_15",
                ], env={
                    "AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key",
                    "AI_COMMERCE_VIDEO_PROXY_URL": f"http://127.0.0.1:{server.server_port}",
                })
                data = json.loads(result.stdout)
                self.assertTrue(data["ok"])
                self.assertEqual(data["network_route"]["source"], "AI_COMMERCE_VIDEO_PROXY_URL")
                self.assertEqual(data["network_route"]["host"], "127.0.0.1")
                self.assertEqual(data["network_route"]["port"], server.server_port)
                self.assertNotIn("test-key", result.stdout)
                self.assertEqual(server.get_count, 1)
                self.assertIn("provider.invalid/v1/models", server.request_path)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_prompt_native_spoken_readiness_does_not_require_voice_roster(self):
        class VoiceReadinessHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.request_paths.append(self.path)
                if self.path == "/v1/models":
                    payload = {"data": [{"id": "grok-imagine-video-1.5"}]}
                elif self.path == "/v1/tts/voices":
                    self.send_error(404)
                    return
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode("utf-8"))

            def do_POST(self):
                self.server.post_count += 1
                self.send_response(500)
                self.end_headers()

            def log_message(self, format, *args):
                return

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            server = HTTPServer(("127.0.0.1", 0), VoiceReadinessHandler)
            server.request_paths = []
            server.post_count = 0
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config_data = json.loads(CONFIG.read_text(encoding="utf-8"))
                model = config_data["models"]["grok_video_15_reference"]
                model["base_url"] = f"http://127.0.0.1:{server.server_port}"
                model["voices_path"] = "/v1/tts/voices"
                config_path = tmp_path / "config.json"
                config_path.write_text(json.dumps(config_data), encoding="utf-8")
                project_dir = tmp_path / "project"
                project_dir.mkdir()
                (project_dir / "generation-plan.json").write_text(json.dumps({
                    "model_key": "grok_video_15_reference",
                    "audio_contract": {
                        "speech_required": True,
                        "voice_policy": "prompt_native",
                        "voice_description": "calm premium Mandarin female advertising voice",
                        "voice_id": "",
                        "preset_voice_ids": [],
                    },
                }), encoding="utf-8")

                result = run_cmd([
                    "python3", str(SCRIPTS / "check_provider_readiness.py"),
                    "--project-dir", str(project_dir),
                    "--config", str(config_path),
                ], env={"AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key"})
                data = json.loads(result.stdout)
                self.assertTrue(data["ok"])
                self.assertEqual(data["speech_readiness_mode"], "prompt_native")
                self.assertFalse(data["voice_roster_checked"])
                self.assertEqual(server.request_paths, ["/v1/models"])
                self.assertEqual(server.post_count, 0)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_stitch_uses_pcm_and_one_final_aac_encode(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            clips = project / "clips"
            clips.mkdir()
            make_test_video(clips / "shot_01.mp4", color="blue", audio=True)
            make_test_video(clips / "shot_02.mp4", size="640x360", fps=30, color="green", audio=True)
            (project / "generation-plan.json").write_text(json.dumps({
                "stitching_plan": {
                    "editorial_boundary_policy": "cut_only_after_complete_visible_action_in_a_stable_exit_state",
                    "sound_continuity_policy": "carry_ambience_and_score_motif_while_preserving_complete_voice_sentences",
                    "edit_boundaries": [{
                        "after_clip": "shot_01",
                        "before_clip": "shot_02",
                        "outgoing_exit_state": "stable_edit_safe_state",
                        "incoming_entry_state": "approved_continuity_state",
                        "stitch_motivation": "action_complete_match_cut",
                        "audio_bridge": "carry_ambience_and_score_motif_after_complete_sentence",
                        "complete_action_boundary_required": True,
                    }],
                },
            }), encoding="utf-8")
            result = run_cmd(
                [
                    "python3",
                    str(SCRIPTS / "stitch_clips.py"),
                    "--project-dir",
                    str(project),
                    "--target-resolution",
                    "720x1280",
                    "--target-fps",
                    "30",
                    "--require-audio",
                ]
            )
            report = json.loads(Path(json.loads(result.stdout)["report_file"]).read_text(encoding="utf-8"))
            self.assertFalse(report["per_clip_fades_applied"])
            self.assertFalse(report["crossfade_applied"])
            self.assertTrue(report["single_final_aac_encode"])
            self.assertEqual(report["intermediate_audio_codec"], "pcm_s16le")
            self.assertEqual(len(report["boundary_seconds"]), 1)
            self.assertEqual(len(report["planned_edit_boundaries"]), 1)
            self.assertEqual(report["planned_edit_boundaries"][0]["actual_boundary_seconds"], report["boundary_seconds"][0])
            self.assertTrue(report["editorial_boundary_review_required"])
            self.assertTrue(report["loudness_consistency_review_required"])
            self.assertTrue(report["output_sha256"])

    def test_review_render_checks_boundaries_and_delivery_hard_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            clips = project / "clips"
            clips.mkdir()
            first = clips / "shot_01.mp4"
            second = clips / "shot_02.mp4"
            make_test_video(first, duration=1.0, color="blue", audio=True)
            make_test_video(second, duration=1.0, color="green", audio=True)
            source = project / "approved-source.png"
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=0.1",
                "-frames:v", "1", str(source),
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            plan = {
                "delivery_max_seconds": 3,
                "total_duration_seconds": 3,
                "shots": [
                    {"id": "shot_01", "clip_file": str(first), "image": {"value": str(source)}, "spoken_script": "第一句完成。", "script_boundary": {"stitch_safe": True}},
                    {"id": "shot_02", "clip_file": str(second), "spoken_script": "第二句完成。", "script_boundary": {"stitch_safe": True}},
                ],
                "stitching_plan": {"required": True},
                "subtitle_plan": {"enabled": False},
                "quality_contract": {"delivery_review_policy": "technical_ready"},
            }
            (project / "generation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            stitched = run_cmd([
                "python3", str(SCRIPTS / "stitch_clips.py"),
                "--project-dir", str(project), "--require-audio",
            ])
            final = Path(json.loads(stitched.stdout)["output"])
            result = run_cmd([
                "python3", str(SCRIPTS / "review_render.py"),
                "--project-dir", str(project), "--video", str(final),
            ])
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["review_scope"], "technical_media_only")
            self.assertEqual(report["technical_status"], "pass")
            self.assertEqual(report["delivery_status"], "technical_ready")
            self.assertFalse(report["formal_delivery_approved"])
            self.assertTrue(report["ready_to_finalize"])
            self.assertFalse(report["multimodal_visual_review_required"])
            self.assertIn("sound_signal_screening", report)
            self.assertFalse(report["sound_signal_screening"]["listening_verdict"])
            self.assertTrue(report["delivery_duration_hard_limit_pass"])
            self.assertEqual(report["boundary_count"], 1)
            self.assertTrue(report["stitch_audio_policy_pass"])
            self.assertEqual(report["source_frame_comparisons"][0]["status"], "multimodal_review_required")
            self.assertTrue(Path(report["source_frame_comparisons"][0]["video_first_frame"]).is_file())
            self.assertTrue(Path(report["source_frame_comparisons"][0]["comparison_image"]).is_file())
            self.assertIn("source_frame_consistency", report["visual_review_fields"])
            self.assertTrue((project / "final-review.json").exists())

    def test_project_stage_does_not_call_technical_media_verification_final(self):
        workflow_engine = importlib.import_module("workflow_engine")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            jobs = {"jobs": {"shot_01": {"state": "verified", "verification_scope": "technical_media_only"}}}
            (project / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
            self.assertEqual(workflow_engine.project_stage(project)["stage"], "awaiting_business_review")
            (project / "final-review.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            (project / "visual-review.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            self.assertEqual(workflow_engine.project_stage(project)["stage"], "awaiting_business_review")
            technical = {"status": "pass", "delivery_duration_hard_limit_pass": True, "video_sha256": "hash"}
            visual = {
                "status": "pass",
                "video_sha256": "hash",
                "video_complete_and_coherent": True,
                "source_frame_consistency": True,
                "approved_product_identity": True,
                "presenter_identity_consistency": True,
                "presenter_outfit_consistency": True,
                "scene_composition_consistency": True,
                "speech_intelligible": True,
                "speech_meaning_preserved": True,
            }
            (project / "final-review.json").write_text(json.dumps(technical), encoding="utf-8")
            (project / "visual-review.json").write_text(json.dumps(visual), encoding="utf-8")
            self.assertEqual(workflow_engine.project_stage(project)["stage"], "ready_to_finalize")

    def test_new_default_policy_needs_technical_review_but_not_business_review(self):
        workflow_engine = importlib.import_module("workflow_engine")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            plan = {
                "quality_contract": {"delivery_review_policy": "technical_ready"},
                "subtitle_plan": {"enabled": False},
            }
            jobs = {"jobs": {"shot_01": {"state": "verified", "verification_scope": "technical_media_only"}}}
            (project / "generation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            (project / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
            self.assertEqual(workflow_engine.project_stage(project)["stage"], "awaiting_technical_review")
            technical = {"status": "pass", "delivery_duration_hard_limit_pass": True, "video_sha256": "hash"}
            (project / "final-review.json").write_text(json.dumps(technical), encoding="utf-8")
            self.assertEqual(workflow_engine.project_stage(project)["stage"], "ready_to_finalize")

    def test_spoken_default_policy_waits_for_narrow_voice_contract_review(self):
        workflow_engine = importlib.import_module("workflow_engine")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            plan = {
                "quality_contract": {
                    "delivery_review_policy": "technical_ready",
                    "required_voice_contract_review": True,
                },
                "subtitle_plan": {"enabled": False},
                "creative_contract": {"speaker_mode": "digital-human-spoken"},
                "audio_contract": {
                    "speech_required": True,
                    "speech_mode": "digital-human-spoken",
                    "speech_presentation": "on_camera_presenter",
                },
            }
            jobs = {"jobs": {"shot_01": {"state": "verified", "verification_scope": "technical_media_only"}}}
            (project / "generation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            (project / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
            technical = {"status": "pass", "delivery_duration_hard_limit_pass": True, "video_sha256": "hash"}
            (project / "final-review.json").write_text(json.dumps(technical), encoding="utf-8")
            self.assertEqual(workflow_engine.project_stage(project)["stage"], "awaiting_voice_review")
            voice_review = {
                "status": "pass",
                "video_sha256": "hash",
                "speech_present": True,
                "speech_intelligible": True,
                "speech_meaning_preserved": True,
                "presenter_speaks_on_camera": True,
                "visible_mouth_movement": True,
            }
            (project / "voice-review.json").write_text(json.dumps(voice_review), encoding="utf-8")
            self.assertEqual(workflow_engine.project_stage(project)["stage"], "ready_to_finalize")

    def test_technical_ready_delivery_rejects_background_only_audio_as_speech(self):
        finalize = importlib.import_module("finalize_project")
        plan = {
            "plan_schema_version": 3,
            "quality_contract": {"delivery_review_policy": "technical_ready"},
            "creative_contract": {"speaker_mode": "digital-human-spoken"},
            "audio_contract": {
                "speech_required": True,
                "speech_mode": "digital-human-spoken",
                "speech_presentation": "on_camera_presenter",
            },
            "production_contract": {
                "base_request_count": 1,
                "approved_paid_cap": 1,
                "repair_reserve": 0,
                "per_shot_repair_limit": 0,
            },
            "subtitle_plan": {"enabled": False},
            "shots": [{"id": "shot_01"}],
        }
        jobs = {"jobs": [{"shot_id": "shot_01", "state": "verified", "submission_attempts": 1}]}
        technical = {
            "status": "pass",
            "delivery_duration_hard_limit_pass": True,
            "provider_duration_shortfall_pass": True,
            "media": {"has_audio": True},
        }
        errors = finalize.delivery_errors(plan, jobs, technical, None, None, None)
        self.assertTrue(any("voice contract review status" in error.lower() for error in errors))
        self.assertTrue(any("background music" in error.lower() for error in errors))

        verified_speech = {
            "status": "pass",
            "speech_present": True,
            "speech_intelligible": True,
            "speech_meaning_preserved": True,
            "presenter_speaks_on_camera": True,
            "visible_mouth_movement": True,
        }
        self.assertEqual(
            finalize.delivery_errors(plan, jobs, technical, None, None, verified_speech),
            [],
        )

    def test_technical_ready_delivery_rejects_unplanned_speech_in_no_speech_plan(self):
        finalize = importlib.import_module("finalize_project")
        plan = {
            "plan_schema_version": 3,
            "quality_contract": {
                "delivery_review_policy": "technical_ready",
                "required_voice_contract_review": True,
            },
            "creative_contract": {"speaker_mode": "no-speech"},
            "audio_contract": {
                "speech_required": False,
                "speech_mode": "no-speech",
                "speech_presentation": "none",
            },
            "production_contract": {
                "base_request_count": 1,
                "approved_paid_cap": 1,
                "repair_reserve": 0,
                "per_shot_repair_limit": 0,
            },
            "subtitle_plan": {"enabled": False},
            "shots": [{"id": "shot_01"}],
        }
        jobs = {"jobs": [{"shot_id": "shot_01", "state": "verified", "submission_attempts": 1}]}
        technical = {
            "status": "pass",
            "delivery_duration_hard_limit_pass": True,
            "provider_duration_shortfall_pass": True,
        }
        failed_review = {"status": "blocked", "unexpected_speech_absent": False}
        errors = finalize.delivery_errors(plan, jobs, technical, None, None, failed_review)
        self.assertTrue(any("unplanned human speech" in error.lower() for error in errors))
        passed_review = {"status": "pass", "unexpected_speech_absent": True}
        self.assertEqual(
            finalize.delivery_errors(plan, jobs, technical, None, None, passed_review),
            [],
        )

    def test_review_voice_contract_records_on_camera_evidence_without_paid_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            video = project / "final.mp4"
            make_test_video(video, duration=1.0, audio=True)
            plan = {
                "quality_contract": {
                    "delivery_review_policy": "technical_ready",
                    "required_voice_contract_review": True,
                },
                "subtitle_plan": {"enabled": False},
                "creative_contract": {"speaker_mode": "digital-human-spoken"},
                "audio_contract": {
                    "speech_required": True,
                    "speech_mode": "digital-human-spoken",
                    "speech_presentation": "on_camera_presenter",
                },
            }
            (project / "generation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "review_voice_contract.py"),
                "--project-dir", str(project),
                "--review-method", "human_listening",
                "--speech-present", "yes",
                "--speech-intelligible", "yes",
                "--speech-meaning-preserved", "yes",
                "--presenter-speaks-on-camera", "yes",
                "--visible-mouth-movement", "yes",
            ])
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "pass")
            self.assertFalse(report["paid_api_call"])
            self.assertFalse(report["automatic_paid_retry_authorized"])
            self.assertTrue((project / "voice-review.json").exists())

    def test_review_voice_contract_records_no_unplanned_speech_for_no_speech_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            video = project / "final.mp4"
            make_test_video(video, duration=1.0, audio=True)
            plan = {
                "quality_contract": {
                    "delivery_review_policy": "technical_ready",
                    "required_voice_contract_review": True,
                },
                "subtitle_plan": {"enabled": False},
                "creative_contract": {"speaker_mode": "no-speech"},
                "audio_contract": {
                    "speech_required": False,
                    "speech_mode": "no-speech",
                    "speech_presentation": "none",
                },
                "sound_design_contract": {"non_speech_required": True},
            }
            (project / "generation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "review_voice_contract.py"),
                "--project-dir", str(project),
                "--review-method", "human_listening",
                "--unexpected-speech-absent", "yes",
            ])
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["required_fields"], ["unexpected_speech_absent"])
            self.assertTrue((project / "voice-review.json").exists())

    def test_provider_trace_prefers_nested_upstream_task_and_supports_legacy_requests(self):
        poll_video = importlib.import_module("poll_video")
        prompt = "approved product and presenter in the confirmed interior scene"
        request = {
            "response": {"request_id": "task_gateway"},
            "payload": {"prompt": prompt, "image_urls": ["data:image/png;base64,bGVnYWN5"]},
        }
        response = {
            "data": {
                "id": 92430,
                "task_id": "task_gateway",
                "channel_id": 11,
                "prompt": prompt,
                "data": {"id": "task_upstream"},
            }
        }
        trace = poll_video.build_provider_trace(request, response, "https://example.com/result.mp4")
        self.assertEqual(trace["gateway_task_id"], "task_gateway")
        self.assertEqual(trace["gateway_record_id"], 92430)
        self.assertEqual(trace["upstream_task_id"], "task_upstream")
        self.assertEqual(trace["channel_id"], 11)
        self.assertTrue(trace["returned_prompt_matches_request"])
        self.assertEqual(len(trace["sent_image_sha256"]), 1)
        self.assertEqual(len(trace["sent_image_sha256"][0]), 64)

    def test_finalize_blocks_incoherent_video_and_reference_identity_drift(self):
        finalize = importlib.import_module("finalize_project")
        plan = {
            "shots": [{"id": "shot_01"}],
            "production_contract": {"base_request_count": 1, "approved_paid_cap": 1},
            "subtitle_plan": {"enabled": False},
        }
        jobs = {
            "approved_paid_cap": 1,
            "jobs": [{"shot_id": "shot_01", "state": "verified", "submission_attempts": 1}],
        }
        technical = {"status": "pass", "delivery_duration_hard_limit_pass": True}
        visual = {
            "status": "blocked",
            "video_complete_and_coherent": False,
            "source_frame_consistency": False,
            "approved_product_identity": False,
            "presenter_identity_consistency": False,
            "presenter_outfit_consistency": True,
            "scene_composition_consistency": True,
            "speech_intelligible": True,
            "speech_meaning_preserved": True,
        }
        errors = finalize.delivery_errors(plan, jobs, technical, visual, None)
        self.assertTrue(any("product identity" in item.lower() for item in errors))
        self.assertTrue(any("reference frame" in item.lower() for item in errors))
        self.assertTrue(any("complete video" in item.lower() for item in errors))
        self.assertFalse(any("generated text" in item.lower() for item in errors))

    def test_finalize_requires_caption_review_when_subtitles_enabled(self):
        finalize = importlib.import_module("finalize_project")
        plan = {
            "shots": [{"id": "shot_01"}],
            "production_contract": {"base_request_count": 1, "approved_paid_cap": 1},
            "subtitle_plan": {
                "enabled": True,
                "request_source": "user_plan_confirmation",
                "confirmation_status": "confirmed",
                "provider_policy": "never_send",
                "render_policy": "postproduction_burn_only",
                "paid_api_call": False,
            },
        }
        jobs = {
            "approved_paid_cap": 1,
            "jobs": [{"shot_id": "shot_01", "state": "verified", "submission_attempts": 1}],
        }
        technical = {"status": "pass", "delivery_duration_hard_limit_pass": True}
        clean_visual = {
            "status": "pass",
            "video_complete_and_coherent": True,
            "source_frame_consistency": True,
            "approved_product_identity": True,
            "presenter_identity_consistency": True,
            "presenter_outfit_consistency": True,
            "scene_composition_consistency": True,
            "speech_intelligible": True,
            "speech_meaning_preserved": True,
        }
        errors = finalize.delivery_errors(plan, jobs, technical, clean_visual, None)
        self.assertTrue(any("caption" in item.lower() for item in errors))

    def test_finalize_accepts_clean_delivery_only_after_all_gates_pass(self):
        finalize = importlib.import_module("finalize_project")
        plan = {
            "shots": [{"id": "shot_01"}],
            "production_contract": {
                "base_request_count": 1,
                "approved_paid_cap": 1,
                "repair_reserve": 0,
                "per_shot_repair_limit": 0,
            },
            "subtitle_plan": {"enabled": False},
        }
        jobs = {
            "approved_paid_cap": 1,
            "jobs": [{"shot_id": "shot_01", "state": "verified", "submission_attempts": 1}],
        }
        technical = {"status": "pass", "delivery_duration_hard_limit_pass": True}
        clean_visual = {
            "status": "pass",
            "video_complete_and_coherent": True,
            "source_frame_consistency": True,
            "approved_product_identity": True,
            "presenter_identity_consistency": True,
            "presenter_outfit_consistency": True,
            "scene_composition_consistency": True,
            "speech_intelligible": True,
            "speech_meaning_preserved": True,
        }
        self.assertEqual(finalize.delivery_errors(plan, jobs, technical, clean_visual, None), [])
        bound_technical = {**technical, "video_sha256": "clean-hash"}
        bound_visual = {**clean_visual, "video_sha256": "clean-hash"}
        self.assertEqual(
            finalize.review_binding_errors(False, "clean-hash", "clean-hash", bound_technical, bound_visual, None),
            [],
        )
        mismatched = finalize.review_binding_errors(
            False,
            "clean-hash",
            "different-delivery-hash",
            bound_technical,
            bound_visual,
            None,
        )
        self.assertTrue(any("hash" in item.lower() for item in mismatched))
        common = importlib.import_module("_common")
        contract = {
            "contract_digest": "contract-1",
            "plan_digest": common.canonical_digest(plan),
            "duration_plan_digest": "",
            "approved_paid_cap": 1,
        }
        confirmation = {
            "contract_digest": "contract-1",
            "plan_digest": contract["plan_digest"],
            "duration_plan_digest": "",
            "approved_paid_cap": 1,
        }
        bound_jobs = {**jobs, "contract_digest": "contract-1"}
        self.assertEqual(finalize.contract_binding_errors(plan, bound_jobs, contract, confirmation), [])
        drifted_plan = {**plan, "unexpected_change": True}
        self.assertTrue(finalize.contract_binding_errors(drifted_plan, bound_jobs, contract, confirmation))

    def test_finalize_cli_writes_passing_delivery_manifest_after_all_reviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            final_video = project / "final.mp4"
            make_test_video(final_video, duration=1.0, audio=True)
            plan = {
                "shots": [{"id": "shot_01"}],
                "production_contract": {
                    "base_request_count": 1,
                    "approved_paid_cap": 1,
                    "repair_reserve": 0,
                    "per_shot_repair_limit": 0,
                },
                "subtitle_plan": {"enabled": False},
            }
            common = importlib.import_module("_common")
            contract = {
                "contract_digest": "contract-1",
                "plan_digest": common.canonical_digest(plan),
                "duration_plan_digest": "",
                "approved_paid_cap": 1,
            }
            confirmation = {
                "contract_digest": "contract-1",
                "plan_digest": contract["plan_digest"],
                "duration_plan_digest": "",
                "approved_paid_cap": 1,
            }
            jobs = {
                "contract_digest": "contract-1",
                "approved_paid_cap": 1,
                "jobs": [{"shot_id": "shot_01", "state": "verified", "submission_attempts": 1}],
            }
            technical = {"status": "pass", "delivery_duration_hard_limit_pass": True}
            visual = {
                "status": "pass",
                "video_complete_and_coherent": True,
                "source_frame_consistency": True,
                "approved_product_identity": True,
                "presenter_identity_consistency": True,
                "presenter_outfit_consistency": True,
                "scene_composition_consistency": True,
                "speech_intelligible": True,
                "speech_meaning_preserved": True,
            }
            video_hash = importlib.import_module("_common").sha256_file(final_video)
            technical["video_sha256"] = video_hash
            visual["video_sha256"] = video_hash
            for name, value in {
                "generation-plan.json": plan,
                "jobs.json": jobs,
                "production-contract.json": contract,
                "video-confirmation.json": confirmation,
                "final-review.json": technical,
                "visual-review.json": visual,
            }.items():
                (project / name).write_text(json.dumps(value), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "finalize_project.py"),
                "--project-dir", str(project), "--video", str(final_video),
            ])
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "pass")
            delivery = json.loads((project / "delivery-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(delivery["status"], "pass")
            self.assertTrue(delivery["final_artifact"]["sha256"])

    def test_finalize_new_default_policy_without_optional_visual_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            final_video = project / "final.mp4"
            make_test_video(final_video, duration=1.0, audio=True)
            plan = {
                "shots": [{"id": "shot_01"}],
                "production_contract": {
                    "base_request_count": 1,
                    "approved_paid_cap": 1,
                    "repair_reserve": 0,
                    "per_shot_repair_limit": 0,
                },
                "quality_contract": {"delivery_review_policy": "technical_ready"},
                "subtitle_plan": {"enabled": False},
            }
            common = importlib.import_module("_common")
            contract = {
                "contract_digest": "contract-1",
                "plan_digest": common.canonical_digest(plan),
                "duration_plan_digest": "",
                "approved_paid_cap": 1,
            }
            confirmation = {
                "contract_digest": "contract-1",
                "plan_digest": contract["plan_digest"],
                "duration_plan_digest": "",
                "approved_paid_cap": 1,
            }
            video_hash = common.sha256_file(final_video)
            files = {
                "generation-plan.json": plan,
                "jobs.json": {
                    "contract_digest": "contract-1",
                    "approved_paid_cap": 1,
                    "jobs": [{"shot_id": "shot_01", "state": "verified", "submission_attempts": 1}],
                },
                "production-contract.json": contract,
                "video-confirmation.json": confirmation,
                "final-review.json": {
                    "status": "pass",
                    "delivery_duration_hard_limit_pass": True,
                    "video_sha256": video_hash,
                },
            }
            for name, value in files.items():
                (project / name).write_text(json.dumps(value), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "finalize_project.py"),
                "--project-dir", str(project), "--video", str(final_video),
            ])
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["delivery_review_policy"], "technical_ready")
            self.assertTrue(any("Optional post-generation" in item for item in report["warnings"]))
            self.assertFalse((project / "visual-review.json").exists())


if __name__ == "__main__":
    unittest.main()
