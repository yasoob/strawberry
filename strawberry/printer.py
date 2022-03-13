from __future__ import annotations

import dataclasses
from itertools import chain
from typing import TYPE_CHECKING, Any, Dict, Iterable, Mapping, Optional, cast

from graphql.language.printer import print_ast
from graphql.type import (
    is_enum_type,
    is_input_type,
    is_object_type,
    is_scalar_type,
    is_specified_directive,
)
from graphql.type.directives import GraphQLDirective
from graphql.utilities.ast_from_value import ast_from_value
from graphql.utilities.print_schema import (
    is_defined_type,
    print_args,
    print_block,
    print_deprecated,
    print_description,
    print_directive,
    print_enum,
    print_implemented_interfaces,
    print_input_value,
    print_scalar,
    print_schema_definition,
    print_type as original_print_type,
)

from strawberry.arguments import is_unset
from strawberry.field import StrawberryField
from strawberry.schema.schema_converter import GraphQLCoreConverter
from strawberry.schema_directive import Location, StrawberrySchemaDirective
from strawberry.types.types import TypeDefinition


if TYPE_CHECKING:
    from strawberry.schema import BaseSchema


def _serialize_dataclass(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, Iterable):
        return [_serialize_dataclass(v) for v in value]
    if isinstance(value, Mapping):
        return {k: _serialize_dataclass(v) for k, v in value.items()}

    return value


def print_schema_directive_params(
    directive: GraphQLDirective, values: Dict[str, Any]
) -> str:
    params = []
    for name, arg in directive.args.items():
        value = values.get(name, arg.default_value)
        if is_unset(arg):
            value = None
        else:
            ast = ast_from_value(value, arg.type)
            value = ast and f"{name}: {print_ast(ast)}"

        if value:
            params.append(value)

    if not params:
        return ""

    return "(" + ", ".join(params) + ")"


def print_schema_directive(
    directive: StrawberrySchemaDirective, schema: BaseSchema
) -> str:
    from strawberry.schema.schema import Schema

    if isinstance(schema, Schema):
        schema_converter = schema.schema_converter
    else:
        schema_converter = GraphQLCoreConverter(schema.config, {})

    gql_directive = schema_converter.from_schema_directive(directive)
    params = print_schema_directive_params(
        gql_directive,
        _serialize_dataclass(directive.instance),
    )

    return f" @{gql_directive.name}{params}"


def print_field_directives(field: Optional[StrawberryField], schema: BaseSchema) -> str:
    if not field:
        return ""

    directives = (
        directive
        for directive in field.directives
        if any(
            location in [Location.FIELD_DEFINITION, Location.INPUT_FIELD_DEFINITION]
            for location in directive.locations
        )
    )

    return "".join(
        (print_schema_directive(directive, schema=schema) for directive in directives)
    )


def print_fields(type_, schema: BaseSchema) -> str:
    strawberry_type = cast(TypeDefinition, schema.get_type_by_name(type_.name))

    fields = []

    for i, (name, field) in enumerate(type_.fields.items()):
        python_name = field.extensions and field.extensions.get("python_name")

        strawberry_field = (
            strawberry_type.get_field(python_name)
            if strawberry_type and python_name
            else None
        )

        args = print_args(field.args, "  ") if hasattr(field, "args") else ""

        fields.append(
            print_description(field, "  ", not i)
            + f"  {name}"
            + args
            + f": {field.type}"
            + print_field_directives(strawberry_field, schema=schema)
            + print_deprecated(field.deprecation_reason)
        )

    return print_block(fields)


def print_extends(type_, schema: BaseSchema):
    strawberry_type = cast(TypeDefinition, schema.get_type_by_name(type_.name))

    if strawberry_type and strawberry_type.extend:
        return "extend "

    return ""


def print_type_directives(type_, schema: BaseSchema) -> str:
    strawberry_type = cast(TypeDefinition, schema.get_type_by_name(type_.name))

    if not strawberry_type:
        return ""

    allowed_locations = (
        [Location.INPUT_OBJECT] if strawberry_type.is_input else [Location.OBJECT]
    )

    directives = (
        directive
        for directive in strawberry_type.directives or []
        if any(location in allowed_locations for location in directive.locations)
    )

    return "".join(
        (print_schema_directive(directive, schema=schema) for directive in directives)
    )


def _print_object(type_, schema: BaseSchema) -> str:
    return (
        print_description(type_)
        + print_extends(type_, schema)
        + f"type {type_.name}"
        + print_implemented_interfaces(type_)
        + print_type_directives(type_, schema)
        + print_fields(type_, schema)
    )


def _print_input_object(type_, schema: BaseSchema) -> str:
    fields = [
        print_description(field, "  ", not i) + "  " + print_input_value(name, field)
        for i, (name, field) in enumerate(type_.fields.items())
    ]
    return (
        print_description(type_)
        + f"input {type_.name}"
        + print_type_directives(type_, schema)
        + print_block(fields)
    )


def _print_type(type_, schema: BaseSchema) -> str:
    # prevents us from trying to print a scalar as an input type
    if is_scalar_type(type_):
        return print_scalar(type_)

    if is_enum_type(type_):
        return print_enum(type_)

    if is_object_type(type_):
        return _print_object(type_, schema)

    if is_input_type(type_):
        return _print_input_object(type_, schema)

    return original_print_type(type_)


def print_schema(schema: BaseSchema) -> str:
    graphql_core_schema = schema._schema  # type: ignore

    directives = filter(
        lambda n: not is_specified_directive(n), graphql_core_schema.directives
    )
    type_map = graphql_core_schema.type_map

    types = filter(is_defined_type, map(type_map.get, sorted(type_map)))

    return "\n\n".join(
        chain(
            filter(None, [print_schema_definition(graphql_core_schema)]),
            (print_directive(directive) for directive in directives),
            (_print_type(type_, schema) for type_ in types),
        )
    )
