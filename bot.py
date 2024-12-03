import os
import nbformat
import base64
from nbconvert.preprocessors import ExecutePreprocessor
from fpdf import FPDF
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from io import BytesIO
from PIL import Image
import arabic_reshaper
from bidi.algorithm import get_display
import json
from typing import Dict, List
import logging


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

USERS_FILE = 'users.json'
ADMIN_ID = 'add your admin id' # add your admin id here

def load_users() -> Dict:
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users(users: Dict):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

def reshape_arabic(text):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

def is_rtl_text(text):
    return any('\u0600' <= char <= '\u06FF' for char in text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Log the start command
    logger.info(f"Received start command from user {update.effective_user.id}")
    try:
        # Get user information
        user = update.effective_user
        users = load_users()
        # Store user details in the database
        users[str(user.id)] = {
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'joined_date': str(update.message.date)
        }
        save_users(users)
        logger.info(f"Saved user data for {user.id}")

        # Send welcome message with usage instructions
        await update.message.reply_text(
            f"Welcome {user.first_name}!\n\n"
            "Send me a text and i'll convert it to a Notebook and a pdf\n\n"
            "You should start with @@@\n\n"
            "use @@@ as a Markdown cell\n\n"
            "use $$$ as a code cell\n\n"
            "Example:\n"
            "@@@\nThis is an example"
            "$$$\nimport numpy as np\nimport pandas as pd\n$$$\nprint(\"Hello world!\")\n"
        )
        logger.info(f"Sent welcome message to user {user.id}")
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}", exc_info=True)
        await update.message.reply_text("An error occurred. Please try again later.")



async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if user is admin
    if str(update.effective_user.id) != str(ADMIN_ID):
        await update.message.reply_text("Sorry, only admin can use this command.")
        return

    # Validate broadcast message
    if not context.args:
        await update.message.reply_text("Please provide a message to broadcast.\nUsage: /broadcast your message")
        return

    broadcast_message = ' '.join(context.args)
    users = load_users()
    
    # Check if there are any users
    if not users:
        await update.message.reply_text("No users found in the database.")
        return
        
    # Initialize progress tracking
    progress_msg = await update.message.reply_text("Broadcasting message...\n[□□□□□□□□□□] 0%")
    total_users = len(users)
    success_count = 0
    fail_count = 0

    # Send message to each user with progress updates
    for i, (user_id, user_data) in enumerate(users.items(), 1):
        try:
            await context.bot.send_message(chat_id=user_id, text=broadcast_message)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send message to user {user_id}: {str(e)}")
            fail_count += 1
        
        # Update progress every 5 users or at completion
        if i % 5 == 0 or i == total_users:
            progress = int((i / total_users) * 10)
            progress_bar = "■" * progress + "□" * (10 - progress)
            percent = int((i / total_users) * 100)
            await progress_msg.edit_text(
                f"Broadcasting message...\n[{progress_bar}] {percent}%\n"
                f"Sent: {success_count} | Failed: {fail_count}"
            )

    # Show final broadcast results
    await progress_msg.edit_text(
        f"✅ Broadcast complete!\n"
        f"Successfully sent to: {success_count} users\n"
        f"Failed to send to: {fail_count} users"
    )

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if user is admin
    if str(update.effective_user.id) != str(ADMIN_ID):
        await update.message.reply_text("Sorry, only admin can use this command.")
        return

    users = load_users()
    if not users:
        await update.message.reply_text("No users found in the database.")
        return

    # Format user list with detailed information
    user_list = "📊 Registered Users:\n\n"
    for user_id, user_data in users.items():
        username = user_data.get('username', 'No username')
        first_name = user_data.get('first_name', 'No first name')
        last_name = user_data.get('last_name', '')
        joined_date = user_data.get('joined_date', 'Unknown')
        
        user_info = (
            f"👤 User ID: {user_id}\n"
            f"📝 Username: @{username}\n"
            f"👋 Name: {first_name} {last_name}\n"
            f"📅 Joined: {joined_date}\n"
            f"{'─' * 30}\n"
        )
        user_list += user_info

    # Split long messages to comply with Telegram's message length limit
    if len(user_list) > 4000:
        parts = [user_list[i:i+4000] for i in range(0, len(user_list), 4000)]
        for i, part in enumerate(parts, 1):
            await update.message.reply_text(f"Part {i}/{len(parts)}\n\n{part}")
    else:
        await update.message.reply_text(user_list)


