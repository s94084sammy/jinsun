# Contributing

金孫是 Hermes Agent 的家用改裝。請先讀 [README.md](README.md) 的理念：用開源、不重複造輪子、符合台灣長輩習慣。

## Before a pull request

1. Do not commit `.env`, `data/`, tokens, or household screenshots.
2. New elder behaviour belongs in `overlay/skills/` plus, if needed, `overlay/mcp/`.
3. Keep LINE at one bubble and at most two buttons. Do not add Flex, carousels, or a rich menu unless the README and quota story change with it.
4. Speak in Taiwan Traditional Chinese toward elders. Use Arabic numerals (208, not 二零八).
5. Run `python3 -m unittest discover -s tests -v` without Docker.

## Language

User-facing elder copy: Taiwan Traditional Chinese.
Maintainer docs: Traditional Chinese in `README.md`, English in `README.en.md`. Keep both in the same change when you touch install steps.
