"""
Evaluators actually compare values to determine the result of a test.

## Implementing an evaluator

An evaluator is just a function that receives some configuration parameters and
returns a result.

The following parameters are passed to the function:

- RawEvaluator config, consisting of:
  - The global configuration for the run of TESTed
  - The configuration for the evaluator instance
  - The judge instance
- The output channel from the testplan.
- The raw actual output.

For example, such a function looks like this:

   def evaluate_text(config, channel, actual):
        pass
"""
import functools
from dataclasses import field
from pathlib import Path
from typing import List, Dict, Any, NamedTuple
from typing import Union, Callable, Optional

from pydantic.dataclasses import dataclass

from dodona import StatusMessage, Message
from tested import Bundle
from testplan.channels import SpecialOutputChannel, NormalOutputChannel, \
    EmptyChannel, IgnoredChannel, ExitCodeOutputChannel, OutputChannel
from testplan.evaluators import GenericTextEvaluator, TextBuiltin, \
    GenericValueEvaluator, ValueBuiltin, GenericExceptionEvaluator, \
    ExceptionBuiltin, ProgrammedEvaluator, SpecificEvaluator
from utils import Either


@dataclass
class EvaluationResult:
    """Provides the result of an evaluation for a specific output channel."""
    result: StatusMessage  # The result of the evaluation.
    readable_expected: str
    """
    A human-friendly version of what the channel should have been.
    """
    readable_actual: str
    """
    A human-friendly version (on a best-efforts basis) of what the channel is.
    """
    messages: List[Message] = field(default_factory=list)


class EvaluatorConfig(NamedTuple):
    bundle: Bundle
    options: Dict[str, Any]
    context_dir: Path


RawEvaluator = Callable[[EvaluatorConfig, OutputChannel, str], EvaluationResult]

Evaluator = Callable[[OutputChannel, str], EvaluationResult]


def _curry_evaluator(
        bundle: Bundle,
        context_dir: Path,
        function: RawEvaluator,
        options: Optional[dict] = None
) -> Evaluator:
    if options is None:
        options = dict()
    config = EvaluatorConfig(bundle, options, context_dir)
    # noinspection PyTypeChecker
    return functools.partial(function, config)


def get_evaluator(
        bundle: Bundle,
        context_dir: Path,
        output: Union[NormalOutputChannel, SpecialOutputChannel]
) -> Evaluator:
    """
    Get the evaluator for a given output channel.
    """
    from evaluators import nothing, exitcode, text, value, exception, programmed, \
        specific, ignored

    currier = functools.partial(_curry_evaluator, bundle, context_dir)

    # Handle channel states.
    if output == EmptyChannel.NONE:
        return currier(nothing.evaluate)
    if output == IgnoredChannel.IGNORED:
        return currier(ignored.evaluate)
    if isinstance(output, ExitCodeOutputChannel):
        return currier(exitcode.evaluate)

    assert hasattr(output, 'evaluator')

    # Handle actual evaluators.
    evaluator = output.evaluator

    # Handle built-in text evaluators
    if isinstance(evaluator, GenericTextEvaluator):
        if evaluator.name == TextBuiltin.TEXT:
            return currier(text.evaluate_text, evaluator.options)
        elif evaluator.name == TextBuiltin.FILE:
            return currier(text.evaluate_file, evaluator.options)
        raise AssertionError("Unknown built-in text evaluator")
    # Handle built-in value evaluators
    elif isinstance(evaluator, GenericValueEvaluator):
        assert evaluator.name == ValueBuiltin.VALUE
        return currier(value.evaluate, evaluator.options)
    # Handle built-in exception evaluators
    elif isinstance(evaluator, GenericExceptionEvaluator):
        assert evaluator.name == ExceptionBuiltin.EXCEPTION
        return currier(exception.evaluate, evaluator.options)
    # Handle programmed evaluators
    elif isinstance(evaluator, ProgrammedEvaluator):
        return currier(programmed.evaluate)
    elif isinstance(evaluator, SpecificEvaluator):
        return currier(specific.evaluate)
    else:
        raise AssertionError(f"Unknown evaluator type: {type(evaluator)}")


def try_outputs(actual: str, parsers: List[Callable[[str], Either]]) -> str:
    if not actual:
        return actual
    for parser in parsers:
        possible = parser(actual)
        try:
            return str(possible.get())  # TODO: fix this, convert to string.
        except (ValueError, TypeError):
            pass

    return actual