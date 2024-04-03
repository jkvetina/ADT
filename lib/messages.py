simple = {
    # https://adaptivecards.io/designer/
    'type': 'message',
    'attachments': [
        {
        'contentType': 'application/vnd.microsoft.card.adaptive',
        'content': {
            'type': 'AdaptiveCard',
            'body': [
            ],
            'actions': [
            ],
            '$schema'           : 'http://adaptivecards.io/schemas/adaptive-card.json',
            'version'           : '1.6',
            'msteams'           : {
                'entities'      : [],
                'width'         : 'Full'
            }
        }
    }]
}

action_link = {
    'type'  : 'Action.OpenUrl',
    'title' : '#',
    'url'   : '#'
}

mentions = {
    'type'      : 'mention',
    'text'      : '#',
    'mentioned' : {
        'id'    : '#',
        'name'  : '#'
    }
}

table_header = {
    'type': 'Container',
    'items': [
        {
            'type': 'ColumnSet',
            'columns': [
            ]
        }
    ],
    'bleed': False
}

table_header_col = {
    'type': 'Column',
    'items': [
        {
            'type'      : 'TextBlock',
            'weight'    : 'Bolder',
            'text'      : '#'
        }
    ],
    'width': 'stretch'
}

table_row = {
    'type': 'ColumnSet',
    'columns': [
    ],
    'bleed': False
}

table_row_col = {
    'type': 'Column',
    'items': [
        {
            'type': 'TextBlock',
            'text': '#',
        }
    ],
    'width': 'stretch'
}

