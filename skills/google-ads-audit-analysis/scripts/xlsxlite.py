"""A small .xlsx writer: plain Python, standard library only.

Enough of the format for a styled report workbook that opens cleanly in Google Sheets and Excel:
cell styles, number formats, merged cells, column widths, row heights, frozen panes, hidden sheets,
tab colours, formulas, dropdowns (list data validation), conditional formatting, doughnut / pie,
stacked bar and line charts, and pictures.

Usage:
    wb = Workbook()
    ws = wb.sheet("Summary", tab="1F3864")
    ws.set(0, 0, "Hello", wb.style(bold=True, fill="FFF2CC"))
    ws.set(1, 0, "=SUM(B1:B9)")
    wb.save("report.xlsx")

Rows and columns are 0-based everywhere in this module. A string value that starts with "=" is
written as a formula.
"""

import re
import zipfile
from xml.sax.saxutils import escape

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
EMU_PER_PX = 9525
_BAD_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


class Text(str):
    """A string that is always written as text, even when it starts with "="."""


def xesc(s):
    return escape(_BAD_XML.sub("", str(s)), {'"': "&quot;"})


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def ref(r, c, abs_=False):
    if abs_:
        return "$%s$%d" % (col_letter(c), r + 1)
    return "%s%d" % (col_letter(c), r + 1)


def rng(r1, c1, r2, c2, abs_=False):
    return "%s:%s" % (ref(r1, c1, abs_), ref(r2, c2, abs_))


def quote_sheet(name):
    return "'%s'" % name.replace("'", "''")


def width_px(chars):
    """Excel column width (characters) to pixels, roughly as Sheets imports it."""
    return int(chars * 7 + 5)


def px_width(px):
    return max(1.0, (px - 5) / 7.0)


