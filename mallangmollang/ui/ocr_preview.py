"""
OCR 전처리 미리보기 창
원본 / 전처리 결과 / 바운딩 박스 이미지를 나란히 표시합니다.
"""

from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QTextEdit, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage
from PIL import Image
import numpy as np


def _pil_to_pixmap(image: Image.Image, max_width: int = 400) -> QPixmap:
    """PIL Image를 QPixmap으로 변환합니다."""
    if image.mode == "L":
        img = image.convert("RGB")
    else:
        img = image.convert("RGB")

    data = np.array(img)
    h, w, ch = data.shape
    qimg = QImage(data.data, w, h, ch * w, QImage.Format.Format_RGB888)
    pixmap = QPixmap.fromImage(qimg)
    if pixmap.width() > max_width:
        pixmap = pixmap.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)
    return pixmap


class OcrPreviewDialog(QDialog):
    """OCR 전처리 미리보기 창"""

    def __init__(
        self,
        original: Image.Image,
        preprocessed: Image.Image,
        bbox_overlay: Image.Image,
        ocr_text: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("OCR 전처리 미리보기")
        self.setMinimumSize(900, 400)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)

        # 이미지 3장 가로 배치
        img_layout = QHBoxLayout()
        for title, img in [
            ("원본", original),
            ("전처리 (이진화)", preprocessed),
            ("바운딩 박스", bbox_overlay),
        ]:
            col = QVBoxLayout()
            lbl_title = QLabel(title)
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_title.setStyleSheet("font-weight: bold; font-size: 13px;")
            col.addWidget(lbl_title)

            lbl_img = QLabel()
            lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_img.setPixmap(_pil_to_pixmap(img))
            lbl_img.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            lbl_img.setScaledContents(False)
            col.addWidget(lbl_img, stretch=1)

            img_layout.addLayout(col)

        layout.addLayout(img_layout, stretch=3)

        # OCR 텍스트 (복사 가능)
        text_label = QLabel("OCR 추출 텍스트:")
        text_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(text_label)

        text_edit = QTextEdit()
        text_edit.setPlainText(ocr_text if ocr_text else "(텍스트 없음)")
        text_edit.setReadOnly(True)
        text_edit.setMaximumHeight(120)
        layout.addWidget(text_edit, stretch=1)
