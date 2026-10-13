"""Шаг 3: разбиение раздела терминов на статьи.

Статья — от якоря (номер в начале строки) до следующего якоря или конца раздела,
поэтому перенос статьи на следующую страницу склеивается сам.
"""
import re


def split_articles(lines, cfg):
    anchor = re.compile(cfg["numbering"]["anchor"])
    section = re.compile(cfg["numbering"]["section"])
    articles = []
    for page, line in lines:
        m = anchor.match(line)
        if m:
            num = m.group(0)
            articles.append({
                "num": num,
                "section": section.match(num).group(1),
                "page": page,
                "lines": [],
            })
        elif not articles:
            raise ValueError(f"текст до первой статьи (стр. {page}): {line}")
        articles[-1]["lines"].append((page, line))
    return articles


def raw_text(article):
    return "\n".join(line for _, line in article["lines"])
