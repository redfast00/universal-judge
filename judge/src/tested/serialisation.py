"""
The serialization format.

This is the authoritative source of the format. For example, json-schema is
generated from this code.

This module does not concern itself with actual decoding or encoding; it is purely
concerned about the format itself and parsing of the format itself (some might expression
this the meta-concerns).

The encoding and decoding of instances of values in this format are done in the
language implementations itself.

A json-schema can be generated from this format by executing the module on the
command line. The schema will be printed to stdout. This can be used to generate
classes for implementations in other config.
"""
import json
import logging
from dataclasses import field
from decimal import Decimal
from typing import Union, List, Dict, Literal, Optional, Any, get_args

import math
from pydantic import BaseModel
from pydantic.dataclasses import dataclass

from tested.features import FeatureSet, Constructs, combine_features, WithFeatures
from datatypes import NumericTypes, StringTypes, BooleanTypes, \
    SequenceTypes, ObjectTypes, NothingTypes, SimpleTypes, resolve_to_basic

logger = logging.getLogger(__name__)


class SerialisationError(ValueError):
    def __init__(self, message, additional_errors=None):
        ValueError.__init__(self, message)
        self.additional_errors = additional_errors or []

    def __str__(self):
        original = super().__str__()
        additional_lines = "\n".join(
            f"* {error}" for error in self.additional_errors)
        return f"{original}\nAdditional errors:\n {additional_lines}"


@dataclass
class NumberType(WithFeatures):
    type: NumericTypes
    data: Union[int, Decimal]

    def get_used_features(self) -> FeatureSet:
        return FeatureSet(Constructs.NOTHING, {self.type})


@dataclass
class StringType(WithFeatures):
    type: StringTypes
    data: str

    def get_used_features(self) -> FeatureSet:
        return FeatureSet(Constructs.NOTHING, {self.type})


@dataclass
class BooleanType(WithFeatures):
    type: BooleanTypes
    data: bool

    def get_used_features(self) -> FeatureSet:
        return FeatureSet(Constructs.NOTHING, {self.type})


@dataclass
class SequenceType(WithFeatures):
    type: SequenceTypes
    data: List['Value']

    def get_used_features(self) -> FeatureSet:
        base_features = FeatureSet(Constructs.NOTHING, {self.type})
        nested_features = [x.get_used_features() for x in self.data]
        return combine_features([base_features] + nested_features)


@dataclass
class ObjectType(WithFeatures):
    type: ObjectTypes
    data: Dict[str, 'Value']

    def get_used_features(self) -> FeatureSet:
        base_features = FeatureSet(Constructs.NOTHING, {self.type})
        nested_features = [y.get_used_features() for x, y in self.data]
        return combine_features([base_features] + nested_features)


@dataclass
class NothingType(WithFeatures):
    type: NothingTypes
    data: Literal[None] = None

    def get_used_features(self) -> FeatureSet:
        return FeatureSet(Constructs.NOTHING, {self.type})


# A value is one of the preceding types.
Value = Union[
    NumberType, StringType, BooleanType, SequenceType, ObjectType, NothingType
]


# Update the forward references, which fixes the schema generation.
ObjectType.__pydantic_model__.update_forward_refs()
SequenceType.__pydantic_model__.update_forward_refs()


class _SerialisationSchema(BaseModel):
    """The schema for serialising data."""
    __root__: Value


def generate_schema():
    """
    Generate a json schema for the serialisation type. It will be printed on stdout.
    """
    sc = _SerialisationSchema.schema()
    sc['$id'] = "universal-judge/serialisation"
    sc['$schema'] = "http://json-schema.org/schema#"
    print(json.dumps(sc, indent=2))


def parse_value(value: str) -> Value:
    """
    Parse the json of a value into the relevant data structures.

    If ``value`` is not valid json, a :class:`SerialisationError` will be thrown.

    :param value: The json to be parsed.
    :return: The parsed data.
    """
    try:
        parsed_json = json.loads(value)
    except Exception as e:
        raise ValueError(f"Could not parse {value} as valid json.", e)

    # We try each value until we find one that works, or we throw an error.
    errors = []
    for clazz in get_args(Value):
        try:
            return clazz(**parsed_json)
        except (TypeError, ValueError) as e:
            errors.append(e)

    logger.warning(f"Could not parse value, errors are {errors}")

    raise TypeError(
        f"Could not find valid type for {value}."
    )


