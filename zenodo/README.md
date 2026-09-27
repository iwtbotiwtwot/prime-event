# Zenodo companion paper, version 1.1

[PDF](Prime_Event_Zenodo_Paper.pdf) · [editable Word](Prime_Event_Zenodo_Paper.docx) ·
[Markdown](PAPER.md) · [LaTeX](Prime_Event_Zenodo_Paper.tex).

This publication edition supersedes manuscript draft 1.0 for public deposit.
It preserves the completed scientific results and adds the public archive identifiers,
open licensing, current data availability, and a tested standalone reproduction appendix.
The original draft remains in manuscript/ for provenance.

Software concept DOI: https://doi.org/10.5281/zenodo.23002148.
Initial software version DOI: https://doi.org/10.5281/zenodo.23002149.
These are software identifiers, not a separately assigned paper DOI. For a separate
Zenodo paper deposit, upload the PDF, select Publication / Preprint and CC BY 4.0,
list Sean Brady as author, include OpenAI ChatGPT and Codex in the collaboration
statement, and relate the software DOI as “is supplemented by”. Let Zenodo assign
the separate paper DOI. Uploading to GitHub does not modify an existing Zenodo record.

Suggested deposit fields are in PAPER_METADATA.json; the title and abstract are also in PAPER.md. The paper is approximately the
same full research manuscript, with its equations, tables and scientific figures.

Build using Python with pypandoc and python-docx, Pandoc 3.x, and Tectonic 0.17.0:
`python zenodo/build_paper.py`. Set TECTONIC to its executable path if needed.
First PDF compilation can download TeX resources. Rendering metadata may differ
between builds; the numerical source files remain frozen.
