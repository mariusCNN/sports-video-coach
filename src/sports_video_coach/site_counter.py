"""The public demo site's visit counter: a GoatCounter script tag (no cookies, aggregate counts only), on the landing,
benchmark and findings pages, and only when the build sets SVC_GOATCOUNTER to the GoatCounter site code. Unset (the
default, and every local build), the pages carry no counter. Report pages (render_html, publish) never get one."""

from __future__ import annotations

import os
import re

ENV = "SVC_GOATCOUNTER"
CODE = re.compile(r"[a-z0-9][a-z0-9-]{0,48}[a-z0-9]")   # a GoatCounter site code: the subdomain of goatcounter.com


def tag() -> str:
    """The script tag for the site code in SVC_GOATCOUNTER, or '' when it is unset or not a valid code."""
    code = os.environ.get(ENV, "").strip().lower()
    if not CODE.fullmatch(code):
        return ""
    return (f'<script data-goatcounter="https://{code}.goatcounter.com/count" async '
            'src="https://gc.zgo.at/count.js"></script>')
