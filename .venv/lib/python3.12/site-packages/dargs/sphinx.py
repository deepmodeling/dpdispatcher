"""Sphinx extension.

To enable dargs Sphinx extension, add :mod:`dargs.sphinx` to the extensions of conf.py:

.. code-block:: python

   extensions = [
       'dargs.sphinx',
   ]


Then `dargs` directive will be added:

.. code-block:: rst

    .. dargs::
       :module: dargs.sphinx
       :func: _test_argument

where `_test_argument` returns an :class:`Argument <dargs.Argument>`. A :class:`list` of :class:`Argument <dargs.Argument>` is also accepted.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Callable, ClassVar, List

from docutils.parsers.rst import Directive
from docutils.parsers.rst.directives import unchanged
from sphinx import addnodes
from sphinx.directives import ObjectDescription
from sphinx.domains import Domain, ObjType
from sphinx.roles import XRefRole
from sphinx.util.nodes import make_refnode

from .dargs import Argument, Variant

if TYPE_CHECKING:
    from sphinx.util.typing import RoleFunction


class DargsDirective(Directive):
    """dargs directive."""

    has_content: ClassVar[bool] = True
    option_spec: ClassVar[dict[str, Callable[[str], Any]] | None] = {
        "module": unchanged,
        "func": unchanged,
    }

    def run(self):
        if "module" in self.options and "func" in self.options:
            module_name = self.options["module"]
            attr_name = self.options["func"]
        else:
            raise self.error(":module: and :func: should be specified")

        try:
            mod = __import__(module_name, globals(), locals(), [attr_name])
        except ImportError as e:
            raise self.error(
                f'Failed to import "{attr_name}" from "{module_name}".\n{sys.exc_info()[1]}'
            ) from e

        if not hasattr(mod, attr_name):
            raise self.error(
                f'Module "{module_name}" has no attribute "{attr_name}"\n'
                "Incorrect argparse :module: or :func: values?"
            )
        func = getattr(mod, attr_name)
        arguments = func()

        if not isinstance(arguments, (list, tuple)):
            arguments = [arguments]

        rsts = []
        for argument in arguments:
            if not isinstance(argument, (Argument, Variant)):
                raise RuntimeError("The function doesn't return Argument")
            rst = argument.gen_doc(
                make_anchor=True, make_link=True, use_sphinx_domain=True
            )
            rsts.extend(rst.split("\n"))
        self.state_machine.insert_input(rsts, f"{module_name}:{attr_name}")
        return []


class DargsObject(ObjectDescription):
    """dargs::argument directive.

    This directive creates a signature node for an argument.
    """

    option_spec: ClassVar[dict] = {
        "path": unchanged,
    }

    def handle_signature(self, sig, signode):
        signode += addnodes.desc_name(sig, sig)
        return sig

    def add_target_and_index(self, name, sig, signode):
        path = self.options["path"]
        targetid = f"{self.objtype}:{path}"
        if targetid not in self.state.document.ids:
            signode["names"].append(targetid)
            signode["ids"].append(targetid)
            signode["first"] = not self.names
            self.state.document.note_explicit_target(signode)
            # for cross-references
            inv = self.env.domaindata["dargs"]["arguments"]
            if targetid in inv:
                self.state.document.reporter.warning(
                    f'Duplicated argument "{targetid}" described in "{self.env.doc2path(inv[targetid][0])}".',
                    line=self.lineno,
                )
            inv[targetid] = (self.env.docname, self.objtype)

        self.indexnode["entries"].append(
            (
                "pair",
                f"{name}; {path} ({self.objtype.title()})",
                targetid,
                "main",
                None,
            )
        )


class DargsDomain(Domain):
    """Dargs domain.

    Includes:
    - dargs::argument directive
    - dargs::argument role
    """

    name: ClassVar[str] = "dargs"
    label: ClassVar[str] = "dargs"
    object_types: ClassVar[dict[str, ObjType]] = {  # type: ignore
        "argument": ObjType("argument", "argument"),
    }
    directives: ClassVar[dict[str, type[Directive]]] = {  # type: ignore
        "argument": DargsObject,
    }
    roles: ClassVar[dict[str, RoleFunction | XRefRole]] = {  # type: ignore
        "argument": XRefRole(),
    }

    initial_data: ClassVar[dict] = {  # type: ignore
        "arguments": {},  # fullname -> docname, objtype
    }

    def resolve_xref(self, env, fromdocname, builder, typ, target, node, contnode):
        """Resolve cross-references."""
        targetid = f"{typ}:{target}"
        obj = self.data["arguments"].get(targetid)
        if obj is None:
            return None
        return make_refnode(builder, fromdocname, obj[0], targetid, contnode, target)


def setup(app):
    """Setup sphinx app."""
    app.add_directive("dargs", DargsDirective)
    app.add_domain(DargsDomain)
    return {"parallel_read_safe": True}


def _test_argument() -> Argument:
    """This internal function is used to generate docs of dargs."""
    doc_test = "This argument/variant is only used to test."
    return Argument(
        name="test",
        dtype=str,
        doc=doc_test,
        sub_fields=[
            Argument("test_argument", dtype=str, doc=doc_test, default="test"),
            Argument("test_list", dtype=List[int], optional=True),
        ],
        sub_variants=[
            Variant(
                "test_variant",
                doc=doc_test,
                choices=[
                    Argument(
                        "test_variant_argument",
                        dtype=dict,
                        optional=True,
                        doc=doc_test,
                        sub_fields=[
                            Argument(
                                "test_repeat_list",
                                dtype=list,
                                repeat=True,
                                doc=doc_test,
                                sub_fields=[
                                    Argument(
                                        "test_repeat_item", dtype=bool, doc=doc_test
                                    ),
                                ],
                            ),
                            Argument(
                                "test_repeat_dict",
                                dtype=dict,
                                repeat=True,
                                doc=doc_test,
                                sub_fields=[
                                    Argument(
                                        "test_repeat_item", dtype=bool, doc=doc_test
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
