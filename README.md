# Jupyter Notebook Creator Bot 📚

A Telegram bot that instantly converts text messages into Jupyter notebooks and PDF documents.

Try it now: [Telegram bot](https://t.me/oiu_ipynb_bot)

## 🌟 Features

- **Easy Text-to-Notebook Conversion**: Transform your text messages into professional Jupyter notebooks
- **PDF Export**: Automatically generates PDF versions of your notebooks
- **Markdown & Code Support**: 
  - Use `@@@` for Markdown cells
  - Use `$$$` for Code cells
- **RTL Language Support**: Full support for Arabic and other right-to-left languages
- **User Management**: Track user interactions and usage statistics

## 🚀 Quick Start

1. Start a chat with the bot on Telegram
2. Send a message in this format:
```
@@@
# My First Notebook
This is a markdown cell

$$$
# This is a Python code cell
print("Hello, World!")

@@@
Here's another markdown cell
```
3. Receive your notebook and PDF files instantly!

## 💻 Technical Requirements

- Python 3.7+
- Required packages:
  - python-telegram-bot
  - nbformat
  - nbconvert
  - FPDF
  - Pillow
  - arabic-reshaper
  - python-bidi

## 🛠️ Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Set your Telegram Bot Token in environment variables
4. Run the bot:
```bash
python bot.py
```

## 🐳 Docker Support

Build and run with Docker:
```bash
docker build -t notebook-creator-bot .
docker run -e BOT_TOKEN=your_token notebook-creator-bot
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.