def parse_cells(user_text: str):
    # Split text into blocks using $$$ as delimiter
    cell_contents = [block.strip() for block in user_text.split("$$$\n") if block.strip()]
    cells = []

    for block in cell_contents:
        # Create markdown cell if block starts with @@@
        if block.startswith("@@@"):
            cells.append(nbformat.v4.new_markdown_cell(block[len("@@@"):].strip()))
        else:
            # Create code cell for other blocks
            code = block
            # Add plt.show() if matplotlib is used but not explicitly called
            if 'plt.' in code and not code.strip().endswith('plt.show()'):
                code = f"{code}\nplt.show()\nplt.close('all')"
            cells.append(nbformat.v4.new_code_cell(code))

    return cells


def execute_notebook(nb):
    # Add initial setup cell for matplotlib configuration
    setup_cell = nbformat.v4.new_code_cell(
        """
        import matplotlib.pyplot as plt
        plt.close('all')
        %matplotlib inline
        """
    )
    nb.cells.insert(0, setup_cell)
    
    # Execute all cells in the notebook
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    
    try:
        ep.preprocess(nb, {"metadata": {"path": "./"}})
        
        # Clean up matplotlib plots after execution
        for cell in nb.cells:
            if cell.cell_type == 'code' and 'plt' in cell.source:
                plt.close('all')
                
    except Exception as e:
        logger.error(f"Error executing notebook: {str(e)}")
        # Add error message as a new cell if execution fails
        error_cell = nbformat.v4.new_code_cell(f"Error During Execution: {str(e)}")
        nb.cells.append(error_cell)
    
    # Remove the setup cell after execution
    nb.cells.pop(0)


