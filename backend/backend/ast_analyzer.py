"""AIC Platform — AST Analysis & Workspace Code Intelligence Engine.

Provides deep AST parsing, symbol extraction, dependency graph generation,
and regression test suite generation for Python and TypeScript/JavaScript codebases.
"""

import ast
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aic.ast")


class SymbolInfo:

    def __init__(
        self,
        name: str,
        kind: str,
        line: int,
        docstring: str = "",
        args: Optional[List[str]] = None,
    ):
        self.name = name
        self.kind = kind  # "class" | "function" | "method" | "variable"
        self.line = line
        self.docstring = docstring
        self.args = args or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "line": self.line,
            "docstring": self.docstring,
            "args": self.args,
        }


class ASTAnalyzer:
    """Python AST Analyzer for extracting symbols, imports, and docstrings."""

    @staticmethod
    def parse_python_file(file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}", "symbols": []}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content, filename=file_path)
            symbols: List[Dict[str, Any]] = []
            imports: List[str] = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")
                elif isinstance(node, ast.ClassDef):
                    symbols.append(
                        SymbolInfo(
                            name=node.name,
                            kind="class",
                            line=node.lineno,
                            docstring=ast.get_docstring(node) or "",
                        ).to_dict()
                    )
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = [a.arg for a in node.args.args]
                    kind = (
                        "function"
                        if not isinstance(
                            getattr(node, "parent", None), ast.ClassDef
                        )
                        else "method"
                    )
                    symbols.append(
                        SymbolInfo(
                            name=node.name,
                            kind=kind,
                            line=node.lineno,
                            docstring=ast.get_docstring(node) or "",
                            args=args,
                        ).to_dict()
                    )

            return {
                "file": file_path,
                "language": "python",
                "symbols": symbols,
                "imports": list(set(imports)),
                "lines": len(content.splitlines()),
                "status": "success",
            }
        except SyntaxError as e:
            return {
                "file": file_path,
                "language": "python",
                "status": "syntax_error",
                "error": str(e),
                "line": e.lineno,
            }
        except Exception as e:
            return {"file": file_path, "status": "error", "error": str(e)}

    @staticmethod
    def parse_js_ts_file(file_path: str) -> Dict[str, Any]:
        """Regex-based AST symbol extractor for JS/TS files."""
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}", "symbols": []}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            symbols = []
            imports = []

            # Imports
            for match in re.finditer(
                r"import\s+.*?from\s+['\"]([^'\"]+)['\"]", content
            ):
                imports.append(match.group(1))

            # Classes
            for line_idx, line in enumerate(content.splitlines(), start=1):
                class_match = re.search(r"class\s+([A-Za-z0-9_]+)", line)
                if class_match:
                    symbols.append(
                        SymbolInfo(
                            name=class_match.group(1),
                            kind="class",
                            line=line_idx,
                        ).to_dict()
                    )

                # Functions / Arrow functions
                func_match = re.search(
                    r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)",
                    line,
                )
                if func_match:
                    args = [
                        a.strip().split(":")[0]
                        for a in func_match.group(2).split(",")
                        if a.strip()
                    ]
                    symbols.append(
                        SymbolInfo(
                            name=func_match.group(1),
                            kind="function",
                            line=line_idx,
                            args=args,
                        ).to_dict()
                    )

            return {
                "file": file_path,
                "language": (
                    "typescript" if file_path.endswith(".ts") else "javascript"
                ),
                "symbols": symbols,
                "imports": list(set(imports)),
                "lines": len(content.splitlines()),
                "status": "success",
            }
        except Exception as e:
            return {"file": file_path, "status": "error", "error": str(e)}

    @staticmethod
    def generate_regression_test_suite(file_path: str) -> Dict[str, Any]:
        """Generate a starter regression test suite based on AST extracted symbols."""
        analysis = (
            ASTAnalyzer.parse_python_file(file_path)
            if file_path.endswith(".py")
            else ASTAnalyzer.parse_js_ts_file(file_path)
        )
        if analysis.get("status") != "success":
            return {"status": "error", "error": analysis.get("error", "Analysis failed")}

        symbols = analysis.get("symbols", [])
        file_name = os.path.basename(file_path)
        module_name = os.path.splitext(file_name)[0]

        if analysis.get("language") == "python":
            test_code_lines = [
                f"# Generated Regression Test Suite for {file_name}",
                "import pytest",
                f"import {module_name}",
                "",
            ]
            for s in symbols:
                name = s["name"]
                kind = s["kind"]
                if kind in ("function", "method"):
                    test_code_lines.append(f"def test_{name}_regression():")
                    test_code_lines.append(f'    """Regression test for {name}."""')
                    test_code_lines.append(f"    assert hasattr({module_name}, '{name}')")
                    test_code_lines.append("")
                elif kind == "class":
                    test_code_lines.append(f"def test_class_{name}_exists():")
                    test_code_lines.append(f"    assert hasattr({module_name}, '{name}')")
                    test_code_lines.append("")

            return {
                "status": "success",
                "target_file": file_path,
                "test_file_suggested": f"test_{module_name}_regression.py",
                "test_code": "\n".join(test_code_lines),
                "symbols_covered": len(symbols),
            }
        else:
            test_code_lines = [
                f"// Generated Regression Test Suite for {file_name}",
                'import { describe, it, expect } from "vitest";',
                f'import * as moduleTarget from "./{module_name}";',
                "",
                f'describe("Regression Test Suite for {module_name}", () => {{',
            ]
            for s in symbols:
                name = s["name"]
                test_code_lines.append(f'  it("should have export {name}", () => {{')
                test_code_lines.append(f'    expect(moduleTarget.{name}).toBeDefined();')
                test_code_lines.append("  });")

            test_code_lines.append("});")
            return {
                "status": "success",
                "target_file": file_path,
                "test_file_suggested": f"{module_name}.test.ts",
                "test_code": "\n".join(test_code_lines),
                "symbols_covered": len(symbols),
            }
