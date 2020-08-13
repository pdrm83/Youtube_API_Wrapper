import os
import pickle

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from urllib.parse import urlparse, parse_qs

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


class YoutubeEasyWrapper:
    def __init__(self):
        self.service = None

    def initialize(self, credentials_path):
        client_secrets_file = os.path.join(credentials_path, 'client_secret.json')
        credentials = None
        if os.path.exists(os.path.join(credentials_path, 'token.pickle')):
            with open(os.path.join(credentials_path, 'token.pickle'), 'rb') as token:
                credentials = pickle.load(token)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
                credentials = flow.run_console()

            with open(os.path.join(credentials_path, 'token.pickle'), 'wb') as token:
                pickle.dump(credentials, token)

        self.service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)

    def search_videos_by_keywords(self, **kwargs):
        items = []
        results = self.service.search().list(**kwargs).execute()

        current_page = 0
        max_pages = 3
        while results and current_page < max_pages:
            items.extend(results['items'])

            if 'nextPageToken' in results:
                kwargs['pageToken'] = results['nextPageToken']
                results = self.service.search().list(**kwargs).execute()
                current_page += 1
            else:
                break

        output = []
        for item in items:
            result = dict()
            result['title'] = item['snippet']['title']
            result['channel'] = item['snippet']['channelTitle']
            result['video_id'] = item['id']['videoId']
            output.append(result)

        return output

    def get_video_details(self, video_id):
        list_videos_by_id = self.service.videos().list(id=video_id,
                                                       part="id, snippet, contentDetails, statistics").execute()
        results = list_videos_by_id.get("items", [])[0]
        output = dict.fromkeys(['title', 'description', 'publishedAt', 'tags', 'contentDetails', 'statistics'], None)

        output['title'] = results['snippet']['title']
        output['description'] = results['snippet']['description']
        output['publishedAt'] = results['snippet']['publishedAt']
        output['contentDetails'] = results['contentDetails']
        output['statistics'] = results['statistics']

        if results['statistics']['commentCount']:
            output['comments'] = self.extract_video_comments(self.service,
                                                             part='snippet',
                                                             videoId=video_id,
                                                             textFormat='plainText')

        return output

    @staticmethod
    def extract_video_id(url):
        url_data = urlparse(url)
        query = parse_qs(url_data.query)
        video_id = query["v"][0]
        return video_id

    @staticmethod
    def extract_video_comments(service, **kwargs):
        comments = []

        try:
            results = service.commentThreads().list(**kwargs).execute()
        except HttpError:
            print('The video has disabled comments.')
            return

        while results:
            for item in results['items']:
                comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                comments.append(comment)
            if 'nextPageToken' in results:
                kwargs['pageToken'] = results['nextPageToken']
                results = service.commentThreads().list(**kwargs).execute()
            else:
                break

        return comments
