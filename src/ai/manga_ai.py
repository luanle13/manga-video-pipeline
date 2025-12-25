import openai
from typing import Any, List
from ..config import get_settings


class MangaAI:
    """AI processing for manga content."""

    def __init__(self):
        self.settings = get_settings()
        openai.api_key = self.settings.openai.api_key

    async def summarize_chapters(self, chapter_texts: list[str]) -> str:
        """Summarize manga chapters using AI."""
        try:
            # Combine all chapter texts
            combined_text = "\n\n".join(chapter_texts)
            
            # Truncate if too long for the model
            if len(combined_text) > 120000:  # Approximate token limit
                combined_text = combined_text[:120000]
            
            response = await openai.ChatCompletion.acreate(
                model=self.settings.openai.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert manga summarizer. Create an engaging, concise summary of the manga chapters that captures the main plot, characters, and key moments. The summary should be suitable for a video voiceover."
                    },
                    {
                        "role": "user",
                        "content": f"Please summarize the following manga chapters:\n\n{combined_text}"
                    }
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content
            return summary
        except Exception as e:
            print(f"Error summarizing chapters: {e}")
            return "Summary not available."

    async def generate_tts(self, text: str, output_path: str) -> bool:
        """Generate TTS audio from text."""
        try:
            # Use OpenAI's TTS API
            response = await openai.Audio.aspeech(
                model=self.settings.openai.tts_model,
                voice=self.settings.openai.tts_voice,
                input=text
            )
            
            # Save the audio file
            with open(output_path, 'wb') as audio_file:
                audio_file.write(response.content)
            
            return True
        except Exception as e:
            print(f"Error generating TTS: {e}")
            return False

    async def generate_video_script(self, manga_info: dict[str, Any], summary: str) -> str:
        """Generate a video script from manga info and summary."""
        try:
            prompt = f"""
            Create a video script for a manga summary video. The script should be engaging and suitable for a video with images and narration. 

            Manga Info:
            - Title: {manga_info.get('title', 'Unknown')}
            - Description: {manga_info.get('description', '')}

            Summary:
            {summary}

            The script should include:
            1. An engaging introduction
            2. A narration part that covers the summary
            3. Suggestions for image placement (manga panels/cover art)
            4. A call-to-action at the end
            5. Total length should be suitable for a 5-10 minute video
            """
            
            response = await openai.ChatCompletion.acreate(
                model=self.settings.openai.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert video scriptwriter. Create engaging video scripts from manga content."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1500,
                temperature=0.8
            )
            
            script = response.choices[0].message.content
            return script
        except Exception as e:
            print(f"Error generating video script: {e}")
            return "Video script not available."


# Global AI instance
ai_processor = MangaAI()