import unittest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import patch

try:
    import yaml
except ImportError:
    yaml = None

from app.cli.utils import compact_error_text, read_yaml_safe, write_yaml_safe
from app.cli.commands import compile_cmd, package_cmd, acceptance_cmd, review_cmd
from app.core.artifact_graph import (
    ArtifactGraph, ArtifactNode, ArtifactEdge, ArtifactNodeType,
    ArtifactEdgeType, ArtifactRef, ArtifactGraphValidationError
)

class TestCLIUtils(unittest.TestCase):
    def test_compact_error_text_no_folding(self):
        text = "\n".join(f"line {i}" for i in range(10))
        result = compact_error_text(text, max_lines=15)
        self.assertEqual(result, text)

    def test_compact_error_text_with_folding(self):
        text = "\n".join(f"line {i}" for i in range(50))
        result = compact_error_text(text, max_lines=15)
        self.assertIn("Folded 36 lines of output", result)
        self.assertTrue(result.startswith("line 0"))
        self.assertTrue(result.endswith("line 49"))

    def test_yaml_safe_operations(self):
        temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(temp_dir))
        
        yaml_path = Path(temp_dir) / "test.yaml"
        data = {"key": "value", "nested": {"num": 42}}
        
        write_success = write_yaml_safe(str(yaml_path), data)
        self.assertTrue(write_success)
        self.assertTrue(yaml_path.exists())
        
        read_data = read_yaml_safe(str(yaml_path))
        self.assertEqual(read_data, data)
        
        self.assertIsNone(read_yaml_safe(str(Path(temp_dir) / "missing.yaml")))


class TestCLICommands(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.temp_dir) / "output"
        self.output_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _write_mock_spec(self, path: Path, data: dict):
        if yaml is not None:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f)
        else:
            import json
            path.write_text(json.dumps(data), encoding="utf-8")

    def test_artifact_graph_validation_rules(self):
        graph = ArtifactGraph(
            work_id="test_work",
            nodes=[
                ArtifactNode(
                    node_id="brief",
                    type=ArtifactNodeType.HUMAN_BRIEF,
                    artifact_ref=ArtifactRef(name="human_brief")
                )
            ],
            edges=[]
        )
        with self.assertRaises(ArtifactGraphValidationError):
            graph.validate()

        graph = ArtifactGraph(
            work_id="test_work",
            nodes=[
                ArtifactNode(
                    node_id="spec",
                    type=ArtifactNodeType.MACHINE_SPEC,
                    artifact_ref=ArtifactRef(name="machine_spec")
                ),
                ArtifactNode(
                    node_id="brief",
                    type=ArtifactNodeType.HUMAN_BRIEF,
                    artifact_ref=ArtifactRef(name="human_brief")
                )
            ],
            edges=[]
        )
        with self.assertRaises(ArtifactGraphValidationError):
            graph.validate()

        graph = ArtifactGraph(
            work_id="test_work",
            nodes=[
                ArtifactNode(
                    node_id="spec",
                    type=ArtifactNodeType.MACHINE_SPEC,
                    artifact_ref=ArtifactRef(name="machine_spec")
                ),
                ArtifactNode(
                    node_id="brief",
                    type=ArtifactNodeType.HUMAN_BRIEF,
                    artifact_ref=ArtifactRef(name="human_brief")
                )
            ],
            edges=[
                ArtifactEdge(
                    edge_id="edge_rev",
                    from_node_id="spec",
                    to_node_id="brief",
                    type=ArtifactEdgeType.DERIVES_FROM
                )
            ]
        )
        with self.assertRaises(ArtifactGraphValidationError):
            graph.validate()

        graph = ArtifactGraph(
            work_id="test_work",
            nodes=[
                ArtifactNode(
                    node_id="spec",
                    type=ArtifactNodeType.MACHINE_SPEC,
                    artifact_ref=ArtifactRef(name="machine_spec")
                ),
                ArtifactNode(
                    node_id="brief",
                    type=ArtifactNodeType.HUMAN_BRIEF,
                    artifact_ref=ArtifactRef(name="human_brief")
                )
            ],
            edges=[
                ArtifactEdge(
                    edge_id="edge_ok",
                    from_node_id="brief",
                    to_node_id="spec",
                    type=ArtifactEdgeType.DERIVES_FROM
                )
            ]
        )
        graph.validate()

    @patch('builtins.input', side_effect=["1", "自定义裁决方案"])
    def test_compile_command_interactive(self, mock_input):
        intent = "设计一个带缓存的商品详情接口"
        materials = []
        compile_cmd(
            intent=intent,
            materials=materials,
            output_dir=str(self.output_dir),
            fake=True
        )
        
        spec_file = self.output_dir / "machine_spec.yaml"
        brief_file = self.output_dir / "human_brief.md"
        
        self.assertTrue(spec_file.exists(), "machine_spec.yaml should be created")
        self.assertTrue(brief_file.exists(), "human_brief.md should be created")
        
        spec_content = spec_file.read_text(encoding="utf-8")
        self.assertIn("商品详情接口", spec_content)
        
        brief_content = brief_file.read_text(encoding="utf-8")
        self.assertIn("商品详情接口", brief_content)

    def test_package_command(self):
        spec_file = self.output_dir / "machine_spec.yaml"
        spec_data = {
            "title": "缓存设计",
            "objective": "验证CLI打包生成",
            "requirements": [{"requirement_id": "r1", "statement": "支持 Redis"}]
        }
        self._write_mock_spec(spec_file, spec_data)
            
        package_file = self.output_dir / "agent_package.md"
        
        package_cmd(
            spec_path=str(spec_file),
            output_path=str(package_file),
            fake=True
        )
        
        self.assertTrue(package_file.exists())
        content = package_file.read_text(encoding="utf-8")
        self.assertIn("缓存设计", content)
        self.assertIn("验证CLI打包生成", content)

    def test_acceptance_command(self):
        spec_file = self.output_dir / "machine_spec.yaml"
        spec_data = {
            "title": "鉴权网关",
            "objective": "保护内部微服务",
            "requirements": [{"requirement_id": "r2", "statement": "拦截未授权请求"}]
        }
        self._write_mock_spec(spec_file, spec_data)
            
        acceptance_file = self.output_dir / "acceptance.md"
        
        acceptance_cmd(
            spec_path=str(spec_file),
            output_path=str(acceptance_file),
            fake=True
        )
        
        self.assertTrue(acceptance_file.exists())
        content = acceptance_file.read_text(encoding="utf-8")
        self.assertIn("鉴权网关", content)
        self.assertIn("拦截未授权请求", content)

    def test_review_command(self):
        spec_file = self.output_dir / "machine_spec.yaml"
        spec_data = {
            "title": "鉴权网关",
            "objective": "保护内部微服务",
            "requirements": [{"requirement_id": "r2", "statement": "拦截未授权请求"}]
        }
        self._write_mock_spec(spec_file, spec_data)
            
        acc_file = self.output_dir / "acceptance.md"
        acc_file.write_text("# 验收协议\n- 拦截未授权请求需返回 401\n", encoding="utf-8")
        
        review_file = self.output_dir / "review_result.md"
        
        review_cmd(
            spec_path=str(spec_file),
            acceptance_path=str(acc_file),
            delivery_text_or_path="开发已实现拦截逻辑，未携带 token 返回 401。",
            output_path=str(review_file),
            fake=True
        )
        
        self.assertTrue(review_file.exists())
        content = review_file.read_text(encoding="utf-8")
        self.assertIn("Review Verdict", content)
        self.assertIn("r2", content)


