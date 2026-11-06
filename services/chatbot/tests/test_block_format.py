import pytest

from app.workflow.answer import complete_block


@pytest.mark.parametrize('text',['```python\nx=1\n```','$$x^2$$','| A | B |\n|---|---|\n| 1 | 2 |'])
def test_complete_markdown(text):
    assert complete_block({'markdown':text}) == text

@pytest.mark.parametrize('text',['```python\nx=1','$$x',''])
def test_incomplete_block_rejected(text):
    with pytest.raises(ValueError): complete_block({'markdown':text})

@pytest.mark.parametrize('text',['$x','```python\nx=1\n~~~','| A | B |\n|---|---|'])
def test_partial_inline_math_fence_or_table_rejected(text):
    with pytest.raises(ValueError): complete_block({'markdown':text})
