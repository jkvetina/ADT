simple = {
    # https://adaptivecards.io/designer/
    "type": "message",
    "attachments": [
        {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "TextBlock",
                    "size": "Large",
                    "weight": "Bolder",
                    "text": "#TITLE#",
                    "style": "heading",
                },
                {
                    "type": "TextBlock",
                    "text": "#MESSAGE#",
                }
            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.0",
            "msteams": {
                "entities": [],
                "width": "Full"
            }
        }
    }]
}

mentions = {
    "type"      : "mention",
    "text"      : "#AUTHOR#",
    "mentioned" : {
        "id"    : "#AUTHOR_MAIL#",
        "name"  : "#AUTHOR_NAME#"
    }
}

table_header = {
    "type": "Container",
    "items": [
        {
            "type": "ColumnSet",
            "columns": [
            ]
        }
    ],
    "bleed": False
}

table_header_col = {
    "type": "Column",
    "items": [
        {
            "type"      : "TextBlock",
            "weight"    : "Bolder",
            "text"      : "#TEXT#"
        }
    ],
    "width": "#WIDTH#"
}

table_row = {
    "type": "ColumnSet",
    "columns": [
    ],
    "bleed": False
}

table_row_col = {
    "type": "Column",
    "items": [
        {
            "type": "TextBlock",
            "text": "#TEXT#",
        }
    ],
    "width": "#WIDTH#"
}