class PrintingDecimal:

    def __init__(self, decimal: Decimal):
        self.decimal = decimal

    def __repr__(self):
        return str(self.decimal)


def _convert_to_python(value: Optional[Value], for_printing=False) -> Any:
    """
    Convert the parsed values into the proper Python type. This is basically
    the same as de-serialising a value, but this function is currently not re-used
    in the Python implementation, since run-time de-serialisation is not supported.
    :param value: The parsed value.
    :param for_printing: If the result will be used for printing or not.
    :return: The Python value.
    """
    if value is None:
        return None

    # If we have a type for which the data is usable in Python, use it.
    if isinstance(value.type, get_args(SimpleTypes)):
        # If we have floats or ints, convert them to Python.
        if value.type in (NumericTypes.SINGLE_PRECISION,
                          NumericTypes.DOUBLE_PRECISION):
            return float(str(value.data))
        if value.type != NumericTypes.FIXED_PRECISION:
            return int(str(value.data))
        if for_printing:
            return PrintingDecimal(value.data)

        return value.data

    if isinstance(value.type, get_args(SequenceTypes)):
        values = [_convert_to_python(x) for x in value.data]
        basic_type = resolve_to_basic(value.type)
        if basic_type == SequenceTypes.SEQUENCE:
            return values
        if basic_type == SequenceTypes.SET:
            return set(values)
        raise AssertionError(f"Unknown basic sequence type {basic_type}.")

    if isinstance(value.type, get_args(ObjectTypes)):
        values = {x: _convert_to_python(y) for x, y in value.data.items()}
        return values

    if isinstance(value, NothingType):
        return None

    # Unknown type.
    logger.warning(f"Unknown data type {value.type} will be interpreted as string.")
    return str(value.data)


def get_readable_representation(value: Value):
    """
    Get a readable representation of the data. In many cases, this is just the
    Python type that will be returned as a string.
    """
    return repr(_convert_to_python(value, True))


class ComparableFloat:

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        # noinspection PyBroadException
        try:
            return math.isclose(self.value, other.value)
        except Exception:
            return False

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return repr(self.value)

    def __bool__(self):
        return bool(self.value)


def to_python_comparable(value: Optional[Value]):
    """
    Convert the value into a comparable Python value. Most values are just
    converted to their
    builtin Python variant. Some, however, are not: floats are converted into a
    wrapper class, that
    allows comparison.

    Note that this means that the types in the return value can be different from
    what is channel;
    the returning types are only guaranteed to support eq, str, repr and bool.
    """
    basic_type = resolve_to_basic(value.type)
    if value is None:
        return None
    if basic_type == SequenceTypes.SEQUENCE:
        return [to_python_comparable(x) for x in value.data]
    if basic_type == SequenceTypes.SET:
        return {to_python_comparable(x) for x in value.data}
    if basic_type == ObjectTypes.MAP:
        return {key: to_python_comparable(val) for key, val in value.data.items()}
    if basic_type == NumericTypes.RATIONAL:
        return ComparableFloat(float(value.data))
    if basic_type == NumericTypes.INTEGER:
        return value.data
    if basic_type in (BooleanTypes.BOOLEAN, StringTypes.TEXT, NothingTypes.NOTHING,
                      StringTypes.UNKNOWN):
        return value.data

    raise AssertionError(f"Unknown value type: {value}")


@dataclass
class SpecificResult:
    """Result of an evaluation by a language specific evaluator."""
    result: bool  # The result of the evaluation.
    readable_expected: Optional[str] = None
    # A human-friendly version of what the channel should have
    # been.
    readable_actual: Optional[str] = None
    # A human-friendly version (best effort at least) of what
    # the channel is.
    messages: List[str] = field(default_factory=list)


@dataclass
class ExceptionValue(WithFeatures):
    """An exception that was thrown while executing the user context."""
    message: str
    stacktrace: str

    def get_used_features(self) -> FeatureSet:
        return FeatureSet(Constructs.EXCEPTIONS, types=set())

    def readable(self) -> str:
        return f"Fout met boodschap: {self.message}\n{self.stacktrace}"


if __name__ == '__main__':
    generate_schema()