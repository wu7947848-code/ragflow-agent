from PIL import Image, ImageDraw, ImageFont


W, H = 2480, 3508  # A4 at 300 DPI
OUT = "正式会议议程_A4_满版.png"

FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"


def font(path, size):
    return ImageFont.truetype(path, size)


def text_size(draw, text, fnt):
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw, text, fnt, max_width):
    lines = []
    current = ""
    for char in text:
        candidate = current + char
        if text_size(draw, candidate, fnt)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def draw_center(draw, xy, text, fnt, fill):
    x, y = xy
    tw, th = text_size(draw, text, fnt)
    draw.text((x - tw / 2, y), text, font=fnt, fill=fill)
    return th


def rounded_rect(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


img = Image.new("RGB", (W, H), "#f7f9fb")
draw = ImageDraw.Draw(img)

navy = "#142f4c"
blue = "#1f5d8f"
ink = "#1f2933"
muted = "#536170"
line = "#c8d3dd"
soft = "#eef4f8"
white = "#ffffff"

title_f = font(FONT_BOLD, 98)
subtitle_f = font(FONT_BOLD, 50)
meta_label_f = font(FONT_BOLD, 36)
meta_f = font(FONT_REG, 42)
time_f = font(FONT_BOLD, 42)
section_f = font(FONT_BOLD, 45)
body_f = font(FONT_REG, 35)
num_f = font(FONT_BOLD, 34)
footer_f = font(FONT_REG, 31)

# Page frame and accent line
draw.rectangle((0, 0, W, 34), fill=navy)
draw.rectangle((0, H - 34, W, H), fill=navy)
draw.rectangle((175, 210, 194, H - 255), fill=blue)

# Header
draw_center(draw, (W / 2, 160), "正式会议议程", title_f, navy)
theme = "大二学业规划、科研认知、考研指导与安全教育大会"
draw_center(draw, (W / 2, 292), theme, subtitle_f, ink)
draw.line((440, 390, W - 440, 390), fill=line, width=3)

# Meeting info band
band_x0, band_y0, band_x1, band_y1 = 265, 455, W - 265, 665
rounded_rect(draw, (band_x0, band_y0, band_x1, band_y1), 18, white, "#d9e1e8", 2)
cols = [
    ("会议时间", "本周四 15:40"),
    ("会议地点", "图书馆四楼报告厅"),
]
col_w = (band_x1 - band_x0) / 2
for i, (label, value) in enumerate(cols):
    x0 = band_x0 + i * col_w
    if i:
        draw.line((x0, band_y0 + 38, x0, band_y1 - 38), fill=line, width=2)
    draw.text((x0 + 78, band_y0 + 44), label, font=meta_label_f, fill=blue)
    draw.text((x0 + 78, band_y0 + 108), value, font=meta_f, fill=ink)

items = [
    (
        "15:40-15:50",
        "学生风采、才艺展示",
        "展示年级学生风貌，活跃会场氛围。",
    ),
    (
        "15:50-16:05",
        "胥院长发言",
        "为全体大二学生详细讲解考研整体规划、本校推免政策、申报条件、常见问题及后续深造发展建议。",
    ),
    (
        "16:05-16:45",
        "院内专业老师分享（2-3位老师）",
        "各位老师依次介绍个人研究方向、所在课题组科研内容、项目资源、研究特色及学生参与科研的途径，帮助同学们全面了解本院科研体系，为后续进组、科研实践做好铺垫。",
    ),
    (
        "16:45-17:00",
        "校外考研指导老师分享",
        "结合近年全国考研整体趋势、分数线变化、择校策略、备考重点及大二备考规划等内容进行分享。",
    ),
    (
        "17:00-17:15",
        "辅导员安全教育与底线纪律讲话",
        "围绕校园安全、日常行为规范、校规校纪、思想底线、学业底线等内容开展教育，强调大二关键阶段的自律意识与安全意识。",
    ),
]

start_y = 735
card_x0, card_x1 = 265, W - 265
num_x = card_x0 + 70
time_x = card_x0 + 145
text_x = card_x0 + 430
max_heading_w = card_x1 - text_x - 65
max_body_w = card_x1 - text_x - 65
y = start_y

for idx, (time_text, heading, body) in enumerate(items, start=1):
    heading_lines = wrap_text(draw, heading, section_f, max_heading_w)
    body_lines = wrap_text(draw, body, body_f, max_body_w)
    card_h = max(385, 78 + len(heading_lines) * 58 + 26 + len(body_lines) * 51 + 92)

    rounded_rect(draw, (card_x0, y, card_x1, y + card_h), 16, white, "#dce5ed", 2)
    draw.rectangle((card_x0, y, card_x0 + 12, y + card_h), fill=blue)

    cx, cy = num_x, y + 92
    draw.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), fill=soft, outline=blue, width=3)
    num = f"{idx:02d}"
    nw, nh = text_size(draw, num, num_f)
    draw.text((cx - nw / 2, cy - nh / 2 - 3), num, font=num_f, fill=blue)

    draw.text((time_x, y + 68), time_text, font=time_f, fill=blue)
    draw.line((text_x - 42, y + 58, text_x - 42, y + card_h - 58), fill="#d1dbe4", width=2)

    ty = y + 64
    for line_text in heading_lines:
        draw.text((text_x, ty), line_text, font=section_f, fill=navy)
        ty += 58
    ty += 10
    for line_text in body_lines:
        draw.text((text_x, ty), line_text, font=body_f, fill=muted)
        ty += 51

    if idx < len(items):
        draw.line((num_x, y + card_h + 5, num_x, y + card_h + 48), fill="#b7c8d6", width=3)
    y += card_h + 58

footer = "请参会同学提前到场，保持会场秩序。"
draw_center(draw, (W / 2, H - 165), footer, footer_f, muted)

img.save(OUT, dpi=(300, 300))
print(OUT)
