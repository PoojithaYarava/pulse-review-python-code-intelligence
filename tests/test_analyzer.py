from app.analyzer import analyze


def test_valid_code_reports_pass_and_complexity():
    result = analyze("def find_max(values):\n    return max(values)\n")
    assert result["syntax"]["status"] == "pass"
    assert result["complexity"]["estimate"] == "O(1)"
    assert result["metrics"]["functions"] == 1


def test_nested_loops_report_quadratic_complexity():
    result = analyze("for left in values:\n    for right in values:\n        print(left, right)\n")
    assert result["complexity"]["estimate"] == "O(n²)"
    assert any(issue["category"] == "complexity" for issue in result["issues"])


def test_invalid_code_returns_syntax_issue():
    result = analyze("def broken(:\n    pass\n")
    assert result["syntax"]["status"] == "error"
    assert result["score"] == 0
    assert result["issues"][0]["severity"] == "critical"


def test_duplicate_logic_is_detected():
    code = """
def add(a, b):
    return a + b

def sum_values(x, y):
    return x + y
"""
    result = analyze(code)
    assert any(issue["category"] == "duplicate" for issue in result["issues"])
