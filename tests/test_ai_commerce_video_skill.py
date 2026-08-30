#!/usr/bin/env python3
"""Offline validation for the ai-commerce-video skill."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
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
    args = list(args)
    if len(args) > 1 and Path(str(args[1])).name == "prepare_project.py" and "--model-key" not in args:
        args.extend(["--model-key", "grok_video_15"])
    full_env = os.environ.copy()
    for key in list(full_env):
        if key in {"AI_COMMERCE_VIDEO_API_KEY", "AI_COMMERCE_VIDEO_MIKUAPI_KEY", "AI_COMMERCE_VIDEO_119337_KEY", "AI_COMMERCE_VIDEO_BASE_URL", "AI_COMMERCE_VIDEO_MODEL", "AI_COMMERCE_VIDEO_PROXY_URL", "AI_COMMERCE_VIDEO_ENV_FILE", "YUNWU_API_KEY", "XAI_API_KEY", "FAL_KEY"} or key.startswith("AI_COMMERCE_VIDEO_MODEL_") or key.startswith("AI_COMMERCE_VIDEO_BASE_URL_"):
            full_env.pop(key, None)
    full_env["AI_COMMERCE_VIDEO_ENV_FILE"] = str(ROOT / ".nonexistent-test-env")
    full_env["AI_COMMERCE_VIDEO_DISABLE_KEYCHAIN"] = "1"
    full_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        full_env.update(env)
    result = subprocess.run(args, cwd=cwd, env=full_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise AssertionError(f"Command failed: {' '.join(map(str, args))}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result


def run_cmd_fail(args, cwd=ROOT, env=None):
    args = list(args)
    if len(args) > 1 and Path(str(args[1])).name == "prepare_project.py" and "--model-key" not in args:
        args.extend(["--model-key", "grok_video_15"])
    full_env = os.environ.copy()
    for key in list(full_env):
        if key in {"AI_COMMERCE_VIDEO_API_KEY", "AI_COMMERCE_VIDEO_MIKUAPI_KEY", "AI_COMMERCE_VIDEO_119337_KEY", "AI_COMMERCE_VIDEO_BASE_URL", "AI_COMMERCE_VIDEO_MODEL", "AI_COMMERCE_VIDEO_PROXY_URL", "AI_COMMERCE_VIDEO_ENV_FILE", "YUNWU_API_KEY", "XAI_API_KEY", "FAL_KEY"} or key.startswith("AI_COMMERCE_VIDEO_MODEL_") or key.startswith("AI_COMMERCE_VIDEO_BASE_URL_"):
            full_env.pop(key, None)
    full_env["AI_COMMERCE_VIDEO_ENV_FILE"] = str(ROOT / ".nonexistent-test-env")
    full_env["AI_COMMERCE_VIDEO_DISABLE_KEYCHAIN"] = "1"
    full_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        full_env.update(env)
    result = subprocess.run(args, cwd=cwd, env=full_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        raise AssertionError(f"Command unexpectedly passed: {' '.join(map(str, args))}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result


def write_model_config(tmp_path: Path, model_overrides: dict, model_key: str = "grok_video_15_reference") -> Path:
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
        if self.path != "/v1/videos/generations":
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
            "request_id": "mock-request-1",
        }).encode("utf-8"))

    def do_GET(self):
        if self.path == "/v1/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"id": "grok-imagine-video-1.5"}]}).encode("utf-8"))
            return
        if self.path == "/v1/videos/mock-request-1":
            self.server.last_get_user_agent = self.headers.get("User-Agent")
            url = f"http://127.0.0.1:{self.server.server_port}/mock-video.mp4"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "request_id": "mock-request-1",
                "status": "done",
                "video_url": url,
                "data": {
                    "id": "upstream-mock-1",
                    "channel_id": 11,
                    "status": "done",
                    "progress": "100%",
                    "result_url": url,
                    "prompt": getattr(self.server, "returned_prompt", self.server.last_payload["prompt"]),
                    "properties": {"input": ""},
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


class MockImageContractRejectHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/v1/videos/generations":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.last_payload = json.loads(body.decode("utf-8"))
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "code": "fail_to_fetch_task",
            "message": "this model requires exactly one reference image",
            "data": None,
        }).encode("utf-8"))

    def do_GET(self):
        if self.path == "/v1/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"id": "grok-imagine-video-1.5"}]}).encode("utf-8"))
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
    def guarded_submit(
        self,
        plan_path: str | Path,
        *,
        config: Path | None = None,
        env: dict | None = None,
        expect_ok: bool = True,
    ):
        plan_path = Path(plan_path)
        preflight = ["python3", str(SCRIPTS / "preflight_project.py"), "--plan", str(plan_path)]
        if config:
            preflight.extend(["--config", str(config)])
        run_cmd(preflight, env=env)
        run_cmd([
            "python3", str(SCRIPTS / "workflow_engine.py"),
            "--project-dir", str(plan_path.parent),
            "confirm", "--approved-by", "offline-test",
        ], env=env)
        submit = [
            "python3", str(SCRIPTS / "workflow_engine.py"),
            "--project-dir", str(plan_path.parent),
            "submit",
        ]
        if config:
            submit.extend(["--config", str(config)])
        return (run_cmd if expect_ok else run_cmd_fail)(submit, env=env)

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
            if not any(part in {"projects", "dist", "outputs", "clips", "requests"} for part in path.parts)
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
            SKILL / "references" / "professional-visual-design.md",
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
            SCRIPTS / "check_provider_readiness.py",
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
        self.assertNotRegex(frontmatter, r"(?m)^compatibility:")
        self.assertLessEqual(len(skill_text.split()), 1200)
        self.assertIn("## Operating Modes", skill_text)
        self.assertNotIn("- Always:", skill_text)

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
            if any(part in {"projects", "dist", "outputs", "clips", "requests"} for part in path.parts):
                continue
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
        self.assertIn("two purposeful approvals", skill_text)
        self.assertIn("actual ordered reference set", skill_text)
        self.assertIn("faithful high-resolution professional product master in `<IMAGE_0>`", skill_text)
        self.assertIn("generated single-purpose controls", skill_text)
        self.assertIn("Creative Plan, Image Preparation, and Final Approval", workflow_text)
        self.assertIn("Stage 1 creative approval", workflow_text)
        self.assertIn("Use Codex `imagegen` / image2", workflow_text)
        self.assertIn("complete generated Reference Pack with the product master first", workflow_text)
        self.assertIn("实际生成用图", template_text)
        self.assertIn("两阶段确认模板", template_text)
        self.assertIn("确认并生成", template_text)
        self.assertIn("最终提交给视频模型的图片数量", template_text)

    def test_normal_flow_uses_two_purposeful_approvals(self):
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow_text = (SKILL / "references" / "workflow.md").read_text(encoding="utf-8")
        template_text = (SKILL / "references" / "proposal-template.md").read_text(encoding="utf-8")
        readme_zh = (SKILL / "README.zh-CN.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, template_text, readme_zh])
        self.assertIn("方案确认，生成参考图", combined)
        self.assertIn("Do not split Stage 1", workflow_text)
        self.assertIn("采用两次有意义的确认", readme_zh)
        self.assertIn("阶段 1", template_text)
        self.assertIn("阶段 2", template_text)

    def test_provider_503_model_visibility_diagnosis_is_documented(self):
        provider_text = (SKILL / "references" / "grok-video-api.md").read_text(encoding="utf-8")
        self.assertIn("503 model_not_found", provider_text)
        self.assertIn("GET /v1/models", provider_text)
        self.assertIn("rather than an image-field failure", provider_text)
        self.assertIn("do not automatically resubmit", provider_text)

    def test_creative_variant_ab_proposal_contract_is_documented(self):
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow_text = (SKILL / "references" / "workflow.md").read_text(encoding="utf-8")
        template_text = (SKILL / "references" / "proposal-template.md").read_text(encoding="utf-8")
        variant_text = (SKILL / "references" / "creative-variants.md").read_text(encoding="utf-8")
        combined = "\n".join([skill_text, workflow_text, template_text, variant_text])
        self.assertIn("AI 推荐的广告方向", template_text)
        self.assertIn("可选方向", template_text)
        self.assertIn("commerce_direct", combined)
        self.assertIn("story_reversal", combined)
        self.assertIn("ugc_review", variant_text)
        self.assertIn("comparison_test", variant_text)
        self.assertIn("lifestyle_seed", variant_text)
        self.assertIn("premium_brand", variant_text)
        self.assertIn("按 AI 推荐", combined)
        self.assertIn("selects one professional AI recommendation automatically", workflow_text)
        self.assertIn("If the user asks for plan-only", variant_text)
        self.assertIn("Stage 1", skill_text)
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
        self.assertIn("Never upload a 6-grid or 9-grid storyboard as the only source frame", strategy_text)
        self.assertIn("--segment-source-image shot_01", strategy_text)

    def test_visual_approval_gate_is_documented_for_asset_consistency(self):
        asset_text = (SKILL / "references" / "asset-consistency.md").read_text(encoding="utf-8")
        capability_text = (SKILL / "references" / "model-capabilities.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("generated professional product master is the first Stage 2 Provider slot", asset_text)
        self.assertIn("covered by `确认并生成`", asset_text)
        self.assertIn("Variable Material Handling", asset_text)
        self.assertIn("Multiple product angles", asset_text)
        self.assertIn("generate only necessary later single-purpose controls", capability_text)
        self.assertIn("storyboard/contact sheet is a human-review preview", capability_text)
        self.assertIn("Stage 2 `确认并生成`", readme)

    def test_validate_config(self):
        result = run_cmd(["python3", str(SCRIPTS / "validate_config.py"), "--config", str(CONFIG)])
        data = json.loads(result.stdout)
        self.assertTrue(data["api_key_present"] in {True, False})
        self.assertNotIn("api_key_preview", data)
        self.assertEqual(data["selected_model"], "grok_video_15_reference")
        self.assertEqual(data["selected_model_id"], "grok-imagine-video-1.5")
        self.assertIn(data["selected_base_url"], {"https://mikuapi.org", "https://mikuapi.org/v1"})
        self.assertEqual(data["selected_generation_path"], "/v1/videos/generations")
        default_route = data["models"]["grok_video_15_reference"]
        self.assertEqual(default_route["provider"], "mikuapi.org")
        self.assertEqual(default_route["model"], "grok-imagine-video-1.5")
        self.assertEqual(default_route["provider_contract_version"], "mikuapi-xai-reference-video-v1.5-2026-08-23.2")
        self.assertEqual(default_route["duration"], [1, 15])
        self.assertEqual(default_route["planning_max_duration_seconds"], 10)
        self.assertIn("about_10s", default_route["duration_reliability_status"])
        self.assertEqual(default_route["max_prompt_chars"], 4096)
        self.assertEqual(default_route["prompt_budget_chars"], 3000)
        self.assertIsNone(default_route["provider_documented_max_prompt_chars"])
        self.assertEqual(default_route["adapter_max_prompt_chars"], 4096)
        self.assertEqual(default_route["workflow_prompt_budget_chars"], 3000)
        self.assertIn("not_official_xai_limit", default_route["prompt_limit_source"])
        self.assertEqual(default_route["duration_field"], "duration")
        self.assertTrue(default_route["supports_multiple_references"])
        self.assertEqual(default_route["reference_field"], "reference_images")
        self.assertEqual(default_route["reference_index_base"], 0)
        self.assertIn("numbering_ambiguity", default_route["reference_index_contract_source"])
        self.assertFalse(default_route["supports_video_extension"])
        self.assertIn("not_verified", default_route["video_extension_status"])
        self.assertTrue(default_route["reference_mode_exclusive_with_source"])
        self.assertEqual(default_route["max_reference_images"], 7)
        self.assertEqual(default_route["reference_asset_policy"], "generated_reference_pack_only")
        self.assertTrue(default_route["require_generated_video_references"])
        self.assertTrue(default_route["require_generated_product_reference"])
        self.assertTrue(default_route["require_product_anchor_reference"])
        self.assertTrue(default_route["product_anchor_first"])
        self.assertFalse(default_route["allow_storyboard_reference_upload"])
        self.assertFalse(default_route["raw_product_assets_are_provider_inputs"])
        self.assertFalse(default_route["raw_non_product_assets_are_provider_inputs"])
        self.assertEqual(default_route["reference_audio_field"], "reference_audios")
        self.assertTrue(default_route["supports_preset_voice_references"])
        self.assertEqual(default_route["voices_path"], "/v1/tts/voices")
        self.assertEqual(default_route["voice_roster_policy"], "optional_diagnostic_only")
        self.assertEqual(default_route["default_voice_policy"], "prompt_native")
        self.assertIn("altair", default_route["approved_preset_voice_ids"])
        self.assertTrue(default_route["supports_native_speech_output"])
        self.assertTrue(default_route["supports_voice_conditioned_speech"])
        self.assertFalse(default_route["frame_exact_lip_sync_guaranteed"])
        self.assertTrue(default_route["supports_timecoded_story_beats"])
        official = data["models"]["grok_video_15_reference_xai"]
        self.assertEqual(official["provider"], "xai")
        self.assertEqual(official["provider_contract_version"], "xai-reference-video-v1.5-2026-07-31")
        self.assertTrue(official["supports_multiple_references"])
        self.assertEqual(official["max_reference_images"], 7)
        self.assertFalse(data["models"]["grok_video_15"]["supports_multiple_references"])
        self.assertEqual(data["models"]["grok_video_15"]["source_image_field"], "image")
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

    def test_miku_routes_never_fall_back_to_xai_api_key(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        default_names = config["models"]["grok_video_15_reference"].get("api_key_env_names") or []
        self.assertEqual(default_names, ["AI_COMMERCE_VIDEO_MIKUAPI_KEY"])
        official_names = config["models"]["grok_video_15_reference_xai"].get("api_key_env_names") or []
        self.assertEqual(official_names, ["XAI_API_KEY"])
        legacy_names = config["models"]["grok_image_video"].get("api_key_env_names") or []
        self.assertEqual(legacy_names, ["AI_COMMERCE_VIDEO_119337_KEY"])
        self.assertEqual(
            config["models"]["grok_image_video"].get("api_key_keychain_service"),
            "ai-commerce-video-119337-video",
        )

        result = run_cmd(
            ["python3", str(SCRIPTS / "validate_config.py"), "--config", str(CONFIG), "--model-key", "grok_video_15"],
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
                "AI_COMMERCE_VIDEO_MIKUAPI_KEY=test-env-file-key\n"
                "AI_COMMERCE_VIDEO_BASE_URL_GROK_VIDEO_15_REFERENCE=https://mikuapi.org\n"
                "AI_COMMERCE_VIDEO_MODEL_GROK_VIDEO_15_REFERENCE=grok-imagine-video-1.5\n",
                encoding="utf-8",
            )
            result = run_cmd(
                ["python3", str(SCRIPTS / "validate_config.py"), "--config", str(CONFIG), "--require-key"],
                env={
                    "AI_COMMERCE_VIDEO_ENV_FILE": str(env_file),
                    "AI_COMMERCE_VIDEO_MIKUAPI_KEY": "",
                    "YUNWU_API_KEY": "",
                    "XAI_API_KEY": "",
                },
            )
            data = json.loads(result.stdout)
            self.assertTrue(data["api_key_present"])
            self.assertIn(str(env_file.resolve()), data["loaded_env_files"])
            self.assertNotIn("api_key_preview", data)
            self.assertNotIn("test-env-file-key", result.stdout)

    def test_setup_private_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "ai-commerce-video.env"
            result = run_cmd([
                "python3", str(SCRIPTS / "setup_private_env.py"),
                "--env-file", str(env_file),
                "--key", "test-key",
                "--storage", "env-file",
                "--proxy-url", "http://127.0.0.1:7897",
            ])
            self.assertIn("Private video API env file written", result.stdout)
            text = env_file.read_text(encoding="utf-8")
            self.assertIn("AI_COMMERCE_VIDEO_MIKUAPI_KEY=test-key", text)
            self.assertIn("AI_COMMERCE_VIDEO_BASE_URL_GROK_VIDEO_15_REFERENCE=https://mikuapi.org", text)
            self.assertIn("AI_COMMERCE_VIDEO_MODEL_GROK_VIDEO_15_REFERENCE=grok-imagine-video-1.5", text)
            self.assertIn("AI_COMMERCE_VIDEO_PROXY_URL=http://127.0.0.1:7897", text)
            self.assertEqual(oct(env_file.stat().st_mode & 0o777), "0o600")

    def test_setup_private_env_keeps_official_xai_as_optional_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "ai-commerce-video-xai.env"
            run_cmd([
                "python3", str(SCRIPTS / "setup_private_env.py"),
                "--env-file", str(env_file),
                "--route", "xai-reference",
                "--key", "test-key",
                "--storage", "env-file",
            ])
            text = env_file.read_text(encoding="utf-8")
            self.assertIn("XAI_API_KEY=test-key", text)
            self.assertIn("AI_COMMERCE_VIDEO_BASE_URL_GROK_VIDEO_15_REFERENCE_XAI=https://api.x.ai", text)
            self.assertIn("AI_COMMERCE_VIDEO_MODEL_GROK_VIDEO_15_REFERENCE_XAI=grok-imagine-video-1.5", text)

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
            self.assertEqual(plan["model_capability_contract"]["source_image_field"], "image")
            prompt = plan["shots"][0]["prompt"]
            self.assertIn("ugc_review", prompt)
            self.assertIn("authentic use > proof > CTA", prompt)
            self.assertNotIn("Platform contract", prompt)
            self.assertNotIn("Safe zone profile: tiktok_in_feed", prompt)
            self.assertIn("Facts: use approved facts only", prompt)
            self.assertEqual(plan["platform_contract"]["safe_zone_profile"], "tiktok_in_feed")
            self.assertEqual(
                plan["shots"][0]["prompt_contract"]["omitted_planning_components"],
                ["platform", "scenario"],
            )

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
                "--model-key", "grok_video_15",
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
            self.assertLessEqual(len(prompt), 2400)
            self.assertEqual(shot["prompt_contract"]["char_count"], len(prompt))
            self.assertEqual(shot["prompt_contract"]["budget_chars"], 2400)
            self.assertEqual(shot["prompt_contract"]["max_chars"], 4096)
            self.assertEqual(shot["prompt_contract"]["compiler"], "director-commerce-v10")
            self.assertEqual(shot["prompt_contract"]["architecture"], "universal-product-director-v6")
            self.assertIn(spoken_script, prompt)
            self.assertEqual(prompt.count(spoken_script), 1)
            self.assertIn("Creative intent: premium_brand", prompt)
            self.assertIn("no newly generated written", prompt)
            self.assertIn("static and inanimate", prompt)
            self.assertNotIn("Platform contract", prompt)
            self.assertNotIn("Commerce scenario", prompt)
            self.assertNotIn("Evidence required for:", prompt)
            self.assertNotIn("Single-source rule:", prompt)
            self.assertNotIn("Clean full-screen commercial footage only:", prompt)
            self.assertNotIn("no, ,", prompt)
            self.assertTrue(plan["compliance_contract"]["evidence_required_for"])

    def test_prompt_compiler_removes_spoken_script_duplicates_from_visual_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            speech = "这款商品设计实用，日常使用方便，现在就去看看。"
            base_prompt = (
                "Use <SOURCE_IMAGE> as the exact approved first frame. An adult presenter demonstrates the approved product "
                "in a clean real-world setting and speaks naturally: " + speech + " " + speech
            )
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Generic Product",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--video-source-image", str(product),
                "--prompt", base_prompt,
                "--spoken-script", speech,
                "--duration", "15",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            prompt = plan["shots"][0]["prompt"]
            contract = plan["shots"][0]["prompt_contract"]
            self.assertEqual(prompt.count(speech), 1)
            self.assertEqual(contract["spoken_script_occurrences"], 1)
            self.assertGreaterEqual(contract["removed_spoken_script_duplicates"], 2)
            self.assertLessEqual(len(prompt), 1500)

    def test_product_categories_share_one_prompt_component_architecture(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            profiles = [
                ("home furniture", "static-inanimate", "Show the approved furniture in a bright home; preserve shape, color, texture and scale."),
                ("skincare", "static-inanimate", "Show the approved skincare package in a clean vanity scene with a natural hand demonstration."),
                ("packaged food", "liquid-food", "Show the approved food package, serving action and appetizing natural food motion."),
                ("kitchen appliance", "demonstrated-function", "Show the approved appliance performing one real function with a clear close-up proof shot."),
                ("software subscription", "software-screen", "Show the approved software interface and one clear user interaction in a realistic device view."),
            ]
            expected_components = [
                "director_action",
                "visual_direction",
                "creative_intent",
                "factual_guardrail",
                "reference_identity",
                "render_guardrails",
                "audio",
            ]
            for index, (category, motion, visual) in enumerate(profiles, start=1):
                speech = f"这是第{index}类商品的简洁带货口播。"
                result = run_cmd([
                    "python3", str(SCRIPTS / "prepare_project.py"),
                    "--name", f"Generic Category {index}",
                    "--project-root", str(tmp_path / "projects"),
                    "--product-image", str(product),
                    "--video-source-image", str(product),
                    "--duration", "15",
                    "--prompt", visual,
                    "--spoken-script", speech,
                    "--product-motion-policy", motion,
                    "--product-category", category,
                ])
                plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
                prompt = plan["shots"][0]["prompt"]
                contract = plan["shots"][0]["prompt_contract"]
                self.assertLessEqual(len(prompt), 1500)
                self.assertEqual(prompt.count(speech), 1)
                self.assertEqual(contract["compiler"], "director-commerce-v10")
                self.assertEqual(contract["architecture"], "universal-product-director-v6")
                self.assertEqual(contract["included_components"], expected_components)
                self.assertGreater(contract["available_visual_chars"], 0)
                self.assertEqual(contract["visual_direction_char_count"], len(visual))
                profile = plan["creative_contract"]["product_director_profile"]
                self.assertEqual(profile["architecture"], "evidence_driven_category_agnostic")
                self.assertFalse(profile["category_branching_allowed"])
                self.assertEqual(
                    set(profile),
                    {
                        "architecture",
                        "product_form",
                        "interaction_mode",
                        "proof_mode",
                        "talent_value",
                        "fact_scope",
                        "category_branching_allowed",
                    },
                )

    def test_prompt_compiler_reports_dynamic_visual_budget_without_semantic_guessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Generic Long Visual",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--prompt", "generic visual direction " * 80,
            ])
            self.assertIn("visual direction length", result.stdout)
            self.assertIn("available_visual_chars", result.stdout)

    def test_project_brief_template_fields_are_normalized_for_every_product(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            brief = tmp_path / "brief.json"
            script = "展示真实包装和使用方式，信息清楚，现在可以查看商品详情。"
            brief.write_text(json.dumps({
                "product": {
                    "name": "Generic Food",
                    "price": "verified price",
                    "category": "packaged food",
                    "selling_points": ["verified feature"],
                },
                "audience": "busy adults",
                "cta": "view product details",
                "visual_direction": "Show the approved food package and one natural serving action.",
                "presenter_script": script,
                "product_motion_policy": "liquid-food",
            }), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Brief Adapter",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--brief", str(brief),
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            self.assertEqual(plan["creative_contract"]["product_category"], "packaged food")
            self.assertEqual(plan["creative_contract"]["product_name"], "Generic Food")
            self.assertEqual(plan["creative_contract"]["product_price"], "verified price")
            self.assertEqual(plan["creative_contract"]["selling_points"], ["verified feature"])
            self.assertEqual(plan["creative_contract"]["audience"], "busy adults")
            self.assertEqual(plan["creative_contract"]["cta_text"], "view product details")
            self.assertEqual(plan["compliance_contract"]["claim_risk"], "medium")
            self.assertEqual(plan["spoken_script"], script)
            self.assertEqual(plan["shots"][0]["spoken_script"], script)
            self.assertTrue(plan["shots"][0]["prompt"].startswith("Cuts: Reveal the product immediately"))
            self.assertIn("Show the approved food package", plan["shots"][0]["prompt"])
            self.assertIn("Keep food or liquid motion natural", plan["shots"][0]["prompt"])

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
            self.assertIn("real experience", plan["creative_contract"]["creative_variant_rule"])
            self.assertIn("Creative intent: lifestyle_seed", plan["shots"][0]["prompt"])
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

    def test_dry_run_generation_payload_uses_explicit_single_image_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Default Duration",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
                "--model-key", "grok_video_15",
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            result = run_cmd(["python3", str(SCRIPTS / "generate_video.py"), "--plan", plan_path, "--dry-run"])
            data = json.loads(result.stdout)
            request_file = Path(data["results"][0]["request_file"])
            record = json.loads(request_file.read_text(encoding="utf-8"))
            self.assertEqual(record["payload"]["duration"], 15)
            self.assertEqual(record["payload"]["aspect_ratio"], "9:16")
            self.assertEqual(record["payload"]["model"], "grok-imagine-video-1.5")
            self.assertNotIn("input_reference", record["payload"])
            self.assertTrue(record["payload"]["image"]["url"].startswith("data:image/png;base64,"))
            self.assertEqual(record["request_evidence"]["source_images"][0]["field"], "image")

    def test_default_miku_reference_to_video_payload_uses_zero_based_ordered_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "raw-product-evidence.png"
            raw_detail = tmp_path / "raw-detail-evidence.png"
            product_master = tmp_path / "generated-product-master.png"
            presenter = tmp_path / "generated-presenter.png"
            scene = tmp_path / "generated-scene.png"
            storyboard = tmp_path / "storyboard-review.png"
            for index, path in enumerate((product, raw_detail, product_master, presenter, scene, storyboard), start=1):
                path.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([index]))
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "visual_design": {
                    "creative_thesis": "Professional product-first commuter story",
                    "reference_plan": [
                        {"role": "product", "source": "generate_after_stage_1", "upload_to_video_model": True, "generation_input_asset_ids": ["input_evidence_product", "ref_01"], "multimodal_qc_result": {"status": "pass", "reviewer": "test", "checked_against_asset_ids": ["input_evidence_product", "ref_01"]}, "image_prompt": "Regenerate a faithful high-resolution professional product master from all supplied product evidence."},
                        {"role": "presenter", "source": "generate_after_stage_1", "upload_to_video_model": True, "generation_input_asset_ids": ["input_evidence_product", "ref_01"], "multimodal_qc_result": {"status": "pass", "reviewer": "test", "checked_against_asset_ids": ["input_evidence_product", "ref_01"]}, "image_prompt": "Generate a clear synthetic presenter identity plate for the approved campaign."},
                        {"role": "scene", "source": "generate_after_stage_1", "upload_to_video_model": True, "multimodal_qc_result": {"status": "pass", "reviewer": "test"}, "image_prompt": "Generate the approved coherent urban set and lighting control."},
                    ],
                    "storyboard_preview": {"usage": "review_only", "image_prompt": "Generate a four-panel review storyboard."},
                }
            }), encoding="utf-8")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Official Reference Video",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--model-key", "grok_video_15_reference",
                "--reference-image", f"product_detail={raw_detail}",
                "--generated-reference", f"product={product_master}",
                "--generated-reference", f"presenter={presenter}",
                "--generated-reference", f"scene={scene}",
                "--storyboard-preview-image", str(storyboard),
                "--brief", str(brief),
                "--prompt", "0-2s macro product hook, motivated hand-pass cut into proof, then a clean hero ending.",
            ])
            plan_path = Path(json.loads(prep.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["model_key"], "grok_video_15_reference")
            self.assertEqual([shot["duration_seconds"] for shot in plan["shots"]], [10, 5])
            self.assertEqual(plan["production_contract"]["approved_paid_cap"], 2)
            self.assertEqual(plan["creative_contract"]["reference_strategy"], "multi_reference_commercial")
            self.assertEqual(
                [item["token"] for item in plan["asset_contract"]["reference_prompt_map"]],
                ["<IMAGE_0>", "<IMAGE_1>", "<IMAGE_2>"],
            )
            self.assertEqual(plan["visual_design_contract"]["schema_version"], "professional-director-visual-v6")
            self.assertEqual(plan["quality_contract"]["delivery_review_policy"], "technical_ready")
            self.assertTrue(plan["quality_contract"]["stage_2_actual_images_are_primary_visual_approval"])
            self.assertFalse(plan["visual_design_contract"]["product_master_qc"]["required"])
            self.assertFalse(plan["visual_design_contract"]["product_master_qc"]["raw_fallback_allowed"])
            self.assertEqual(
                plan["visual_design_contract"]["product_master_qc"]["failure_action"],
                "regenerate_only_when_stage_2_user_rejects_the_image",
            )
            self.assertFalse(plan["asset_contract"]["raw_inputs_provider_upload_allowed"])
            self.assertFalse(plan["asset_contract"]["raw_product_inputs_provider_upload_allowed"])
            self.assertFalse(plan["asset_contract"]["raw_non_product_inputs_provider_upload_allowed"])
            self.assertEqual(len(plan["asset_contract"]["input_evidence_assets"]), 2)
            self.assertEqual([item["role"] for item in plan["references"]], ["product", "presenter", "scene"])
            self.assertEqual(plan["approval_preview_assets"][0]["role"], "storyboard_preview")
            validation = run_cmd([
                "python3", str(SCRIPTS / "validate_platform_plan.py"),
                "--plan", str(plan_path),
            ])
            validation_data = json.loads(validation.stdout)
            self.assertTrue(validation_data["ok"])
            self.assertTrue(any(
                check["text"] == "All Provider references are generated and the product master is first" and check["passed"]
                for check in validation_data["checks"]
            ))
            dry_run = run_cmd([
                "python3", str(SCRIPTS / "generate_video.py"),
                "--plan", str(plan_path), "--dry-run",
            ])
            request_file = Path(json.loads(dry_run.stdout)["results"][0]["request_file"])
            record = json.loads(request_file.read_text(encoding="utf-8"))
            payload = record["payload"]
            self.assertEqual(record["provider"], "mikuapi.org")
            self.assertEqual(record["submit_url"], "https://mikuapi.org/v1/videos/generations")
            self.assertEqual(payload["model"], "grok-imagine-video-1.5")
            self.assertEqual(payload["duration"], 10)
            self.assertEqual(len(payload["reference_images"]), 3)
            self.assertNotIn("image", payload)
            self.assertNotIn("reference_image_urls", payload)
            self.assertTrue(all(item["url"].startswith("data:image/png;base64,") for item in payload["reference_images"]))
            self.assertFalse(record["asset_trace"]["source_image_included_in_payload"])
            self.assertTrue(record["asset_trace"]["reference_mode_exclusive_with_source"])
            self.assertEqual(record["asset_trace"]["reference_asset_policy"], "generated_reference_pack_only")
            self.assertFalse(record["asset_trace"]["raw_input_assets_uploaded"])
            self.assertFalse(record["asset_trace"]["raw_non_product_assets_uploaded"])

    def test_multiple_product_images_form_one_ordered_identity_evidence_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product_front = tmp_path / "product-front.png"
            product_side = tmp_path / "product-side.png"
            product_back = tmp_path / "product-back.png"
            product_master = tmp_path / "generated-product-master.png"
            for index, path in enumerate(
                (product_front, product_side, product_back, product_master),
                start=1,
            ):
                path.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([index]))

            expected_ids = [
                "input_evidence_product",
                "input_evidence_product_02",
                "input_evidence_product_03",
            ]
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "visual_design": {
                    "reference_plan": [{
                        "role": "product",
                        "source": "generate_after_stage_1",
                        "image_prompt": "Generate one faithful product master using all three ordered same-SKU views.",
                        "generation_input_asset_ids": expected_ids,
                        "multimodal_qc_result": {
                            "status": "pass",
                            "reviewer": "codex_multimodal",
                            "checked_against_asset_ids": expected_ids,
                        },
                    }],
                },
            }), encoding="utf-8")

            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Three Product Views",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product_front),
                "--product-image", str(product_side),
                "--product-image", str(product_back),
                "--generated-reference", f"product={product_master}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference",
            ])
            plan_path = Path(json.loads(prepared.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))

            evidence = plan["asset_contract"]["product_identity_evidence"]
            self.assertEqual([item["id"] for item in evidence], expected_ids)
            self.assertEqual(len(plan["asset_contract"]["input_evidence_assets"]), 3)
            reference = plan["generated_reference_assets"][0]
            self.assertEqual(reference["generation_input_asset_ids"], expected_ids)
            self.assertEqual(len(reference["generation_input_paths"]), 3)
            self.assertEqual(len(reference["generation_input_sha256"]), 3)
            self.assertTrue(all(reference["generation_input_sha256"]))
            self.assertEqual(
                reference["generation_input_policy"],
                "all_relevant_product_identity_evidence",
            )

            validation = run_cmd([
                "python3", str(SCRIPTS / "validate_platform_plan.py"),
                "--plan", str(plan_path),
            ])
            checks = json.loads(validation.stdout)["checks"]
            self.assertTrue(any(
                check["text"] == "Product-dependent generated references used the complete product identity evidence set"
                and check["passed"]
                for check in checks
            ))

    def test_missing_imagegen_input_record_is_advisory_not_a_paid_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            master = tmp_path / "master.png"
            product.write_bytes(b"raw-product")
            master.write_bytes(b"generated-master")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "visual_design": {
                    "reference_plan": [{
                        "role": "product",
                        "source": "generate_after_stage_1",
                        "image_prompt": "Generate a faithful professional product master.",
                        "multimodal_qc_result": {"status": "pass", "reviewer": "test"},
                    }],
                },
            }), encoding="utf-8")
            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Missing Actual Imagegen Record",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--generated-reference", f"product={master}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference",
            ])
            plan_path = Path(json.loads(prepared.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            reference = plan["generated_reference_assets"][0]
            self.assertEqual(reference["generation_input_asset_ids"], [])
            self.assertEqual(reference["generation_input_record_status"], "no_reference_input_recorded")
            self.assertNotIn("checked_against_asset_ids", reference["multimodal_qc_result"])
            preflight = run_cmd([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(plan_path),
            ])
            report = json.loads(preflight.stdout)
            self.assertTrue(report["paid_generation_allowed"])
            self.assertTrue(any("complete product identity evidence set" in item for item in report["warnings"]))

    def test_dual_role_worn_product_evidence_is_included_but_scene_evidence_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            worn = tmp_path / "worn-product.png"
            scene = tmp_path / "scene.png"
            master = tmp_path / "master.png"
            presenter = tmp_path / "presenter.png"
            for index, path in enumerate((product, worn, scene, master, presenter), start=1):
                path.write_bytes(b"asset-" + bytes([index]))

            identity_ids = ["input_evidence_product", "ref_01"]
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "visual_design": {
                    "talent_presence": "presenter",
                    "product_identity_evidence_asset_ids": identity_ids,
                    "reference_plan": [
                        {
                            "role": "product",
                            "source": "generate_after_stage_1",
                            "image_prompt": "Generate the faithful product master from the front and worn views.",
                            "generation_input_asset_ids": identity_ids,
                            "multimodal_qc_result": {"status": "pass"},
                        },
                        {
                            "role": "presenter",
                            "source": "generate_after_stage_1",
                            "image_prompt": "Generate the presenter wearing the exact approved product.",
                            "generation_input_asset_ids": identity_ids,
                            "multimodal_qc_result": {"status": "pass"},
                        },
                    ],
                },
            }), encoding="utf-8")

            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Dual Role Worn Evidence",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--reference-image", f"model={worn}",
                "--reference-image", f"scene={scene}",
                "--generated-reference", f"product={master}",
                "--generated-reference", f"presenter={presenter}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference",
            ])
            plan = json.loads(
                Path(json.loads(prepared.stdout)["plan"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                plan["asset_contract"]["product_identity_evidence_asset_ids"],
                identity_ids,
            )
            self.assertNotIn("ref_02", identity_ids)
            for reference in plan["generated_reference_assets"]:
                self.assertEqual(reference["generation_input_asset_ids"], identity_ids)

    def test_preflight_warns_when_product_reference_omits_one_product_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product_front = tmp_path / "front.png"
            product_back = tmp_path / "back.png"
            master = tmp_path / "master.png"
            product_front.write_bytes(b"front")
            product_back.write_bytes(b"back")
            master.write_bytes(b"master")
            identity_ids = ["input_evidence_product", "input_evidence_product_02"]
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "visual_design": {
                    "product_identity_evidence_asset_ids": identity_ids,
                    "reference_plan": [{
                        "role": "product",
                        "source": "generate_after_stage_1",
                        "image_prompt": "Generate the product master.",
                        "generation_input_asset_ids": ["input_evidence_product"],
                        "multimodal_qc_result": {
                            "status": "pass",
                            "checked_against_asset_ids": identity_ids,
                        },
                    }],
                },
            }), encoding="utf-8")
            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Missing Product View",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product_front),
                "--product-image", str(product_back),
                "--generated-reference", f"product={master}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference",
            ])
            plan_path = Path(json.loads(prepared.stdout)["plan"])
            preflight = run_cmd([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(plan_path),
            ])
            report = json.loads(preflight.stdout)
            self.assertTrue(report["paid_generation_allowed"])
            self.assertTrue(any("complete product identity evidence set" in item for item in report["warnings"]))

    def test_default_xai_reference_route_rejects_raw_evidence_as_provider_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "raw-product.png"
            product.write_bytes(b"raw-product-evidence")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Reject Raw Evidence",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--model-key", "grok_video_15_reference",
            ])
            self.assertIn("requires a complete generated Reference Pack", result.stdout)

    def test_default_xai_route_rejects_raw_copy_storyboard_upload_and_manual_token_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_product = tmp_path / "raw-product.png"
            copied_product = tmp_path / "copied-product.png"
            product_master = tmp_path / "generated-product-master.png"
            storyboard = tmp_path / "storyboard.png"
            raw_product.write_bytes(b"same-product-bytes")
            copied_product.write_bytes(b"same-product-bytes")
            product_master.write_bytes(b"new-generated-product-master")
            storyboard.write_bytes(b"storyboard-bytes")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "visual_design": {
                    "reference_plan": [
                        {"role": "product", "source": "generate_after_stage_1", "upload_to_video_model": True, "image_prompt": "Regenerate a faithful professional product master."},
                        {"role": "scene", "source": "generate_after_stage_1", "upload_to_video_model": True, "image_prompt": "Generate clean scene control."},
                        {"role": "storyboard", "source": "generate_after_stage_1", "upload_to_video_model": True, "image_prompt": "Generate storyboard."},
                    ]
                }
            }), encoding="utf-8")
            copied = run_cmd_fail([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Reject Copied Raw",
                "--project-root", str(tmp_path / "projects-a"),
                "--product-image", str(raw_product),
                "--model-key", "grok_video_15_reference",
                "--generated-reference", f"product={copied_product}",
                "--brief", str(brief),
            ])
            self.assertIn("byte-identical to user-supplied evidence", copied.stdout)

            crop_brief = tmp_path / "crop-brief.json"
            crop_brief.write_text(json.dumps({
                "visual_design": {
                    "reference_plan": [
                        {
                            "role": "product",
                            "source": "generate_after_stage_1",
                            "generation_mode": "non_generative_crop",
                            "upload_to_video_model": True,
                            "image_prompt": "Crop the uploaded product image without regeneration.",
                        }
                    ]
                }
            }), encoding="utf-8")
            cropped = run_cmd_fail([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Reject Non Generative Crop",
                "--project-root", str(tmp_path / "projects-crop"),
                "--product-image", str(raw_product),
                "--model-key", "grok_video_15_reference",
                "--generated-reference", f"product={product_master}",
                "--brief", str(crop_brief),
            ])
            self.assertIn("must use a generative product-master mode", cropped.stdout)

            storyboard_upload = run_cmd_fail([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Reject Storyboard Upload",
                "--project-root", str(tmp_path / "projects-b"),
                "--product-image", str(raw_product),
                "--model-key", "grok_video_15_reference",
                "--generated-reference", f"product={product_master}",
                "--generated-reference", f"scene={storyboard}",
                "--generated-reference", f"storyboard={storyboard}",
                "--brief", str(brief),
            ])
            self.assertIn("storyboard/contact sheets as review-only planning assets", storyboard_upload.stdout)

            generated_scene = tmp_path / "generated-scene.png"
            generated_scene.write_bytes(b"new-generated-scene")
            manual_token = run_cmd_fail([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Reject Manual Token",
                "--project-root", str(tmp_path / "projects-c"),
                "--product-image", str(raw_product),
                "--model-key", "grok_video_15_reference",
                "--generated-reference", f"product={product_master}",
                "--generated-reference", f"scene={generated_scene}",
                "--brief", str(brief),
                "--prompt", "Use <IMAGE_0> as a manually assigned scene.",
            ])
            self.assertIn("manual reference tokens", manual_token.stdout)

    def test_provider_image_count_rejection_is_recorded_as_contract_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            server = HTTPServer(("127.0.0.1", 0), MockImageContractRejectHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                prep = run_cmd([
                    "python3", str(SCRIPTS / "prepare_project.py"),
                    "--name", "Provider Contract Mismatch",
                    "--project-root", str(tmp_path / "projects"),
                    "--product-image", str(image),
                    "--model-key", "grok_video_15",
                ])
                plan_path = Path(json.loads(prep.stdout)["plan"])
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                result = self.guarded_submit(plan_path, expect_ok=False, env={
                    "AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key",
                    "AI_COMMERCE_VIDEO_BASE_URL_GROK_VIDEO_15": f"http://127.0.0.1:{server.server_port}/v1",
                })
                self.assertIn("exactly one reference image", result.stdout)
                request_file = Path(plan["shots"][0]["request_file"])
                record = json.loads(request_file.read_text(encoding="utf-8"))
                diagnostic = record["provider_contract_diagnostic"]
                self.assertEqual(diagnostic["code"], "provider_image_contract_mismatch")
                self.assertEqual(diagnostic["provider_contract_version"], "mikuapi-xai-image-video-v1")
                self.assertEqual(diagnostic["local_image_count"], 1)
                self.assertEqual(diagnostic["configured_field"], "image")
                self.assertFalse(diagnostic["automatic_retry_allowed"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

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
            ], env={"AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key"})
            self.assertIn("guarded paid workflow", result.stdout)

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
            ], env={"AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key"})
            self.assertIn("guarded paid workflow", result.stdout)

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
                    "--model-key", "grok_video_15",
                ])
                plan_path = json.loads(prep.stdout)["plan"]
                env = {
                    "AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key",
                    "AI_COMMERCE_VIDEO_BASE_URL_GROK_VIDEO_15": f"http://127.0.0.1:{server.server_port}/v1",
                }
                submitted = self.guarded_submit(plan_path, env=env)
                request_file = Path(json.loads(submitted.stdout)["results"][0]["request_file"])
                record = json.loads(request_file.read_text(encoding="utf-8"))
                self.assertEqual(record["confirmation"]["source"], "confirmation_file")
                self.assertTrue(record["confirmation"]["image_assets_confirmed"])
                self.assertTrue(record["confirmation"]["video_generation_confirmed"])
                self.assertEqual(record["confirmation"]["approved_by"], "offline-test")
                self.assertEqual(server.last_payload["duration"], 15)
                self.assertTrue(server.last_payload["image"]["url"].startswith("data:image/png;base64,"))
                self.assertNotIn("input_reference", server.last_payload)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_mikuapi_base_url_override_avoids_duplicate_v1(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "product.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "URL Normalize",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(image),
                "--model-key", "grok_video_15",
            ])
            plan_path = json.loads(prep.stdout)["plan"]
            result = run_cmd([
                "python3", str(SCRIPTS / "generate_video.py"),
                "--plan", plan_path,
                "--dry-run",
            ], env={"AI_COMMERCE_VIDEO_BASE_URL_GROK_VIDEO_15": "https://mikuapi.org/v1"})
            request_file = Path(json.loads(result.stdout)["results"][0]["request_file"])
            record = json.loads(request_file.read_text(encoding="utf-8"))
            self.assertEqual(record["submit_url"], "https://mikuapi.org/v1/videos/generations")

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
            self.assertIn("<IMAGE_1>=product identity", plan["shots"][0]["prompt"])
            self.assertIn("<IMAGE_2>=presenter identity", plan["shots"][0]["prompt"])

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
            self.assertEqual(summary["prompt_budget_chars"], 2400)
            self.assertEqual(summary["max_prompt_chars"], 4096)
            self.assertTrue(summary["within_budget"])
            self.assertTrue(summary["within_max"])
            self.assertEqual(summary["compiler"], "director-commerce-v10")

    def test_preflight_blocks_duplicate_spoken_script_even_if_length_contract_is_forged(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            speech = "确认口播只允许出现一次。"
            prep = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Duplicate Speech Gate",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--spoken-script", speech,
            ])
            plan_path = Path(json.loads(prep.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            shot = plan["shots"][0]
            shot["prompt"] += " " + speech
            shot["prompt_contract"]["char_count"] = len(shot["prompt"])
            shot["prompt_contract"]["spoken_script_occurrences"] = 2
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "preflight_project.py"), "--plan", str(plan_path),
            ])
            self.assertIn("spoken script must appear exactly once", result.stdout)

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
            self.assertIn("<IMAGE_1>=product identity", plan["shots"][0]["prompt"])
            self.assertIn("<IMAGE_2>=presenter identity", plan["shots"][0]["prompt"])
            self.assertIn("<IMAGE_3>=storyboard", plan["shots"][0]["prompt"])

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
                "--model-key", "grok_video_15",
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
            self.assertEqual(first_record["payload"]["duration"], 15)
            self.assertTrue(first_record["payload"]["image"]["url"].startswith("data:image/png;base64,"))
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
                "--model-key", "grok_video_15",
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
            self.assertIn("@Image1=product identity", prompt)
            self.assertIn("@Image2=presenter identity", prompt)

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
            self.assertIn("@Image3=storyboard", prompt)
            self.assertIn("use each image only for its named role", prompt)
            self.assertIn("render full-screen rather than a grid", prompt)

    def test_seedance_fal_queue_submit_poll_and_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mock_video = tmp_path / "fal-video.mp4"
            make_test_video(mock_video, duration=4.0, audio=True)
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
                    "--duration", "4",
                ])
                plan_path = json.loads(prep.stdout)["plan"]
                env = {"FAL_KEY": "test-fal-key"}
                submitted = self.guarded_submit(plan_path, config=config, env=env)
                request_file = Path(json.loads(submitted.stdout)["results"][0]["request_file"])
                record = json.loads(request_file.read_text(encoding="utf-8"))
                self.assertEqual(record["model_key"], "seedance2")
                self.assertEqual(record["provider"], "fal_queue")
                self.assertEqual(record["response"]["request_id"], "fal-request-1")
                self.assertIn("status_url", record["response"])
                self.assertIn("response_url", record["response"])
                self.assertNotIn("model", server.last_payload)
                self.assertEqual(server.last_payload["duration"], 4)
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
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            prompt = (
                "Create a product ad. Chinese voiceover and captions: 这款商品适合日常使用。 "
                "Show subtle product motion and a clean hero shot."
            )
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Generic Static Product",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--prompt", prompt,
                "--spoken-script", "这款商品适合日常使用。",
                "--commerce-platform", "amazon-cross-border",
                "--product-category", "general merchandise",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            contract = plan["creative_contract"]
            shot_prompt = plan["shots"][0]["prompt"]
            self.assertEqual(contract["speaker_mode"], "voiceover")
            self.assertEqual(contract["product_motion_policy"], "static-inanimate")
            self.assertEqual(contract["commerce_platform"], "amazon-cross-border")
            self.assertIn("off-screen voiceover", shot_prompt)
            self.assertNotIn("presenter speech and captions", shot_prompt)
            self.assertIn("no newly generated written or typographic elements", shot_prompt)
            self.assertNotIn("Chinese voiceover and captions", shot_prompt)
            self.assertNotIn("visible people demonstrate silently", shot_prompt)
            self.assertIn("No person, face, body, hand, or human silhouette appears", shot_prompt)
            self.assertEqual(contract["talent_contract"]["presence"], "none")
            self.assertIn("never acts alive", shot_prompt)
            self.assertIn("camera movement around the product", shot_prompt)
            self.assertNotIn("subtle product motion", shot_prompt)

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
            self.assertEqual(plan["creative_contract"]["speaker_mode"], "no-speech")
            self.assertIn("conversion-focused product ad", plan["creative_contract"]["creative_variant_rule"])
            self.assertIn("Creative intent: commerce_direct", plan["shots"][0]["prompt"])
            self.assertIn("Speech=none", plan["shots"][0]["prompt"])
            self.assertIn("Voice=none", plan["shots"][0]["prompt"])
            self.assertNotIn("speaks to camera", plan["shots"][0]["prompt"])

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
            self.assertIn("Creative intent: story_reversal", prompt)
            self.assertIn("hook > conflict > reversal > product solution > CTA", prompt)

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
            self.assertIn("Creative intent: hybrid", prompt)
            self.assertIn("story hook > product proof > CTA", prompt)

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
                planning_rule = plan["creative_contract"]["creative_variant_rule"]
                self.assertEqual(plan["creative_contract"]["creative_variant"], variant)
                self.assertIn(f"Creative intent: {variant}", prompt)
                for term in terms:
                    self.assertIn(term, planning_rule)

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
                "--spoken-script", "这是一段画外功能讲解。",
                "--product-motion-policy", "demonstrated-function",
                "--prompt", "Use voiceover and captions for a functional product demo.",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            shot_prompt = plan["shots"][0]["prompt"]
            self.assertEqual(plan["creative_contract"]["speaker_mode"], "voiceover")
            self.assertEqual(plan["creative_contract"]["product_motion_policy"], "demonstrated-function")
            self.assertIn("Use off-screen voiceover", shot_prompt)
            self.assertIn("real product function or mechanism", shot_prompt)

    def test_stage_1_voiceover_with_visible_presenter_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "speaker_mode": "voiceover",
                "spoken_script": "坐下来轻轻一摇，让家的松弛感回来。",
                "seller_persona": "approved adult female presenter who demonstrates silently",
                "visual_design": {
                    "talent_presence": "presenter",
                    "talent_gender": "female",
                    "talent_description": "Approved adult East Asian female presenter",
                },
            }, ensure_ascii=False), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Visible Presenter Speech",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--brief", str(brief),
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            prompt = plan["shots"][0]["prompt"]
            self.assertEqual(plan["creative_contract"]["speaker_mode"], "voiceover")
            self.assertEqual(
                plan["creative_contract"]["speaker_mode_decision_source"],
                "stage_1_visual_plan",
            )
            self.assertEqual(plan["audio_contract"]["speech_presentation"], "off_screen_voiceover")
            self.assertIn("VO=“坐下来轻轻一摇，让家的松弛感回来。”", prompt)
            self.assertIn("off-screen voiceover", prompt)
            self.assertIn("demonstrates silently", prompt)
            self.assertNotIn("Dialogue=“", prompt)

    def test_stage_1_on_camera_presenter_speech_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "speaker_mode": "digital-human-spoken",
                "speech_presentation": "on_camera_presenter",
                "spoken_script": "坐下来轻轻一摇，让家的松弛感回来。",
                "visual_design": {
                    "talent_presence": "presenter",
                    "talent_gender": "female",
                },
            }, ensure_ascii=False), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Approved On Camera Speech",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--brief", str(brief),
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            prompt = plan["shots"][0]["prompt"]
            self.assertEqual(plan["creative_contract"]["speaker_mode"], "digital-human-spoken")
            self.assertEqual(plan["audio_contract"]["speech_presentation"], "on_camera_presenter")
            self.assertIn("Dialogue=“坐下来轻轻一摇，让家的松弛感回来。”", prompt)
            self.assertIn("visibly speaks", prompt)
            self.assertIn("natural mouth movement", prompt)
            self.assertNotIn("VO=“", prompt)

    def test_stage_1_no_speech_presenter_keeps_environment_and_music_without_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "speaker_mode": "no-speech",
                "speech_presentation": "none",
                "visual_design": {
                    "talent_presence": "presenter",
                    "talent_gender": "female",
                    "sound_design": {"mode": "layered_native"},
                },
            }, ensure_ascii=False), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Silent Presenter With Sound Design",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--brief", str(brief),
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            prompt = plan["shots"][0]["prompt"]
            self.assertEqual(plan["creative_contract"]["speaker_mode"], "no-speech")
            self.assertEqual(plan["audio_contract"]["speech_presentation"], "none")
            self.assertFalse(plan["audio_contract"]["speech_required"])
            self.assertTrue(plan["audio_contract"]["human_voice_forbidden"])
            self.assertTrue(plan["sound_design_contract"]["non_speech_required"])
            self.assertIn("Speech=none", prompt)
            self.assertIn("Voice=none", prompt)
            self.assertIn("Ambience=", prompt)
            self.assertIn("Music=", prompt)
            self.assertNotIn("Dialogue=“", prompt)
            self.assertNotIn("VO=“", prompt)

    def test_stage_1_speaker_mode_conflicts_are_blocked_instead_of_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "speaker_mode": "voiceover",
                "speech_presentation": "off_screen_voiceover",
                "spoken_script": "保持这段画外旁白。",
            }, ensure_ascii=False), encoding="utf-8")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Voice Contract Drift",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--brief", str(brief),
                "--speaker-mode", "digital-human-spoken",
            ])
            self.assertIn("differs from the approved Stage 1 visual plan", result.stdout)

    def test_stage_1_mode_and_speech_presentation_conflict_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "speaker_mode": "voiceover",
                "speech_presentation": "on_camera_presenter",
                "spoken_script": "冲突的声音方案。",
            }, ensure_ascii=False), encoding="utf-8")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Conflicting Voice Contract",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--brief", str(brief),
            ])
            self.assertIn("Stage 1 voice contract conflicts", result.stdout)

    def test_ambiguous_presenter_and_spoken_copy_requires_stage_1_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "spoken_script": "这句到底由谁说还没有决定。",
                "visual_design": {"talent_presence": "presenter", "talent_gender": "female"},
            }, ensure_ascii=False), encoding="utf-8")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Ambiguous Speaker",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--brief", str(brief),
            ])
            self.assertIn("does not say who speaks", result.stdout)

    def test_brief_can_preserve_user_explicit_off_screen_voiceover(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "speaker_mode": "voiceover",
                "speaker_mode_source": "user_explicit",
                "spoken_script": "这是一段用户明确选择的画外旁白。",
                "visual_design": {"talent_presence": "presenter", "talent_gender": "female"},
            }, ensure_ascii=False), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Explicit Off Screen Voiceover",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--brief", str(brief),
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            prompt = plan["shots"][0]["prompt"]
            self.assertEqual(plan["creative_contract"]["speaker_mode"], "voiceover")
            self.assertEqual(plan["audio_contract"]["speech_presentation"], "off_screen_voiceover")
            self.assertIn("Use off-screen voiceover", prompt)
            self.assertIn("VO=“这是一段用户明确选择的画外旁白。”", prompt)

    def test_preflight_rejects_on_camera_speech_prompt_with_silent_contradiction(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Contradictory Speech Prompt",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--speaker-mode", "digital-human-spoken",
                "--spoken-script", "这句口播必须由画面人物说出来。",
            ])
            plan_path = Path(json.loads(prepared.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["shots"][0]["prompt"] = plan["shots"][0]["prompt"].replace(
                "visibly speaks",
                "demonstrates silently",
            )
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(plan_path),
                "--config", str(CONFIG),
            ])
            self.assertIn("on-camera speech prompt", result.stdout)

    def test_preflight_rejects_no_speech_prompt_with_injected_voiceover(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"\x89PNG\r\n\x1a\n")
            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "No Speech Contract Drift",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--speaker-mode", "no-speech",
            ])
            plan_path = Path(json.loads(prepared.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["shots"][0]["prompt"] = plan["shots"][0]["prompt"].replace(
                "Speech=none",
                "VO=“这段旁白不在批准方案里”",
            )
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(plan_path),
                "--config", str(CONFIG),
            ])
            self.assertIn("no-speech prompt", result.stdout)

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
                    "--model-key", "grok_video_15",
                    "--duration", "1",
                ])
                plan_path = json.loads(prep.stdout)["plan"]
                env = {
                    "AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key",
                    "AI_COMMERCE_VIDEO_BASE_URL_GROK_VIDEO_15": f"http://127.0.0.1:{server.server_port}/v1",
                }
                submitted = self.guarded_submit(plan_path, env=env)
                request_file = Path(json.loads(submitted.stdout)["results"][0]["request_file"])
                request_record = json.loads(request_file.read_text(encoding="utf-8"))
                evidence = request_record["request_evidence"]
                self.assertEqual(evidence["prompt_char_count"], len(server.last_payload["prompt"]))
                self.assertEqual(len(evidence["prompt_sha256"]), 64)
                self.assertEqual(len(evidence["payload_sha256"]), 64)
                self.assertEqual(evidence["source_images"][0]["transport"], "data_uri")
                self.assertEqual(len(evidence["source_images"][0]["sha256"]), 64)
                polled = run_cmd(["python3", str(SCRIPTS / "poll_video.py"), "--request-file", str(request_file)], env=env)
                output = Path(json.loads(polled.stdout)["output"])
                self.assertTrue(output.exists())
                self.assertGreater(output.stat().st_size, 1000)
                self.assertTrue(json.loads(polled.stdout)["media"]["has_video"])
                self.assertEqual(server.last_payload["duration"], 1)
                self.assertEqual(server.last_payload["model"], "grok-imagine-video-1.5")
                self.assertTrue(server.last_payload["image"]["url"].startswith("data:image/png;base64,"))
                self.assertNotIn("input_reference", server.last_payload)
                self.assertEqual(server.last_post_user_agent, "ai-commerce-video-skill/1.0")
                self.assertEqual(server.last_get_user_agent, "ai-commerce-video-skill/1.0")
                poll_record = json.loads(request_file.with_name("shot_01_poll.json").read_text(encoding="utf-8"))
                trace = poll_record["provider_trace"]
                self.assertEqual(trace["gateway_task_id"], "mock-request-1")
                self.assertEqual(trace["upstream_task_id"], "upstream-mock-1")
                self.assertEqual(trace["channel_id"], 11)
                self.assertTrue(trace["returned_prompt_matches_request"])
                self.assertEqual(trace["provider_input_receipt_status"], "unverified_provider_input")
                self.assertEqual(len(trace["downloaded_video_sha256"]), 64)
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

    def test_poll_blocks_provider_prompt_mismatch_before_video_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mock_video = tmp_path / "mock-video.mp4"
            make_test_video(mock_video, audio=True)
            server = HTTPServer(("127.0.0.1", 0), MockVideoHandler)
            server.video_bytes = mock_video.read_bytes()
            server.returned_prompt = "unrelated market and vegetables"
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                image = tmp_path / "product.png"
                image.write_bytes(b"\x89PNG\r\n\x1a\n")
                prep = run_cmd([
                    "python3", str(SCRIPTS / "prepare_project.py"),
                    "--name", "Provider Prompt Mismatch",
                    "--project-root", str(tmp_path / "projects"),
                    "--product-image", str(image),
                    "--model-key", "grok_video_15",
                ])
                plan_path = json.loads(prep.stdout)["plan"]
                env = {
                    "AI_COMMERCE_VIDEO_MIKUAPI_KEY": "test-key",
                    "AI_COMMERCE_VIDEO_BASE_URL_GROK_VIDEO_15": f"http://127.0.0.1:{server.server_port}/v1",
                }
                submitted = self.guarded_submit(plan_path, env=env)
                request_file = Path(json.loads(submitted.stdout)["results"][0]["request_file"])
                polled = run_cmd_fail([
                    "python3", str(SCRIPTS / "poll_video.py"), "--request-file", str(request_file),
                ], env=env)
                self.assertIn("does not match", polled.stdout)
                poll_record = json.loads(request_file.with_name("shot_01_poll.json").read_text(encoding="utf-8"))
                self.assertEqual(poll_record["status"], "blocked")
                self.assertFalse(poll_record["provider_trace"]["returned_prompt_matches_request"])
                self.assertFalse((request_file.parents[1] / "clips" / "shot_01.mp4").exists())
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

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

    def test_explicit_preset_reference_plan_uses_one_15s_request_with_timecoded_beats(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product_master = tmp_path / "product-master.png"
            scene = tmp_path / "scene.png"
            proof_keyframe = tmp_path / "proof-keyframe.png"
            product.write_bytes(b"raw-product")
            product_master.write_bytes(b"generated-product-master")
            scene.write_bytes(b"generated-scene")
            proof_keyframe.write_bytes(b"generated-proof-keyframe")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "speaker_mode": "voiceover",
                "speech_presentation": "off_screen_voiceover",
                "spoken_script": "看见真实细节。",
                "visual_design": {
                    "style_type": "cinematic_product_hero",
                    "reference_plan": [
                        {"role": "product", "source": "generate_after_stage_1", "image_prompt": "Regenerate a faithful high-resolution professional product master."},
                        {"role": "scene", "source": "generate_after_stage_1", "image_prompt": "Generate one clean empty scene."},
                        {"role": "beat_keyframe_proof", "source": "generate_after_stage_1", "image_prompt": "Generate one clean full-frame proof composition without grid or text."},
                    ],
                    "storyboard": [
                        {"time": "0-5s", "action": "Reveal product in warm light", "camera_move": "push_in"},
                        {"time": "5-11s", "action": "Show one truthful liquid proof", "camera_move": "locked_macro"},
                        {"time": "11-15s", "action": "Return to stable hero packshot", "camera_move": "pull_back"},
                    ],
                }
            }), encoding="utf-8")
            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Director Single Generation",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--generated-reference", f"product={product_master}",
                "--generated-reference", f"scene={scene}",
                "--generated-reference", f"beat_keyframe_proof={proof_keyframe}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference_xai",
                "--voice-id", "eve",
            ])
            plan_path = Path(json.loads(prepared.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual([shot["duration_seconds"] for shot in plan["shots"]], [15])
            self.assertEqual(plan["production_contract"]["approved_paid_cap"], 1)
            self.assertFalse(plan["stitching_plan"]["required"])
            self.assertEqual(plan["references"][0]["provenance"], "generated_from_approved_visual_plan")
            self.assertEqual(plan["references"][1]["provenance"], "generated_from_approved_visual_plan")
            shot = plan["shots"][0]
            self.assertEqual(shot["prompt_contract"]["compiler"], "director-commerce-v10")
            self.assertEqual(shot["prompt_contract"]["budget_chars"], 3000)
            self.assertEqual(shot["prompt_contract"]["camera_move"], "timecoded_per_beat")
            self.assertEqual(shot["continuity_mode"], "single_generation_timecoded_beats")
            self.assertEqual(len(shot["director_clip"]["beat_timeline"]), 3)
            self.assertEqual(shot["prompt_contract"]["camera_moves_by_beat"], ["push_in", "locked_macro", "pull_back"])
            self.assertIn("0-5s ", shot["prompt"])
            self.assertIn("5-11s ", shot["prompt"])
            self.assertIn("11-15s ", shot["prompt"])
            self.assertIn("beat composition", shot["prompt"])
            self.assertIn("AUDIO:", shot["prompt"])
            self.assertIn("<AUDIO_0>", shot["prompt"])
            self.assertEqual(plan["audio_contract"]["preset_voice_source"], "cli_user_explicit")
            dry = run_cmd(["python3", str(SCRIPTS / "generate_video.py"), "--plan", str(plan_path), "--dry-run"])
            self.assertEqual(len(json.loads(dry.stdout)["results"]), 1)
            request_file = Path(json.loads(dry.stdout)["results"][0]["request_file"])
            payload = json.loads(request_file.read_text(encoding="utf-8"))["payload"]
            self.assertEqual(payload["duration"], 15)
            self.assertEqual(payload["reference_audios"], [{"voice_id": "eve"}])

            del plan["audio_contract"]["preset_voice_source"]
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            legacy = run_cmd_fail([
                "python3", str(SCRIPTS / "generate_video.py"), "--plan", str(plan_path), "--dry-run",
            ])
            self.assertIn("explicit user choice", legacy.stdout.lower())

    def test_reference_spoken_plan_uses_prompt_native_voice_without_reference_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product_master = tmp_path / "product-master.png"
            hook = tmp_path / "hook.png"
            payoff = tmp_path / "payoff.png"
            product.write_bytes(b"raw-skincare-product")
            product_master.write_bytes(b"generated-faithful-product-master")
            hook.write_bytes(b"generated-hook-keyframe")
            payoff.write_bytes(b"generated-payoff-keyframe")
            speech = "轻拍唤醒水润光泽，让每日护肤更显从容。"
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "product_category": "premium skincare",
                "creative_variant": "premium_brand",
                "spoken_script": speech,
                "visual_design": {
                    "style_type": "cinematic_product_hero",
                    "single_minded_proposition": "一瓶开启从容水润仪式",
                    "audience_tension": "希望高效补水但拒绝廉价叫卖感",
                    "visual_proof": "真实瓶身、水光材质与轻拍使用动作",
                    "big_idea": "海光唤醒",
                    "emotional_arc": "好奇到感受再到拥有欲",
                    "talent_presence": "none",
                    "talent_role": "不使用人物，商品与液体完成全部视觉表达",
                    "sound_intent": "克制、成熟、温柔的普通话女性高级广告旁白",
                    "reference_plan": [
                        {"role": "product", "source": "generate_after_stage_1", "image_prompt": "Faithfully regenerate the same SKU as a clean product master."},
                        {"role": "beat_keyframe_hook", "source": "generate_after_stage_1", "image_prompt": "Generate a full-screen campaign hook keyframe."},
                        {"role": "beat_keyframe_payoff", "source": "generate_after_stage_1", "image_prompt": "Generate a full-screen proof and payoff keyframe."}
                    ]
                }
            }, ensure_ascii=False), encoding="utf-8")
            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Premium Skincare Auto Voice",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--generated-reference", f"product={product_master}",
                "--generated-reference", f"beat_keyframe_hook={hook}",
                "--generated-reference", f"beat_keyframe_payoff={payoff}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference_xai",
            ])
            plan_path = Path(json.loads(prepared.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            shot = plan["shots"][0]
            self.assertEqual(plan["plan_schema_version"], 3)
            self.assertEqual(shot["prompt_contract"]["compiler"], "director-commerce-v10")
            self.assertEqual(shot["prompt"].count("AUDIO:"), 1)
            self.assertEqual(shot["prompt"].count("Cuts:"), 1)
            self.assertEqual(shot["prompt"].count("Reference image map:"), 1)
            self.assertEqual(shot["prompt"].count(speech), 1)
            self.assertNotIn(", ,", shot["prompt"])
            self.assertLess(
                shot["prompt_contract"]["fixed_instruction_char_count"] / shot["prompt_contract"]["char_count"],
                0.60,
            )
            self.assertEqual(plan["audio_contract"]["voice_policy"], "prompt_native")
            self.assertEqual(plan["audio_contract"]["voice_id"], "")
            self.assertEqual(plan["audio_contract"]["voice_prompt_token"], "")
            self.assertEqual(plan["audio_contract"]["preset_voice_ids"], [])
            self.assertEqual(plan["audio_contract"]["voice_gender"], "female")
            self.assertEqual(plan["creative_contract"]["talent_contract"]["presence"], "none")
            self.assertIn("高级广告旁白", plan["audio_contract"]["voice_description"])
            self.assertTrue(plan["audio_contract"]["speech_required"])
            self.assertTrue(plan["audio_contract"]["speech_verification_required"])
            self.assertIn("prompt", plan["audio_contract"]["voice_selection_reason"].lower())
            self.assertNotIn("<AUDIO_0>", shot["prompt"])
            self.assertIn("Voice=", shot["prompt"])
            self.assertIn("高级广告旁白", shot["prompt"])
            self.assertIn("女性", shot["prompt"])
            self.assertIn("No person, face, body, hand, or human silhouette appears", shot["prompt"])
            self.assertNotIn("visible people demonstrate silently", shot["prompt"])
            self.assertEqual(len(plan["creative_contract"]["commercial_strategy"]["commercial_quality_gate"]), 6)
            for reference in plan["generated_reference_assets"]:
                self.assertIn("fact_source", reference)
                self.assertEqual(reference["fact_source_asset_ids"], ["input_evidence_product"])
                self.assertIn("mechanism_lock", reference)
                self.assertIn("observed", reference["mechanism_contract"])
                self.assertIn("forbidden_inventions", reference)
                self.assertIn("multimodal_qc", reference)
                self.assertIn("multimodal_qc_result", reference)
            dry = run_cmd(["python3", str(SCRIPTS / "generate_video.py"), "--plan", str(plan_path), "--dry-run"])
            request_file = Path(json.loads(dry.stdout)["results"][0]["request_file"])
            payload = json.loads(request_file.read_text(encoding="utf-8"))["payload"]
            self.assertNotIn("reference_audios", payload)

    def test_miku_15_second_reference_plan_uses_verified_10_plus_5_route_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            master = tmp_path / "master.png"
            hook = tmp_path / "hook.png"
            product.write_bytes(b"raw-product")
            master.write_bytes(b"generated-master")
            hook.write_bytes(b"generated-hook")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "duration_seconds": 15,
                "spoken_script": "洁面之后，轻柔整理肌肤。清透水感，开启每日护理。",
                "visual_design": {
                    "talent_presence": "none",
                    "talent_role": "No talent is used.",
                    "sound_intent": "soft restrained female Mandarin voiceover",
                    "storyboard": [
                        {"time": "0-4s", "action": "Reveal the product in controlled light", "camera_move": "push_in"},
                        {"time": "4-11s", "action": "Show a truthful liquid texture proof", "camera_move": "locked_macro"},
                        {"time": "11-15s", "action": "Return to the clean hero packshot", "camera_move": "pull_back"},
                    ],
                    "reference_plan": [
                        {"role": "product", "source": "generate_after_stage_1", "image_prompt": "Generate a faithful product master."},
                        {"role": "beat_keyframe_hook", "source": "generate_after_stage_1", "image_prompt": "Generate a full-screen product hook."},
                    ],
                },
            }, ensure_ascii=False), encoding="utf-8")
            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Miku Verified Duration",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--generated-reference", f"product={master}",
                "--generated-reference", f"beat_keyframe_hook={hook}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference",
            ])
            plan_path = Path(json.loads(prepared.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["duration_plan"]["request_durations_seconds"], [10, 5])
            self.assertEqual(plan["production_contract"]["approved_paid_cap"], 2)
            self.assertEqual(plan["model_capability_contract"]["planning_max_duration_seconds"], 10)
            self.assertEqual(plan["model_capability_contract"]["official_max_duration_seconds"], 15)
            self.assertEqual(plan["shots"][0]["director_clip"]["beat"], "route_split_storyboard")
            self.assertEqual(plan["shots"][1]["director_clip"]["beat"], "route_split_storyboard")
            self.assertTrue(plan["shots"][0]["director_clip"]["beat_timeline"])
            self.assertTrue(plan["shots"][1]["director_clip"]["beat_timeline"])
            all_beats = [
                beat
                for shot in plan["shots"]
                for beat in shot["director_clip"]["beat_timeline"]
            ]
            self.assertEqual([beat["beat_id"] for beat in all_beats], ["beat_01", "beat_02", "beat_03"])
            self.assertEqual(len({beat["beat_id"] for beat in all_beats}), 3)
            self.assertTrue(all(beat["timing_adjustment"] == "route_boundary_reflow" for beat in all_beats))
            self.assertEqual(plan["shots"][0]["director_clip"]["exit_state"], "stable_edit_safe_state")
            self.assertEqual(plan["shots"][1]["director_clip"]["entry_state"], "approved_continuity_state")
            self.assertEqual(len(plan["continuity_plan"]["edit_boundaries"]), 1)
            self.assertNotIn("4-1s", plan["shots"][1]["prompt"])

    def test_reference_prompt_keeps_commercial_direction_dominant(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            generated = []
            product.write_bytes(b"raw-product-evidence")
            for role in ("product", "presenter", "scene", "beat_keyframe_hook", "beat_keyframe_payoff"):
                path = tmp_path / f"generated-{role}.png"
                path.write_bytes(f"generated-{role}".encode())
                generated.append((role, path))
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "duration_seconds": 15,
                "speaker_mode": "voiceover",
                "speech_presentation": "off_screen_voiceover",
                "spoken_script": "看见真实细节，感受设计价值，现在了解更多。",
                "visual_design": {
                    "talent_presence": "presenter",
                    "talent_gender": "female",
                    "talent_role": "an adult woman establishes scale and trust",
                    "shot_mode": "commercial_montage",
                    "storyboard": [
                        {
                            "time": "0-4s",
                            "commercial_job": "stop the scroll with immediate recognition",
                            "entry_state": "dark frame with one precise edge light",
                            "action": "the adult woman enters and reveals the product at full readable scale",
                            "framing": "low-angle medium-wide hero composition",
                            "camera_move": "push_in",
                            "lighting_motion": "edge light travels across the product silhouette",
                            "physical_response": "wardrobe and hair respond subtly to her step",
                            "exit_state": "product label faces camera in a stable pose",
                            "transition_out": "light_wipe_cut",
                            "sound_cue": "footstep and a tight reveal whoosh",
                        },
                        {
                            "time": "4-11s",
                            "commercial_job": "prove one visible product truth",
                            "action": "show the approved surface and mechanism without inventing parts",
                            "framing": "clean macro proof composition",
                            "camera_move": "locked_macro",
                            "lighting_motion": "specular highlight traces the approved material",
                            "physical_response": "only the demonstrated real part responds",
                            "exit_state": "proof detail resolves into the hero silhouette",
                            "transition_out": "shape_match_cut",
                            "sound_cue": "precise tactile click synchronized to the visible action",
                        },
                        {
                            "time": "11-15s",
                            "commercial_job": "convert desire into memory",
                            "action": "settle on the clean product hero with the presenter behind it",
                            "framing": "full-screen packshot with clear visual hierarchy",
                            "camera_move": "pull_back",
                            "lighting_motion": "background glow blooms then settles",
                            "physical_response": "all motion resolves before the final hold",
                            "exit_state": "stable one-second hero hold",
                            "transition_out": "end_hold_1s",
                            "sound_cue": "music resolves with a soft product signature",
                        },
                    ],
                    "sound_design": {
                        "mode": "layered_native",
                        "sonic_idea": "precision becomes desire",
                        "ambience": "quiet architectural interior",
                        "music": "minimal modern instrumental pulse",
                    },
                    "reference_plan": [
                        {"role": role, "source": "generate_after_stage_1", "image_prompt": f"Generate the approved {role} control."}
                        for role, _ in generated
                    ],
                },
            }, ensure_ascii=False), encoding="utf-8")
            args = [
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Universal Commercial Prompt",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference_xai",
            ]
            for role, path in generated:
                args.extend(["--generated-reference", f"{role}={path}"])
            prepared = run_cmd(args)
            plan = json.loads(Path(json.loads(prepared.stdout)["plan"]).read_text(encoding="utf-8"))
            shot = plan["shots"][0]
            contract = shot["prompt_contract"]
            self.assertEqual(contract["compiler"], "director-commerce-v10")
            self.assertEqual(contract["architecture"], "universal-product-director-v6")
            self.assertGreaterEqual(contract["creative_execution_ratio"], 0.50)
            self.assertLessEqual(contract["reference_map_ratio"], 0.25)
            self.assertEqual(contract["structural_block_counts"]["director_timeline"], 1)
            self.assertEqual(shot["prompt"].count("Reference image map:"), 1)
            self.assertIn("Cues=", shot["prompt"])
            self.assertIn("precision becomes desire", plan["sound_design_contract"]["sonic_idea"])
            self.assertEqual(len(plan["sound_design_contract"]["beat_cue_map"]), 3)

    def test_continuous_sequence_uses_one_sequence_block_instead_of_fake_cuts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            master = tmp_path / "master.png"
            product.write_bytes(b"raw")
            master.write_bytes(b"generated-master")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "duration_seconds": 10,
                "visual_design": {
                    "talent_presence": "none",
                    "shot_mode": "continuous_sequence",
                    "storyboard": [
                        {"time": "0-4s", "action": "begin on a macro material detail", "camera_move": "pull_back", "sound_cue": "soft material texture"},
                        {"time": "4-10s", "action": "resolve into the complete product hero", "camera_move": "orbit", "sound_cue": "one restrained resolving accent"},
                    ],
                    "reference_plan": [
                        {"role": "product", "source": "generate_after_stage_1", "image_prompt": "Generate a faithful product master."},
                    ],
                },
            }), encoding="utf-8")
            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Continuous Product Film",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--generated-reference", f"product={master}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference_xai",
            ])
            plan = json.loads(Path(json.loads(prepared.stdout)["plan"]).read_text(encoding="utf-8"))
            shot = plan["shots"][0]
            self.assertEqual(shot["prompt"].count("Sequence:"), 1)
            self.assertEqual(shot["prompt"].count("Cuts:"), 0)
            self.assertEqual(shot["prompt_contract"]["structural_block_counts"]["director_timeline"], 1)

    def test_visible_female_presenter_requires_a_presenter_reference_and_locked_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            master = tmp_path / "master.png"
            presenter = tmp_path / "presenter.png"
            product.write_bytes(b"raw-product")
            master.write_bytes(b"generated-master")
            presenter.write_bytes(b"generated-female-presenter")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "duration_seconds": 10,
                "speaker_mode": "voiceover",
                "speech_presentation": "off_screen_voiceover",
                "spoken_script": "清透水感，让每日护理更加从容。",
                "visual_design": {
                    "talent_presence": "presenter",
                    "talent_gender": "female",
                    "talent_role": "一位成年女性用于建立信任和使用情绪",
                    "talent_description": "elegant adult skincare customer",
                    "sound_intent": "warm female Mandarin commercial voice",
                    "reference_plan": [
                        {"role": "product", "source": "generate_after_stage_1", "image_prompt": "Generate a faithful product master."},
                        {"role": "presenter", "source": "generate_after_stage_1", "image_prompt": "Generate one adult female presenter control."},
                    ],
                },
            }, ensure_ascii=False), encoding="utf-8")
            missing = run_cmd_fail([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Missing Presenter Control",
                "--project-root", str(tmp_path / "missing-projects"),
                "--product-image", str(product),
                "--generated-reference", f"product={master}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference",
            ])
            self.assertIn("generated presenter control image", missing.stdout)
            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Female Presenter Control",
                "--project-root", str(tmp_path / "approved-projects"),
                "--product-image", str(product),
                "--generated-reference", f"product={master}",
                "--generated-reference", f"presenter={presenter}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference",
            ])
            plan = json.loads(Path(json.loads(prepared.stdout)["plan"]).read_text(encoding="utf-8"))
            prompt = plan["shots"][0]["prompt"]
            self.assertEqual(plan["creative_contract"]["talent_contract"]["gender"], "female")
            self.assertIn("adult female", prompt)
            self.assertIn("Do not substitute a presenter of another gender", prompt)

    def test_poll_download_blocks_provider_clip_shorter_than_requested_duration(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg is required for media validation tests")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request_file = tmp_path / "shot_01_request.json"
            mock_video = tmp_path / "provider-10s.mp4"
            make_test_video(mock_video, duration=10.0, audio=True)
            request_file.write_text(json.dumps({
                "shot_id": "shot_01",
                "model_key": "grok_video_15_reference",
                "payload": {"duration": 15},
                "response": {"request_id": "offline-duration-test"},
                "quality_contract": {"max_provider_duration_shortfall_seconds": 1.0},
            }), encoding="utf-8")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "poll_video.py"),
                "--request-file", str(request_file),
                "--mock-video", str(mock_video),
            ])
            report = json.loads(result.stdout)
            self.assertEqual(report["error_code"], "QC_DURATION_SHORTFALL")
            self.assertFalse(report["duration_contract"]["pass"])
            self.assertGreater(report["duration_contract"]["shortfall_seconds"], 4.0)

    def test_prompt_compiler_removes_duplicate_structural_blocks_before_rendering(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"product")
            speech = "这款商品值得认真看看。"
            dirty_prompt = (
                "Cuts: 0-5s old hook; 5-15s old ending. "
                "Show the approved product with premium light. "
                f"AUDIO: VO=“{speech}”; SFX=none. "
                "Reference image map: <SOURCE_IMAGE> = old source."
            )
            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Clean Structural Prompt",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--video-source-image", str(product),
                "--prompt", dirty_prompt,
                "--spoken-script", speech,
                "--model-key", "grok_video_15",
            ])
            plan = json.loads(Path(json.loads(prepared.stdout)["plan"]).read_text(encoding="utf-8"))
            prompt = plan["shots"][0]["prompt"]
            contract = plan["shots"][0]["prompt_contract"]
            self.assertEqual(prompt.count("Cuts:"), 1)
            self.assertEqual(prompt.count("Reference image map:"), 0)
            self.assertEqual(prompt.count("AUDIO:"), 1)
            self.assertEqual(prompt.count(speech), 1)
            self.assertEqual(contract["structural_block_counts"]["audio"], 1)
            plan["shots"][0]["prompt"] += " AUDIO: VO=none."
            plan_path = Path(json.loads(prepared.stdout)["plan"])
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            preflight = run_cmd_fail([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(plan_path),
            ])
            self.assertIn("must contain exactly one AUDIO block", preflight.stdout)

    def test_spoken_r2v_plan_without_voice_reference_uses_prompt_native_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            master = tmp_path / "master.png"
            product.write_bytes(b"raw-product")
            master.write_bytes(b"generated-master")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "spoken_script": "这是一条需要清楚人声的带货旁白。",
                "visual_design": {"reference_plan": [{
                    "role": "product",
                    "source": "generate_after_stage_1",
                    "image_prompt": "Generate a faithful professional product master."
                }]}
            }, ensure_ascii=False), encoding="utf-8")
            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Legacy Missing Voice",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--generated-reference", f"product={master}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference_xai",
            ])
            plan_path = Path(json.loads(prepared.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["audio_contract"]["preset_voice_ids"] = []
            plan["audio_contract"]["voice_id"] = ""
            plan["audio_contract"]["voice_prompt_token"] = ""
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "generate_video.py"),
                "--plan", str(plan_path),
                "--dry-run",
            ])
            request_file = Path(json.loads(result.stdout)["results"][0]["request_file"])
            payload = json.loads(request_file.read_text(encoding="utf-8"))["payload"]
            self.assertNotIn("reference_audios", payload)

    def test_generated_action_reference_rejects_unsupported_dropper(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            master = tmp_path / "master.png"
            action = tmp_path / "action.png"
            product.write_bytes(b"raw-product")
            master.write_bytes(b"generated-master")
            action.write_bytes(b"generated-action")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "visual_design": {"reference_plan": [
                    {"role": "product", "source": "generate_after_stage_1", "image_prompt": "Generate a faithful product master."},
                    {"role": "hand_action", "source": "generate_after_stage_1", "image_prompt": "Generate a hand using a glass dropper above the bottle."}
                ]}
            }), encoding="utf-8")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Unsupported Dropper",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--generated-reference", f"product={master}",
                "--generated-reference", f"hand_action={action}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference",
            ])
            self.assertIn("unsupported product mechanism", result.stdout)
            self.assertIn("dropper", result.stdout)

    def test_review_blocks_provider_clip_shorter_than_plan_by_more_than_one_second(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg is required for media validation tests")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            clip = project / "shot_01.mp4"
            make_test_video(clip, duration=5.0, audio=True)
            (project / "generation-plan.json").write_text(json.dumps({
                "plan_schema_version": 2,
                "total_duration_seconds": 15,
                "delivery_max_seconds": 15,
                "quality_contract": {"max_provider_duration_shortfall_seconds": 1.0},
                "shots": [{
                    "id": "shot_01",
                    "duration_seconds": 15,
                    "clip_file": str(clip),
                    "script_boundary": {"stitch_safe": True},
                    "image": {},
                }],
            }), encoding="utf-8")
            result = run_cmd_fail([
                "python3", str(SCRIPTS / "review_render.py"),
                "--project-dir", str(project),
                "--video", str(clip),
            ])
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "blocked")
            self.assertFalse(report["provider_duration_shortfall_pass"])
            self.assertGreater(report["max_provider_duration_shortfall_seconds"], 1.0)

    def test_background_audio_without_verified_speech_cannot_be_delivered(self):
        sys.path.insert(0, str(SCRIPTS))
        try:
            from finalize_project import delivery_errors
        finally:
            sys.path.pop(0)
        plan = {
            "plan_schema_version": 2,
            "audio_contract": {"speech_required": True},
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
        visual = {
            "status": "pass_with_notes",
            "video_complete_and_coherent": True,
            "source_frame_consistency": True,
            "approved_product_identity": True,
            "presenter_identity_consistency": True,
            "presenter_outfit_consistency": True,
            "scene_composition_consistency": True,
            "speech_intelligible": False,
            "speech_meaning_preserved": False,
        }
        errors = delivery_errors(plan, jobs, technical, visual, None)
        self.assertTrue(any("Speech intelligibility" in error for error in errors))
        self.assertTrue(any("visual review must be blocked" in error for error in errors))

    def test_product_only_plan_blocks_an_unexpected_person(self):
        sys.path.insert(0, str(SCRIPTS))
        try:
            from finalize_project import delivery_errors
        finally:
            sys.path.pop(0)
        plan = {
            "plan_schema_version": 2,
            "creative_contract": {"talent_contract": {"presence": "none", "gender": "not_applicable"}},
            "audio_contract": {"speech_required": False, "voice_gender": "not_applicable"},
            "production_contract": {"base_request_count": 1, "approved_paid_cap": 1},
            "subtitle_plan": {"enabled": False},
            "shots": [{"id": "shot_01"}],
        }
        jobs = {"jobs": [{"shot_id": "shot_01", "state": "verified", "submission_attempts": 1}]}
        technical = {"status": "pass", "delivery_duration_hard_limit_pass": True, "provider_duration_shortfall_pass": True}
        visual = {
            "status": "pass_with_notes",
            "video_complete_and_coherent": True,
            "source_frame_consistency": True,
            "approved_product_identity": True,
            "scene_composition_consistency": True,
            "unexpected_person_absent": False,
        }
        errors = delivery_errors(plan, jobs, technical, visual, None)
        self.assertTrue(any("appeared against" in error for error in errors))

    def test_explicit_female_voice_direction_blocks_a_male_voice_result(self):
        sys.path.insert(0, str(SCRIPTS))
        try:
            from finalize_project import delivery_errors
        finally:
            sys.path.pop(0)
        plan = {
            "plan_schema_version": 2,
            "creative_contract": {"talent_contract": {"presence": "none", "gender": "not_applicable"}},
            "audio_contract": {"speech_required": True, "voice_gender": "female"},
            "production_contract": {"base_request_count": 1, "approved_paid_cap": 1},
            "subtitle_plan": {"enabled": False},
            "shots": [{"id": "shot_01"}],
        }
        jobs = {"jobs": [{"shot_id": "shot_01", "state": "verified", "submission_attempts": 1}]}
        technical = {"status": "pass", "delivery_duration_hard_limit_pass": True, "provider_duration_shortfall_pass": True}
        visual = {
            "status": "pass_with_notes",
            "video_complete_and_coherent": True,
            "source_frame_consistency": True,
            "approved_product_identity": True,
            "scene_composition_consistency": True,
            "unexpected_person_absent": True,
            "speech_intelligible": True,
            "speech_meaning_preserved": True,
            "voice_gender_matches_plan": False,
        }
        errors = delivery_errors(plan, jobs, technical, visual, None)
        self.assertTrue(any("voice gender" in error.lower() for error in errors))

    def test_food_category_allows_presenter_when_director_uses_it_as_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            product = Path(tmp) / "food.png"
            product.write_bytes(b"food-product")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Food Talent Director Choice",
                "--project-root", str(Path(tmp) / "projects"),
                "--product-image", str(product),
                "--model-key", "grok_video_15",
                "--product-category", "packaged food",
                "--speaker-mode", "digital-human-spoken",
                "--spoken-script", "这一口真实风味，值得现在品尝。",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            self.assertEqual(plan["creative_contract"]["talent_effects_contract"]["decision"], "director_judgment")

    def test_preflight_treats_reference_qc_as_advisory_and_accepts_recorded_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            master = tmp_path / "master.png"
            product.write_bytes(b"raw-product")
            master.write_bytes(b"generated-master")

            def prepare(qc_status: str) -> Path:
                brief = tmp_path / f"brief-{qc_status}.json"
                brief.write_text(json.dumps({
                    "visual_design": {"reference_plan": [{
                        "role": "product",
                        "source": "generate_after_stage_1",
                        "generation_input_asset_ids": ["input_evidence_product"],
                        "fact_source_asset_ids": ["input_evidence_product"],
                        "observed_mechanisms": ["fixed_cap"],
                        "image_prompt": "Generate a faithful professional product master.",
                        "multimodal_qc_result": {
                            "status": qc_status,
                            "reviewer": "codex_multimodal",
                            "checked_against_asset_ids": ["input_evidence_product"],
                        },
                    }]},
                }, ensure_ascii=False), encoding="utf-8")
                prepared = run_cmd([
                    "python3", str(SCRIPTS / "prepare_project.py"),
                    "--name", f"Reference QC {qc_status}",
                    "--project-root", str(tmp_path / "projects"),
                    "--product-image", str(product),
                    "--generated-reference", f"product={master}",
                    "--brief", str(brief),
                    "--model-key", "grok_video_15_reference",
                ])
                return Path(json.loads(prepared.stdout)["plan"])

            pending_plan = prepare("required_before_stage_2_confirmation")
            pending = run_cmd([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(pending_plan),
            ])
            pending_report = json.loads(pending.stdout)
            self.assertTrue(pending_report["paid_generation_allowed"])
            self.assertTrue(any("Stage 2 user review remains the approval gate" in item for item in pending_report["warnings"]))

            passed_plan = prepare("pass")
            passed = run_cmd([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(passed_plan),
            ])
            self.assertTrue(json.loads(passed.stdout)["ok"])
            plan = json.loads(passed_plan.read_text(encoding="utf-8"))
            reference = plan["generated_reference_assets"][0]
            self.assertEqual(reference["multimodal_qc_result"]["status"], "pass")
            self.assertEqual(reference["fact_source_asset_ids"], ["input_evidence_product"])
            self.assertEqual(reference["mechanism_contract"]["observed"], ["fixed_cap"])

    def test_voiceover_fallback_does_not_invent_a_presenter(self):
        with tempfile.TemporaryDirectory() as tmp:
            product = Path(tmp) / "product.png"
            product.write_bytes(b"product")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Product Led Voiceover",
                "--project-root", str(Path(tmp) / "projects"),
                "--product-image", str(product),
                "--video-source-image", str(product),
                "--model-key", "grok_video_15",
                "--speaker-mode", "voiceover",
                "--spoken-script", "看见商品细节，了解真实卖点。",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            prompt = plan["shots"][0]["prompt"].lower()
            self.assertNotIn("natural presenter delivery", prompt)
            self.assertIn("product-led visual storytelling", prompt)

    def test_default_commercial_plan_requires_layered_native_sound(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"product")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Layered Commercial Sound",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--video-source-image", str(product),
                "--model-key", "grok_video_15",
                "--spoken-script", "看见细节，也听见质感。",
            ])
            plan_path = Path(json.loads(result.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            sound = plan["sound_design_contract"]
            prompt = plan["shots"][0]["prompt"]

            self.assertEqual(sound["mode"], "layered_native")
            self.assertTrue(sound["non_speech_required"])
            self.assertEqual(sound["music_policy"], "original_instrumental")
            self.assertEqual(sound["required_layers"], {"sfx": True, "ambience": True, "music": True})
            self.assertTrue(sound["verification_required"])
            self.assertEqual(
                plan["model_capability_contract"]["native_sound_design_prompting"],
                "prompt_directed_best_effort",
            )
            self.assertFalse(
                plan["model_capability_contract"]["native_cross_clip_audio_state_shared"]
            )
            self.assertTrue(
                plan["model_capability_contract"]["exact_score_continuity_requires_local_post_mix"]
            )
            self.assertFalse(plan["model_capability_contract"]["native_sound_layers_guaranteed"])
            self.assertNotIn("Music=no music", prompt)
            self.assertIn("Cues=", prompt)
            self.assertIn("Ambience=", prompt)
            self.assertIn("Music=", prompt)
            self.assertIn("Mix=", prompt)

            sys.path.insert(0, str(SCRIPTS))
            try:
                from review_render import planned_visual_review_fields
                from preflight_project import plan_errors
            finally:
                sys.path.pop(0)
            fields = planned_visual_review_fields(plan)
            self.assertIn("planned_sfx_audible", fields)
            self.assertIn("planned_ambience_audible", fields)
            self.assertIn("planned_music_audible", fields)
            self.assertIn("non_speech_sound_supports_story", fields)
            self.assertIn("audio_mix_balanced", fields)

            plan["shots"][0]["prompt"] = re.sub(
                r"Cues=.*?; Ambience=",
                "Cues=none; Ambience=",
                prompt,
            )
            model = json.loads(CONFIG.read_text(encoding="utf-8"))["models"]["grok_video_15"]
            errors = plan_errors(plan, model)
            self.assertTrue(any("missing an audible synchronized sound cue" in error for error in errors))

    def test_multiclip_sound_prompts_are_self_contained_and_preserve_clip_sfx(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            master = tmp_path / "master.png"
            product.write_bytes(b"raw-sneaker-evidence")
            master.write_bytes(b"generated-sneaker-master")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "duration_seconds": 15,
                "spoken_script": "黑白层次更有个性。穿上这一双，走出街头态度。",
                "visual_design": {
                    "talent_presence": "none",
                    "shot_mode": "commercial_montage",
                    "clip_plan": [
                        {
                            "sfx": "subtle turntable mechanics and material glide",
                            "ambience": "continuous quiet modern studio ambience",
                            "music": "restrained warm low-frequency electronic pulse",
                            "audio_bridge": "carry the low-frequency pulse after the complete sentence",
                        },
                        {
                            "sfx": "soft sole-contact accent aligned to the hero reveal",
                            "ambience": "the same continuous quiet modern studio ambience",
                            "music": "the same original warm electronic beat lifting before a clean resolution",
                        },
                    ],
                    "storyboard": [
                        {
                            "time": "0-4s",
                            "action": "reveal the complete sneaker on the turntable",
                            "camera_move": "orbit",
                            "sound_cue": "turntable mechanics align to the reveal",
                        },
                        {
                            "time": "4-10s",
                            "action": "glide across the material and outsole proof",
                            "camera_move": "track",
                            "sound_cue": "material glide aligns to the macro move",
                        },
                        {
                            "time": "10-15s",
                            "action": "pull back to the stable sneaker hero",
                            "camera_move": "pull_back",
                            "sound_cue": "沿用上一段低频尾音，电子节拍抬升后干净收束",
                        },
                    ],
                    "sound_design": {
                        "mode": "layered_native",
                        "sonic_idea": "a restrained low-frequency pulse reveals black-and-white layers",
                        "signature_sfx": "precise product-action accents",
                        "ambience": "continuous quiet modern studio ambience",
                        "music": "restrained warm low-frequency electronic pulse with no vocals",
                    },
                    "reference_plan": [{
                        "role": "product",
                        "source": "generate_after_stage_1",
                        "image_prompt": "Generate a faithful sneaker product master.",
                    }],
                },
            }, ensure_ascii=False), encoding="utf-8")
            prepared = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Self Contained Sneaker Sound",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--generated-reference", f"product={master}",
                "--brief", str(brief),
                "--model-key", "grok_video_15_reference",
            ])
            plan_path = Path(json.loads(prepared.stdout)["plan"])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            second = plan["shots"][1]
            audio_block = second["prompt"].split("AUDIO:", 1)[1]
            coverage = second["prompt_contract"]["sound_cue_coverage"]

            self.assertEqual(second["prompt_contract"]["compiler"], "director-commerce-v10")
            self.assertEqual(second["prompt_contract"]["architecture"], "universal-product-director-v6")
            self.assertIn("sound on action", second["prompt"])
            self.assertIn("soft sole-contact accent aligned to the hero reveal", audio_block)
            self.assertIn("continuous quiet modern studio ambience", audio_block)
            self.assertIn("restrained warm low-frequency electronic pulse", audio_block)
            self.assertNotIn("the same", audio_block.lower())
            self.assertNotIn("上一段", audio_block)
            self.assertNotIn("沿用", audio_block)
            self.assertTrue(coverage["clip_sfx_rendered"])
            self.assertTrue(coverage["all_beat_cues_rendered_in_timeline"])
            self.assertTrue(coverage["audio_block_links_timecoded_cues"])
            self.assertTrue(coverage["self_contained"])
            self.assertGreaterEqual(coverage["cross_clip_dependency_terms_removed"], 1)
            self.assertEqual(
                plan["sound_design_contract"]["continuity_strategy"],
                "self_contained_restatement_per_paid_clip",
            )
            self.assertFalse(plan["sound_design_contract"]["native_cross_clip_audio_state_shared"])

            sys.path.insert(0, str(SCRIPTS))
            try:
                from preflight_project import plan_errors
            finally:
                sys.path.pop(0)
            model = {
                **json.loads(CONFIG.read_text(encoding="utf-8"))["models"]["grok_video_15_reference"],
                "key": "grok_video_15_reference",
            }
            self.assertFalse(plan_errors(plan, model))
            broken = json.loads(json.dumps(plan))
            broken["shots"][1]["prompt_contract"]["sound_cue_coverage"]["self_contained"] = False
            errors = plan_errors(broken, model)
            self.assertTrue(any("self-contained" in error for error in errors))
            plan_path.write_text(json.dumps(broken), encoding="utf-8")
            preflight = run_cmd([
                "python3", str(SCRIPTS / "preflight_project.py"),
                "--plan", str(plan_path),
            ])
            preflight_report = json.loads(preflight.stdout)
            self.assertTrue(preflight_report["paid_generation_allowed"])
            self.assertTrue(any("self-contained" in item for item in preflight_report["warnings"]))

    def test_explicit_no_music_uses_ambience_led_sound_instead_of_voice_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            product.write_bytes(b"product")
            brief = tmp_path / "brief.json"
            brief.write_text(json.dumps({
                "spoken_script": "夜色已就位，现在出发。",
                "visual_design": {
                    "clip_plan": [{
                        "beat": "night_departure",
                        "action": "The car departs through the city at night",
                        "camera_move": "track",
                        "transition_out": "end_hold_1s",
                        "sfx": "distinct ignition and restrained engine note",
                        "ambience": "open-air city night ambience",
                        "music": "no music"
                    }]
                }
            }, ensure_ascii=False), encoding="utf-8")
            result = run_cmd([
                "python3", str(SCRIPTS / "prepare_project.py"),
                "--name", "Ambience Led Sound",
                "--project-root", str(tmp_path / "projects"),
                "--product-image", str(product),
                "--video-source-image", str(product),
                "--brief", str(brief),
                "--model-key", "grok_video_15",
            ])
            plan = json.loads(Path(json.loads(result.stdout)["plan"]).read_text(encoding="utf-8"))
            sound = plan["sound_design_contract"]
            prompt = plan["shots"][0]["prompt"]

            self.assertEqual(sound["mode"], "ambience_led")
            self.assertTrue(sound["non_speech_required"])
            self.assertEqual(sound["music_policy"], "ambience_led_no_music")
            self.assertEqual(sound["required_layers"], {"sfx": True, "ambience": True, "music": False})
            self.assertIn("Music=no music", prompt)
            self.assertIn("Cues=", prompt)
            self.assertIn("Ambience=", prompt)
            sys.path.insert(0, str(SCRIPTS))
            try:
                from review_render import planned_visual_review_fields
            finally:
                sys.path.pop(0)
            fields = planned_visual_review_fields(plan)
            self.assertIn("planned_sfx_audible", fields)
            self.assertIn("planned_ambience_audible", fields)
            self.assertNotIn("planned_music_audible", fields)

    def test_missing_planned_sound_layers_block_formal_delivery(self):
        sys.path.insert(0, str(SCRIPTS))
        try:
            from finalize_project import delivery_errors
        finally:
            sys.path.pop(0)
        plan = {
            "plan_schema_version": 2,
            "audio_contract": {"speech_required": True},
            "sound_design_contract": {
                "mode": "layered_native",
                "non_speech_required": True,
                "verification_required": True,
                "required_layers": {"sfx": True, "ambience": True, "music": True},
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
        visual = {
            "status": "pass_with_notes",
            "video_complete_and_coherent": True,
            "source_frame_consistency": True,
            "approved_product_identity": True,
            "scene_composition_consistency": True,
            "unexpected_person_absent": True,
            "speech_intelligible": True,
            "speech_meaning_preserved": True,
            "planned_sfx_audible": False,
            "planned_ambience_audible": False,
            "planned_music_audible": False,
            "non_speech_sound_supports_story": False,
            "audio_mix_balanced": False,
        }
        errors = delivery_errors(plan, jobs, technical, visual, None)
        self.assertTrue(any("sound effect" in error.lower() for error in errors))
        self.assertTrue(any("ambience" in error.lower() for error in errors))
        self.assertTrue(any("music" in error.lower() for error in errors))
        self.assertTrue(any("sound design" in error.lower() for error in errors))
        self.assertTrue(any("audio mix" in error.lower() for error in errors))

    def test_reference_storyboard_requires_two_to_four_flexible_beats(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            product = tmp_path / "product.png"
            master = tmp_path / "master.png"
            product.write_bytes(b"raw-product")
            master.write_bytes(b"generated-master")
            for beat_count in (1, 5):
                brief = tmp_path / f"brief-{beat_count}.json"
                brief.write_text(json.dumps({
                    "visual_design": {
                        "reference_plan": [{
                            "role": "product",
                            "source": "generate_after_stage_1",
                            "image_prompt": "Generate a faithful product master.",
                            "multimodal_qc_result": {"status": "pass"},
                        }],
                        "storyboard": [
                            {"time": f"beat-{index}", "action": "Show one commercial beat", "camera_move": "static"}
                            for index in range(beat_count)
                        ],
                    },
                }), encoding="utf-8")
                result = run_cmd_fail([
                    "python3", str(SCRIPTS / "prepare_project.py"),
                    "--name", f"Invalid Beat Count {beat_count}",
                    "--project-root", str(tmp_path / "projects"),
                    "--product-image", str(product),
                    "--generated-reference", f"product={master}",
                    "--brief", str(brief),
                    "--model-key", "grok_video_15_reference",
                ])
                self.assertIn("semantic beats", result.stdout)


if __name__ == "__main__":
    unittest.main()
