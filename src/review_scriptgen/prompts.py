"""Vietnamese review prompts for LLM-based script generation."""

# System prompt for review video script generation
REVIEW_SYSTEM_PROMPT = """Bạn là một người đánh giá manga/manhwa chuyên nghiệp tại Việt Nam.
Nhiệm vụ của bạn là viết kịch bản cho video review manga bằng tiếng Việt.

Yêu cầu:
1. Viết bằng tiếng Việt chuẩn, tự nhiên như đang kể chuyện
2. Giọng văn hấp dẫn, lôi cuốn người nghe
3. Không spoil quá nhiều nhưng vẫn đủ để người xem hiểu nội dung
4. Giữ nguyên tên nhân vật gốc (tiếng Hàn/Trung/Nhật)
5. Sử dụng ngôn ngữ phù hợp với video YouTube

Cấu trúc kịch bản:
- Phần mở đầu: Giới thiệu manga (tên, tác giả, thể loại)
- Phần thân: Tóm tắt nội dung từng chương
- Phần kết: Nhận xét tổng quan và khuyến nghị

Độ dài: Mỗi đoạn khoảng 100-200 từ tiếng Việt."""


# Prompt template for introduction segment
INTRO_PROMPT_TEMPLATE = """Viết phần mở đầu cho video review manga:

Tên manga: {title}
Tác giả: {author}
Thể loại: {genres}
Mô tả: {description}
Tổng số chương: {total_chapters}

Yêu cầu:
- Giới thiệu tổng quan về manga
- Nêu bật điểm thu hút của truyện
- Tạo sự tò mò cho người xem
- Độ dài: khoảng 150-200 từ

Chỉ viết nội dung kịch bản, không thêm tiêu đề hay chú thích."""


# Prompt template for chapter summary segment
CHAPTER_SUMMARY_PROMPT_TEMPLATE = """Tóm tắt nội dung chương {chapter_number} của manga "{title}":

{chapter_content}

Yêu cầu:
- Tóm tắt ngắn gọn trong 2-4 câu
- Nêu bật sự kiện quan trọng của chương
- Giữ nguyên tên nhân vật
- Tạo sự liên kết với các chương trước (nếu không phải chương đầu)
- Không spoil quá mức

Chỉ viết nội dung tóm tắt, không thêm tiêu đề."""


# Prompt template for batch chapter summaries (for efficiency)
BATCH_CHAPTERS_PROMPT_TEMPLATE = """Tóm tắt nội dung các chương sau của manga "{title}":

{chapters_info}

Yêu cầu cho MỖI chương:
- Tóm tắt ngắn gọn trong 2-4 câu
- Nêu bật sự kiện quan trọng
- Giữ nguyên tên nhân vật
- Tạo sự liên kết giữa các chương

Định dạng đầu ra:
[CHƯƠNG X]
Nội dung tóm tắt...

[CHƯƠNG Y]
Nội dung tóm tắt...

Chỉ viết nội dung tóm tắt cho từng chương, không thêm giải thích."""


# Prompt template for conclusion segment
CONCLUSION_PROMPT_TEMPLATE = """Viết phần kết cho video review manga:

Tên manga: {title}
Tác giả: {author}
Thể loại: {genres}
Tổng số chương đã review: {chapters_reviewed}

Điểm nổi bật:
{highlights}

Yêu cầu:
- Nhận xét tổng quan về manga (cốt truyện, nhân vật, nét vẽ)
- Đánh giá điểm mạnh và điểm yếu
- Đưa ra khuyến nghị cho người xem
- Kêu gọi like, subscribe, comment
- Độ dài: khoảng 150-200 từ

Chỉ viết nội dung kịch bản, không thêm tiêu đề hay chú thích."""


