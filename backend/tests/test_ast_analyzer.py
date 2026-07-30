import os
import pytest
from backend.ast_analyzer import ASTAnalyzer

def test_ast_analyzer_python(tmp_path):
    test_file = tmp_path / "sample.py"
    test_file.write_text('''
import os
import sys

class Calculator:
    """A simple calculator class."""
    def add(self, a, b):
        return a + b

def multiply(x, y):
    """Multiply two numbers."""
    return x * y
''')

    res = ASTAnalyzer.parse_python_file(str(test_file))
    assert res["status"] == "success"
    assert res["language"] == "python"
    assert "os" in res["imports"]
    assert "sys" in res["imports"]
    
    symbols = {s["name"]: s for s in res["symbols"]}
    assert "Calculator" in symbols
    assert symbols["Calculator"]["kind"] == "class"
    assert "multiply" in symbols
    assert symbols["multiply"]["kind"] == "function"
    assert symbols["multiply"]["args"] == ["x", "y"]

def test_ast_analyzer_ts(tmp_path):
    test_file = tmp_path / "sample.ts"
    test_file.write_text('''
import { useState } from "react";

export class UserStore {
  name: string = "";
}

export async function fetchUser(userId: string) {
  return { id: userId };
}
''')

    res = ASTAnalyzer.parse_js_ts_file(str(test_file))
    assert res["status"] == "success"
    assert res["language"] == "typescript"
    assert "react" in res["imports"]
    
    symbols = {s["name"]: s for s in res["symbols"]}
    assert "UserStore" in symbols
    assert "fetchUser" in symbols

@pytest.mark.asyncio
async def test_ast_analyzer_api():
    from backend.ast_analyzer import ASTAnalyzer
    res = ASTAnalyzer.parse_python_file("backend/ast_analyzer.py")
    assert res["status"] == "success"
    assert "ASTAnalyzer" in [s["name"] for s in res["symbols"]]

