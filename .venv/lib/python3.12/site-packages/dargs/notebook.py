r'''IPython/Jupyter Notebook display for dargs.

It is expected to be used in Jupyter Notebook, where
the IPython module is available.

Examples
--------
>>> from dargs.sphinx import _test_argument
>>> from dargs.notebook import JSON
>>> jstr = """
... {
...     "test_argument": "test1",
...     "test_variant": "test_variant_argument",
...     "_comment": "This is an example data"
... }
... """
>>> JSON(jstr, _test_argument())
'''

from __future__ import annotations

import html
import json
import re
from typing import Any

from IPython.display import HTML, display

from dargs import Argument, Variant

__all__ = ["JSON"]

# https://www.w3schools.com/css/css_tooltip.asp
css = """<style>
.dargs-codeblock {
  width: 100%;
  background-color: #f9f9f9;
  border-color: #f9f9f9;
  color: #000000;
}
.dargs-codeblock::before {
  counter-reset: listing;
}
.dargs-codeblock code.dargs-linebegin {
  counter-increment: listing;
}
.dargs-codeblock code.dargs-linebegin::before {
  content: counter(listing) " ";
  display: inline-block;
  width: 2em;
  padding-left: auto;
  margin-left: auto;
  text-align: right;
  color: #6e7781;
}
.dargs-codeblock code.dargs-code {
  padding-left: 0;
  padding-right: 0;
  margin-left: 0;
  margin-right: 0;
  background-color: #f9f9f9;
  border-color: #f9f9f9;
  color: #000000;
}
.dargs-codeblock .dargs-key {
  position: relative;
  display: inline-block;
  border-bottom: 1px dotted black;
}
.dargs-codeblock .dargs-key code.dargs-code {
  color: #0550ae;
}
.dargs-codeblock .dargs-key .dargs-doc {
  visibility: hidden;
  width: 600px;
  background-color: black;
  color: #fff;
  padding: 1em 1em;
  border-radius: 6px;
  position: absolute;
  z-index: 1;
}
.dargs-codeblock .dargs-key:hover .dargs-doc {
  visibility: visible;
}
.dargs-codeblock .dargs-key .dargs-doc .dargs-doc-code {
  color: #bbbbff;
}
</style>
"""


def JSON(data: dict | str, arg: Argument | list[Argument]):
    """Display JSON data with Argument in the Jupyter Notebook.

    Parameters
    ----------
    data : dict or str
        The JSON data to be displayed, either JSON string or a dict.
    arg : dargs.Argument or list[dargs.Argument]
        The Argument that describes the JSON data.
    """
    display(HTML(print_html(data, arg)))


def print_html(data: Any, arg: Argument | list[Argument]) -> str:
    """Print HTML string with Argument in the Jupyter Notebook.

    Parameters
    ----------
    data : dict or str
        The JSON data to be displayed, either JSON string or a dict.
    arg : dargs.Argument or list[dargs.Argument]
        The Argument that describes the JSON data.

    Returns
    -------
    str
        The HTML string.
    """
    if isinstance(data, str):
        data = json.loads(data)
    elif isinstance(data, dict):
        pass
    else:
        raise ValueError(f"Unknown type: {type(data)}")

    if isinstance(arg, list):
        arg = Argument("data", dtype=dict, sub_fields=arg)
    elif isinstance(arg, Argument):
        pass
    else:
        raise ValueError(f"Unknown type: {type(arg)}")
    argdata = ArgumentData(data, arg)
    buff = [css, r"""<div class="dargs-codeblock">""", argdata.print_html(), r"</div>"]
    return "".join(buff)


