from __future__ import annotations

import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation


def create_template(path: str = "jobs_template.xlsx") -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "jobs"

    headers = [
        "account_id",
        "device_id",
        "post_url",
        "intent",
        "sentiment_tag",
        "comment_template",
        "priority",
        "description",
    ]
    ws.append(headers)

    examples = [
        ["acct_01", "R58M1234ABC", "https://instagram.com/p/AAA", "like", "positive", "", 5, "launch teaser post"],
        ["acct_02", "R58M1234ABC", "https://instagram.com/p/BBB", "comment", "neutral", "Great update", 4, "community engagement"],
        ["acct_03", "R58M1234ABC", "https://instagram.com/p/CCC", "like_and_comment", "positive", "", 5, "product release highlights"],
        ["acct_04", "R58M1234ABC", "https://instagram.com/p/DDD", "review", "neutral", "", 2, "content QA"],
        ["acct_05", "R58M1234ABC", "https://instagram.com/p/EEE", "post", "neutral", "", 3, "open post and verify"],
        ["acct_06", "R58M1234ABC", "https://instagram.com/p/FFF", "repost", "neutral", "", 3, "repost scenario"],
        ["acct_07", "R58M1234ABC", "https://instagram.com/p/GGG", "share", "neutral", "", 3, "share scenario"],
    ]
    for row in examples:
        ws.append(row)

    intent_dv = DataValidation(
        type="list",
        formula1='"review,launch,terminate,post,scroll,like,comment,repost,share,like_and_comment"',
        allow_blank=False,
    )
    ws.add_data_validation(intent_dv)
    intent_dv.add("D2:D5000")

    pri_dv = DataValidation(type="whole", operator="between", formula1="1", formula2="5")
    ws.add_data_validation(pri_dv)
    pri_dv.add("G2:G5000")

    for col, width in {
        "A": 16,
        "B": 16,
        "C": 40,
        "D": 18,
        "E": 14,
        "F": 34,
        "G": 10,
        "H": 40,
    }.items():
        ws.column_dimensions[col].width = width

    wb.save(path)


if __name__ == "__main__":
    create_template()
    print("Created jobs_template.xlsx")
