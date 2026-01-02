# Manga Video Pipeline

An automated manga video pipeline for creating YouTube Shorts, TikTok, and Facebook Reels content from trending manga chapters.

## 🚀 Features

- **Trend Detection**: Automatically discovers trending manga from various sources
- **Chapter Scraping**: Downloads manga chapter images for processing
- **AI-Powered Summarization**: GPT-4o-mini generates engaging narration scripts
- **Text-to-Speech**: Converts chapters to audio using advanced TTS technology
- **Video Generation**: Creates vertical videos optimized for social media
- **Multi-Platform Upload**: Uploads to YouTube, TikTok, and Facebook simultaneously
- **Social Media Notifications**: Sends updates via Telegram bot
- **Automated Scheduling**: Processes new content on regular intervals
- **Dashboard Interface**: Monitor pipeline status and performance

## 🔧 Requirements

- **Python 3.13.3+** - Core programming language
- **Docker** - Containerization and orchestration
- **FFmpeg** - Video/audio processing
- **Redis** - Message queue and caching
- **Internet Connection** - For API calls and downloads

## 🚀 Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/manga-video-pipeline.git
   cd manga-video-pipeline
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

4. **Run the pipeline:**
   ```bash
   # Development
   uvicorn src.dashboard.app:app --reload
   
   # Or with Docker
   docker-compose up
   ```

5. **Access the dashboard:**
   - Navigate to `http://localhost:8000`
   - Monitor pipeline status and performance

## 💰 Cost Estimate

Monthly operational costs are estimated at **~$35/month**:

- **AWS EC2 t3.small**: ~$10/month
- **OpenAI API usage**: ~$15/month
- **Storage (S3)**: ~$5/month
- **CDN & Data transfer**: ~$5/month

Actual costs may vary based on usage volume and region.

## 📚 Documentation

- [Setup Guide](./docs/SETUP.md) - Installation and configuration
- [Architecture](./docs/ARCHITECTURE.md) - System design and components
- [Configuration](./docs/CONFIGURATION.md) - Environment variables and settings
- [Troubleshooting](./docs/TROUBLESHOOTING.md) - Common issues and solutions

## 🤝 Contributing

Contributions are welcome! See the [CONTRIBUTING.md](CONTRIBUTING.md) file for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

Made with ❤️ for manga enthusiasts worldwide!