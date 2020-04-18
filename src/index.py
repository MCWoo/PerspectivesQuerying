import boto3
import os
import requests

from bs4 import BeautifulSoup
from datetime import datetime
from datetime import timedelta

sns = boto3.client('sns')
sns_arn = os.environ['SnsTopicArn']

ddb = boto3.client('dynamodb')
classes_table_name = os.environ['DdbTableName']

perspectives_query_url = 'https://class.perspectives.org/Visitor/SearchResult.aspx?strState=ca'

def query_perspectives(event, context):
    # Make the request
    response = requests.get(perspectives_query_url)

    # Parse the HTML
    class_info = parse_classes(response.text)

    # Determine if any classes were added
    delta = get_class_delta(class_info=class_info, ddb_table_name=classes_table_name)

    if len(delta) > 0:
        save_classes(class_info=delta, ddb_table_name=classes_table_name)

        message = create_message(class_info=delta, link=perspectives_query_url)
        sns.publish(TopicArn=sns_arn, Message=message)
        print('Published to SNS! Message:\n{}'.format(message))
    else:
        print('No new classes to publish!')

    return {
            'statusCode': 200,
            'body': 'OK',
            }


def parse_classes(html):
    soup = BeautifulSoup(html, 'html.parser')

    # Main table
    table = soup.body.find(id='ctl00_ContentPlaceHolder1_grdSearchResult')

    class_info = {}
    session = 'unknown'
    tr_class = ''

    # For each row
    for tr in table.find_all('tr'):
        try:
            tr_class = tr['class'][0]
        except:
            continue

        # Defines the session name
        if tr_class.startswith('GroupHeader'):
            session = tr.td.text
            class_info[session] = {}

        # Defines the class info
        elif tr_class.startswith('GridRow'):
            tds = tr.find_all('td')
            name = tds[0].a.text
            class_info[session][name] = {
                'city': tds[1].span.text.strip(),
                'start': tds[3].span.text.strip(),
                'end': tds[4].span.text.strip(),
            }

    return class_info


def create_message(class_info, link):
    message = 'New Perspectives sessions!'
    for session in class_info.keys():
        message += '\n{}:\n'.format(session)

        for name in class_info[session].keys():
            message += '[{}]\tstarting {}\n'.format(
                    class_info[session][name]['city'],
                    class_info[session][name]['start'])

    message += '\n\nLink: {}'.format(link)

    return message


def get_class_delta(class_info, ddb_table_name):
    delta = {}
    count = 0
    
    for session in class_info:
        # Query ddb for each session
        response = ddb.query(TableName=ddb_table_name,
                Select='SPECIFIC_ATTRIBUTES',
                ProjectionExpression='#name',
                KeyConditionExpression='#session = :session',
                ExpressionAttributeNames={ '#session': 'session', '#name': 'name' },
                ExpressionAttributeValues={ ':session': { 'S': session } })

        # clean the list for searching
        ddb_class_names = [item['name']['S'] for item in response['Items']]
        for name in class_info[session]:
            # Put any class name that wasn't in DDB into the delta
            if name not in ddb_class_names:
                if session not in delta:
                    delta[session] = {}

                delta[session][name] = class_info[session][name]
                count += 1

    print('Delta contains {} new class{}'.format(count, '' if count == 1 else 'es'))
    return delta


def save_classes(class_info, ddb_table_name):
    one_year = timedelta(days=365)

    now = datetime.utcnow().replace(microsecond=0)
    now_iso = now.isoformat() + 'Z'
    request_items = {}
    request_items[ddb_table_name] = [{
            'PutRequest': {
                'Item': {
                    'session': { 'S': session },
                    'name': { 'S': name },
                    'city': { 'S': class_info[session][name]['city'] },
                    'start': { 'S': class_info[session][name]['start'] },
                    'end': { 'S': class_info[session][name]['end'] },
                    'created': { 'S': now_iso },
                    'modified': { 'S': now_iso },
                    'ttl': { 'N': str((now + one_year).timestamp()) },
                }
            }
        }
        for session in class_info for name in class_info[session]
    ]

    response = ddb.batch_write_item(RequestItems=request_items)

    while 'UnprocessedItems' in response and len(response['UnprocessedItems']) > 0:
        print('{}'.format(response['UnprocessedItems']))
        response = ddb.batch_write_item(RequestItems=response['UnprocessedItems'])


if __name__ == '__main__':
    query_perspectives({}, {})