def create_pdf_from_notebook(notebook, pdf_filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf", uni=True)
    pdf.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf", uni=True)
    
    for cell in notebook.cells:
        if cell.cell_type == "markdown":
            pdf.set_font("DejaVu", style='B', size=16)
            text = cell.source
            if is_rtl_text(text):
                pdf.set_right_margin(10)
                pdf.set_left_margin(10)
                text = reshape_arabic(text)
                pdf.r_margin = 10
                pdf.set_xy(10, pdf.get_y())
                pdf.multi_cell(0, 10, text, align='R')
            else:
                pdf.set_right_margin(10)
                pdf.set_left_margin(10)
                pdf.multi_cell(0, 10, text, align='L')
            pdf.ln(5)
        
        elif cell.cell_type == "code":
            pdf.set_fill_color(0, 0, 0)
            pdf.set_text_color(255, 255, 255)
            pdf.set_draw_color(128, 128, 128)
            pdf.set_line_width(0.4)
            pdf.set_font("DejaVu", size=10)
            pdf.set_left_margin(10)
            pdf.set_right_margin(10)
            pdf.multi_cell(0, 10, cell.source, border=1, fill=True, align='L')
            pdf.ln(5)
            
            pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(0, 0, 0)
            
            if hasattr(cell, 'outputs'):
                for output in cell.outputs:
                    if output.output_type == 'stream':
                        pdf.set_font("DejaVu", size=12)
                        text = output.text
                        if is_rtl_text(text):
                            # RTL output text
                            text = reshape_arabic(text)
                            pdf.set_xy(10, pdf.get_y())
                            pdf.multi_cell(0, 10, text, align='R')
                        else:
                            # LTR output text
                            pdf.multi_cell(0, 10, text, align='L')
                        pdf.ln(5)
                    
                    elif output.output_type == 'display_data' or output.output_type == 'execute_result':
                        if 'image/png' in output.data:
                            img_data = base64.b64decode(output.data['image/png'])
                            img_file = f"temp_img_{hash(img_data)}.png"
                            with open(img_file, 'wb') as f:
                                f.write(img_data)
                            # Center align images
                            pdf.ln(5)
                            image_width = 190
                            x_position = (pdf.w - image_width) / 2
                            pdf.image(img_file, x=x_position, w=image_width)
                            pdf.ln(5)
                            os.remove(img_file)
                        
                        elif 'text/plain' in output.data:
                            pdf.set_font("DejaVu", size=12)
                            text = str(output.data['text/plain'])
                            if is_rtl_text(text):
                                text = reshape_arabic(text)
                                pdf.set_xy(10, pdf.get_y())
                                pdf.multi_cell(0, 10, text, align='R')
                            else:
                                pdf.multi_cell(0, 10, text, align='L')
                            pdf.ln(5)
                    
                    elif output.output_type == 'error':
                        pdf.set_font("DejaVu", size=10)
                        pdf.set_text_color(255, 0, 0)
                        pdf.set_fill_color(255, 240, 240)
                        error_text = f"Error: {output.ename}: {output.evalue}"
                        pdf.multi_cell(0, 10, error_text, fill=True, align='L')
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_fill_color(255, 255, 255)
                        pdf.ln(5)

    pdf.output(pdf_filename)


async def text_to_ipynb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    timestamp = update.message.date.strftime("%Y%m%d_%H%M%S")

    try:
        # Show initial progress message
        progress_message = await update.message.reply_text("Processing your notebook 📝\n[□□□□□□□□□□] 0%")
        
        # Generate unique filenames using user ID and timestamp
        base_filename = f"output_{user_id}_{timestamp}"
        notebook_filename = f"{base_filename}.ipynb"
        executed_filename = f"{base_filename}_executed.ipynb"
        pdf_filename = f"{base_filename}.pdf"

        # Create notebook structure from user input
        await progress_message.edit_text("Creating notebook structure 📚\n[■■□□□□□□□□] 20%")
        cells = parse_cells(user_text)
        nb = nbformat.v4.new_notebook()
        nb.cells = cells

        # Save initial notebook
        with open(notebook_filename, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)
        
        # Execute notebook cells
        await progress_message.edit_text("Executing code cells ⚙️\n[■■■■□□□□□□] 40%")
        execute_notebook(nb)
        
        # Save executed notebook
        await progress_message.edit_text("Saving executed notebook 💾\n[■■■■■■□□□□] 60%")
        with open(executed_filename, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)

        # Generate PDF from notebook
        await progress_message.edit_text("Generating PDF 📄\n[■■■■■■■■□□] 80%")
        create_pdf_from_notebook(nb, pdf_filename)

        # Send files to user
        await progress_message.edit_text("Sending files 📤\n[■■■■■■■■■■] 100%")
        
        with open(executed_filename, "rb") as f:
            await update.message.reply_document(f)

        with open(pdf_filename, "rb") as f:
            await update.message.reply_document(f)

        # Clean up temporary files
        for filename in [notebook_filename, executed_filename, pdf_filename]:
            try:
                os.remove(filename)
            except Exception as e:
                logger.error(f"Error removing file {filename}: {str(e)}")
        
        await progress_message.edit_text("✅ All files have been created and sent successfully!")

    except Exception as e:
        logger.error(f"Error processing notebook for user {user_id}: {str(e)}", exc_info=True)
        if 'progress_message' in locals():
            await progress_message.edit_text("❌ An error occurred while processing your notebook. Please try again.")
        else:
            await update.message.reply_text("❌ An error occurred while processing your notebook. Please try again.")


async def send_startup_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.bot_data['chat_id']
    await context.bot.send_message(chat_id=chat_id, text="Bot started!")


def main():
    logger.info("Starting bot...")
    TOKEN = "add your token here" # add your token here
    try:
        application = Application.builder().token(TOKEN).build()
        logger.info("Application built successfully")

        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

        application.add_error_handler(error_handler)
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("broadcast", broadcast))
        application.add_handler(CommandHandler("users", list_users))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_to_ipynb))
        logger.info("Handlers added successfully")

        application.job_queue.run_once(send_startup_message, when=1)
        logger.info("Starting polling...")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()