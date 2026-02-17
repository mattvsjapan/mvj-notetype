
from aqt.qt import *

from pitch_graph import make_sequences, make_graphs


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

    .keihan_heiban, 
    .keihan_heiban line, 
    .keihan_heiban circle, 
    .keihan_heiban text, .h {
        fill: #3bb2ed;
        stroke: #3bb2ed;
        color: #3bb2ed;
    }

    .keihan_low_heiban, 
    .keihan_low_heiban line, 
    .keihan_low_heiban circle, 
    .keihan_low_heiban text, .l {
        fill: #096999;
        stroke: #096999;
        color: #096999;
    }

    .keihan_atamadaka, 
    .keihan_atamadaka line, 
    .keihan_atamadaka circle,
    .keihan_atamadaka text, .a {
        fill: #f76d94;
        stroke: #f76d94;
        color: #f76d94;
    }

    .keihan_nakadaka line, 
    .keihan_nakadaka circle, 
    .keihan_nakadaka text, .n {
        fill: #a89c0f;
        stroke: #a89c0f;
        color: #a89c0f;
    }

    .keihan_low_nakadaka line, 
    .keihan_low_nakadaka circle, 
    .keihan_low_nakadaka text, .m {
        fill: #876333;
        stroke: #876333;
        color: #876333;
    }


    .keihan_odaka line, 
    .keihan_odaka circle,
    .keihan_odaka text,
    .keihan_low_odaka line, 
    .keihan_low_odaka circle,
    .keihan_low_odaka text, .o {
        fill: #658065;
        stroke: #658065;
        color: #658065
    }

    .connector line,
    .connector circle,
    .connector text,
    .particle line,
    .particle circle,
    .particle text,
    .setsubigo line,
    .setsubigo circle,
    .setsubigo text, 
    .keihan_particle line,
    .keihan_particle circle,
    .keihan_particle text,
    .keihan_setsubigo line,
    .keihan_setsubigo circle,
    .keihan_setsubigo text, .p {
        fill: gray;
        stroke: gray;
        color: gray;
    }

  .atamadaka,
    .atamadaka line,
    .atamadaka circle,
    .atamadaka text {
        fill: #E60000;
        stroke: #E60000;
        color: #E60000;
    }

    .heiban, 
    .heiban line,
    .heiban circle,
    .heiban text {
        fill: #005CE6;
        stroke: #005CE6;
        color: #005CE6;
    }

    .nakadaka,
    .nakadaka line,
    .nakadaka circle,
    .nakadaka text {
        fill: #E68A00;
        stroke: #E68A00;
        color: #E68A00;
    }

    .kifuku, 
    .kifuku line, 
    .kifuku circle,
    .kifuku text {
        fill: #AC00E6;
        stroke: #AC00E6;
        color: #AC00E6;
    }

    .odaka,
    .odaka line,
    .odaka circle,
    .odaka text {
        fill: #00802B;
        stroke: #00802B;
        color: #00802B;
    }


    .particle circle,
    .keihan_particle circle {
        fill: none;
    }

    .black line,
    .black circle,
    .black text {
        color: #4f4b4b;
        fill: #4f4b4b;
        stroke: #4f4b4b;
}

    .atamadaka text,
    .heiban text,
    .nakadaka text,
    .kifuku text,
    .odaka text,
    .keihan_heiban text,
    .keihan_low_heiban text,
    .keihan_atamadaka text,
    .keihan_nakadaka text,
    .keihan_low_nakadaka text,
    .keihan_odaka text,
    .keihan_low_odaka text,
    .keihan_particle text,
    .keihan_setsubigo text,
    .black text,
    .particle text,
    .setsubigo text {
        stroke: none;
}

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
