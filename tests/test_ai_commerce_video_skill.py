#!/usr/bin/env python3
"""Offline validation for the ai-commerce-video skill."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT
SCRIPTS = SKILL / "scripts"
CONFIG = SKILL / "assets" / "templates" / "model-config.example.json"


def run_cmd(args, cwd=ROOT, env=None):
    full_env = os.environ.copy()
    for key in list(full_env):
        if key in {"AI_COMMERCE_VIDEO_API_KEY", "AI_COMMERCE_VIDEO_BASE_URL", "AI_COMMERCE_VIDEO_MODEL", "AI_COMMERCE_VIDEO_ENV_FILE", "YUNWU_API_KEY", "XAI_API_KEY", "FAL_KEY"} or key.startswith("AI_COMMERCE_VIDEO_MODEL_"):
            full_env.pop(key, None)
    full_env["AI_COMMERCE_VIDEO_ENV_FILE"] = str(ROOT / ".nonexistent-test-env")
    if env:
        full_env.update(env)
    result = subprocess.run(args, cwd=cwd, env=full_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise AssertionError(f"Command failed: {' '.join(map(str, args))}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result


def run_cmd_fail(args, cwd=ROOT, env=None):
    full_env = os.environ.copy()
    for key in list(full_env):
        if key in {"AI_COMMERCE_VIDEO_API_KEY", "AI_COMMERCE_VIDEO_BASE_URL", "AI_COMMERCE_VIDEO_MODEL", "AI_COMMERCE_VIDEO_ENV_FILE", "YUNWU_API_KEY", "XAI_API_KEY", "FAL_KEY"} or key.startswith("AI_COMMERCE_VIDEO_MODEL_"):
            full_env.pop(key, None)
    full_env["AI_COMMERCE_VIDEO_ENV_FILE"] = str(ROOT / ".nonexistent-test-env")
    if env:
        full_env.update(env)
    result = subprocess.run(args, cwd=cwd, env=full_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        raise AssertionError(f"Command unexpectedly passed: {' '.join(map(str, args))}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result


def write_model_config(tmp_path: Path, model_overrides: dict, model_key: str = "grok_video_15") -> Path:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    data["models"][model_key].update(model_overrides)
    path = tmp_path / "model-config.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def make_test_video(path: Path, size="320x240", fps=24, duration=1.0, color="red", audio=True):
    if not shutil.which("ffmpeg"):
        raise unittest.SkipTest("ffmpeg is required for media validation tests")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={color}:s={size}:r={fps}:d={duration}",
    ]
    if audio:
        cmd.extend(["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}", "-shortest"])
    cmd.extend([
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac" if audio else "copy",
        "-movflags", "+faststart",
        str(path),
    ])
    if not audio:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s={size}:r={fps}:d={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path),
        ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)


class MockVideoHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/v1/video/generations":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
        self.server.last_payload = payload
        self.server.last_post_user_agent = self.headers.get("User-Agent")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "code": "success",
            "message": "",
            "data": {"task_id": "mock-request-1", "status": "SUBMITTED"},
        }).encode("utf-8"))

    def do_GET(self):
        if self.path == "/v1/video/generations/mock-request-1":
            self.server.last_get_user_agent = self.headers.get("User-Agent")
            url = f"http://127.0.0.1:{self.server.server_port}/mock-video.mp4"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "code": "success",
                "message": "",
                "data": {
                    "task_id": "mock-request-1",
                    "status": "SUCCESS",
                    "progress": "100%",
                    "result_url": url,
                    "fail_reason": "",
                },
            }).encode("utf-8"))
            return
        if self.path == "/mock-video.mp4":
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.end_headers()
            self.wfile.write(self.server.video_bytes)
            return
        self.send_error(404)

    def log_message(self, format, *args):
        return


class MockFalVideoHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/bytedance/seedance-2.0/reference-to-video":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
        self.server.last_payload = payload
        self.server.last_post_auth = self.headers.get("Authorization")
        status_url = f"http://127.0.0.1:{self.server.server_port}/bytedance/seedance-2.0/reference-to-video/requests/fal-request-1/status"
        response_url = f"http://127.0.0.1:{self.server.server_port}/bytedance/seedance-2.0/reference-to-video/requests/fal-request-1/response"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "request_id": "fal-request-1",
            "status_url": status_url,
            "response_url": response_url,
            "queue_position": 0,
        }).encode("utf-8"))

    def do_GET(self):
        if self.path == "/bytedance/seedance-2.0/reference-to-video/requests/fal-request-1/status":
            self.server.last_status_auth = self.headers.get("Authorization")
            response_url = f"http://127.0.0.1:{self.server.server_port}/bytedance/seedance-2.0/reference-to-video/requests/fal-request-1/response"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "COMPLETED",
                "request_id": "fal-request-1",
                "response_url": response_url,
            }).encode("utf-8"))
            return
        if self.path == "/bytedance/seedance-2.0/reference-to-video/requests/fal-request-1/response":
            self.server.last_response_auth = self.headers.get("Authorization")
            url = f"http://127.0.0.1:{self.server.server_port}/fal-video.mp4"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"video": {"url": url}, "seed": 42}).encode("utf-8"))
            return
        if self.path == "/fal-video.mp4":
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.end_headers()
            self.wfile.write(self.server.video_bytes)
            return
        self.send_error(404)

    def log_message(self, format, *args):
        return


class SkillValidationTests(unittest.TestCase):
    def test_single_skill_repository_is_self_contained(self):
        expected = [
            SKILL / "README.md",
            SKILL / "README.zh-CN.md",
            SKILL / ".gitignore",
            SKILL / "SECURITY.md",
            SKILL / "CONTRIBUTING.md",
            SKILL / "CHANGELOG.md",
            SKILL / ".github" / "workflows" / "tests.yml",
            SKILL / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml",
            SKILL / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml",
            SKILL / "tests" / "test_ai_commerce_video_skill.py",
            SKILL / "tests" / "test_ai_commerce_video_production_core.py",
            SCRIPTS / "audit_release.py",
            SCRIPTS / "package_skill.py",
        ]
        for path in expected:
            self.assertTrue(path.exists(), path)

    def test_source_tree_contains_no_runtime_cache(self):
        forbidden = [
            path
            for path in SKILL.rglob("*")
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"} or path.name == ".DS_Store"
        ]
        self.assertEqual(forbidden, [])

    def test_local_packager_builds_clean_skill_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ai-commerce-video.skill"
            result = run_cmd([
                "python3",
                str(SCRIPTS / "package_skill.py"),
                "--output",
                str(output),
            ])
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"])
            self.assertTrue(output.exists())
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn("ai-commerce-video/SKILL.md", names)
                self.assertIn("ai-commerce-video/scripts/prepare_project.py", names)
                self.assertNotIn("ai-commerce-video/README.md", names)
                self.assertNotIn("ai-commerce-video/README.zh-CN.md", names)
                self.assertNotIn("ai-commerce-video/SECURITY.md", names)
                self.assertNotIn("ai-commerce-video/CONTRIBUTING.md", names)
                self.assertNotIn("ai-commerce-video/CHANGELOG.md", names)
                self.assertFalse(any("/tests/" in name for name in names))
                self.assertFalse(any("__pycache__" in name or name.endswith((".pyc", ".env")) for name in names))

    def test_required_files_exist(self):
        expected = [
            ROOT / "README.md",
            ROOT / "LICENSE",
            ROOT / ".gitignore",
            SKILL / "SKILL.md",
            SKILL / "LICENSE",
            SKILL / "references" / "workflow.md",
            SKILL / "references" / "model-capabilities.md",
            SKILL / "references" / "grok-video-api.md",
            SKILL / "references" / "seedance-video-api.md",
            SKILL / "references" / "seedance-prompting.md",
            SKILL / "references" / "ecommerce-quality-rules.md",
            SKILL / "references" / "platform-requirements.md",
            SKILL / "references" / "platform-safe-zones.md",
            SKILL / "references" / "commerce-scenarios.md",
            SKILL / "references" / "claims-and-compliance.md",
            SKILL / "references" / "asset-consistency.md",
            SKILL / "references" / "creative-variants.md",
            SKILL / "references" / "storyboard-reference-strategies.md",
            SKILL / "references" / "composition-and-stitching.md",
            SKILL / "references" / "script-duration-and-pacing.md",
            SKILL / "references" / "subtitles-and-safe-layout.md",
            SKILL / "references" / "post-generation-review.md",
            SKILL / "assets" / "templates" / "subtitle-style-profiles.example.json",
            SCRIPTS / "prepare_project.py",
            SCRIPTS / "setup_private_env.py",
            SCRIPTS / "validate_config.py",
            SCRIPTS / "validate_platform_plan.py",
            SCRIPTS / "generate_video.py",
            SCRIPTS / "poll_video.py",
            SCRIPTS / "stitch_clips.py",
            SCRIPTS / "duration_planning.py",
            SCRIPTS / "subtitle_policy.py",
            SCRIPTS / "subtitle_profiles.py",
            SCRIPTS / "subtitle_runtime.py",
            SCRIPTS / "generate_subtitles.py",
            SCRIPTS / "burn_subtitles.py",
            SCRIPTS / "preflight_project.py",
            SCRIPTS / "workflow_engine.py",
            SCRIPTS / "review_render.py",
            SCRIPTS / "finalize_project.py",
        ]
        for path in expected:
            self.assertTrue(path.exists(), path)

    def test_skill_frontmatter_is_share_ready_and_main_file_is_concise(self):
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = skill_text.split("---", 2)[1]
        self.assertRegex(frontmatter, r"(?m)^description: Use when ")
        self.assertRegex(frontmatter, r"(?m)^license: MIT$")
        self.assertRegex(frontmatter, r"(?m)^compatibility: .+")
        self.assertLessEqual(len(skill_text.split()), 1600)

    def test_open_source_release_files_warn_about_secrets_and_outputs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("Do not put API keys in the repository", readme)
        self.assertIn("Do not commit generated videos", readme)
        self.assertIn("当前适配的视频模型", readme_zh)
        self.assertIn("切换其他视频模型", readme_zh)
        self.assertIn("grok-imagine-video-1.5", readme_zh)
        self.assertIn("模型名称相同不代表接口兼容", readme_zh)
        self.assertIn("dist/", gitignore)
        self.assertIn("*.mp4", gitignore)
        self.assertIn(".env.*", gitignore)

    def test_skill_tree_does_not_contain_raw_api_keys(self):
        pattern = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
        scanned = []
        for path in SKILL.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".py", ".json", ".example"}:
                scanned.append(path)
                self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")), path)
        self.assertGreater(len(scanned), 10)

    def test_shareable_skill_does_not_contain_developer_absolute_paths(self):
        pattern = re.compile(r"/(?:Users|Volumes)/[^\s`]+")
        for path in SKILL.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".py", ".json", ".example"}:
                self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")), path)

    def test_codex_native_analysis_contract_is_documented(self):
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow_text = (SKILL / "references" / "workflow.md").read_text(encoding="utf-8")
        template_text = (SKILL / "references" / "proposal-template.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, template_text])
        self.assertIn("Codex's native multimodal model", skill_text)
        self.assertIn("Codex `imagegen`", combined)
        self.assertIn("Do not add or call a separate LLM/vision API", skill_text)
        self.assertIn("external video API only after confirmation", workflow_text)
        self.assertIn("visual approval images", skill_text)
        self.assertIn("After the user approves the first proposal", skill_text)
        self.assertIn("supplied product images and a model image", skill_text)
        self.assertIn("Image Generation and Visual Approval Gate", workflow_text)
        self.assertIn("First proposal: analyze the supplied materials", workflow_text)
        self.assertIn("After approval: use Codex `imagegen` / image2", workflow_text)
        self.assertIn("product+model-only token map is incomplete", workflow_text)
        self.assertIn("计划生成的验收图", template_text)
        self.assertIn("第一步请确认", template_text)
        self.assertIn("图片验收与视频生成确认", template_text)
        self.assertIn("同一批本地图片路径", template_text)

    def test_creative_variant_ab_proposal_contract_is_documented(self):
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow_text = (SKILL / "references" / "workflow.md").read_text(encoding="utf-8")
        template_text = (SKILL / "references" / "proposal-template.md").read_text(encoding="utf-8")
        variant_text = (SKILL / "references" / "creative-variants.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, template_text, variant_text])
        self.assertIn("方案 A", template_text)
        self.assertIn("正规商品广告", template_text)
        self.assertIn("方案 B", template_text)
        self.assertIn("剧情反转广告", template_text)
        self.assertIn("commerce_direct", combined)
        self.assertIn("story_reversal", combined)
        self.assertIn("ugc_review", variant_text)
        self.assertIn("comparison_test", variant_text)
        self.assertIn("lifestyle_seed", variant_text)
        self.assertIn("premium_brand", variant_text)
        self.assertIn("选 A", combined)
        self.assertIn("选 B", combined)
        self.assertIn("两个融合", combined)
        self.assertIn("按 AI 推荐", combined)
        self.assertIn("Only after the user selects and confirms a variant", variant_text)
        self.assertIn("Do not generate new images before the user selects and confirms", workflow_text)
        self.assertNotIn("previews immediately", workflow_text)

    def test_platform_scenario_and_compliance_references_are_documented(self):
        platform_text = (SKILL / "references" / "platform-requirements.md").read_text(encoding="utf-8")
        safe_zone_text = (SKILL / "references" / "platform-safe-zones.md").read_text(encoding="utf-8")
        scenario_text = (SKILL / "references" / "commerce-scenarios.md").read_text(encoding="utf-8")
        compliance_text = (SKILL / "references" / "claims-and-compliance.md").read_text(encoding="utf-8")
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow_text = (SKILL / "references" / "workflow.md").read_text(encoding="utf-8")
        template_text = (SKILL / "references" / "proposal-template.md").read_text(encoding="utf-8")
        for expected in [
            "TikTok",
            "Douyin",
            "Xiaohongshu",
            "Amazon Sponsored Brands Video",
            "Amazon Sponsored Products Video",
            "YouTube",
            "Meta Reels",
            "Shopify",
        ]:
            self.assertIn(expected, platform_text)
        for expected in [
            "tiktok_in_feed",
            "douyin_in_feed",
            "xiaohongshu_note",
            "amazon_product_feature_video",
            "youtube_universal_safe_zone",
            "meta_reels",
        ]:
            self.assertIn(expected, safe_zone_text)
        for expected in [
            "feature_demo",
            "product_detail_page",
            "ugc_review",
            "unboxing",
            "comparison_test",
            "lifestyle_seed",
            "premium_brand",
            "live_shopping_teaser",
            "retargeting_offer",
            "new_launch",
        ]:
            self.assertIn(expected, scenario_text)
        for expected in ["Beauty", "Supplements", "Food", "Mother and baby", "Pets", "Electronics", "Medical-related"]:
            self.assertIn(expected, compliance_text)
        combined = "\n".join([skill_text, workflow_text, template_text])
        self.assertIn("platform_contract", combined)
        self.assertIn("scenario_contract", combined)
        self.assertIn("compliance_contract", combined)
        self.assertIn("validate_platform_plan.py", combined)

    def test_storyboard_reference_strategy_is_documented(self):
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow_text = (SKILL / "references" / "workflow.md").read_text(encoding="utf-8")
        model_text = (SKILL / "references" / "model-capabilities.md").read_text(encoding="utf-8")
        asset_text = (SKILL / "references" / "asset-consistency.md").read_text(encoding="utf-8")
        strategy_text = (SKILL / "references" / "storyboard-reference-strategies.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, model_text, asset_text, strategy_text])
        self.assertIn("per_segment_source_frames", combined)
        self.assertIn("multi_reference_storyboard", combined)
        self.assertIn("storyboard_sheet_reference", combined)
        self.assertIn("Never upload a 6-grid or 9-grid storyboard sheet as the only source image", strategy_text)
        self.assertIn("--segment-source-image shot_01", strategy_text)

    def test_visual_approval_gate_is_documented_for_asset_consistency(self):
        asset_text = (SKILL / "references" / "asset-consistency.md").read_text(encoding="utf-8")
        capability_text = (SKILL / "references" / "model-capabilities.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("User-supplied product/model images are source assets", asset_text)
        self.assertIn("Do not proceed from a product+model-only plan", asset_text)
        self.assertIn("Variable Material Handling", asset_text)
        self.assertIn("Multiple product angles", asset_text)
        self.assertIn("still plan the video-facing approval image", capability_text)
        self.assertIn("two-step approval flow", readme)

    def test_validate_config(self):
        result = run_cmd(["python3", str(SCRIPTS / "validate_config.py"), "--config", str(CONFIG)])
        data = json.loads(result.stdout)
        self.assertTrue(data["api_key_present"] in {True, False})
        self.assertEqual(data["selected_model"], "grok_video_15")
        self.assertEqual(data["selected_model_id"], "grok-video-1.5")
        self.assertEqual(data["selected_base_url"], "https://api.119337.xyz/v1")
        self.assertEqual(data["selected_generation_path"], "/video/generations")
        self.assertEqual(data["models"]["grok_video_15"]["model"], "grok-video-1.5")
        self.assertEqual(data["models"]["grok_video_15"]["duration"], [4, 15])
        self.assertEqual(data["models"]["grok_video_15"]["max_prompt_chars"], 4096)
        self.assertEqual(data["models"]["grok_video_15"]["prompt_budget_chars"], 3200)
        self.assertEqual(data["models"]["grok_video_15"]["duration_field"], "seconds")
        self.assertFalse(data["models"]["grok_video_15"]["supports_multiple_references"])
        self.assertEqual(data["models"]["grok_video_15"]["source_image_field"], "image_urls")
        self.assertEqual(data["models"]["grok_image_video"]["model"], "grok-image-video")
        self.assertTrue(data["models"]["grok_image_video"]["supports_multiple_references"])
        self.assertEqual(data["models"]["grok_image_video"]["reference_field"], "image_urls")
        self.assertEqual(data["models"]["grok_image_video"]["max_reference_images"], 7)
        self.assertEqual(data["models"]["grok_image_video"]["max_duration_multi_reference_seconds"], 10)
        self.assertTrue(data["models"]["seedance2"]["enabled"])
        self.assertEqual(data["models"]["seedance2"]["provider"], "fal_queue")
        self.assertTrue(data["models"]["seedance2"]["base_url_set"])
        self.assertEqual(data["models"]["seedance2"]["duration_field"], "duration")
        self.assertEqual(data["models"]["seedance2"]["reference_field"], "image_urls")
        self.assertEqual(data["models"]["seedance2"]["reference_prompt_style"], "seedance_image")
        self.assertEqual(data["models"]["seedance2"]["max_reference_images"], 9)
        self.assertEqual(data["models"]["seedance2"]["api_key_env_names"], ["FAL_KEY"])
        self.assertEqual(data["models"]["seedance2"]["auth_scheme"], "Key")
        self.assertTrue(data["models"]["seedance2"]["omit_model_from_payload"])
        self.assertIn("generate_audio", data["models"]["seedance2"]["payload_defaults"])
        self.assertEqual(data["models"]["seedance2"]["issues"], [])

    def test_third_party_grok_route_never_falls_back_to_xai_api_key(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        for model_key in ("grok_video_15", "grok_image_video"):
            key_names = config["models"][model_key].get("api_key_env_names") or []
            self.assertIn("AI_COMMERCE_VIDEO_API_KEY", key_names)
            self.assertNotIn("XAI_API_KEY", key_names)

        result = run_cmd(
            ["python3", str(SCRIPTS / "validate_config.py"), "--config", str(CONFIG)],
            env={"XAI_API_KEY": "xai-key-must-not-reach-third-party"},
        )
        report = json.loads(result.stdout)
        self.assertFalse(report["api_key_present"])

    def test_validate_config_rejects_prompt_budget_above_provider_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = write_model_config(tmp_path, {
                "max_prompt_chars": 4096,
                "prompt_budget_chars": 5000,
            })
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "validate_config.py"),
                "--config", str(config),
            ])
            self.assertIn("prompt_budget_chars must be <= max_prompt_chars", result.stdout)

    def test_validate_config_loads_private_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "video.env"
            env_file.write_text(
                "AI_COMMERCE_VIDEO_API_KEY=test-env-file-key\n"
                "AI_COMMERCE_VIDEO_BASE_URL=https://api.119337.xyz\n"
                "AI_COMMERCE_VIDEO_MODEL=grok-video-1.5\n",
                encoding="utf-8",
            )
            result = run_cmd(
                ["python3", str(SCRIPTS / "validate_config.py"), "--config", str(CONFIG), "--require-key"],
                env={
                    "AI_COMMERCE_VIDEO_ENV_FILE": str(env_file),
                    "AI_COMMERCE_VIDEO_API_KEY": "",
                    "YUNWU_API_KEY": "",
                    "XAI_API_KEY": "",
                },
            )
            data = json.loads(result.stdout)
            self.assertTrue(data["api_key_present"])
            self.assertIn(str(env_file.resolve()), data["loaded_env_files"])
            self.assertEqual(data["api_key_preview"], "test...-key")

    def test_setup_private_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "ai-commerce-video.env"
            result = run_cmd([
                "python3", str(SCRIPTS / "setup_private_env.py"),
                "--env-file", str(env_file),
                "--key", "test-key",
            ])
            self.assertIn("Private video API env file written", result.stdout)
            text = env_file.read_text(encoding="utf-8")
            self.assertIn("AI_COMMERCE_VIDEO_API_KEY=test-key", text)
            self.assertIn("AI_COMMERCE_VIDEO_BASE_URL=https://api.119337.xyz/v1", text)
            self.assertIn("AI_COMMERCE_VIDEO_MODEL=grok-video-1.5", text)
            self.assertEqual(oct(env_file.stat().st_mode & 0o777), "0o600")

    def test_prepare_project_default_and_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Test Product",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
                "--duration", "45",
            ])
            data = json.loads(result.stdout)
            self.assertEqual(data["segments"], [15, 15, 15])
            plan = json.loads(Path(data["plan"]).read_text(encoding="utf-8"))
            self.assertEqual(plan["total_duration_seconds"], 45)
            self.assertEqual(len(plan["shots"]), 3)

    def test_prepare_project_records_platform_scenario_compliance_and_model_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "TikTok UGC Contract",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
                "--platform", "tiktok",
                "--placement", "in_feed",
                "--campaign-goal", "conversion",
                "--funnel-stage", "consideration",
                "--creative-variant", "ugc_review",
                "--commerce-scenario", "ugc_review",
                "--cta-type", "shop_now",
                "--offer", "15% off",
                "--sku", "SKU-123",
                "--product-url", "https://example.com/product",
                "--shop-destination", "product_page",
                "--marketplace-locale", "US",
                "--claim-risk", "medium",
                "--safe-zone-profile", "tiktok_in_feed",
                "--subtitle-style", "large safe-zone captions",
                "--segment-strategy", "single_clip",
                "--product-category", "beauty device",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            self.assertIn("platform_contract", plan)
            self.assertIn("scenario_contract", plan)
            self.assertIn("compliance_contract", plan)
            self.assertIn("reference_asset_contract", plan)
            self.assertIn("model_capability_contract", plan)
            self.assertEqual(plan["platform_contract"]["profile_key"], "tiktok_in_feed")
            self.assertEqual(plan["platform_contract"]["actual_aspect_ratio"], "9:16")
            self.assertEqual(plan["platform_contract"]["cta_type"], "shop_now")
            self.assertEqual(plan["platform_contract"]["safe_zone_profile"], "tiktok_in_feed")
            self.assertEqual(plan["scenario_contract"]["commerce_scenario"], "ugc_review")
            self.assertEqual(plan["compliance_contract"]["claim_risk"], "medium")
            self.assertEqual(plan["creative_contract"]["platform"], "tiktok")
            self.assertEqual(plan["creative_contract"]["placement"], "in_feed")
            self.assertEqual(plan["creative_contract"]["campaign_goal"], "conversion")
            self.assertEqual(plan["creative_contract"]["funnel_stage"], "consideration")
            self.assertEqual(plan["creative_contract"]["offer"], "15% off")
            self.assertEqual(plan["creative_contract"]["sku"], "SKU-123")
            self.assertEqual(plan["creative_contract"]["segment_strategy"], "single_clip")
            self.assertEqual(plan["model_capability_contract"]["source_image_field"], "image_urls")
            prompt = plan["shots"][0]["prompt"]
            self.assertIn("ugc_review", prompt)
            self.assertIn("buyer-perspective", prompt)
            self.assertIn("Platform contract", prompt)
            self.assertIn("Safe zone profile: tiktok_in_feed", prompt)
            self.assertIn("Compliance contract", prompt)

    def test_realistic_15s_prompt_is_compiled_below_safe_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "perfume-product.png"
            source = tmp_path / "approved-perfume-source.png"
            for path in (product, source):
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
            base_prompt = (
                "Use <SOURCE_IMAGE> as the exact approved first frame and preserve the perfume bottle, "
                "ribbon bow, glass proportions, pink liquid, cap, and visible packaging identity without alteration. "
                "Create a 15-second vertical premium fragrance commercial. Begin with a sharp hero product close-up. "
                "A synthetic adult female presenter naturally approaches and lightly handles the bottle; she speaks "
                "the approved Chinese script with natural lip sync. Use gentle pink-lilac vanity lighting, soft "
                "reflections, restrained floating sparkle particles, and a slow elegant camera push-in. The bottle is "
                "static and inanimate: only hands, camera, lighting, and particles may move. Keep product large, fully "
                "visible, and centered throughout. Clean full-screen commercial footage only: no subtitles, captions, "
                "lower thirds, price tags, CTA text, disclaimers, signage, collage, or new written elements."
            )
            spoken_script = (
                "这支香水，第一眼就让人心动。甜美的粉色瓶身，搭配精致蝴蝶结。"
                "日常约会或通勤，都能为造型添一份精致感。把这份浪漫香气，留给今天的自己。"
            )
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Pink Fragrance Premium",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--video-source-image", str(source),
                "--duration", "15",
                "--prompt", base_prompt,
                "--spoken-script", spoken_script,
                "--creative-variant", "premium_brand",
                "--commerce-scenario", "premium_brand",
                "--product-category", "fragrance",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            shot = plan["shots"][0]
            prompt = shot["prompt"]
            self.assertLessEqual(len(prompt), 2800)
            self.assertLessEqual(len(prompt), 3200)
            self.assertEqual(shot["prompt_contract"]["char_count"], len(prompt))
            self.assertEqual(shot["prompt_contract"]["budget_chars"], 3200)
            self.assertEqual(shot["prompt_contract"]["max_chars"], 4096)
            self.assertEqual(shot["prompt_contract"]["compiler"], "compact-commerce-v1")
            self.assertIn(spoken_script, prompt)
            self.assertIn("high-end brand", prompt)
            self.assertIn("no newly generated written", prompt)
            self.assertIn("inanimate physical product", prompt)
            self.assertNotIn("Evidence required for:", prompt)
            self.assertNotIn("Single-source rule:", prompt)
            self.assertNotIn("Clean full-screen commercial footage only:", prompt)
            self.assertNotIn("no, ,", prompt)
            self.assertTrue(plan["compliance_contract"]["evidence_required_for"])

    def test_prompt_budget_and_compiler_are_documented(self):
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow_text = (SKILL / "references" / "workflow.md").read_text(encoding="utf-8")
        capability_text = (SKILL / "references" / "model-capabilities.md").read_text(encoding="utf-8")
        combined = "\n".join((skill_text, workflow_text, capability_text)).lower()
        self.assertIn("prompt compiler", combined)
        self.assertIn("max_prompt_chars", combined)
        self.assertIn("prompt_budget_chars", combined)
        self.assertIn("do not truncate", combined)

    def test_validate_platform_plan_accepts_tiktok_vertical_safe_zone_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "TikTok Plan",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
                "--platform", "tiktok",
                "--placement", "in_feed",
                "--creative-variant", "ugc_review",
                "--commerce-scenario", "ugc_review",
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            result = run_cmd(["python3", str(SCRIPTS / "validate_platform_plan.py"), "--plan", plan_path])
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"], report)
            texts = [item["text"] for item in report["checks"]]
            self.assertIn("TikTok/Douyin plan uses vertical 9:16", texts)
            self.assertIn("TikTok/Douyin plan has a safe-zone profile", texts)
            self.assertIn("TikTok/Douyin plan requires subtitles", texts)
            self.assertIn("TikTok/Douyin plan includes a strong hook structure", texts)

    def test_amazon_sponsored_products_video_defaults_to_caption_led_product_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Amazon SPV",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
                "--platform", "amazon",
                "--placement", "sponsored_products_video",
                "--creative-variant", "feature_demo",
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
            self.assertEqual(plan["aspect_ratio"], "16:9")
            self.assertEqual(plan["creative_contract"]["speaker_mode"], "silent-captions")
            self.assertEqual(plan["platform_contract"]["audio_policy"], "no_audio")
            self.assertEqual(plan["platform_contract"]["speaker_policy"], "avoid_talking_head")
            result = run_cmd(["python3", str(SCRIPTS / "validate_platform_plan.py"), "--plan", plan_path])
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"], report)
            texts = [item["text"] for item in report["checks"]]
            self.assertIn("Amazon Sponsored Products Video does not use talking-head spoken selling", texts)
            self.assertIn("Amazon Sponsored Products Video does not depend on audio", texts)

    def test_amazon_sponsored_brands_video_uses_supported_ratio_and_duration_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Amazon SBV",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
                "--platform", "amazon",
                "--placement", "sponsored_brands_video",
                "--duration", "15",
                "--creative-variant", "premium_brand",
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
            self.assertEqual(plan["aspect_ratio"], "16:9")
            self.assertEqual(plan["platform_contract"]["min_duration_seconds"], 6)
            self.assertEqual(plan["platform_contract"]["max_duration_seconds"], 45)
            result = run_cmd(["python3", str(SCRIPTS / "validate_platform_plan.py"), "--plan", plan_path])
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"], report)
            texts = [item["text"] for item in report["checks"]]
            self.assertIn("Amazon Sponsored Brands Video uses supported 16:9 or 9:16 aspect ratio", texts)
            self.assertIn("Amazon Sponsored Brands Video duration is within 6-45 seconds", texts)

    def test_amazon_sponsored_brands_video_allows_vertical_mobile_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Amazon SBV Vertical",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
                "--platform", "amazon",
                "--placement", "sponsored_brands_video",
                "--aspect-ratio", "9:16",
                "--duration", "15",
                "--creative-variant", "ugc_review",
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            result = run_cmd(["python3", str(SCRIPTS / "validate_platform_plan.py"), "--plan", plan_path])
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"], report)

    def test_xiaohongshu_plan_contains_authenticity_and_compliance_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "XHS Seed",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
                "--platform", "xiaohongshu",
                "--creative-variant", "lifestyle_seed",
                "--commerce-scenario", "lifestyle_seed",
                "--product-category", "skincare",
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
            self.assertEqual(plan["platform_contract"]["profile_key"], "xiaohongshu")
            self.assertIn("fake personal experience", " ".join(plan["platform_contract"]["common_risks"]))
            self.assertEqual(plan["compliance_contract"]["claim_risk"], "high")
            self.assertIn("real experience", plan["shots"][0]["prompt"])
            result = run_cmd(["python3", str(SCRIPTS / "validate_platform_plan.py"), "--plan", plan_path])
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"], report)
            texts = [item["text"] for item in report["checks"]]
            self.assertIn("Xiaohongshu plan includes authenticity risk control", texts)

    def test_youtube_plan_contains_abcd_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "YouTube Brand",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
                "--platform", "youtube",
                "--creative-variant", "premium_brand",
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
            self.assertIn("Attention, Branding, Connection, Direction", plan["platform_contract"]["recommended_structure"])
            result = run_cmd(["python3", str(SCRIPTS / "validate_platform_plan.py"), "--plan", plan_path])
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"], report)
            texts = [item["text"] for item in report["checks"]]
            self.assertIn("YouTube plan follows ABCD structure", texts)

    def test_dry_run_generation_payload_defaults_to_15s(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Default Duration",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            result = run_cmd(["python3", str(SCRIPTS / "generate_video.py"), "--plan", plan_path, "--dry-run"])
            data = json.loads(result.stdout)
            request_file = Path(data["results"][0]["request_file"])
            record = json.loads(request_file.read_text(encoding="utf-8"))
            self.assertEqual(record["payload"]["seconds"], 15)
            self.assertEqual(record["payload"]["aspect_ratio"], "9:16")
            self.assertEqual(record["payload"]["model"], "grok-video-1.5")
            self.assertIn("image_urls", record["payload"])
            self.assertEqual(len(record["payload"]["image_urls"]), 1)

    def test_real_generation_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Confirmation Gate",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "generate_video.py"),
                "--plan", plan_path,
            ], env={"AI_COMMERCE_VIDEO_API_KEY": "test-key"})
            self.assertIn("explicit final confirmation", result.stdout)

    def test_confirmation_file_requires_image_asset_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Confirmation File Gate",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            confirmation_file = tmp_path / "confirmation.json"
            confirmation_file.write_text(json.dumps({"confirmed": True}), encoding="utf-8")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "generate_video.py"),
                "--plan", plan_path,
                "--confirmation-file", str(confirmation_file),
            ], env={"AI_COMMERCE_VIDEO_API_KEY": "test-key"})
            self.assertIn("image_assets_confirmed=true", result.stdout)

    def test_confirmation_file_accepts_final_image_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            server = HTTPServer(("127.0.0.1", 0), MockVideoHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                image = tmp_path / "product.png"
                image.write_bytes(b"\x89PNG\r\n\x1a\n")
                prep = run_cmd([
                    "python3", str(SCRIPTS / "prepare_project.py"),
                    "--name", "Final Image Approval",
                    "--project-root", str(tmp_path / "projects"),
                    "--product-image", str(image),
                ])
                plan_path = json.loads(prep.stdout)["plan"]
                confirmation_file = tmp_path / "confirmation.json"
                confirmation_file.write_text(json.dumps({
                    "image_assets_confirmed": True,
                    "video_generation_confirmed": True,
                    "approved_by": "test",
                }), encoding="utf-8")
                env = {
                    "AI_COMMERCE_VIDEO_API_KEY": "test-key",
                    "AI_COMMERCE_VIDEO_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1",
                }
                submitted = run_cmd([
                    "python3", str(SCRIPTS / "generate_video.py"),
                    "--plan", plan_path,
                    "--confirmation-file", str(confirmation_file),
                ], env=env)
                request_file = Path(json.loads(submitted.stdout)["results"][0]["request_file"])
                record = json.loads(request_file.read_text(encoding="utf-8"))
                self.assertEqual(record["confirmation"]["source"], "confirmation_file")
                self.assertTrue(record["confirmation"]["image_assets_confirmed"])
                self.assertTrue(record["confirmation"]["video_generation_confirmed"])
                self.assertEqual(record["confirmation"]["approved_by"], "test")
                self.assertEqual(server.last_payload["seconds"], 15)
                self.assertIn("image_urls", server.last_payload)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_119337_base_url_normalizes_to_v1(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "URL Normalize",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            result = run_cmd([
                "python3", str(SCRIPTS / "generate_video.py"),
                "--plan", plan_path,
                "--dry-run",
            ], env={"AI_COMMERCE_VIDEO_BASE_URL": "https://api.119337.xyz"})
            request_file = Path(json.loads(result.stdout)["results"][0]["request_file"])
            record = json.loads(request_file.read_text(encoding="utf-8"))
            self.assertEqual(record["submit_url"], "https://api.119337.xyz/v1/video/generations")

    def test_prepare_project_records_reference_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            model = tmp_path / "model.png"
            scene = tmp_path / "scene.png"
            for path in (product, model, scene):
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Reference Images",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--model-image", str(model),
                "--reference-image", f"scene={scene}",
                "--model-key", "grok_image_video",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            self.assertEqual([item["role"] for item in plan["references"]], ["model", "scene"])
            self.assertEqual(plan["shots"][0]["references"][0]["role"], "model")
            self.assertIn("/assets/references/model/", plan["references"][0]["value"])
            self.assertIn("/assets/references/scene/", plan["references"][1]["value"])
            self.assertEqual(plan["asset_contract"]["video_source_asset"]["role"], "product")
            self.assertEqual(plan["shots"][0]["image"]["role"], "product")
            self.assertEqual([item["role"] for item in plan["shots"][0]["video_references"]], ["product", "model", "scene"])
            self.assertEqual(plan["shots"][0]["reference_prompt_map"][0]["token"], "<IMAGE_1>")
            self.assertIn("<IMAGE_1> = product reference", plan["shots"][0]["prompt"])
            self.assertIn("<IMAGE_2> = model reference", plan["shots"][0]["prompt"])

    def test_video_source_image_is_uploaded_for_single_image_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = write_model_config(tmp_path, {
                "mode": "image-to-video",
                "input_mode": "image-to-video",
                "supports_multiple_references": False,
            })
            product = tmp_path / "product.png"
            source = tmp_path / "approved-presenter-product-source.png"
            storyboard = tmp_path / "storyboard.png"
            for path in (product, source, storyboard):
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Source Consistency",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--video-source-image", str(source),
                "--reference-image", f"storyboard={storyboard}",
                "--config", str(config),
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
            locked_source = plan["asset_contract"]["video_source_asset"]["value"]
            self.assertIn("approved-presenter-product-source.png", locked_source)
            self.assertEqual(plan["shots"][0]["image"]["value"], locked_source)

            dry_run = run_cmd(["python3", str(SCRIPTS / "generate_video.py"), "--plan", plan_path, "--config", str(config), "--dry-run"])
            request_file = Path(json.loads(dry_run.stdout)["results"][0]["request_file"])
            record = json.loads(request_file.read_text(encoding="utf-8"))
            self.assertEqual(record["asset_trace"]["source_image"]["value"], locked_source)
            self.assertEqual(record["asset_trace"]["locked_video_source"]["value"], locked_source)
            self.assertFalse(record["asset_trace"]["references_included_in_payload"])

    def test_generate_video_rejects_confirmed_reference_mismatch_for_single_image_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = write_model_config(tmp_path, {
                "mode": "image-to-video",
                "input_mode": "image-to-video",
                "supports_multiple_references": False,
            })
            product = tmp_path / "product.png"
            model = tmp_path / "approved-model-source.png"
            for path in (product, model):
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
            request_file = tmp_path / "requests" / "shot_01_request.json"
            clip_file = tmp_path / "clips" / "shot_01.mp4"
            request_file.parent.mkdir()
            clip_file.parent.mkdir()
            plan = {
                "project_name": "bad-asset-plan",
                "model_key": "grok_video_15",
                "aspect_ratio": "9:16",
                "resolution": "720p",
                "product_asset": {"kind": "file", "value": str(product), "role": "product"},
                "references": [{"kind": "file", "value": str(model), "role": "model", "id": "ref_01"}],
                "shots": [{
                    "id": "shot_01",
                    "duration_seconds": 15,
                    "prompt": "bad mismatch",
                    "image": {"kind": "file", "value": str(product), "role": "product"},
                    "references": [{"kind": "file", "value": str(model), "role": "model", "id": "ref_01"}],
                    "request_file": str(request_file),
                    "clip_file": str(clip_file),
                }],
            }
            plan_path = tmp_path / "generation-plan.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            result = run_cmd_fail(["python3", str(SCRIPTS / "generate_video.py"), "--plan", str(plan_path), "--config", str(config), "--dry-run"])
            self.assertIn("Asset mismatch for single-image video model", result.stdout)

    def test_preflight_blocks_provider_prompt_over_configured_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Oversized Preflight Prompt",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
            ])
            plan_path = Path(json.loads(prep.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["shots"][0]["prompt"] = "no newly generated written elements. " + ("x" * 4096)
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(plan_path),
            ])
            self.assertIn("prompt length", result.stdout)
            self.assertIn("max_prompt_chars=4096", result.stdout)

    def test_preflight_reports_exact_provider_prompt_lengths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Prompt Length Report",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
            ])
            plan_path = Path(json.loads(prep.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            preflight = run_cmd([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(plan_path),
            ])
            report = json.loads(preflight.stdout)
            summary = report["prompt_summary"][0]
            prompt = plan["shots"][0]["prompt"]
            self.assertEqual(summary["shot_id"], "shot_01")
            self.assertEqual(summary["char_count"], len(prompt))
            self.assertEqual(summary["utf8_bytes"], len(prompt.encode("utf-8")))
            self.assertEqual(summary["prompt_budget_chars"], 3200)
            self.assertEqual(summary["max_prompt_chars"], 4096)
            self.assertTrue(summary["within_budget"])
            self.assertTrue(summary["within_max"])
            self.assertEqual(summary["compiler"], "compact-commerce-v1")

    def test_generate_video_dry_run_rejects_provider_prompt_over_configured_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Oversized Direct Prompt",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
            ])
            plan_path = Path(json.loads(prep.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["shots"][0]["prompt"] = "no newly generated written elements. " + ("x" * 4096)
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "generate_video.py"),
                "--plan", str(plan_path),
                "--dry-run",
            ])
            self.assertIn("prompt length", result.stdout)
            self.assertIn("max_prompt_chars=4096", result.stdout)

    def test_multi_reference_payload_uses_confirmed_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            model = tmp_path / "model-reference.png"
            storyboard = tmp_path / "storyboard-reference.png"
            for path in (product, model, storyboard):
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Multi Reference",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--model-image", str(model),
                "--reference-image", f"storyboard={storyboard}",
                "--model-key", "grok_image_video",
                "--prompt", "Create a marketplace product ad using the approved presenter and storyboard.",
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
            self.assertEqual([item["role"] for item in plan["shots"][0]["video_references"]], ["product", "model", "storyboard"])
            self.assertIn("<IMAGE_1> = product reference", plan["shots"][0]["prompt"])
            self.assertIn("<IMAGE_2> = model reference", plan["shots"][0]["prompt"])
            self.assertIn("<IMAGE_3> = storyboard reference", plan["shots"][0]["prompt"])

            dry_run = run_cmd(["python3", str(SCRIPTS / "generate_video.py"), "--plan", plan_path, "--dry-run"])
            request_file = Path(json.loads(dry_run.stdout)["results"][0]["request_file"])
            record = json.loads(request_file.read_text(encoding="utf-8"))
            self.assertNotIn("image", record["payload"])
            self.assertNotIn("reference_images", record["payload"])
            self.assertIn("image_urls", record["payload"])
            self.assertEqual(record["payload"]["model"], "grok-image-video")
            self.assertEqual(len(record["payload"]["image_urls"]), 3)
            self.assertTrue(all(value.startswith("data:image/png;base64,") for value in record["payload"]["image_urls"]))
            self.assertTrue(record["asset_trace"]["references_included_in_payload"])
            self.assertEqual(record["asset_trace"]["payload_reference_roles"], ["product", "model", "storyboard"])

    def test_grok_image_video_multi_reference_splits_at_10s(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            model = tmp_path / "model-reference.png"
            storyboard = tmp_path / "storyboard-reference.png"
            for path in (product, model, storyboard):
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Multi Reference Split",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--model-image", str(model),
                "--reference-image", f"storyboard={storyboard}",
                "--duration", "15",
                "--model-key", "grok_image_video",
            ])
            data = json.loads(prep.stdout)
            self.assertEqual(data["segments"], [10, 6])
            plan = json.loads(Path(data["plan"]).read_text(encoding="utf-8"))
            self.assertEqual([shot["duration_seconds"] for shot in plan["shots"]], [10, 6])
            self.assertTrue(all(value in {4, 6, 8, 10} for value in data["segments"]))

            dry_run = run_cmd(["python3", str(SCRIPTS / "generate_video.py"), "--plan", data["plan"], "--dry-run"])
            request_file = Path(json.loads(dry_run.stdout)["results"][0]["request_file"])
            record = json.loads(request_file.read_text(encoding="utf-8"))
            self.assertEqual(record["payload"]["seconds"], 10)
            self.assertEqual(len(record["payload"]["image_urls"]), 3)

    def test_per_segment_source_frames_create_multiple_single_image_shots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            sources = [tmp_path / f"shot-{index}.png" for index in range(1, 3)]
            for path in [product, *sources]:
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Segment Sources",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--reference-strategy", "per_segment_source_frames",
                "--segment-source-image", f"shot_01={sources[0]}",
                "--segment-source-image", f"shot_02={sources[1]}",
                "--duration", "30",
            ])
            data = json.loads(prep.stdout)
            self.assertEqual(data["segments"], [15, 15])
            plan_path = data["plan"]
            plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
            self.assertEqual(plan["creative_contract"]["reference_strategy"], "per_segment_source_frames")
            self.assertEqual(len(plan["asset_contract"]["segment_source_assets"]), 2)
            self.assertEqual([shot["duration_seconds"] for shot in plan["shots"]], [15, 15])
            self.assertEqual([shot["image"]["role"] for shot in plan["shots"]], ["segment_source", "segment_source"])
            self.assertIn("shot-1.png", plan["shots"][0]["image"]["value"])
            self.assertIn("per_segment_source_frames", plan["shots"][0]["prompt"])

            dry_run = run_cmd(["python3", str(SCRIPTS / "generate_video.py"), "--plan", plan_path, "--dry-run"])
            results = json.loads(dry_run.stdout)["results"]
            self.assertEqual([item["shot_id"] for item in results], ["shot_01", "shot_02"])
            first_record = json.loads(Path(results[0]["request_file"]).read_text(encoding="utf-8"))
            self.assertEqual(first_record["payload"]["seconds"], 15)
            self.assertEqual(len(first_record["payload"]["image_urls"]), 1)
            self.assertEqual(first_record["asset_trace"]["reference_strategy"], "per_segment_source_frames")
            self.assertEqual(first_record["asset_trace"]["segment_source_count"], 2)
            self.assertIn("shot-1.png", first_record["asset_trace"]["source_image"]["value"])

    def test_single_image_model_rejects_storyboard_sheet_reference_strategy(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            storyboard = tmp_path / "storyboard.png"
            for path in (product, storyboard):
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Bad Storyboard Strategy",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--reference-strategy", "storyboard_sheet_reference",
                "--reference-image", f"storyboard={storyboard}",
            ])
            self.assertIn("requires a model with supports_multiple_references=true", result.stdout)

    def test_global_model_env_does_not_override_explicit_multi_reference_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            model = tmp_path / "model-reference.png"
            for path in (product, model):
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Explicit Multi Route",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--model-image", str(model),
                "--model-key", "grok_image_video",
            ], env={"AI_COMMERCE_VIDEO_MODEL": "grok-video-1.5"})
            plan_path = json.loads(prep.stdout)["plan"]
            dry_run = run_cmd([
                "python3", str(SCRIPTS / "generate_video.py"),
                "--plan", plan_path,
                "--dry-run",
            ], env={"AI_COMMERCE_VIDEO_MODEL": "grok-video-1.5"})
            request_file = Path(json.loads(dry_run.stdout)["results"][0]["request_file"])
            record = json.loads(request_file.read_text(encoding="utf-8"))
            self.assertEqual(record["payload"]["model"], "grok-image-video")
            self.assertEqual(len(record["payload"]["image_urls"]), 2)

    def test_global_base_url_env_does_not_override_explicit_seedance_route(self):
        result = run_cmd([
            "python3", str(SCRIPTS / "validate_config.py"),
            "--config", str(CONFIG),
            "--model-key", "seedance2",
        ], env={"AI_COMMERCE_VIDEO_BASE_URL": "https://api.119337.xyz/v1"})
        data = json.loads(result.stdout)
        self.assertEqual(data["selected_model"], "seedance2")
        self.assertEqual(data["selected_base_url"], "https://queue.fal.run")

    def test_seedance_prompt_style_uses_at_reference_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            model = tmp_path / "model.png"
            for path in (product, model):
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Seedance References",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--model-image", str(model),
                "--model-key", "seedance2",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            prompt = plan["shots"][0]["prompt"]
            self.assertEqual([item["token"] for item in plan["shots"][0]["reference_prompt_map"]], ["@Image1", "@Image2"])
            self.assertIn("@Image1 = product reference", prompt)
            self.assertIn("@Image2 = model reference", prompt)

    def test_seedance_multi_reference_storyboard_prompt_uses_storyboard_as_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            model = tmp_path / "model.png"
            storyboard = tmp_path / "storyboard.png"
            for path in (product, model, storyboard):
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Seedance Storyboard",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--model-image", str(model),
                "--reference-image", f"storyboard={storyboard}",
                "--model-key", "seedance2",
                "--reference-strategy", "multi_reference_storyboard",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            prompt = plan["shots"][0]["prompt"]
            self.assertEqual(plan["creative_contract"]["reference_strategy"], "multi_reference_storyboard")
            self.assertEqual([item["role"] for item in plan["shots"][0]["video_references"]], ["product", "model", "storyboard"])
            self.assertIn("@Image3 = storyboard reference", prompt)
            self.assertIn("storyboard controls sequence and rhythm only", prompt)
            self.assertIn("do not reproduce grid panels", prompt)

    def test_seedance_fal_queue_submit_poll_and_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mock_video = tmp_path / "fal-video.mp4"
            make_test_video(mock_video, audio=True)
            server = HTTPServer(("127.0.0.1", 0), MockFalVideoHandler)
            server.video_bytes = mock_video.read_bytes()
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config = write_model_config(tmp_path, {"base_url": f"http://127.0.0.1:{server.server_port}"}, model_key="seedance2")
                product = tmp_path / "product.png"
                model = tmp_path / "model-reference.png"
                storyboard = tmp_path / "storyboard-reference.png"
                for path in (product, model, storyboard):
                    path.write_bytes(b"\x89PNG\r\n\x1a\n")
                prep = run_cmd([
                    "python3", str(SCRIPTS / "prepare_project.py"),
                    "--name", "Seedance Fal Queue",
                    "--project-root", str(tmp_path / "projects"),
                    "--product-image", str(product),
                    "--model-image", str(model),
                    "--reference-image", f"storyboard={storyboard}",
                    "--model-key", "seedance2",
                    "--config", str(config),
                    "--reference-strategy", "multi_reference_storyboard",
                    "--duration", "15",
                ])
                plan_path = json.loads(prep.stdout)["plan"]
                confirmation_file = tmp_path / "confirmation.json"
                confirmation_file.write_text(json.dumps({
                    "image_assets_confirmed": True,
                    "video_generation_confirmed": True,
                    "approved_by": "test",
                }), encoding="utf-8")
                env = {"FAL_KEY": "test-fal-key"}
                submitted = run_cmd([
                    "python3", str(SCRIPTS / "generate_video.py"),
                    "--plan", plan_path,
                    "--config", str(config),
                    "--confirmation-file", str(confirmation_file),
                ], env=env)
                request_file = Path(json.loads(submitted.stdout)["results"][0]["request_file"])
                record = json.loads(request_file.read_text(encoding="utf-8"))
                self.assertEqual(record["model_key"], "seedance2")
                self.assertEqual(record["provider"], "fal_queue")
                self.assertEqual(record["response"]["request_id"], "fal-request-1")
                self.assertIn("status_url", record["response"])
                self.assertIn("response_url", record["response"])
                self.assertNotIn("model", server.last_payload)
                self.assertEqual(server.last_payload["duration"], 15)
                self.assertEqual(server.last_payload["aspect_ratio"], "9:16")
                self.assertEqual(server.last_payload["resolution"], "720p")
                self.assertTrue(server.last_payload["generate_audio"])
                self.assertEqual(server.last_payload["bitrate_mode"], "standard")
                self.assertEqual(len(server.last_payload["image_urls"]), 3)
                self.assertTrue(server.last_payload["prompt"].count("@Image") >= 3)
                self.assertEqual(server.last_post_auth, "Key test-fal-key")

                polled = run_cmd([
                    "python3", str(SCRIPTS / "poll_video.py"),
                    "--request-file", str(request_file),
                    "--config", str(config),
                ], env=env)
                output = Path(json.loads(polled.stdout)["output"])
                self.assertTrue(output.exists())
                self.assertGreater(output.stat().st_size, 1000)
                self.assertEqual(server.last_status_auth, "Key test-fal-key")
                self.assertEqual(server.last_response_auth, "Key test-fal-key")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_prepare_project_defaults_to_presenter_spoken_and_static_product(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "rabbit.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            prompt = (
                "Create a product ad. Chinese voiceover and captions: 这只小白兔太可爱了。 "
                "Show subtle plush motion and a clean hero shot."
            )
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Rabbit Plush",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--prompt", prompt,
                "--commerce-platform", "amazon-cross-border",
                "--product-category", "plush toy",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            contract = plan["creative_contract"]
            shot_prompt = plan["shots"][0]["prompt"]
            self.assertEqual(contract["speaker_mode"], "digital-human-spoken")
            self.assertEqual(contract["product_motion_policy"], "static-inanimate")
            self.assertEqual(contract["commerce_platform"], "amazon-cross-border")
            self.assertIn("Chinese on-camera presenter speech", shot_prompt)
            self.assertNotIn("presenter speech and captions", shot_prompt)
            self.assertIn("no newly generated written or typographic elements", shot_prompt)
            self.assertNotIn("Chinese voiceover and captions", shot_prompt)
            self.assertIn("visible synthetic e-commerce presenter is the presenter", shot_prompt)
            self.assertIn("must not blink, breathe, talk, walk", shot_prompt)
            self.assertIn("camera movement around the plush", shot_prompt)
            self.assertNotIn("subtle plush motion", shot_prompt)

    def test_prepare_project_records_story_reversal_creative_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Story Reversal",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--creative-variant", "story_reversal",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            self.assertEqual(plan["creative_contract"]["creative_variant"], "story_reversal")
            self.assertIn("Creative variant: story_reversal", plan["creative_contract"]["creative_variant_rule"])

    def test_prepare_project_defaults_creative_variant_to_commerce_direct(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Default Creative",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            self.assertEqual(plan["creative_contract"]["creative_variant"], "commerce_direct")
            self.assertIn("conversion-focused product ad", plan["shots"][0]["prompt"])

    def test_story_reversal_prompt_contains_story_beats_and_cta(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Story Prompt",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--creative-variant", "story_reversal",
                "--commerce-platform", "douyin",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            prompt = plan["shots"][0]["prompt"]
            self.assertIn("story_reversal", prompt)
            self.assertIn("story hook", prompt)
            self.assertIn("conflict or pain point", prompt)
            self.assertIn("reversal", prompt)
            self.assertIn("product as the solution", prompt)
            self.assertIn("CTA", prompt)

    def test_hybrid_creative_variant_prompt_balances_hook_and_selling(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Hybrid Prompt",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--creative-variant", "hybrid",
                "--commerce-platform", "tiktok",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            prompt = plan["shots"][0]["prompt"]
            self.assertEqual(plan["creative_contract"]["creative_variant"], "hybrid")
            self.assertIn("Creative variant: hybrid", prompt)
            self.assertIn("lifestyle/story hook", prompt)
            self.assertIn("direct product proof", prompt)
            self.assertIn("product clarity wins over plot complexity", prompt)

    def test_extended_creative_variant_prompts_are_supported(self):
        expected = {
            "ugc_review": ["buyer-perspective", "real-feeling", "selling points", "CTA"],
            "comparison_test": ["side-by-side", "objective features", "Avoid malicious competitor attacks"],
            "lifestyle_seed": ["aspirational", "believable daily scenario", "soft CTA"],
            "premium_brand": ["high-end brand", "design", "do not turn the ad into low-price"],
            "feature_demo": ["functional product demonstration", "real use", "close-up proof"],
            "unboxing": ["first-impression", "package reveal", "included accessories"],
            "live_shopping_teaser": ["live-room", "limited offer", "live/shop destination"],
            "retargeting_offer": ["remarketing", "answer one likely objection", "fake scarcity"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            for variant, terms in expected.items():
                result = run_cmd([
                    "python3", str(SCRIPTS / "prepare_project.py"),
                    "--name", f"{variant} Prompt",
                    "--project-root", str(tmp_path / "projects"),
                    "--product-image", str(product),
                    "--creative-variant", variant,
                    "--platform", "xiaohongshu" if variant in {"ugc_review", "lifestyle_seed"} else "amazon",
                ])
                plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
                prompt = plan["shots"][0]["prompt"]
                self.assertEqual(plan["creative_contract"]["creative_variant"], variant)
                for term in terms:
                    self.assertIn(term, prompt)

    def test_prepare_project_allows_explicit_voiceover(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Narrated Product",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--speaker-mode", "voiceover",
                "--product-motion-policy", "demonstrated-function",
                "--prompt", "Use voiceover and captions for a functional product demo.",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            shot_prompt = plan["shots"][0]["prompt"]
            self.assertEqual(plan["creative_contract"]["speaker_mode"], "voiceover")
            self.assertEqual(plan["creative_contract"]["product_motion_policy"], "demonstrated-function")
            self.assertIn("use off-screen voiceover", shot_prompt)
            self.assertIn("real product function or mechanism", shot_prompt)

    def test_mock_api_submit_poll_and_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mock_video = tmp_path / "mock-video.mp4"
            make_test_video(mock_video, audio=True)
            server = HTTPServer(("127.0.0.1", 0), MockVideoHandler)
            server.video_bytes = mock_video.read_bytes()
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                tmp_path = Path(tmp)
                image = tmp_path / "product.png"
                image.write_bytes(b"\x89PNG\r\n\x1a\n")
                prep = run_cmd([
                    "python3", str(SCRIPTS / "prepare_project.py"),
                    "--name", "Mock API",
                    "--project-root", str(tmp_path / "projects"),
                    "--product-image", str(image),
                ])
                plan_path = json.loads(prep.stdout)["plan"]
                env = {
                    "AI_COMMERCE_VIDEO_API_KEY": "test-key",
                    "AI_COMMERCE_VIDEO_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1",
                }
                submitted = run_cmd(["python3", str(SCRIPTS / "generate_video.py"), "--plan", plan_path, "--confirmed"], env=env)
                request_file = Path(json.loads(submitted.stdout)["results"][0]["request_file"])
                polled = run_cmd(["python3", str(SCRIPTS / "poll_video.py"), "--request-file", str(request_file)], env=env)
                output = Path(json.loads(polled.stdout)["output"])
                self.assertTrue(output.exists())
                self.assertGreater(output.stat().st_size, 1000)
                self.assertTrue(json.loads(polled.stdout)["media"]["has_video"])
                self.assertEqual(server.last_payload["seconds"], 15)
                self.assertEqual(server.last_payload["model"], "grok-video-1.5")
                self.assertIn("image_urls", server.last_payload)
                self.assertEqual(len(server.last_payload["image_urls"]), 1)
                self.assertEqual(server.last_post_user_agent, "ai-commerce-video-skill/1.0")
                self.assertEqual(server.last_get_user_agent, "ai-commerce-video-skill/1.0")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_poll_rejects_invalid_video_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request_file = tmp_path / "requests" / "shot_01_request.json"
            request_file.parent.mkdir()
            request_file.write_text(json.dumps({"shot_id": "shot_01", "response": {"request_id": "mock"}}), encoding="utf-8")
            invalid = tmp_path / "bad.mp4"
            invalid.write_bytes(b"not a real mp4")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "poll_video.py"),
                "--request-file", str(request_file),
                "--mock-video", str(invalid),
            ])
            self.assertIn("Command failed", result.stdout)

    def test_stitch_normalizes_and_validates_real_mp4s(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            clips = project / "clips"
            clips.mkdir()
            make_test_video(clips / "shot_01.mp4", size="320x240", fps=24, duration=1, color="blue", audio=True)
            make_test_video(clips / "shot_02.mp4", size="640x360", fps=30, duration=1, color="green", audio=True)
            result = run_cmd([
                "python3", str(SCRIPTS / "stitch_clips.py"),
                "--project-dir", str(project),
                "--target-resolution", "720x1280",
                "--target-fps", "30",
                "--require-audio",
            ])
            data = json.loads(result.stdout)
            final = Path(data["output"])
            self.assertTrue(final.exists())
            self.assertTrue(data["final_media"]["has_video"])
            self.assertTrue(data["final_media"]["has_audio"])
            self.assertEqual(data["final_media"]["video"]["width"], 720)
            self.assertEqual(data["final_media"]["video"]["height"], 1280)
            self.assertEqual(data["intermediate_audio_codec"], "pcm_s16le")
            self.assertTrue(data["single_final_aac_encode"])
            self.assertFalse(data["per_clip_fades_applied"])
            self.assertTrue(Path(data["report_file"]).exists())


if __name__ == "__main__":
    unittest.main()
