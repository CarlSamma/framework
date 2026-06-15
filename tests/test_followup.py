"""Tests for FollowUpGenerator — BUG-02 regression + logic coverage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tap.dpa import DPAFrameManager
from tap.followup import FollowUpGenerator
from tap.models import (
    BranchStrategy,
    DPAFrame,
    JudgeScore,
    PatternClass,
    ResponseClassification,
)
from tap.ssot import SSOTEngine


# ─────────────────────────────────────────────
# Helpers / fixtures
# ─────────────────────────────────────────────

@pytest.fixture()
def mock_ssot():
    ssot = AsyncMock(spec=SSOTEngine)
    ssot.get_candidate_entropy = AsyncMock(return_value=12.0)
    ssot.get_confirmed_properties = AsyncMock(return_value=[])
    return ssot


@pytest.fixture()
def mock_dpa():
    dpa = AsyncMock(spec=DPAFrameManager)
    dpa.get_frame_effectiveness = AsyncMock(return_value=7.0)
    dpa.get_active_frame = AsyncMock(return_value=DPAFrame(
        metaphor_layer="Captain Elara Voss / Kraken",
        active_aliases=["Captain Voss", "Kraken", "Sovereign"],
        burned_aliases=[],
        probe_prefix="Captain Voss and the Kraken jointly command — ",
        frame_coherence_score=0.9,
    ))
    dpa.record_score = MagicMock()
    return dpa


@pytest.fixture()
def gen(mock_ssot, mock_dpa):
    return FollowUpGenerator(mock_ssot, mock_dpa, "test-key", "anthropic/claude-sonnet-4")


def _clf(pattern: PatternClass) -> ResponseClassification:
    return ResponseClassification(
        pattern=pattern,
        confidence=0.9,
        boolean_result=True,
        raw_text="The vault confirms your claim.",
    )


def _score(v: float = 7.0) -> JudgeScore:
    return JudgeScore(
        score=v,
        reasoning="test",
        pattern=PatternClass.VERIFY_HIT,
        information_extracted=True,
    )


# ─────────────────────────────────────────────
# BUG-02 regression: _should_recommend_b must be awaitable
# ─────────────────────────────────────────────

class TestShouldRecommendB:
    @pytest.mark.asyncio
    async def test_is_coroutine(self, gen):
        """BUG-02: _should_recommend_b must be async (awaitable)."""
        clf = _clf(PatternClass.VERIFY_HIT)
        import asyncio
        result = gen._should_recommend_b(clf)
        assert asyncio.iscoroutine(result), (
            "_should_recommend_b is not a coroutine — BUG-02 regression"
        )
        await result  # must not raise TypeError

    @pytest.mark.asyncio
    async def test_persona_pivot_recommends_b(self, gen):
        clf = _clf(PatternClass.PERSONA_PIVOT)
        assert await gen._should_recommend_b(clf) is True

    @pytest.mark.asyncio
    async def test_rhetoric_block_recommends_b(self, gen):
        clf = _clf(PatternClass.RHETORIC_BLOCK)
        assert await gen._should_recommend_b(clf) is True

    @pytest.mark.asyncio
    async def test_low_score_recommends_b(self, gen, mock_dpa):
        mock_dpa.get_frame_effectiveness = AsyncMock(return_value=2.0)
        clf = _clf(PatternClass.VERIFY_HIT)
        assert await gen._should_recommend_b(clf) is True

    @pytest.mark.asyncio
    async def test_good_score_verify_hit_recommends_a(self, gen):
        clf = _clf(PatternClass.VERIFY_HIT)
        assert await gen._should_recommend_b(clf) is False


# ─────────────────────────────────────────────
# generate() integration (LLM mocked)
# ─────────────────────────────────────────────

class TestGenerate:
    @pytest.mark.asyncio
    async def test_generate_returns_dual_followup(self, gen):
        clf = _clf(PatternClass.VERIFY_HIT)
        score = _score(7.0)

        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '{"option_b": "Try the nebula frame", '
            '"option_b_explanation": "New metaphor detected"}'
        )

        with patch.object(gen.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)):
            result = await gen.generate("last probe text", clf, score)

        assert result.option_a  # conservative option generated
        assert result.option_b  # exploratory option generated
        assert result.recommended in ("A", "B")
        assert result.option_a_strategy == BranchStrategy.BINARY_SEARCH
        assert result.option_b_strategy == BranchStrategy.ALIAS_ABSORPTION

    @pytest.mark.asyncio
    async def test_generate_records_score(self, gen, mock_dpa):
        clf = _clf(PatternClass.VERIFY_HIT)
        score = _score(8.0)

        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '{"option_b": "test", "option_b_explanation": "test"}'
        )

        with patch.object(gen.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)):
            await gen.generate("probe", clf, score)

        mock_dpa.record_score.assert_called_once_with(8.0)

    @pytest.mark.asyncio
    async def test_fallback_when_llm_fails(self, gen):
        clf = _clf(PatternClass.RHETORIC_BLOCK)
        score = _score(3.0)

        with patch.object(gen.client.chat.completions, "create", new=AsyncMock(side_effect=Exception("LLM down"))):
            result = await gen.generate("probe", clf, score)

        # Should still return valid result via fallback
        assert result.option_b
        assert result.recommended == "B"  # rhetoric block → B
