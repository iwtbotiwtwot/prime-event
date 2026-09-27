"""Render manuscript to editable Word, HTML, LaTeX and PDF."""
from pathlib import Path
import subprocess,json,os,re
import pypandoc
from docx import Document
from docx.shared import Inches,Pt,RGBColor
P=Path(__file__).resolve().parent
stem='Prime_Event_Zenodo_Paper'
with (P/'reference.docx').open('wb') as f:
    subprocess.run([pypandoc.get_pandoc_path(),'--print-default-data-file=reference.docx'],stdout=f,check=True)
d=Document(P/'reference.docx')
for s in d.sections:
    s.top_margin=s.bottom_margin=Inches(.75)
    s.left_margin=s.right_margin=Inches(.8)
style=d.styles['Normal'];style.font.name='Liberation Serif';style.font.size=Pt(11)
style.paragraph_format.space_after=Pt(6)
for level in range(1,4):
    st=d.styles[f'Heading {level}'];st.font.name='Liberation Sans';st.font.size=Pt(16-level*2);st.font.color.rgb=RGBColor.from_string('24485B');st.paragraph_format.keep_with_next=True
d.save(P/'reference.docx')
common=['--standalone','--resource-path='+str(P)]
pypandoc.convert_file(str(P/'PAPER.md'),'docx',outputfile=str(P/(stem+'.docx')),extra_args=common+['--reference-doc='+str(P/'reference.docx')])
d=Document(P/(stem+'.docx'))
for table in d.tables:
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for r in p.runs:r.font.size=Pt(9)
for s in d.sections:
    p=s.footer.paragraphs[0];p.text='Balanced hidden-spin feedback · Zenodo companion paper 1.1 · 27 September 2026';p.style='Caption'
d.save(P/(stem+'.docx'))
pypandoc.convert_file(str(P/'PAPER.md'),'latex',outputfile=str(P/(stem+'.tex')),extra_args=common+['-V','geometry:margin=0.75in','-V','fontsize=11pt'])
texpath=P/(stem+'.tex');tex=texpath.read_text()
tex=tex.replace(r'\begin{document}',r'\usepackage{fvextra,seqsplit,needspace}'+'\n'+r'\DefineVerbatimEnvironment{Highlighting}{Verbatim}{commandchars=\\\{\},breaklines,fontsize=\footnotesize}'+'\n'+r'\AtBeginEnvironment{longtable}{\footnotesize}'+'\n'+r'\begin{document}')
tex=re.sub(r'\\texttt\{([^{}]{26,})\}',lambda m:r'\texttt{\seqsplit{'+m.group(1)+'}}',tex)
tex=re.sub(r'(?m)^Table ([1-4])\.',lambda m:r'\Needspace{9\baselineskip}'+'\nTable '+m.group(1)+'.',tex)
tex=tex.replace(r'\begin{Shaded}', r'\Needspace{22\baselineskip}'+'\n'+r'\begin{Shaded}')
texpath.write_text(tex)
subprocess.run([os.environ.get('TECTONIC','tectonic'),'--keep-logs',str(texpath)],cwd=P,check=True)
assert (P/(stem+'.pdf')).exists()
(P/'reference.docx').unlink()
print('Built Word, PDF, and LaTeX.')
