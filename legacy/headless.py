import os

from aqt.qt import *

from pitch_graph import make_sequences, make_graphs

_dir = os.path.dirname(__file__)
with open(os.path.join(_dir, 'accent_colors.css')) as f:
    _accent_css = f.read()


# Tests
##########################################################################

def html_page(body_content: str):
    head_content = """
    <meta charset="UTF-8" />
    <title>Pronunciations</title>
    <style>
        body {
            box-sizing: border-box;
            font-size: 25px;
            font-family: "Noto Serif",
                "Noto Serif CJK JP",
                "Yu Mincho",
                "Liberation Serif",
                "Times New Roman",
                Times,
                Georgia,
                Serif;
            background-color: #FFFAF0;
            color: #2A1B0A;
            line-height: 1.4;
            text-align: left;

            display: grid;
            grid-template-columns: max-content max-content;
            row-gap: 8px;
            column-gap: 8px;
        }
        svg {
            border: 1px solid pink;
            display: block;
        }
""" + _accent_css + """
    </style>
    """

    return f'<!DOCTYPE html><html><head>{head_content}</head><body>{body_content}</body></html>'


def main():
    sentence = """
    大物[おおもの];2 ; まで;1
    じんせい;1 | まで;1
    じんせい;1 ; まで;a-1
    つかう; , つかった;-
    稼[かせ]いで;k2. がっこう;
    がっこう;1. つくった;2.
    君[dきdみ]; dの 嘘[dうdそ];1 dを.
    自分[じぶん]; じゃ | できない;k2.
    ひとり;1-
    ひとり;2-
    ひとり;3-
    よねん; ぐらい;pa
    よねん; ぐらい;po1
    """

    app = QApplication([])

    widget = QWidget()
    layout = QVBoxLayout()
    webview = QWebEngineView(parent=widget)
    layout.addWidget(webview)
    webview.setHtml(html_page(''.join(make_graphs(make_sequences(sentence)))))
    widget.setLayout(layout)
    widget.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
