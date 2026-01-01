from playwright.async_api import async_playwright
from datetime import datetime
from typing import Any
from .base import DiscoverySource, MangaInfo, ChapterInfo


class WebtoonSource(DiscoverySource):
    """Webtoon.com scraping implementation for discovery."""
    
    def __init__(self):
        self.base_url = "https://www.webtoons.com"
        self.playwright = None
        self.browser = None
        self.context = None
    
    async def _init_browser(self):
        """Initialize the Playwright browser."""
        if self.playwright is None:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
    
    async def get_trending(self, limit: int = 20) -> list[MangaInfo]:
        """Get trending webtoons from webtoons.com."""
        await self._init_browser()
        
        try:
            page = await self.context.new_page()
            
            # Navigate to the trending page (usually home or popular page)
            await page.goto(f"{self.base_url}/en/dailySchedule")
            await page.wait_for_load_state('networkidle')
            
            # Find trending webtoon elements
            webtoon_elements = await page.query_selector_all('div.daily_lst li')
            
            mangas = []
            for i, element in enumerate(webtoon_elements[:limit]):
                if i >= limit:
                    break
                
                try:
                    # Extract title
                    title_element = await element.query_selector('a span')
                    title = await title_element.text_content() if title_element else "Unknown"
                    title = title.strip()
                    
                    # Extract ID from the link
                    link_element = await element.query_selector('a')
                    href = await link_element.get_attribute('href') if link_element else ""
                    webtoon_id = None
                    if href:
                        # Extract webtoon ID from URL
                        import re
                        match = re.search(r'titleId=(\d+)', href)
                        if match:
                            webtoon_id = match.group(1)
                    
                    # Extract cover image
                    img_element = await element.query_selector('img')
                    cover_url = await img_element.get_attribute('src') if img_element else None
                    
                    if webtoon_id:
                        manga_info = MangaInfo(
                            source='webtoon',
                            source_id=webtoon_id,
                            title=title,
                            cover_url=cover_url,
                            trending_rank=i + 1,  # Rank based on position
                            genres=None  # Genres not easily available on this page
                        )
                        mangas.append(manga_info)
                except Exception as e:
                    print(f"Error parsing webtoon element: {e}")
                    continue
            
            await page.close()
            return mangas
        except Exception as e:
            print(f"Error fetching trending webtoons: {e}")
            return []
    
    async def get_chapters(self, manga_id: str) -> list[ChapterInfo]:
        """Get all chapters for a specific webtoon."""
        await self._init_browser()
        
        try:
            page = await self.context.new_page()
            
            # Navigate to the webtoon's main page
            await page.goto(f"{self.base_url}/en/webtoon/list?titleId={manga_id}")
            await page.wait_for_load_state('networkidle')
            
            chapters = []
            
            # Find chapter elements (using the actual selectors from webtoons.com)
            chapter_elements = await page.query_selector_all('li._episode_item')
            
            for element in chapter_elements:
                try:
                    # Extract chapter number
                    subtitle_element = await element.query_selector('.sub_title span')
                    subtitle_text = await subtitle_element.text_content() if subtitle_element else ""
                    
                    # Extract number from subtitle (usually in format like "EP 123")
                    import re
                    match = re.search(r'EP\s*(\d+(?:\.\d+)?)', subtitle_text, re.IGNORECASE)
                    if match:
                        chapter_number = float(match.group(1))
                    else:
                        # If we can't parse the chapter number, try to extract any number
                        numbers = re.findall(r'\d+(?:\.\d+)?', subtitle_text)
                        if numbers:
                            chapter_number = float(numbers[0])
                        else:
                            continue  # Skip if no chapter number found
                    
                    # Extract chapter URL
                    link_element = await element.query_selector('a')
                    href = await link_element.get_attribute('href') if link_element else None
                    if href and not href.startswith('http'):
                        href = self.base_url + href
                    
                    # Extract title if available
                    title_element = await element.query_selector('.sub_title a')
                    title_text = await title_element.text_content() if title_element else f"Episode {chapter_number}"
                    title_text = title_text.strip()
                    
                    # Extract published date if available
                    date_element = await element.query_selector('.date')
                    date_text = await date_element.text_content() if date_element else None
                    published_at = None
                    if date_text:
                        try:
                            # Date could be in various formats like "2 hours ago", "2 days ago", "Dec 25, 2023"
                            # For now, we'll just use today if it says "today" or "yesterday", else None
                            from datetime import date, timedelta
                            today = date.today()
                            if "today" in date_text.lower():
                                published_at = datetime.combine(today, datetime.min.time())
                            elif "yesterday" in date_text.lower():
                                yesterday = today - timedelta(days=1)
                                published_at = datetime.combine(yesterday, datetime.min.time())
                            else:
                                # Try to parse dates like "Dec 25, 2023"
                                # This is a simplified parsing - in a full implementation, we'd need more robust date parsing
                                import re
                                date_match = re.search(r'(\w+)\s+(\d{1,2}),\s*(\d{4})', date_text)
                                if date_match:
                                    month_str, day_str, year_str = date_match.groups()
                                    # Simple date parsing - in a real implementation we'd use dateutil
                                    from datetime import date
                                    try:
                                        # Attempt simple month name to number conversion
                                        months = {
                                            'jan': 1, 'january': 1,
                                            'feb': 2, 'february': 2,
                                            'mar': 3, 'march': 3,
                                            'apr': 4, 'april': 4,
                                            'may': 5,
                                            'jun': 6, 'june': 6,
                                            'jul': 7, 'july': 7,
                                            'aug': 8, 'august': 8,
                                            'sep': 9, 'september': 9,
                                            'oct': 10, 'october': 10,
                                            'nov': 11, 'november': 11,
                                            'dec': 12, 'december': 12
                                        }
                                        month_num = months.get(month_str.lower(), 1)  # Default to January if parsing fails
                                        parsed_date = date(int(year_str), month_num, int(day_str))
                                        published_at = datetime.combine(parsed_date, datetime.min.time())
                                    except:
                                        published_at = None
                        except:
                            published_at = None
                    
                    chapter_info = ChapterInfo(
                        chapter_number=chapter_number,
                        source_url=href,
                        title=title_text,
                        published_at=published_at
                    )
                    chapters.append(chapter_info)
                except Exception as e:
                    print(f"Error parsing chapter element: {e}")
                    continue
            
            await page.close()
            return chapters
        except Exception as e:
            print(f"Error fetching chapters for webtoon {manga_id}: {e}")
            return []
    
    async def get_new_chapters(self, manga_id: str, since: datetime) -> list[ChapterInfo]:
        """Get new chapters for a specific webtoon since a given date."""
        all_chapters = await self.get_chapters(manga_id)
        
        # Filter chapters that were published after the 'since' date
        new_chapters = []
        for chapter in all_chapters:
            if chapter.published_at and chapter.published_at > since:
                new_chapters.append(chapter)
        
        return new_chapters
    
    async def close(self):
        """Close the Playwright browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()