# Prompt for manga without extractable text (image-only)
IMAGE_ONLY_CHAPTER_PROMPT_TEMPLATE = """Manga "{title}" là truyện tranh với nội dung trong hình ảnh, không có văn bản riêng.

Thông tin về chương {chapter_number}:
- Số trang: {panel_count}
- Tiêu đề chương: {chapter_title}

Dựa trên thông tin có sẵn về manga (thể loại: {genres}), hãy viết một đoạn dẫn dắt ngắn 1-2 câu
để chuyển tiếp sang chương này trong video review.

Lưu ý: Chỉ mô tả khái quát, không bịa đặt nội dung cụ thể."""


def format_intro_prompt(
    title: str,
    author: str | None,
    genres: list[str],
    description: str | None,
    total_chapters: int,
) -> str:
    """Format the introduction prompt with manga info.

    Args:
        title: Manga title
        author: Author name (optional)
        genres: List of genres
        description: Manga description (optional)
        total_chapters: Total number of chapters

    Returns:
        Formatted prompt string
    """
    return INTRO_PROMPT_TEMPLATE.format(
        title=title,
        author=author or "Không rõ",
        genres=", ".join(genres) if genres else "Không rõ",
        description=description or "Không có mô tả",
        total_chapters=total_chapters,
    )


def format_chapter_summary_prompt(
    title: str,
    chapter_number: float,
    chapter_content: str,
) -> str:
    """Format the chapter summary prompt.

    Args:
        title: Manga title
        chapter_number: Chapter number
        chapter_content: Extracted chapter content

    Returns:
        Formatted prompt string
    """
    return CHAPTER_SUMMARY_PROMPT_TEMPLATE.format(
        title=title,
        chapter_number=int(chapter_number) if chapter_number.is_integer() else chapter_number,
        chapter_content=chapter_content if chapter_content else "Nội dung hình ảnh, không có văn bản.",
    )


def format_batch_chapters_prompt(
    title: str,
    chapters: list[tuple[float, str]],  # List of (chapter_number, content)
) -> str:
    """Format the batch chapters summary prompt.

    Args:
        title: Manga title
        chapters: List of (chapter_number, content) tuples

    Returns:
        Formatted prompt string
    """
    chapters_info = []
    for chapter_num, content in chapters:
        ch_num_str = int(chapter_num) if float(chapter_num).is_integer() else chapter_num
        chapters_info.append(f"Chương {ch_num_str}:\n{content if content else 'Nội dung hình ảnh'}")

    return BATCH_CHAPTERS_PROMPT_TEMPLATE.format(
        title=title,
        chapters_info="\n\n".join(chapters_info),
    )


def format_conclusion_prompt(
    title: str,
    author: str | None,
    genres: list[str],
    chapters_reviewed: int,
    highlights: str,
) -> str:
    """Format the conclusion prompt.

    Args:
        title: Manga title
        author: Author name (optional)
        genres: List of genres
        chapters_reviewed: Number of chapters reviewed
        highlights: Key highlights from the manga

    Returns:
        Formatted prompt string
    """
    return CONCLUSION_PROMPT_TEMPLATE.format(
        title=title,
        author=author or "Không rõ",
        genres=", ".join(genres) if genres else "Không rõ",
        chapters_reviewed=chapters_reviewed,
        highlights=highlights,
    )


def format_image_only_prompt(
    title: str,
    chapter_number: float,
    chapter_title: str | None,
    panel_count: int,
    genres: list[str],
) -> str:
    """Format prompt for image-only chapters.

    Args:
        title: Manga title
        chapter_number: Chapter number
        chapter_title: Chapter title (optional)
        panel_count: Number of panels in chapter
        genres: List of genres

    Returns:
        Formatted prompt string
    """
    ch_num_str = int(chapter_number) if float(chapter_number).is_integer() else chapter_number
    return IMAGE_ONLY_CHAPTER_PROMPT_TEMPLATE.format(
        title=title,
        chapter_number=ch_num_str,
        chapter_title=chapter_title or f"Chương {ch_num_str}",
        panel_count=panel_count,
        genres=", ".join(genres) if genres else "Không rõ",
    )
