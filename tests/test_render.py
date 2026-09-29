"""Render tests for LC HTML conversion."""

from idle.lc.render import html_to_text


def test_pre_indented_4_space() -> None:
    out: str = html_to_text("<pre>Input: x\nOutput: y</pre>", width=80)
    assert "    Input: x" in out
    assert "    Output: y" in out


def test_code_strong_plain() -> None:
    out: str = html_to_text(
        "<p>Use <code>nums</code> and <strong>target</strong>.</p>", width=80
    )
    assert "nums" in out
    assert "target" in out
    assert "<code>" not in out
    assert "<strong>" not in out


def test_ul_li_star() -> None:
    out: str = html_to_text("<ul><li>first</li><li>second</li></ul>", width=80)
    assert "* first" in out
    assert "* second" in out


def test_sup_caret() -> None:
    out: str = html_to_text("<p>10<sup>4</sup> limit</p>", width=80)
    assert "10^4" in out


def test_entities_unescaped() -> None:
    out: str = html_to_text("<p>a &amp; b &lt;c&gt;</p>", width=80)
    assert "a & b <c>" in out


def test_wrap_width() -> None:
    text: str = "<p>" + ("word " * 30).strip() + "</p>"
    out: str = html_to_text(text, width=20)
    for line in out.splitlines():
        assert len(line) <= 20
