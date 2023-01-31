#!/usr/bin/python
import argparse
import http.client as httplib
import httplib2
import os
import random
import time

# import urllib.request
# import urllib.error
 
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets

from oauth2client import tools

# from oauth2client.tools import run
from apiclient.discovery import build


import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow

# Explicitly tell the underlying HTTP transport library not to retry, since
# we are handling retry logic ourselves.
httplib2.RETRIES = 1

# Maximum number of times to retry before giving up.
MAX_RETRIES = 10

# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, httplib.NotConnected,
  httplib.IncompleteRead, httplib.ImproperConnectionState,
  httplib.CannotSendRequest, httplib.CannotSendHeader,
  httplib.ResponseNotReady, httplib.BadStatusLine)

# Always retry when an apiclient.errors.HttpError with one of these status
# codes is raised.
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the {{ Google Cloud Console }} at
# {{ https://cloud.google.com/console }}.
# Please ensure that you have enabled the YouTube Data API for your project.
# For more information about using OAuth2 to access the YouTube Data API, see:
#   https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client_secrets.json file format, see:
#   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets

# This OAuth 2.0 access scope allows an application to upload files to the
# authenticated user's YouTube channel, but doesn't allow other types of access.
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

VALID_PRIVACY_STATUSES = ('public', 'private', 'unlisted')

def filename(path):
  return os.path.basename(path)
  
# Authorize the request and store authorization credentials.
def get_authenticated_service(client_secret_file):
  client_secret_name, _ext = os.path.splitext(filename(client_secret_file))
  if not os.path.exists("/content/drive/MyDrive/youtube_upload"):
     os.makedirs("/content/drive/MyDrive/youtube_upload")
     os.makedirs("/content/drive/MyDrive/youtube_upload/credentials")

  folder_containing_credential = "/content/drive/MyDrive/youtube_upload/credentials/" + client_secret_name
  if not os.path.exists(folder_containing_credential):
    os.makedirs(folder_containing_credential)
    print("making folder containing credentials for {}".format(client_secret_name))
  else:
    print("folder containing credentials for {} exists".format(client_secret_name))
    
  credential_json = folder_containing_credential + "/" + "credentials_for_" + client_secret_name + ".json"
  storage = Storage(credential_json)
  credentials = storage.get()
  if credentials is None or credentials.invalid:
    flow = flow_from_clientsecrets(client_secret_file, SCOPES)
    flags = tools.argparser.parse_args(args=['--noauth_local_webserver'])
    credentials = tools.run_flow(flow, storage, flags)

  return build(API_SERVICE_NAME, API_VERSION, credentials = credentials)


def initialize_upload(youtube, options):
  tags = None
  if options.keywords:
    tags = options.keywords.split(',')

  body=dict(
    snippet=dict(
      title=options.title,
      description=options.description,
      tags=tags,
      categoryId=options.category,
      defaultLanguage=options.default_language,
      defaultAudioLanguage=options.default_audio_language,
      language=options.language
    ),
    status=dict(
      privacyStatus=options.privacyStatus
    )
  )

  # Call the API's videos.insert method to create and upload the video.
  insert_request = youtube.videos().insert(
    part=','.join(body.keys()),
    body=body,
    # The chunksize parameter specifies the size of each chunk of data, in
    # bytes, that will be uploaded at a time. Set a higher value for
    # reliable connections as fewer chunks lead to faster uploads. Set a lower
    # value for better recovery on less reliable connections.
    #
    # Setting 'chunksize' equal to -1 in the code below means that the entire
    # file will be uploaded in a single HTTP request. (If the upload fails,
    # it will still be retried where it left off.) This is usually a best
    # practice, but if you're using Python older than 2.6 or if you're
    # running on App Engine, you should set the chunksize to something like
    # 1024 * 1024 (1 megabyte).
    media_body=MediaFileUpload(options.file, chunksize=-1, resumable=True)
  )

  resumable_upload(insert_request)

# This method implements an exponential backoff strategy to resume a
# failed upload.
def resumable_upload(request):
  response = None
  error = None
  retry = 0
  while response is None:
    try:
      print('Uploading file...')
      status, response = request.next_chunk()
      if response is not None:
        if 'id' in response:
          print("Video id {} was successfully uploaded.".format(response['id']))
          print("https://www.youtube.com/watch?v={}".format(response['id']))
        else:
          exit('The upload failed with an unexpected response: %s' % response)
    except HttpError as e:
      if e.resp.status in RETRIABLE_STATUS_CODES:
        error = 'A retriable HTTP error %d occurred:\n%s' % (e.resp.status,
                                                             e.content)
      else:
        raise
    except RETRIABLE_EXCEPTIONS as e:
      error = 'A retriable error occurred: %s' % e

    if error is not None:
      print(error)
      retry += 1
      if retry > MAX_RETRIES:
        exit('No longer attempting to retry.')

      max_sleep = 2 ** retry
      sleep_seconds = random.random() * max_sleep
      print("Sleeping {} seconds and then retrying...".format(sleep_seconds))
      time.sleep(sleep_seconds)

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--json', required=True, help='Client secrets file')
  parser.add_argument('--file', required=True, help='Video file to upload')
  parser.add_argument('--title', help='Video title', default='Test Title')
  parser.add_argument('--description', help='Video description',
    default='')
  parser.add_argument('--category', default='22',
    help='Numeric video category. ' +
      'See https://developers.google.com/youtube/v3/docs/videoCategories/list')
  parser.add_argument('--keywords', help='Video keywords, comma separated',
    default='')
  parser.add_argument('--privacyStatus', choices=VALID_PRIVACY_STATUSES,
    default='public', help='Video privacy status.')

  parser.add_argument('--language',
      default=None,
      help="Language (ISO 639-1: en | fr | de | ...)")

  parser.add_argument('--default_language',
      default=None,
      help="Default language (ISO 639-1: en | fr | de | ...)")
  parser.add_argument('--default_audio_language',
      default=None,
      help="Default audio language (ISO 639-1: en | fr | de | ...)")
      
  args = parser.parse_args()

  youtube = get_authenticated_service(args.json)

  try:
    initialize_upload(youtube, args)
  except HttpError as e:
    print("An HTTP error {} occurred:\n{}".format(e.resp.status, e.content))