class TestCLIMain(unittest.TestCase):
    @patch('app.cli.main.compile_cmd')
    def test_main_compile_args(self, mock_compile):
        from app.cli.main import main
        main(["compile", "--intent", "test_intent", "-m", "mat1", "mat2", "--output-dir", "/tmp/out"])
        mock_compile.assert_called_once_with(
            intent="test_intent",
            materials=["mat1", "mat2"],
            output_dir="/tmp/out",
            fake=False
        )

    @patch('app.cli.main.package_cmd')
    def test_main_package_args(self, mock_package):
        from app.cli.main import main
        main(["package", "--spec", "spec.yaml", "--output", "pkg.md", "--fake"])
        mock_package.assert_called_once_with(
            spec_path="spec.yaml",
            output_path="pkg.md",
            fake=True
        )

    @patch('app.cli.main.acceptance_cmd')
    def test_main_acceptance_args(self, mock_acceptance):
        from app.cli.main import main
        main(["acceptance", "--spec", "spec.yaml", "--output", "acc.md", "--fake"])
        mock_acceptance.assert_called_once_with(
            spec_path="spec.yaml",
            output_path="acc.md",
            fake=True
        )

    @patch('app.cli.main.review_cmd')
    def test_main_review_args(self, mock_review):
        from app.cli.main import main
        main(["review", "--spec", "spec.yaml", "--acceptance", "acc.md", "--delivery", "del.txt", "--output", "rev.md", "--fake"])
        mock_review.assert_called_once_with(
            spec_path="spec.yaml",
            acceptance_path="acc.md",
            delivery_text_or_path="del.txt",
            output_path="rev.md",
            fake=True
        )


if __name__ == "__main__":
    unittest.main()