class ArgumentData:
    """ArgumentData is a class to hold the data and Argument.

    It is used to print the data with Argument in the Jupyter Notebook.

    Parameters
    ----------
    data : dict
        The data to be displayed.
    arg : Union[dargs.Argument, dargs.Variant]
        The Argument that describes the data.
    repeat : bool, optional
        The argument is repeat
    """

    def __init__(self, data: dict, arg: Argument | Variant, repeat: bool = False):
        self.data = data
        self.arg = arg
        self.repeat = repeat
        self.subdata = []
        self._init_subdata()

    def _init_subdata(self):
        """Initialize sub ArgumentData."""
        if (
            isinstance(self.data, dict)
            and isinstance(self.arg, Argument)
            and not (self.arg.repeat and not self.repeat)
        ):
            sub_fields = self.arg.sub_fields.copy()
            # extend subfiles with sub_variants
            for vv in self.arg.sub_variants.values():
                choice = self.data.get(vv.flag_name, vv.default_tag)
                if choice and choice in vv.choice_dict:
                    sub_fields.update(vv.choice_dict[choice].sub_fields)

            for kk in self.data:
                if kk in sub_fields:
                    self.subdata.append(ArgumentData(self.data[kk], sub_fields[kk]))
                elif kk in self.arg.sub_variants:
                    self.subdata.append(
                        ArgumentData(self.data[kk], self.arg.sub_variants[kk])
                    )
                else:
                    self.subdata.append(ArgumentData(self.data[kk], kk))
        elif (
            isinstance(self.data, list)
            and isinstance(self.arg, Argument)
            and self.arg.repeat
            and not self.repeat
        ):
            for dd in self.data:
                self.subdata.append(ArgumentData(dd, self.arg, repeat=True))
        elif (
            isinstance(self.data, dict)
            and isinstance(self.arg, Argument)
            and self.arg.repeat
            and not self.repeat
        ):
            for dd in self.data.values():
                self.subdata.append(ArgumentData(dd, self.arg, repeat=True))

    def print_html(self, _level=0, _last_one=True):
        """Print the data with Argument in HTML format.

        Parameters
        ----------
        _level : int, optional
            The level of indentation, by default 0
        _last_one : bool, optional
            Whether it is the last one, by default True
        """
        linebreak = "<br/>"
        indent = (
            r"""<code class="dargs-code dargs-linebegin">"""
            + "&nbsp;" * (_level * 2)
            + "</code>"
        )
        buff = []
        buff.append(indent)
        if _level > 0 and not (
            isinstance(self.data, dict)
            and isinstance(self.arg, Argument)
            and self.repeat
        ):
            if isinstance(self.arg, (Argument, Variant)):
                buff.append(r"""<span class="dargs-key">""")
            else:
                buff.append(r"""<span>""")
            buff.append(r"""<code class="dargs-code">""")
            buff.append('"')
            if isinstance(self.arg, Argument):
                buff.append(self.arg.name)
            elif isinstance(self.arg, Variant):
                buff.append(self.arg.flag_name)
            elif isinstance(self.arg, str):
                buff.append(self.arg)
            else:
                raise ValueError(f"Unknown type: {type(self.arg)}")
            buff.append('"')
            buff.append("</code>")
            if isinstance(self.arg, (Argument, Variant)):
                buff.append(r"""<span class="dargs-doc">""")
                if isinstance(self.arg, Argument):
                    doc_head = (
                        self.arg.gen_doc_head()
                        .replace("| type:", "type:")
                        .replace("\n", linebreak)
                    )
                    # use re to replace ``xx`` to <code>xx</code>
                    doc_head = re.sub(
                        r"``(.*?)``",
                        r'<span class="dargs-doc-code">\1</span>',
                        doc_head,
                    )
                    doc_head = re.sub(r"\*(.+)\*", r"<i>\1</i>", doc_head)
                    buff.append(doc_head)
                elif isinstance(self.arg, Variant):
                    buff.append(f"{self.arg.flag_name}:<br/>type: ")
                    buff.append(r"""<span class="dargs-doc-code">""")
                    buff.append("str")
                    buff.append(r"""</span>""")
                    if self.arg.default_tag:
                        buff.append(", default: ")
                        buff.append(r"""<span class="dargs-doc-code">""")
                        buff.append(self.arg.default_tag)
                        buff.append(r"""</span>""")
                else:
                    raise ValueError(f"Unknown type: {type(self.arg)}")

                doc_body = html.escape(self.arg.doc.strip())
                if doc_body:
                    buff.append("<hr/>")
                doc_body = re.sub(r"""\n+""", "\n", doc_body)
                doc_body = doc_body.replace("\n", linebreak)
                doc_body = re.sub(
                    r"`+(.*?)`+", r'<span class="dargs-doc-code">\1</span>', doc_body
                )
                doc_body = re.sub(r"\*(.+)\*", r"<i>\1</i>", doc_body)
                buff.append(doc_body)

                buff.append(r"""</span>""")
            buff.append(r"""</span>""")
            buff.append(r"""<code class="dargs-code">""")
            buff.append(": ")
            buff.append("</code>")
        if self.subdata and isinstance(self.data, dict):
            buff.append(r"""<code class="dargs-code">""")
            buff.append("{")
            buff.append("</code>")
            buff.append(linebreak)
            for ii, sub in enumerate(self.subdata):
                buff.append(
                    sub.print_html(_level + 1, _last_one=(ii == len(self.subdata) - 1))
                )
            buff.append(indent)
            buff.append(r"""<code class="dargs-code">""")
            buff.append("}")
            if not _last_one:
                buff.append(",")
            buff.append("</code>")
            buff.append(linebreak)
        elif self.subdata and isinstance(self.data, list):
            buff.append(r"""<code class="dargs-code">""")
            buff.append("[")
            buff.append("</code>")
            buff.append(linebreak)
            for ii, sub in enumerate(self.subdata):
                buff.append(
                    sub.print_html(_level + 1, _last_one=(ii == len(self.subdata) - 1))
                )
            buff.append(indent)
            buff.append(r"""<code class="dargs-code">""")
            buff.append("]")
            if not _last_one:
                buff.append(",")
            buff.append("</code>")
            buff.append(linebreak)
        else:
            buff.append(r"""<code class="dargs-code">""")
            buff.append(
                json.dumps(self.data, indent=2)
                .replace(" ", "&nbsp;")
                .replace(
                    "\n", f"""</code>{linebreak}{indent}<code class="dargs-code">"""
                )
            )
            if not _last_one:
                buff.append(",")
            buff.append("</code>")
            buff.append(linebreak)
        return "".join(buff)
