from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
import io

class PreservadorPptx:
    def __init__(self, traductor):
        self.traductor = traductor

    def tradueix_text_frame(self, tf):
        for para in tf.paragraphs:
            text = para.text.strip()
            if not text or not para.runs:
                continue
            traduit = self.traductor(text)
            for run in para.runs[1:]:
                try:
                    para._p.remove(run._r)
                except Exception:
                    pass
            if para.runs:
                para.runs[0].text = traduit

    def tradueix_shape(self, shape):
        try:
            if shape.has_text_frame:
                self.tradueix_text_frame(shape.text_frame)
            if shape.has_table:
                for fila in shape.table.rows:
                    for cel in fila.cells:
                        self.tradueix_text_frame(cel.text_frame)
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                for s in shape.shapes:
                    self.tradueix_shape(s)
        except Exception:
            pass

    def tradueix_document(self, entrada, sortida=None):
        if isinstance(entrada, bytes):
            entrada = io.BytesIO(entrada)
        prs = Presentation(entrada)
        for diap in prs.slides:
            for shape in diap.shapes:
                self.tradueix_shape(shape)
            if diap.has_notes_slide:
                try:
                    self.tradueix_text_frame(
                        diap.notes_slide.notes_text_frame)
                except Exception:
                    pass
        buf = io.BytesIO()
        prs.save(buf)
        if sortida:
            prs.save(sortida)
        return buf.getvalue()
