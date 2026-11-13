# Third-party material

`src/sts_hawk/assets/wiki.md` contains text from the Slay the Spire Wiki at
https://slay-the-spire.fandom.com/, contributed by that wiki's editors. It is
a user-provided scrape converted to Markdown, with each article's title and
source URL retained. Article histories and contributor attribution are available
through those linked source pages. The text is redistributed under the
[Creative Commons Attribution-ShareAlike 3.0 Unported license](https://creativecommons.org/licenses/by-sa/3.0/),
consistent with [Fandom's licensing policy](https://www.fandom.com/licensing).
The exact scrape date was not included in the provided archive.

`src/sts_hawk/assets/computer/` is copied from Inspect AI's computer-tool backend
at upstream commit `099d83a` (Inspect 0.3.289 source tree). Its MIT license is
retained in that directory.

Slay the Spire, its game files, ModTheSpire and game mods are not included in
this repository or its release assets. Users must supply an appropriately
licensed private runtime separately.

Local modification: `_x11_client.py` checks for Firefox ESR before browser actions and returns an ordinary tool error when it is absent. Screenshot/input behavior is unchanged.
