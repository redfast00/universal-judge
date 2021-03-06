"""
Evaluators for text.
"""
from typing import Optional, Dict, Any

import math

from . import EvaluationResult, EvaluatorConfig
from ..dodona import StatusMessage, Status
from ..testplan import TextOutputChannel, FileOutputChannel, OutputChannel


def _is_number(string: str) -> Optional[float]:
    try:
        return float(string)
    except ValueError:
        return None


def _text_options(config: EvaluatorConfig) -> dict:
    defaults = {
        # Options for textual comparison
        'ignoreWhitespace': True,
        'caseInsensitive':  False,
        # Options for numerical comparison
        'tryFloatingPoint': False,
        'applyRounding':    False,
        'roundTo':          3
    }
    defaults.update(config.options)
    return defaults


def _file_defaults(config: EvaluatorConfig) -> dict:
    defaults = {
        "mode": "exact"
    }
    defaults.update(config.options)
    if defaults["mode"] not in {"exact", "lines", "values"}:
        raise ValueError(f"Unknown mode for file evaluator: {defaults['mode']}")
    return defaults


def compare_text(
        options: Dict[str, Any],
        expected: str,
        actual: str) -> EvaluationResult:
    if options['ignoreWhitespace']:
        expected = expected.strip()
        actual = actual.strip()

    if options['caseInsensitive']:
        expected = expected.lower()
        actual = actual.lower()

    if options['tryFloatingPoint'] and (actual_float := _is_number(actual)):
        expected_float = float(expected)
        if options['applyRounding']:
            numbers = int(options['roundTo'])
            # noinspection PyUnboundLocalVariable
            actual_float = round(actual_float, numbers)
            expected_float = round(expected_float, numbers)
        # noinspection PyUnboundLocalVariable
        result = math.isclose(actual_float, expected_float)
        expected = str(expected_float)
        actual = str(actual_float)
    else:
        result = actual == expected

    return EvaluationResult(
        result=StatusMessage(enum=Status.CORRECT if result else Status.WRONG),
        readable_expected=str(expected),
        readable_actual=str(actual)
    )


def evaluate_text(
        config: EvaluatorConfig,
        channel: OutputChannel,
        actual: str) -> EvaluationResult:
    """
    The base evaluator, used to compare two strings. As this evaluator is
    intended for evaluating stdout, it supports various options to make life
    easier:

    - ``ignoreWhitespace``: whitespace before and after will be stripped
    - ``caseInsensitive``: all comparisons will be in lower-case
    - ``tryFloatingPoint``: try to evaluate_text the value as a floating-point
    - ``applyRounding``: limit floating points to ``roundTo`` numbers
    - ``roundTo``: amount of numbers to round to.

    Note: floating points inside other texts are currently not supported.
    """
    assert isinstance(channel, TextOutputChannel)
    options = _text_options(config)
    expected = channel.get_data_as_string(config.bundle.config.resources)
    return compare_text(options, expected, actual)


def evaluate_file(config: EvaluatorConfig,
                  channel: FileOutputChannel,
                  actual: str) -> EvaluationResult:
    """
    Evaluate the contents of two files. The file evaluator supports one option,
    ``mode``, used to define in which mode the evaluator should operate:

    1. ``full``: The complete contents are passed to the :class:`TextEvaluator`.
    2. ``line``: The file is split by lines and each line is compared to the
       corresponding line with the :class:`TextEvaluator`. The lines are compared
       without newlines.

    Since the text evaluator is used behind the scenes, this evaluator also supports
    all parameters of that evaluator.

    When no mode is passed, the evaluator will default to ``full``.
    """
    assert isinstance(channel, FileOutputChannel)
    options = _text_options(config)

    # There must be nothing as output.
    if actual:
        message = f"Verwachtte geen uitvoer voor kanaal, maar vond {actual}."
        return EvaluationResult(
            result=StatusMessage(
                enum=Status.WRONG,
                human="Onverwachte uitvoer."
            ),
            readable_expected="",
            readable_actual=actual,
            messages=[message]
        )

    expected_path = f"{config.bundle.config.resources}/{channel.expected_path}"

    try:
        with open(expected_path, "r") as file:
            expected = file.read()
    except FileNotFoundError:
        raise ValueError(f"File {expected_path} not found in resources.")

    actual_path = config.context_dir / channel.actual_path

    try:
        with open(str(actual_path), "r") as file:
            actual = file.read()
    except FileNotFoundError:
        return EvaluationResult(
            result=StatusMessage(
                enum=Status.RUNTIME_ERROR,
                human="Bestand niet gevonden."
            ),
            readable_expected=expected,
            readable_actual="",
        )

    if options["mode"] == "full":
        return compare_text(options, expected, actual)
    else:
        assert options["mode"] == "line"
        strip_newlines = options.get("stripNewlines", False)
        expected_lines = expected.splitlines(keepends=not strip_newlines)
        actual_lines = actual.splitlines(keepends=not strip_newlines)
        correct = len(actual_lines) == len(expected_lines)
        for (expected_line, actual_line) in zip(expected_lines, actual_lines):
            r = compare_text(options, expected_line, actual_line)
            correct = correct and r.result.enum == Status.CORRECT
        return EvaluationResult(
            result=StatusMessage(enum=Status.CORRECT if correct else Status.WRONG),
            readable_expected=expected,
            readable_actual=actual
        )
