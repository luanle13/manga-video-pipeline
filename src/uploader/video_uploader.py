import os
import json
from typing import Any
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from ..config import get_settings


class VideoUploader:
    """Upload videos to various platforms."""
    
    def __init__(self):
        self.settings = get_settings()
        self.youtube_service = self._get_youtube_service()
    
    def _get_youtube_service(self):
        """Get authenticated YouTube service."""
        try:
            creds = None
            # The file token.json stores the user's access and refresh tokens.
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/youtube.upload'])
            
            # If there are no (valid) credentials available, let the user log in.
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.settings.youtube.en_credentials_path,
                        ['https://www.googleapis.com/auth/youtube.upload']
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
            
            return build('youtube', 'v3', credentials=creds)
        except Exception as e:
            print(f"Error setting up YouTube service: {e}")
            return None

    async def upload_to_youtube(self, video_path: str, title: str, description: str, tags: list = None) -> dict[str, Any]:
        """Upload video to YouTube."""
        if not self.youtube_service:
            return {"success": False, "error": "YouTube service not available"}
        
        try:
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags or [],
                    'categoryId': '24'  # People & Blogs category
                },
                'status': {
                    'privacyStatus': 'public'
                }
            }
            
            # Upload the video
            media = MediaFileUpload(
                video_path,
                mimetype='video/mp4',
                resumable=True
            )
            
            request = self.youtube_service.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"Uploaded {int(status.progress() * 100)}%.")
            
            return {
                "success": True,
                "video_id": response.get('id'),
                "url": f"https://www.youtube.com/watch?v={response.get('id')}"
            }
        except Exception as e:
            print(f"Error uploading to YouTube: {e}")
            return {"success": False, "error": str(e)}

    async def upload_to_tiktok(self, video_path: str, title: str) -> dict[str, Any]:
        """Upload video to TikTok (placeholder implementation)."""
        # Note: TikTok doesn't have an official API for uploading
        # This would require using browser automation or third-party services
        print("TikTok upload is not fully implemented yet")
        return {"success": False, "error": "TikTok upload not implemented"}

    async def upload_to_facebook(self, video_path: str, title: str, description: str) -> dict[str, Any]:
        """Upload video to Facebook."""
        # Facebook video upload implementation
        # This is a simplified approach - a full implementation would require proper API calls
        try:
            import requests
            
            # Use the Graph API to upload the video
            url = f"https://graph.facebook.com/v18.0/{self.settings.facebook.en_page_id}/videos"
            params = {
                'access_token': self.settings.facebook.en_access_token,
                'description': title + "\n\n" + description
            }
            
            with open(video_path, 'rb') as video_file:
                files = {'source': video_file}
                response = requests.post(url, params=params, files=files)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "video_id": result.get('id'),
                    "url": f"https://www.facebook.com/{settings.facebook_page_id}/videos/{result.get('id')}"
                }
            else:
                return {"success": False, "error": f"Facebook API error: {response.text}"}
        except Exception as e:
            print(f"Error uploading to Facebook: {e}")
            return {"success": False, "error": str(e)}


# Global uploader instance
uploader = VideoUploader()