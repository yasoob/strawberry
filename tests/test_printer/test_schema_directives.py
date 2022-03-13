import textwrap
from typing import List, Optional

import strawberry
from strawberry.arguments import UNSET
from strawberry.printer import print_schema
from strawberry.schema_directive import Location


def test_print_simple_directive():
    @strawberry.schema_directive(locations=[Location.FIELD_DEFINITION])
    class Sensitive:
        reason: str

    @strawberry.type
    class Query:
        first_name: str = strawberry.field(directives=[Sensitive(reason="GDPR")])

    expected_type = """
    type Query {
      firstName: String! @sensitive(reason: "GDPR")
    }
    """

    schema = strawberry.Schema(query=Query)

    assert print_schema(schema) == textwrap.dedent(expected_type).strip()


def test_print_directive_with_name():
    @strawberry.schema_directive(locations=[Location.FIELD_DEFINITION])
    class SensitiveField:
        reason: str

    @strawberry.type
    class Query:
        first_name: str = strawberry.field(directives=[SensitiveField(reason="GDPR")])

    expected_type = """
    type Query {
      firstName: String! @sensitiveField(reason: "GDPR")
    }
    """

    schema = strawberry.Schema(query=Query)

    assert print_schema(schema) == textwrap.dedent(expected_type).strip()


def test_directive_on_types():
    @strawberry.input
    class SensitiveValue:
        key: str
        value: str

    @strawberry.schema_directive(locations=[Location.OBJECT, Location.FIELD_DEFINITION])
    class SensitiveData:
        reason: str
        meta: Optional[List[SensitiveValue]] = UNSET

    @strawberry.schema_directive(locations=[Location.INPUT_OBJECT])
    class SensitiveInput:
        reason: str
        meta: Optional[List[SensitiveValue]] = UNSET

    @strawberry.input(directives=[SensitiveInput(reason="GDPR")])
    class Input:
        first_name: str

    @strawberry.type(directives=[SensitiveData(reason="GDPR")])
    class User:
        first_name: str
        phone: str = strawberry.field(
            directives=[
                SensitiveData(
                    reason="PRIVATE",
                    meta=[
                        SensitiveValue(
                            key="can_share_field", value="phone_share_accepted"
                        )
                    ],
                )
            ]
        )
        phone_share_accepted: bool

    @strawberry.type
    class Query:
        @strawberry.field
        def user(self, input: Input) -> User:
            return User(
                first_name=input.first_name,
                phone="+551191551234",
                phone_share_accepted=False,
            )

    expected_type = """
    input Input @sensitiveInput(reason: "GDPR") {
      firstName: String!
    }

    type Query {
      user(input: Input!): User!
    }

    type User @sensitiveData(reason: "GDPR") {
      firstName: String!
      phone: String! @sensitiveData(reason: "PRIVATE", meta: [{key: "can_share_field", value: "phone_share_accepted"}])
      phoneShareAccepted: Boolean!
    }
    """  # noqa:E501

    schema = strawberry.Schema(query=Query)

    assert print_schema(schema) == textwrap.dedent(expected_type).strip()
