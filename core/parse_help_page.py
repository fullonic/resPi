"""Markdown web page parser.

Converts raw markdown gitlab project help page into a html page."""

import markdown2
import requests


def parser(url="https://gitlab.com/fullonic/resPi/-/raw/master/README.md"):
    """Download page from gitlab and generate a html."""
    return markdown2.markdown(requests.get(url).text)