class Workbook:
    def __init__(self, font="Arial", size=10):
        self.sheets = []
        self.font = font
        self.size = size
        self._num_fmts = {}
        self._fonts = [self._font_xml({})]
        self._fills = ['<fill><patternFill patternType="none"/></fill>', '<fill><patternFill patternType="gray125"/></fill>']
        self._borders = ['<border><left/><right/><top/><bottom/><diagonal/></border>']
        self._xfs = ['<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>']
        self._xf_index = {}
        self._dxfs = []
        self._dxf_index = {}
        self.media = []  # (name, bytes)
        self.charts = 0

    # ---- styles -------------------------------------------------------------------------
    def _font_xml(self, f):
        parts = []
        if f.get("bold"):
            parts.append("<b/>")
        if f.get("italic"):
            parts.append("<i/>")
        if f.get("underline"):
            parts.append('<u/>')
        parts.append('<sz val="%s"/>' % f.get("size", self.size))
        parts.append('<color rgb="FF%s"/>' % f.get("color", "000000"))
        parts.append('<name val="%s"/>' % xesc(f.get("font", self.font)))
        return "<font>%s</font>" % "".join(parts)

    def _idx(self, pool, xml):
        if xml not in pool:
            pool.append(xml)
        return pool.index(xml)

    def _num_fmt(self, fmt):
        builtin = {"General": 0, "0": 1, "0.00": 2, "#,##0": 3, "#,##0.00": 4, "0%": 9, "0.00%": 10}
        if fmt is None:
            return 0
        if fmt in builtin:
            return builtin[fmt]
        if fmt not in self._num_fmts:
            self._num_fmts[fmt] = 164 + len(self._num_fmts)
        return self._num_fmts[fmt]

    def _border_xml(self, border):
        if not border:
            return self._borders[0]
        color = border.get("color", "BFBFBF")
        sides = []
        for side in ("left", "right", "top", "bottom"):
            st = border.get(side)
            if st:
                sides.append('<%s style="%s"><color rgb="FF%s"/></%s>' % (side, st, color, side))
            else:
                sides.append("<%s/>" % side)
        return "<border>%s<diagonal/></border>" % "".join(sides)

    def style(self, bold=False, italic=False, underline=False, color=None, size=None, fill=None, fmt=None,
              h=None, v="center", wrap=False, indent=0, border=None, font=None):
        """Return a cell style id. border: dict of side->style ('thin', 'medium') plus optional 'color'."""
        key = (bold, italic, underline, color, size, fill, fmt, h, v, wrap, indent,
               tuple(sorted((border or {}).items())), font)
        if key in self._xf_index:
            return self._xf_index[key]
        f = {"bold": bold, "italic": italic, "underline": underline}
        if color:
            f["color"] = color
        if size:
            f["size"] = size
        if font:
            f["font"] = font
        font_id = self._idx(self._fonts, self._font_xml(f))
        fill_id = 0
        if fill:
            fill_id = self._idx(self._fills, '<fill><patternFill patternType="solid"><fgColor rgb="FF%s"/>'
                                             '<bgColor indexed="64"/></patternFill></fill>' % fill)
        border_id = self._idx(self._borders, self._border_xml(border))
        num_id = self._num_fmt(fmt)
        align = []
        if h:
            align.append('horizontal="%s"' % h)
        if v:
            align.append('vertical="%s"' % v)
        if wrap:
            align.append('wrapText="1"')
        if indent:
            align.append('indent="%d"' % indent)
        xml = ('<xf numFmtId="%d" fontId="%d" fillId="%d" borderId="%d" xfId="0" applyNumberFormat="1" '
               'applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment %s/></xf>'
               % (num_id, font_id, fill_id, border_id, " ".join(align)))
        self._xfs.append(xml)
        self._xf_index[key] = len(self._xfs) - 1
        return self._xf_index[key]

    def dxf(self, bold=None, color=None, fill=None, italic=None):
        """A differential style for conditional formatting. Returns its id."""
        key = (bold, color, fill, italic)
        if key in self._dxf_index:
            return self._dxf_index[key]
        font = ""
        if bold is not None or color or italic is not None:
            font = "<font>%s%s%s</font>" % ("<b/>" if bold else "", "<i/>" if italic else "",
                                            '<color rgb="FF%s"/>' % color if color else "")
        fill_xml = ""
        if fill:
            fill_xml = ('<fill><patternFill patternType="solid"><fgColor rgb="FF%s"/><bgColor rgb="FF%s"/>'
                        '</patternFill></fill>' % (fill, fill))
        self._dxfs.append("<dxf>%s%s</dxf>" % (font, fill_xml))
        self._dxf_index[key] = len(self._dxfs) - 1
        return self._dxf_index[key]

    def _styles_xml(self):
        nf = "".join('<numFmt numFmtId="%d" formatCode="%s"/>' % (i, xesc(f)) for f, i in self._num_fmts.items())
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<styleSheet xmlns="%s">' % NS_MAIN
                + ('<numFmts count="%d">%s</numFmts>' % (len(self._num_fmts), nf) if self._num_fmts else "")
                + '<fonts count="%d">%s</fonts>' % (len(self._fonts), "".join(self._fonts))
                + '<fills count="%d">%s</fills>' % (len(self._fills), "".join(self._fills))
                + '<borders count="%d">%s</borders>' % (len(self._borders), "".join(self._borders))
                + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                + '<cellXfs count="%d">%s</cellXfs>' % (len(self._xfs), "".join(self._xfs))
                + '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
                + '<dxfs count="%d">%s</dxfs>' % (len(self._dxfs), "".join(self._dxfs))
                + "</styleSheet>")

    # ---- sheets -------------------------------------------------------------------------
    def sheet(self, name, tab=None, hidden=False, grid=False):
        if len(name) > 31 or re.search(r"[\[\]\*\?/\\:]", name):
            raise ValueError("Bad sheet name: %r" % name)
        ws = Sheet(self, name, tab, hidden, grid)
        self.sheets.append(ws)
        return ws

    def add_media(self, data, ext="png"):
        name = "image%d.%s" % (len(self.media) + 1, ext)
        self.media.append((name, data))
        return name

    def save(self, path):
        visible = [s for s in self.sheets if not s.hidden]
        if not visible:
            raise ValueError("At least one visible sheet is needed")
        first_visible = self.sheets.index(visible[0])
        ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Default Extension="xml" ContentType="application/xml"/>'
              '<Default Extension="png" ContentType="image/png"/>'
              '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
              '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
        wb_sheets, wb_rels = [], []
        files = {}
        chart_no = 0
        drawing_no = 0
        for i, ws in enumerate(self.sheets):
            n = i + 1
            ct.append('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % n)
            wb_sheets.append('<sheet name="%s" sheetId="%d" %sr:id="rId%d"/>'
                             % (xesc(ws.name), n, 'state="hidden" ' if ws.hidden else "", n))
            wb_rels.append('<Relationship Id="rId%d" Type="%s/worksheet" Target="worksheets/sheet%d.xml"/>' % (n, REL, n))
            drawing_rid = None
            if ws.objects:
                drawing_no += 1
                drawing_rid = "rId1"
                files["xl/worksheets/_rels/sheet%d.xml.rels" % n] = (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rId1" Type="%s/drawing" Target="../drawings/drawing%d.xml"/></Relationships>'
                    % (REL, drawing_no))
                ct.append('<Override PartName="/xl/drawings/drawing%d.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>' % drawing_no)
                anchors, drels = [], []
                for k, obj in enumerate(ws.objects):
                    rid = "rId%d" % (k + 1)
                    if obj["kind"] == "chart":
                        chart_no += 1
                        files["xl/charts/chart%d.xml" % chart_no] = obj["xml"]
                        ct.append('<Override PartName="/xl/charts/chart%d.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>' % chart_no)
                        drels.append('<Relationship Id="%s" Type="%s/chart" Target="../charts/chart%d.xml"/>' % (rid, REL, chart_no))
                        body = ('<xdr:graphicFrame macro=""><xdr:nvGraphicFramePr><xdr:cNvPr id="%d" name="Chart %d"/>'
                                '<xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr><xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm>'
                                '<a:graphic><a:graphicData uri="%s"><c:chart xmlns:c="%s" r:id="%s"/></a:graphicData></a:graphic>'
                                '</xdr:graphicFrame>' % (k + 2, k + 1, NS_C, NS_C, rid))
                    else:
                        drels.append('<Relationship Id="%s" Type="%s/image" Target="../media/%s"/>' % (rid, REL, obj["media"]))
                        body = ('<xdr:pic><xdr:nvPicPr><xdr:cNvPr id="%d" name="%s"/><xdr:cNvPicPr><a:picLocks noChangeAspect="1"/></xdr:cNvPicPr></xdr:nvPicPr>'
                                '<xdr:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>'
                                '<xdr:spPr><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic>'
                                % (k + 2, xesc(obj.get("name", "Picture")), rid))
                    r, c, dx, dy, w, h = obj["pos"]
                    anchors.append('<xdr:oneCellAnchor><xdr:from><xdr:col>%d</xdr:col><xdr:colOff>%d</xdr:colOff>'
                                   '<xdr:row>%d</xdr:row><xdr:rowOff>%d</xdr:rowOff></xdr:from><xdr:ext cx="%d" cy="%d"/>'
                                   '%s<xdr:clientData/></xdr:oneCellAnchor>'
                                   % (c, dx * EMU_PER_PX, r, dy * EMU_PER_PX, w * EMU_PER_PX, h * EMU_PER_PX, body))
                files["xl/drawings/drawing%d.xml" % drawing_no] = (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<xdr:wsDr xmlns:xdr="%s" xmlns:a="%s" xmlns:r="%s">%s</xdr:wsDr>' % (NS_XDR, NS_A, NS_R, "".join(anchors)))
                files["xl/drawings/_rels/drawing%d.xml.rels" % drawing_no] = (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>'
                    % "".join(drels))
            files["xl/worksheets/sheet%d.xml" % n] = ws._xml(selected=(i == first_visible), drawing_rid=drawing_rid)
        nsheets = len(self.sheets)
        wb_rels.append('<Relationship Id="rId%d" Type="%s/styles" Target="styles.xml"/>' % (nsheets + 1, REL))
        files["xl/workbook.xml"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                                    '<workbook xmlns="%s" xmlns:r="%s"><bookViews><workbookView activeTab="%d"/></bookViews>'
                                    '<sheets>%s</sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>'
                                    % (NS_MAIN, NS_R, first_visible, "".join(wb_sheets)))
        files["xl/_rels/workbook.xml.rels"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                                               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>'
                                               % "".join(wb_rels))
        files["_rels/.rels"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                '<Relationship Id="rId1" Type="%s/officeDocument" Target="xl/workbook.xml"/></Relationships>' % REL)
        files["xl/styles.xml"] = self._styles_xml()
        ct.append("</Types>")
        files["[Content_Types].xml"] = "".join(ct)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", files.pop("[Content_Types].xml"))
            z.writestr("_rels/.rels", files.pop("_rels/.rels"))
            for name, data in files.items():
                z.writestr(name, data)
            for name, data in self.media:
                z.writestr("xl/media/" + name, data)


class Sheet:
    def __init__(self, wb, name, tab, hidden, grid):
        self.wb = wb
        self.name = name
        self.tab = tab
        self.hidden = hidden
        self.grid = grid
        self.cells = {}
        self.widths = {}
        self.heights = {}
        self.merges = []
        self.validations = []
        self.conditionals = []
        self.freeze = None
        self.objects = []
        self.autofilter = None
        self.max_r = 0
        self.max_c = 0

    @property
    def q(self):
        return quote_sheet(self.name)

    def set(self, r, c, value, style=0):
        self.cells[(r, c)] = (value, style)
        self.max_r = max(self.max_r, r)
        self.max_c = max(self.max_c, c)

    def row(self, r, c, values, style=0):
        for i, v in enumerate(values):
            self.set(r, c + i, v, style[i] if isinstance(style, (list, tuple)) else style)

    def fill(self, r1, c1, r2, c2, style):
        """Apply a style to empty cells in a block (keeps values already set)."""
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                v, _ = self.cells.get((r, c), (None, 0))
                self.set(r, c, v, style)

    def merge(self, r1, c1, r2, c2, value=None, style=None):
        self.merges.append(rng(r1, c1, r2, c2))
        if style is not None:
            self.fill(r1, c1, r2, c2, style)
        if value is not None:
            self.set(r1, c1, value, style if style is not None else 0)

    def width(self, c, chars):
        self.widths[c] = chars

    def height(self, r, points):
        self.heights[r] = points

    def dropdown(self, r, c, source, r2=None, c2=None):
        """source: a list of strings (inline, under 255 chars) or a formula range like "'Lists'!$A$1:$A$9"."""
        sq = rng(r, c, r2 if r2 is not None else r, c2 if c2 is not None else c)
        if isinstance(source, (list, tuple)):
            body = '"%s"' % ",".join(str(x).replace('"', "") for x in source)
            if len(body) > 255:
                raise ValueError("Inline dropdown list too long; use a range")
        else:
            body = source
        self.validations.append((sq, body))

    def number_rule(self, r, c, minimum, maximum):
        self.validations.append((ref(r, c), ("whole", minimum, maximum)))

    def conditional(self, sqref, formula, dxf_id):
        self.conditionals.append((sqref, formula, dxf_id))

    def chart(self, r, c, w, h, xml, dx=0, dy=0):
        self.objects.append({"kind": "chart", "pos": (r, c, dx, dy, w, h), "xml": xml})

    def picture(self, r, c, w, h, media_name, dx=0, dy=0, name="Picture"):
        self.objects.append({"kind": "picture", "pos": (r, c, dx, dy, w, h), "media": media_name, "name": name})

    def _cell_xml(self, r, c, value, style):
        a = ref(r, c)
        s = ' s="%d"' % style if style else ""
        if value is None or value == "":
            return '<c r="%s"%s/>' % (a, s) if style else ""
        if isinstance(value, bool):
            return '<c r="%s"%s t="b"><v>%d</v></c>' % (a, s, 1 if value else 0)
        if isinstance(value, (int, float)):
            if value != value or value in (float("inf"), float("-inf")):
                return '<c r="%s"%s/>' % (a, s)
            return '<c r="%s"%s><v>%s</v></c>' % (a, s, repr(float(value)) if isinstance(value, float) else value)
        value = str(value)
        if value.startswith("=") and not isinstance(value, Text):
            return '<c r="%s"%s><f>%s</f></c>' % (a, s, xesc(value[1:]))
        return '<c r="%s"%s t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (a, s, xesc(value))

    def _xml(self, selected, drawing_rid):
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="%s" xmlns:r="%s">' % (NS_MAIN, NS_R)]
        if self.tab:
            out.append('<sheetPr><tabColor rgb="FF%s"/></sheetPr>' % self.tab)
        out.append('<dimension ref="A1:%s"/>' % ref(self.max_r, self.max_c))
        view = '<sheetView workbookViewId="0"%s%s>' % ("" if self.grid else ' showGridLines="0"', ' tabSelected="1"' if selected else "")
        if self.freeze:
            fr, fc = self.freeze
            attrs = []
            if fc:
                attrs.append('xSplit="%d"' % fc)
            if fr:
                attrs.append('ySplit="%d"' % fr)
            pane = "bottomRight" if fr and fc else ("bottomLeft" if fr else "topRight")
            view += '<pane %s topLeftCell="%s" activePane="%s" state="frozen"/>' % (" ".join(attrs), ref(fr, fc), pane)
        out.append("<sheetViews>%s</sheetView></sheetViews>" % view)
        out.append('<sheetFormatPr defaultRowHeight="15"/>')
        if self.widths:
            out.append("<cols>%s</cols>" % "".join('<col min="%d" max="%d" width="%.2f" customWidth="1"/>' % (c + 1, c + 1, w)
                                                   for c, w in sorted(self.widths.items())))
        out.append("<sheetData>")
        rows = {}
        for (r, c), (v, s) in self.cells.items():
            rows.setdefault(r, []).append((c, v, s))
        for r in sorted(set(rows) | set(self.heights)):
            cells = "".join(self._cell_xml(r, c, v, s) for c, v, s in sorted(rows.get(r, []), key=lambda x: x[0]))
            ht = ' ht="%s" customHeight="1"' % self.heights[r] if r in self.heights else ""
            out.append('<row r="%d"%s>%s</row>' % (r + 1, ht, cells))
        out.append("</sheetData>")
        if self.autofilter:
            out.append('<autoFilter ref="%s"/>' % self.autofilter)
        if self.merges:
            out.append('<mergeCells count="%d">%s</mergeCells>' % (len(self.merges), "".join('<mergeCell ref="%s"/>' % m for m in self.merges)))
        prio = 1
        for sq, formula, dxf_id in self.conditionals:
            out.append('<conditionalFormatting sqref="%s"><cfRule type="expression" dxfId="%d" priority="%d" stopIfTrue="1">'
                       '<formula>%s</formula></cfRule></conditionalFormatting>' % (sq, dxf_id, prio, xesc(formula)))
            prio += 1
        if self.validations:
            dv = []
            for sq, body in self.validations:
                if isinstance(body, tuple):
                    _, lo, hi = body
                    dv.append('<dataValidation type="whole" operator="between" allowBlank="1" showErrorMessage="1" sqref="%s">'
                              '<formula1>%d</formula1><formula2>%d</formula2></dataValidation>' % (sq, lo, hi))
                else:
                    dv.append('<dataValidation type="list" allowBlank="1" showErrorMessage="1" sqref="%s"><formula1>%s</formula1></dataValidation>'
                              % (sq, xesc(body)))
            out.append('<dataValidations count="%d">%s</dataValidations>' % (len(dv), "".join(dv)))
        out.append('<pageMargins left="0.5" right="0.5" top="0.5" bottom="0.5" header="0.3" footer="0.3"/>')
        if drawing_rid:
            out.append('<drawing r:id="%s"/>' % drawing_rid)
        out.append("</worksheet>")
        return "".join(out)


# ---- charts ---------------------------------------------------------------------------------

def _rich(text, size=1100, bold=True, color="333333"):
    return ('<c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="%d" b="%d"/></a:pPr><a:r>'
            '<a:rPr lang="en-US" sz="%d" b="%d"><a:solidFill><a:srgbClr val="%s"/></a:solidFill></a:rPr><a:t>%s</a:t></a:r></a:p></c:rich></c:tx>'
            % (size, 1 if bold else 0, size, 1 if bold else 0, color, xesc(text)))


def _chart_wrap(title, plot, legend="r", extra=""):
    leg = ('<c:legend><c:legendPos val="%s"/><c:overlay val="0"/><c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr>'
           '<a:defRPr sz="900"/></a:pPr><a:endParaRPr lang="en-US"/></a:p></c:txPr></c:legend>' % legend) if legend else ""
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<c:chartSpace xmlns:c="%s" xmlns:a="%s" xmlns:r="%s"><c:roundedCorners val="0"/><c:chart>'
            '<c:title>%s<c:overlay val="0"/></c:title><c:autoTitleDeleted val="0"/><c:plotArea><c:layout/>%s</c:plotArea>'
            '%s<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart>'
            '<c:spPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:ln><a:solidFill><a:srgbClr val="D9D9D9"/></a:solidFill></a:ln></c:spPr>'
            '%s</c:chartSpace>' % (NS_C, NS_A, NS_R, _rich(title), plot, leg, extra))


def _fill(color):
    return '<c:spPr><a:solidFill><a:srgbClr val="%s"/></a:solidFill></c:spPr>' % color


def _str_ref(f):
    return "<c:strRef><c:f>%s</c:f></c:strRef>" % xesc(f)


def _num_ref(f):
    return "<c:numRef><c:f>%s</c:f></c:numRef>" % xesc(f)


def doughnut_chart(title, cat_ref, val_ref, colors, hole=55):
    """colors: one hex colour per slice position."""
    pts = "".join('<c:dPt><c:idx val="%d"/><c:bubble3D val="0"/>%s</c:dPt>' % (i, _fill(c)) for i, c in enumerate(colors))
    ser = ('<c:ser><c:idx val="0"/><c:order val="0"/>%s<c:cat>%s</c:cat><c:val>%s</c:val></c:ser>'
           % (pts, _str_ref(cat_ref), _num_ref(val_ref)))
    plot = ('<c:doughnutChart><c:varyColors val="1"/>%s<c:firstSliceAng val="0"/><c:holeSize val="%d"/></c:doughnutChart>'
            % (ser, hole))
    return _chart_wrap(title, plot)


def _axes(cat_id, val_id, cat_pos, val_pos, val_fmt, cat_title=None, val_title=None, date_axis=False, cat_fmt=None):
    def title(t):
        return '<c:title>%s<c:overlay val="0"/></c:title>' % _rich(t, 900, False, "595959") if t else ""
    grid = '<c:majorGridlines><c:spPr><a:ln><a:solidFill><a:srgbClr val="E7E6E6"/></a:solidFill></a:ln></c:spPr></c:majorGridlines>'
    small = '<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="800"/></a:pPr><a:endParaRPr lang="en-US"/></a:p></c:txPr>'
    tag = "c:dateAx" if date_axis else "c:catAx"
    cat_num = '<c:numFmt formatCode="%s" sourceLinked="0"/>' % xesc(cat_fmt) if cat_fmt else ""
    cat = ('<%s><c:axId val="%d"/><c:scaling><c:orientation val="%s"/></c:scaling><c:delete val="0"/><c:axPos val="%s"/>%s%s'
           '<c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="low"/>%s<c:crossAx val="%d"/><c:crosses val="autoZero"/>'
           '%s</%s>' % (tag, cat_id, "maxMin" if cat_pos == "l" else "minMax", cat_pos, title(cat_title), cat_num, small, val_id,
                        '<c:auto val="1"/><c:lblOffset val="100"/>' if not date_axis else '<c:auto val="0"/><c:lblOffset val="100"/><c:baseTimeUnit val="days"/>', tag))
    val = ('<c:valAx><c:axId val="%d"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="%s"/>%s%s'
           '<c:numFmt formatCode="%s" sourceLinked="0"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>%s'
           '<c:crossAx val="%d"/><c:crosses val="%s"/><c:crossBetween val="between"/></c:valAx>'
           % (val_id, val_pos, grid, title(val_title), xesc(val_fmt), small, cat_id, "max" if cat_pos == "l" else "autoZero"))
    return cat + val


def stacked_bar_chart(title, cat_ref, series, val_fmt="#,##0"):
    """Horizontal stacked bars. series: list of (name, values_ref, colour). Names are plain text: a cell
    reference as a series name makes Google Sheets pull the header row into the series on import."""
    sers = []
    for i, (name, vals, color) in enumerate(series):
        tx = "<c:tx><c:v>%s</c:v></c:tx>" % xesc(name)
        sers.append('<c:ser><c:idx val="%d"/><c:order val="%d"/>%s%s<c:invertIfNegative val="0"/><c:cat>%s</c:cat><c:val>%s</c:val></c:ser>'
                    % (i, i, tx, _fill(color), _str_ref(cat_ref), _num_ref(vals)))
    plot = ('<c:barChart><c:barDir val="bar"/><c:grouping val="stacked"/><c:varyColors val="0"/>%s<c:gapWidth val="60"/>'
            '<c:overlap val="100"/><c:axId val="501"/><c:axId val="502"/></c:barChart>%s'
            % ("".join(sers), _axes(501, 502, "l", "b", val_fmt)))
    return _chart_wrap(title, plot, legend="b")


def line_chart(title, cat_ref, series, val_fmt="#,##0", date_fmt="d mmm", val_title=None):
    """series: list of (name, values_ref, colour), names as plain text. Categories are dates when date_fmt is set."""
    sers = []
    for i, (name, vals, color) in enumerate(series):
        tx = "<c:tx><c:v>%s</c:v></c:tx>" % xesc(name)
        sers.append('<c:ser><c:idx val="%d"/><c:order val="%d"/>%s<c:spPr><a:ln w="22225" cap="rnd"><a:solidFill><a:srgbClr val="%s"/></a:solidFill>'
                    '<a:round/></a:ln></c:spPr><c:marker><c:symbol val="none"/></c:marker><c:cat>%s</c:cat><c:val>%s</c:val><c:smooth val="0"/></c:ser>'
                    % (i, i, tx, color, _num_ref(cat_ref) if date_fmt else _str_ref(cat_ref), _num_ref(vals)))
    plot = ('<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>%s<c:marker val="1"/><c:axId val="601"/><c:axId val="602"/></c:lineChart>%s'
            % ("".join(sers), _axes(601, 602, "b", "l", val_fmt, val_title=val_title, date_axis=bool(date_fmt), cat_fmt=date_fmt)))
    return _chart_wrap(title, plot, legend="b")
