from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph as DocxPara
import io

class PreservadorDocx:
    def __init__(self, traductor):
        self.traductor = traductor

    def tradueix_paragraf(self, para):
        text = para.text.strip()
        if not text or not para.runs:
            return
        for run in para.runs:
            if run._r.find(qn('w:fldChar')) is not None:
                return
            if run._r.find(qn('w:instrText')) is not None:
                return
        traduit = self.traductor(text)
        for run in para.runs[1:]:
            p = run._r.getparent()
            if p is not None:
                p.remove(run._r)
        para.runs[0].text = traduit

    def tradueix_taula(self, taula):
        for fila in taula.rows:
            for cel in fila.cells:
                for para in cel.paragraphs:
                    self.tradueix_paragraf(para)

    def tradueix_document(self, entrada, sortida=None):
        if isinstance(entrada, bytes):
            entrada = io.BytesIO(entrada)
        doc = Document(entrada)
        for para in doc.paragraphs:
            self.tradueix_paragraf(para)
        for taula in doc.tables:
            self.tradueix_taula(taula)
        for seccio in doc.sections:
            for part in [seccio.header, seccio.footer]:
                try:
                    for para in part.paragraphs:
                        self.tradueix_paragraf(para)
                except Exception:
                    pass
        for txbx in doc.element.body.iter(qn('w:txbxContent')):
            for p_elem in txbx.iter(qn('w:p')):
                try:
                    self.tradueix_paragraf(DocxPara(p_elem, doc))
                except Exception:
                    pass
        buf = io.BytesIO()
        doc.save(buf)
        if sortida:
            doc.save(sortida)
        return buf.getvalue()
