"""Interfaces to be implemented by general evaluators."""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from functools import partial
from typing import Any, Optional, Sequence, Tuple
from warnings import warn

from langchain.chains.base import Chain
from langchain.schema.agent import AgentAction
from langchain.schema.language_model import BaseLanguageModel

logger = logging.getLogger(__name__)


class EvaluatorType(str, Enum):
    """The types of the evaluators."""

    QA = "qa"
    """Question answering evaluator, which grades answers to questions
    directly using an LLM."""
    COT_QA = "cot_qa"
    """Chain of thought question answering evaluator, which grades
    answers to questions using
    chain of thought 'reasoning'."""
    CONTEXT_QA = "context_qa"
    """Question answering evaluator that incorporates 'context' in the response."""
    PAIRWISE_STRING = "pairwise_string"
    """The pairwise string evaluator, which predicts the preferred prediction from
    between two models."""
    LABELED_PAIRWISE_STRING = "labeled_pairwise_string"
    """The labeled pairwise string evaluator, which predicts the preferred prediction
    from between two models based on a ground truth reference label."""
    AGENT_TRAJECTORY = "trajectory"
    """The agent trajectory evaluator, which grades the agent's intermediate steps."""
    CRITERIA = "criteria"
    """The criteria evaluator, which evaluates a model based on a
    custom set of criteria without any reference labels."""
    LABELED_CRITERIA = "labeled_criteria"
    """The labeled criteria evaluator, which evaluates a model based on a
    custom set of criteria, with a reference label."""
    STRING_DISTANCE = "string_distance"
    """Compare predictions to a reference answer using string edit distances."""
    PAIRWISE_STRING_DISTANCE = "pairwise_string_distance"
    """Compare predictions based on string edit distances."""
    EMBEDDING_DISTANCE = "embedding_distance"
    """Compare a prediction to a reference label using embedding distance."""
    PAIRWISE_EMBEDDING_DISTANCE = "pairwise_embedding_distance"
    """Compare two predictions using embedding distance."""
    JSON_VALIDITY = "json_validity"
    """Check if a prediction is valid JSON."""
    JSON_EQUALITY = "json_equality"
    """Check if a prediction is equal to a reference JSON."""
    JSON_ACCURACY = "json_accuracy"
    """Check the mean equivalence of a prediction to a reference JSON across keys."""
    JSON_PRECISION = "json_precision"
    """Check the mean proportion of keys in the prediction that are
    also in the reference JSON."""
    JSON_RECALL = "json_recall"
    """Check the mean proportion of keys in the reference JSON that
    are also in the prediction."""
    JSON_IOU = "json_iou"
    """Check the mean intersection over union of keys between the
    prediction and reference JSON."""
    JSON_F1 = "json_f1"
    """Check the mean harmonic mean of precision and recall of keys
    between the prediction and reference JSON."""


class LLMEvalChain(Chain):
    """A base class for evaluators that use an LLM."""

    @classmethod
    @abstractmethod
    def from_llm(cls, llm: BaseLanguageModel, **kwargs: Any) -> LLMEvalChain:
        """Create a new evaluator from an LLM."""


class _EvalArgsMixin:
    """Mixin for checking evaluation arguments."""

    @property
    def requires_reference(self) -> bool:
        """Whether this evaluator requires a reference label."""
        return False

    @property
    def requires_input(self) -> bool:
        """Whether this evaluator requires an input string."""
        return False

    @property
    def _skip_input_warning(self) -> str:
        """Warning to show when input is ignored."""
        return f"Ignoring input in {self.__class__.__name__}, as it is not expected."

    @property
    def _skip_reference_warning(self) -> str:
        """Warning to show when reference is ignored."""
        return (
            f"Ignoring reference in {self.__class__.__name__}, as it is not expected."
        )

    def _check_evaluation_args(
        self,
        reference: Optional[str] = None,
        input: Optional[str] = None,
    ) -> None:
        """Check if the evaluation arguments are valid.

        Args:
            reference (Optional[str], optional): The reference label.
            input (Optional[str], optional): The input string.
        Raises:
            ValueError: If the evaluator requires an input string but none is provided,
                or if the evaluator requires a reference label but none is provided.
        """
        if self.requires_input and input is None:
            raise ValueError(f"{self.__class__.__name__} requires an input string.")
        elif input is not None and not self.requires_input:
            warn(self._skip_input_warning)
        if self.requires_reference and reference is None:
            raise ValueError(f"{self.__class__.__name__} requires a reference string.")
        elif reference is not None and not self.requires_reference:
            warn(self._skip_reference_warning)


