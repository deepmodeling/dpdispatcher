"""Generate JSON schema from a given dargs.Argument."""

from __future__ import annotations

from typing import Any

from dargs.dargs import Argument, _Flags

try:
    from typing import get_origin
except ImportError:
    from typing_extensions import get_origin


def generate_json_schema(argument: Argument, id: str = "") -> dict:
    """Generate JSON schema from a given dargs.Argument.

    Parameters
    ----------
    argument : Argument
        The argument to generate JSON schema.
    id : str, optional
        The URL of the schema, by default "".

    Returns
    -------
    dict
        The JSON schema. Use :func:`json.dump` to save it to a file
        or :func:`json.dumps` to get a string.

    Examples
    --------
    Dump the JSON schema of DeePMD-kit to a file:

    >>> from dargs.json_schema import generate_json_schema
    >>> from deepmd.utils.argcheck import gen_args
    >>> import json
    >>> from dargs import Argument
    >>> a = Argument("DeePMD-kit", dtype=dict, sub_fields=gen_args())
    >>> schema = generate_json_schema(a)
    >>> with open("deepmd.json", "w") as f:
    ...     json.dump(schema, f, indent=2)
    """
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": id,
        "title": argument.name,
        **_convert_single_argument(argument),
    }
    return schema


def _convert_single_argument(argument: Argument) -> dict:
    """Convert a single argument to JSON schema.

    Parameters
    ----------
    argument : Argument
        The argument to convert.

    Returns
    -------
    dict
        The JSON schema of the argument.
    """
    data = {
        "description": argument.doc,
        "type": list({_convert_types(tt) for tt in argument.dtype}),
    }
    if argument.default is not _Flags.NONE:
        data["default"] = argument.default
    properties = {
        **{
            nn: _convert_single_argument(aa)
            for aa in argument.sub_fields.values()
            for nn in (aa.name, *aa.alias)
        },
        **{
            vv.flag_name: {
                "type": "string",
                "enum": list(vv.choice_dict.keys()) + list(vv.choice_alias.keys()),
                "default": vv.default_tag,
                "description": vv.doc,
            }
            for vv in argument.sub_variants.values()
        },
    }
    required = [
        aa.name
        for aa in argument.sub_fields.values()
        if not aa.optional and not aa.alias
    ] + [vv.flag_name for vv in argument.sub_variants.values() if not vv.optional]
    allof = [
        {
            "if": {
                "oneOf": [
                    {
                        "properties": {vv.flag_name: {"const": kkaa}},
                    }
                    for kkaa in (kk, *aa.alias)
                ],
                "required": [vv.flag_name]
                if not (vv.optional and vv.default_tag == kk)
                else [],
            },
            "then": _convert_single_argument(aa),
        }
        for vv in argument.sub_variants.values()
        for kk, aa in vv.choice_dict.items()
    ]
    allof += [
        {"oneOf": [{"required": [nn]} for nn in (aa.name, *aa.alias)]}
        for aa in argument.sub_fields.values()
        if not aa.optional and aa.alias
    ]
    if not argument.repeat:
        data["properties"] = properties
        data["required"] = required
        if allof:
            data["allOf"] = allof
    else:
        data["items"] = {
            "type": "object",
            "properties": properties,
            "required": required,
        }
        if allof:
            data["items"]["allOf"] = allof
    return data


def _convert_types(T: type | Any | None) -> str:
    """Convert a type to JSON schema type.

    Parameters
    ----------
    T : type | Any | None
        The type to convert.

    Returns
    -------
    str
        The JSON schema type.
    """
    # string, number, integer, object, array, boolean, null
    if T is None or T is type(None):
        return "null"
    elif T is str:
        return "string"
    elif T in (int, float):
        return "number"
    elif T is bool:
        return "boolean"
    elif T is list or get_origin(T) is list:
        return "array"
    elif T is dict or get_origin(T) is dict:
        return "object"
    raise ValueError(f"Unknown type: {T}")