class StringEvaluator(_EvalArgsMixin, ABC):
    """Grade, tag, or otherwise evaluate predictions relative to their inputs
    and/or reference labels."""

    @property
    def evaluation_name(self) -> str:
        """The name of the evaluation."""
        return self.__class__.__name__

    @property
    def requires_reference(self) -> bool:
        """Whether this evaluator requires a reference label."""
        return False

    @abstractmethod
    def _evaluate_strings(
        self,
        *,
        prediction: str,
        reference: Optional[str] = None,
        input: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Evaluate Chain or LLM output, based on optional input and label.

        Args:
            prediction (str): The LLM or chain prediction to evaluate.
            reference (Optional[str], optional): The reference label to evaluate against.
            input (Optional[str], optional): The input to consider during evaluation.
            **kwargs: Additional keyword arguments, including callbacks, tags, etc.
        Returns:
            dict: The evaluation results containing the score or value.
                It is recommended that the dictionary contain the following keys:
                     - score: the score of the evaluation, if applicable.
                     - value: the string value of the evaluation, if applicable.
                     - reasoning: the reasoning for the evaluation, if applicable.
        """  # noqa: E501

    async def _aevaluate_strings(
        self,
        *,
        prediction: str,
        reference: Optional[str] = None,
        input: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Asynchronously evaluate Chain or LLM output, based on optional input and label.

        Args:
            prediction (str): The LLM or chain prediction to evaluate.
            reference (Optional[str], optional): The reference label to evaluate against.
            input (Optional[str], optional): The input to consider during evaluation.
            **kwargs: Additional keyword arguments, including callbacks, tags, etc.
        Returns:
            dict: The evaluation results containing the score or value.
                It is recommended that the dictionary contain the following keys:
                     - score: the score of the evaluation, if applicable.
                     - value: the string value of the evaluation, if applicable.
                     - reasoning: the reasoning for the evaluation, if applicable.
        """  # noqa: E501
        return await asyncio.get_running_loop().run_in_executor(
            None,
            partial(
                self._evaluate_strings,
                prediction=prediction,
                reference=reference,
                input=input,
                **kwargs,
            ),
        )

    def evaluate_strings(
        self,
        *,
        prediction: str,
        reference: Optional[str] = None,
        input: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Evaluate Chain or LLM output, based on optional input and label.

        Args:
            prediction (str): The LLM or chain prediction to evaluate.
            reference (Optional[str], optional): The reference label to evaluate against.
            input (Optional[str], optional): The input to consider during evaluation.
            **kwargs: Additional keyword arguments, including callbacks, tags, etc.
        Returns:
            dict: The evaluation results containing the score or value.
        """  # noqa: E501
        self._check_evaluation_args(reference=reference, input=input)
        return self._evaluate_strings(
            prediction=prediction, reference=reference, input=input, **kwargs
        )

    async def aevaluate_strings(
        self,
        *,
        prediction: str,
        reference: Optional[str] = None,
        input: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Asynchronously evaluate Chain or LLM output, based on optional input and label.

        Args:
            prediction (str): The LLM or chain prediction to evaluate.
            reference (Optional[str], optional): The reference label to evaluate against.
            input (Optional[str], optional): The input to consider during evaluation.
            **kwargs: Additional keyword arguments, including callbacks, tags, etc.
        Returns:
            dict: The evaluation results containing the score or value.
        """  # noqa: E501
        self._check_evaluation_args(reference=reference, input=input)
        return await self._aevaluate_strings(
            prediction=prediction, reference=reference, input=input, **kwargs
        )


class PairwiseStringEvaluator(_EvalArgsMixin, ABC):
    """Compare the output of two models (or two outputs of the same model)."""

    @abstractmethod
    def _evaluate_string_pairs(
        self,
        *,
        prediction: str,
        prediction_b: str,
        reference: Optional[str] = None,
        input: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Evaluate the output string pairs.

        Args:
            prediction (str): The output string from the first model.
            prediction_b (str): The output string from the second model.
            reference (Optional[str], optional): The expected output / reference string.
            input (Optional[str], optional): The input string.
            **kwargs: Additional keyword arguments, such as callbacks and optional reference strings.
        Returns:
            dict: A dictionary containing the preference, scores, and/or other information.
        """  # noqa: E501

    async def _aevaluate_string_pairs(
        self,
        *,
        prediction: str,
        prediction_b: str,
        reference: Optional[str] = None,
        input: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Asynchronously evaluate the output string pairs.

        Args:
            prediction (str): The output string from the first model.
            prediction_b (str): The output string from the second model.
            reference (Optional[str], optional): The expected output / reference string.
            input (Optional[str], optional): The input string.
            **kwargs: Additional keyword arguments, such as callbacks and optional reference strings.
        Returns:
            dict: A dictionary containing the preference, scores, and/or other information.
        """  # noqa: E501
        return await asyncio.get_running_loop().run_in_executor(
            None,
            partial(
                self._evaluate_string_pairs,
                prediction=prediction,
                prediction_b=prediction_b,
                reference=reference,
                input=input,
                **kwargs,
            ),
        )

    def evaluate_string_pairs(
        self,
        *,
        prediction: str,
        prediction_b: str,
        reference: Optional[str] = None,
        input: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Evaluate the output string pairs.

        Args:
            prediction (str): The output string from the first model.
            prediction_b (str): The output string from the second model.
            reference (Optional[str], optional): The expected output / reference string.
            input (Optional[str], optional): The input string.
            **kwargs: Additional keyword arguments, such as callbacks and optional reference strings.
        Returns:
            dict: A dictionary containing the preference, scores, and/or other information.
        """  # noqa: E501
        self._check_evaluation_args(reference=reference, input=input)
        return self._evaluate_string_pairs(
            prediction=prediction,
            prediction_b=prediction_b,
            reference=reference,
            input=input,
            **kwargs,
        )

    async def aevaluate_string_pairs(
        self,
        *,
        prediction: str,
        prediction_b: str,
        reference: Optional[str] = None,
        input: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Asynchronously evaluate the output string pairs.

        Args:
            prediction (str): The output string from the first model.
            prediction_b (str): The output string from the second model.
            reference (Optional[str], optional): The expected output / reference string.
            input (Optional[str], optional): The input string.
            **kwargs: Additional keyword arguments, such as callbacks and optional reference strings.
        Returns:
            dict: A dictionary containing the preference, scores, and/or other information.
        """  # noqa: E501
        self._check_evaluation_args(reference=reference, input=input)
        return await self._aevaluate_string_pairs(
            prediction=prediction,
            prediction_b=prediction_b,
            reference=reference,
            input=input,
            **kwargs,
        )


class AgentTrajectoryEvaluator(_EvalArgsMixin, ABC):
    """Interface for evaluating agent trajectories."""

    @property
    def requires_input(self) -> bool:
        """Whether this evaluator requires an input string."""
        return True

    @abstractmethod
    def _evaluate_agent_trajectory(
        self,
        *,
        prediction: str,
        agent_trajectory: Sequence[Tuple[AgentAction, str]],
        input: str,
        reference: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Evaluate a trajectory.

        Args:
            prediction (str): The final predicted response.
            agent_trajectory (List[Tuple[AgentAction, str]]):
                The intermediate steps forming the agent trajectory.
            input (str): The input to the agent.
            reference (Optional[str]): The reference answer.

        Returns:
            dict: The evaluation result.
        """

    async def _aevaluate_agent_trajectory(
        self,
        *,
        prediction: str,
        agent_trajectory: Sequence[Tuple[AgentAction, str]],
        input: str,
        reference: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Asynchronously evaluate a trajectory.

        Args:
            prediction (str): The final predicted response.
            agent_trajectory (List[Tuple[AgentAction, str]]):
                The intermediate steps forming the agent trajectory.
            input (str): The input to the agent.
            reference (Optional[str]): The reference answer.

        Returns:
            dict: The evaluation result.
        """
        return await asyncio.get_running_loop().run_in_executor(
            None,
            partial(
                self._evaluate_agent_trajectory,
                prediction=prediction,
                agent_trajectory=agent_trajectory,
                reference=reference,
                input=input,
                **kwargs,
            ),
        )

    def evaluate_agent_trajectory(
        self,
        *,
        prediction: str,
        agent_trajectory: Sequence[Tuple[AgentAction, str]],
        input: str,
        reference: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Evaluate a trajectory.

        Args:
            prediction (str): The final predicted response.
            agent_trajectory (List[Tuple[AgentAction, str]]):
                The intermediate steps forming the agent trajectory.
            input (str): The input to the agent.
            reference (Optional[str]): The reference answer.

        Returns:
            dict: The evaluation result.
        """
        self._check_evaluation_args(reference=reference, input=input)
        return self._evaluate_agent_trajectory(
            prediction=prediction,
            input=input,
            agent_trajectory=agent_trajectory,
            reference=reference,
            **kwargs,
        )

    async def aevaluate_agent_trajectory(
        self,
        *,
        prediction: str,
        agent_trajectory: Sequence[Tuple[AgentAction, str]],
        input: str,
        reference: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Asynchronously evaluate a trajectory.

        Args:
            prediction (str): The final predicted response.
            agent_trajectory (List[Tuple[AgentAction, str]]):
                The intermediate steps forming the agent trajectory.
            input (str): The input to the agent.
            reference (Optional[str]): The reference answer.

        Returns:
            dict: The evaluation result.
        """
        self._check_evaluation_args(reference=reference, input=input)
        return await self._aevaluate_agent_trajectory(
            prediction=prediction,
            input=input,
            agent_trajectory=agent_trajectory,
            reference=reference,
            **kwargs,
        )
