import customtkinter as ctk
import tkinter as tk
import pandas as pd
import threading
import queue
import time
import os
import shutil
import smtplib
import json
from collections import deque
from tkinter import scrolledtext
from tkinter import simpledialog
from tkinter import filedialog, messagebox
from customtkinter import filedialog
from textExtract import extract
from textExtract1 import extract1
from textExtract2 import extract2
from textGrade import grade
from textGrade1 import grade1
from textGrade2 import grade2
from datetime import datetime
from PIL import Image, ImageTk
from pathlib import Path
from email.message import EmailMessage
import mysql.connector


#=IMAGE QUEUE=#
image_queue_1 = queue.Queue()
image_queue_2 = queue.Queue()
image_queue_3 = queue.Queue()
grade_queue_1 = queue.Queue()
grade_queue_2 = queue.Queue()
grade_queue_3 = queue.Queue()

failed = {}
failed_grading = {}
graded_images = {}
processed_data = {}
image_buttons = {}

MAX_COLUMNS = 5  # Limit to 5 squares per row
API_LIMIT = 5  # Maximum requests
PERIOD = 65  # Time window (seconds)

#==API LOCKS AND TIMERS FOR QUOTA MANAGEMENT==#
API_LOCK_1 = threading.Lock()
API_LOCK_2 = threading.Lock()
API_LOCK_3 = threading.Lock()

last_api_call_1 = deque(maxlen=API_LIMIT)
last_api_call_2 = deque(maxlen=API_LIMIT)
last_api_call_3 = deque(maxlen=API_LIMIT)
api_sleep_status = [False, False, False]

#==FLAGS TO STOP THREADS==#
stop_grading_1 = False
stop_grading_2 = False
stop_grading_3 = False

total_tasks = 0  # Tracks total number of tasks ever added
completed_tasks = 0  # Tracks tasks completed
graded_tasks = 0

#==DIRECTORIES==#
script_dir = Path(__file__).parent

monitored_directory = script_dir / "answers"
icons_directory = script_dir / "icons"
archive_directory = script_dir / "archives"
sessions_directory = script_dir / "saved sessions"

#==ICONS==#
folder_path = icons_directory / "icons8-folder-24.png"
control_path = icons_directory / "icons8-control-24.png"
images_path = icons_directory / "icons8-images-24.png"

monitored_directory.mkdir(exist_ok=True)
icons_directory.mkdir(exist_ok=True)
archive_directory.mkdir(exist_ok=True)
sessions_directory.mkdir(exist_ok=True)

#=STYLES=#
font = ("Segoe UI", 15, "bold")
black = "#333333"
grey = "#6C757D"
grey_hover = "#565E64"
background = "#f6f7fb"
white = "#f8f9fa"
green = "#198754"
green_hover = "#157347"
red = "#DC3545"
red_hover = "#B02A37"

def change_directory():
    global monitored_directory
    new_directory = filedialog.askdirectory(initialdir=monitored_directory, title="Select Directory to Monitor")
    if new_directory:  # Only update if the user selects a directory
        monitored_directory = new_directory
        update_directory_text(monitored_directory)

def move_to_archive(image_path):
    filename = os.path.basename(image_path)
    new_path = os.path.join(archive_directory, filename)
    try:
        shutil.move(image_path, new_path)

        # Update all data references
        processed_data[new_path] = processed_data.pop(image_path)

        if image_path in graded_images:
            graded_images[new_path] = graded_images.pop(image_path)
        if image_path in failed:
            failed[new_path] = failed.pop(image_path)
        if image_path in failed_grading:
            failed_grading[new_path] = failed_grading.pop(image_path)
        if image_path in image_buttons:
            image_buttons[new_path] = image_buttons.pop(image_path)

        return new_path
    except Exception as e:
        print(f"[ARCHIVE ERROR] Could not move {image_path}: {e}")
        return image_path

def reset_all():
    global completed_tasks, total_tasks, graded_tasks
    global processed_data, graded_images, grade_queue_1, grade_queue_2, grade_queue_3
    global image_buttons, failed, failed_grading
    global script_dir, monitored_directory
    global stop_grading_1, stop_grading_2, stop_grading_3

    # Show a confirmation message box before resetting
    confirm = messagebox.askyesno("Confirm Reset", "This will remove all previously processed data. Proceed?")

    if not confirm:  # If the user selects "No", cancel the reset
        return

    # Update progress bar UI (if applicable)
    update_progress_bar()
    grading_progress_bar()

    # Clear UI elements (like image buttons or grids)
    for button in image_buttons.values():
        button.destroy()  # Remove each image button from the UI
    image_buttons.clear()  # Clear the list of image buttons

    # Move and archive all processed files to archive/
    for image_path in list(processed_data.keys()):
        if os.path.exists(image_path):
            move_to_archive(image_path)

    # Also archive anything else in the monitored directory
    for filename in os.listdir(monitored_directory):
        file_path = os.path.join(monitored_directory, filename)
        if os.path.isfile(file_path):
            try:
                shutil.move(file_path, os.path.join(archive_directory, filename))
            except Exception as e:
                print(f"Error archiving unprocessed file {filename}: {e}")
                
    # Reset processed data and grades
    monitored_directory = script_dir / "answers"
    monitored_directory.mkdir(exist_ok=True)
    update_directory_text(monitored_directory)

        # Clear the processing queues
    grade_queue_1.queue.clear()
    grade_queue_2.queue.clear()
    grade_queue_3.queue.clear()

    completed_tasks = 0
    total_tasks = 0
    graded_tasks = 0

    failed.clear()
    failed_grading.clear()
    image_buttons.clear()  # Store image buttons by image path
    processed_data.clear()
    graded_images.clear()

    update_progress_bar()
    grading_progress_bar()
    grade_button.configure(state="disabled")
    export_button.configure(state="disabled")
    reset_button.configure(state="disabled")
    stop_grading_1 = True
    stop_grading_2 = True
    stop_grading_3 = True

    # Show confirmation message
    messagebox.showinfo("Reset Successful", f"Reset complete. All files moved to {archive_directory}")

def send_email_with_attachment(to_email, subject, body, filename):
    sender_email = "your_email@sample.com"  # Change to your email
    sender_password = "your_password"  # Change to your email password

    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    # Attach the file
    with open(filename, "rb") as file:
        msg.add_attachment(file.read(), maintype="application", subtype="octet-stream", filename=os.path.basename(filename))

    # Send email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:  # Adjust SMTP settings for your email provider
            server.login(sender_email, sender_password)
            server.send_message(msg)
        messagebox.showinfo("Email Sent", f"File successfully sent to {to_email}")
    except Exception as e:
        messagebox.showerror("Email Error", f"Failed to send email: {str(e)}")

def export_to_excel():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_filename = f"exported_grades_{timestamp}.xlsx"

    if not processed_data:
        messagebox.showwarning("Export Warning", "No data to export.")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx")],
        title="Save Excel File",
        initialfile=default_filename
    )

    if not file_path:
        return  # User canceled file selection

    data_list = []
    for details in processed_data.values():
        student_no = details.get("student no", "")
        name = details.get("name", "")
        section = details.get("section", "")
        question = details.get("question", "")
        answer = details.get("answer", "")
        grade = details.get("grade", "")
        feedback = details.get("feedback", "")

        if grade is not None:
            data_list.append([student_no, name, section, question, answer, grade, feedback])

    if not data_list:
        messagebox.showwarning("Export Warning", "No valid graded data found.")
        return

    df = pd.DataFrame(data_list, columns=["Student No.", "Name", "Section", "Question", "Answer", "Score", "Feedback"])
    df.to_excel(file_path, index=False)

    messagebox.showinfo("Export Successful", f"Data successfully exported to:\n{file_path}")

    # Ask user if they want to send via email
    send_email = messagebox.askyesno("Send Email", "Do you want to email the exported file?")
    if send_email:
        recipient_email = simpledialog.askstring("Recipient Email", "Enter recipient email:")
        if recipient_email:
            send_email_with_attachment(recipient_email, "Exported Student Grades", "Please find the attached file.", file_path)

def update_progress_bar():
    global total_tasks, completed_tasks

    progress_label.configure(text=f"Processed {completed_tasks} of {total_tasks}")
    progress_label.pack()

    if completed_tasks < total_tasks:
        progress_bar.set(completed_tasks / total_tasks)
        progress_bar.pack()
        grade_button.configure(state="disabled")  # Disable grading button while processing
        export_button.configure(state="disabled")
        directory_button.configure(state="disabled")
        reset_button.configure(state="disabled")
    elif completed_tasks == total_tasks:
        progress_bar.pack_forget()
        progress_label.pack_forget()
        time.sleep(0.1)
        progress_bar.pack_forget()
        progress_label.pack_forget()
        directory_button.configure(state="normal")
        if total_tasks > 0:  # Enable only if there are processed images
            grade_button.configure(state="normal")
            reset_button.configure(state="normal")
        if any("Score:" in details["text"] for details in processed_data.values()):
            export_button.configure(state="normal")

def grading_progress_bar():
    global graded_tasks, total_tasks, stop_grading_1, stop_grading_2, stop_grading_3
    
    progress_label.configure(text=f"Graded {graded_tasks} of {total_tasks}")
    progress_label.pack()

    if graded_tasks < total_tasks:
        progress_bar.set(graded_tasks / total_tasks)
        progress_bar.pack()
        grade_button.configure(state="disabled")  # Disable grading button while processing
        export_button.configure(state="disabled")
        directory_button.configure(state="disabled")
        reset_button.configure(state="disabled")
        save_db_button.configure(state="disabled")  # Ensure it’s disabled during grading
    elif graded_tasks == total_tasks:
        progress_bar.pack_forget()
        progress_label.pack_forget()
        directory_button.configure(state="normal")
        if total_tasks > 0:  # Enable only if there are processed images
            progress_bar.pack_forget()
            progress_label.pack_forget()
            directory_button.configure(state="normal")
            reset_button.configure(state="normal")
            grade_button.configure(state="disabled")
            save_db_button.configure(state="normal")
            time.sleep(0.1)
            reset_button.configure(state="normal")
            grade_button.configure(state="disabled")
            save_db_button.configure(state="normal")
        if any("grade" in details for details in processed_data.values()):
            export_button.configure(state="normal")
            stop_grading_1 = True
            stop_grading_2 = True
            stop_grading_3 = True
            print("===stop grading===")

def enforce_api_limit(api_lock, last_api_call, api_index, label):
    global api_sleep_status
    with api_lock:
        if len(last_api_call) == API_LIMIT:
            elapsed_time = time.time() - last_api_call[0]
            remaining_time = PERIOD - elapsed_time

            if remaining_time > 0:
                print(f"API {api_index + 1} Rate limit reached. Sleeping for {remaining_time:.2f} seconds.")

                # Mark API as sleeping
                api_sleep_status[api_index] = True
                if all(api_sleep_status):  # If all APIs are sleeping
                    label.configure(text="ALL APIS SLEEPING. WAIT FOR A WHILE...")
                else:
                    label.configure(text="ALL APIS ACTIVE")

                time.sleep(remaining_time)  # Sleep for remaining time

                # Mark API as active again
                api_sleep_status[api_index] = False
                if all(api_sleep_status):  # If all APIs are sleeping
                    label.configure(text="ALL APIS SLEEPING. WAIT FOR A WHILE...")
                else:
                    label.configure(text="ALL APIS ACTIVE")

        last_api_call.append(time.time())  # Add current timestamp

def process_images_1():
    global completed_tasks, total_tasks
    print("API1 STARTED")
    while True:
        image_path = image_queue_1.get(block=True)
        start_time = time.time()

        enforce_api_limit(API_LOCK_1, last_api_call_1, 0, status_label)
        print(f"[PROCESSING IMAGE API 1] {image_path}")

        try:
            student_no, name, section, answer, question = extract(image_path)

            # Replace NoneType values with "N/A"
            student_no = student_no or "N/A"
            name = name or "N/A"
            section = section or "N/A"
            answer = answer or "N/A"
            question = question or "N/A"

            processed_data[image_path] = {
                "text": f"\nName: {name}\nStudent No: {student_no}\nSection: {section}\n\nQUESTION: {question}\n\nANSWER: {answer}",
                "name": name,
                "student no": str(student_no),
                "section": section,
                "question": question,
                "answer": answer,
                "api": 1
            }

            # Check if any value is exactly "N/A", if so, skip grading
            if "N/A" not in (name, answer, question):
                grade_queue_1.put((image_path, question, answer))
                completed_tasks += 1
            else:
                total_tasks -= 1
                failed[image_path] = "failed"

            update_ui(image_path)

        except Exception as e:
            print(f"[ERROR] Image processing failed for {image_path}: {e}")

        update_progress_bar()

        # Record total processing time for reference
        processing_time = time.time() - start_time
        print(f"[API 1] Processing time: {processing_time:.2f} seconds")

def process_images_2():
    global completed_tasks, total_tasks
    print("API2 STARTED")
    while True:
        image_path = image_queue_2.get(block=True)
        start_time = time.time()

        enforce_api_limit(API_LOCK_2, last_api_call_2, 1, status_label)
        print(f"[PROCESSING IMAGE API 2] {image_path}")

        try:
            student_no, name, section, answer, question = extract1(image_path)

            # Replace NoneType values with "N/A"
            student_no = student_no or "N/A"
            name = name or "N/A"
            section = section or "N/A"
            answer = answer or "N/A"
            question = question or "N/A"

            processed_data[image_path] = {
                "text": f"\nName: {name}\nStudent No: {student_no}\nSection: {section}\n\nQUESTION: {question}\n\nANSWER: {answer}",
                "name": name,
                "student no": str(student_no),
                "section": section,
                "question": question,
                "answer": answer,
                "api": 2
            }

            # Check if any value is exactly "N/A", if so, skip grading
            if "N/A" not in (name, answer, question):
                grade_queue_2.put((image_path, question, answer))
                completed_tasks += 1
            else:
                total_tasks -= 1
                failed[image_path] = "failed"

            update_ui(image_path)

        except Exception as e:
            print(f"[ERROR] Image processing failed for {image_path}: {e}")

        update_progress_bar()

        # Record total processing time for reference
        processing_time = time.time() - start_time
        print(f"[API 2] Processing time: {processing_time:.2f} seconds")

def process_images_3():
    global completed_tasks, total_tasks
    print("API3 STARTED")
    while True:
        image_path = image_queue_3.get(block=True)
        start_time = time.time()

        enforce_api_limit(API_LOCK_3, last_api_call_3, 2, status_label)
        print(f"[PROCESSING IMAGE API 3] {image_path}")

        try:
            student_no, name, section, answer, question = extract2(image_path)

            # Replace NoneType values with "N/A"
            student_no = student_no or "N/A"
            name = name or "N/A"
            section = section or "N/A"
            answer = answer or "N/A"
            question = question or "N/A"

            processed_data[image_path] = {
                "text": f"\nName: {name}\nStudent No: {student_no}\nSection: {section}\n\nQUESTION: {question}\n\nANSWER: {answer}",
                "name": name,
                "student no": str(student_no),
                "section": section,
                "question": question,
                "answer": answer,
                "api": 3
            }

            # Check if any value is exactly "N/A", if so, skip grading
            if "N/A" not in (name, answer, question):
                grade_queue_3.put((image_path, question, answer))
                completed_tasks += 1
            else:
                total_tasks -= 1
                failed[image_path] = "failed"

            update_ui(image_path)

        except Exception as e:
            print(f"[ERROR] Image processing failed for {image_path}: {e}")

        update_progress_bar()

        # Record total processing time for reference
        processing_time = time.time() - start_time
        print(f"[API 3] Processing time: {processing_time:.2f} seconds")

def process_grades_1():
    global graded_tasks
    print("API1 GRADING STARTED")
    while not stop_grading_1:  # ✅ Stop loop when grading is canceled
        try:
            image_path, question, answer = grade_queue_1.get(block=True, timeout=1)  # Prevent deadlocks
        except queue.Empty:
            continue  # If queue is empty, check stop flag again

        # Skip removed images
        if image_path not in processed_data:
            print(f"[SKIPPED] {image_path} removed before grading.")
            continue

        # Skip removed images
        if image_path in graded_images:
            continue

        #Replace None values with "N/A"
        question = question or "N/A"
        answer = answer or "N/A"

        #Skip grading if any field contains exactly "N/A"
        if question == "N/A" or answer == "N/A":
            print(f"[SKIPPED] Grading skipped for {image_path}: Contains 'N/A'.")

            #Mark button red for skipped images
            if image_path in image_buttons:
                image_buttons[image_path].configure(fg_color=red, text_color=white)
            continue

        start_time = time.time()

        enforce_api_limit(API_LOCK_1, last_api_call_1, 0, status_label)  # Apply dynamic rate limiting
        print(f"[GRADING API 1] {image_path}")

        try:
            score, feedback = grade(image_path, question, answer)  # Perform grading
            processed_data[image_path]["grade"] = score
            processed_data[image_path]["feedback"] = feedback
            graded_images[image_path] = 'graded'  # Mark as graded

            update_ui(image_path, update_only=True)
            graded_tasks += 1
            grading_progress_bar()

        except Exception as e:
            print(f"[ERROR] Grading API 1 failed for {image_path}: {e}")
            failed_grading[image_path] = "failed"
            print("added to failed")

        # Log processing time
        processing_time = time.time() - start_time
        print(f"[API 1] Grading time: {processing_time:.2f} seconds")
        time.sleep(1)

    print("[THREAD 1] Grading stopped.")  # Confirm thread exit

def process_grades_2():
    global graded_tasks
    print("API2 GRADING STARTED")
    while not stop_grading_2:  # Stop loop when grading is canceled
        try:
            image_path, question, answer = grade_queue_2.get(block=True, timeout=1)  # Prevent deadlocks
        except queue.Empty:
            continue  # If queue is empty, check stop flag again

        # Skip removed images
        if image_path not in processed_data:
            print(f"[SKIPPED] {image_path} removed before grading.")
            continue

        if image_path in graded_images:
            continue

        # Replace None values with "N/A"
        question = question or "N/A"
        answer = answer or "N/A"

        # Skip grading if any field contains exactly "N/A"
        if question == "N/A" or answer == "N/A":
            print(f"[SKIPPED] Grading skipped for {image_path}: Contains 'N/A'.")

            # Mark button red for skipped images
            if image_path in image_buttons:
                image_buttons[image_path].configure(fg_color=red, text_color=white)
            continue

        start_time = time.time()

        enforce_api_limit(API_LOCK_2, last_api_call_2, 1, status_label)  # Apply dynamic rate limiting
        print(f"[GRADING API 2] {image_path}")

        try:
            score, feedback = grade1(image_path, question, answer)  # Perform grading
            processed_data[image_path]["grade"] = score
            processed_data[image_path]["feedback"] = feedback
            graded_images[image_path] = 'graded'  # Mark as graded

            update_ui(image_path, update_only=True)
            graded_tasks += 1
            grading_progress_bar()

        except Exception as e:
            print(f"[ERROR] Grading API 2 failed for {image_path}: {e}")
            failed_grading[image_path] = "failed"
            print("added to failed")

        # Log processing time
        processing_time = time.time() - start_time
        print(f"[API 2] Grading time: {processing_time:.2f} seconds")
        time.sleep(1)

    print("[THREAD 2] Grading stopped.")  # Confirm thread exit

def process_grades_3():
    global graded_tasks
    print("API1 GRADING STARTED")
    while not stop_grading_3:  # Stop loop when grading is canceled
        try:
            image_path, question, answer = grade_queue_3.get(block=True, timeout=1)  # Prevent deadlocks
        except queue.Empty:
            continue  # If queue is empty, check stop flag again

        # Skip removed images
        if image_path not in processed_data:
            print(f"[SKIPPED] {image_path} removed before grading.")
            continue

        if image_path in graded_images:
            continue

        # Replace None values with "N/A"
        question = question or "N/A"
        answer = answer or "N/A"

        # Skip grading if any field contains exactly "N/A"
        if question == "N/A" or answer == "N/A":
            print(f"[SKIPPED] Grading skipped for {image_path}: Contains 'N/A'.")

            # Mark button red for skipped images
            if image_path in image_buttons:
                image_buttons[image_path].configure(fg_color=red, text_color=white)
            continue

        start_time = time.time()

        enforce_api_limit(API_LOCK_3, last_api_call_3, 2, status_label)  # Apply dynamic rate limiting
        print(f"[GRADING API 3] {image_path}")

        try:
            score, feedback = grade2(image_path, question, answer)  # Perform grading
            processed_data[image_path]["grade"] = score
            processed_data[image_path]["feedback"] = feedback
            graded_images[image_path] = 'graded'  # Mark as graded

            update_ui(image_path, update_only=True)
            graded_tasks += 1
            grading_progress_bar()

        except Exception as e:
            print(f"[ERROR] Grading API 3 failed for {image_path}: {e}")
            failed_grading[image_path] = "failed"
            print("added to failed")

        # Log processing time
        processing_time = time.time() - start_time
        print(f"[API 3] Grading time: {processing_time:.2f} seconds")
        time.sleep(1)

    print("[THREAD 3] Grading stopped.")  # Confirm thread exit

def check_graded():
    global graded_tasks
    if failed_grading:
        for image_path in failed_grading:
            if graded_tasks > 0:
                graded_tasks -= 1
        recheck()

def recheck():
    for image_path in failed_grading:
        if image_path in processed_data: # check if the image_path is in processed_data
            if processed_data[image_path]["api"] == 1:
                question = processed_data[image_path]["question"]
                answer = processed_data[image_path]["answer"]
                grade_queue_1.put((image_path, question, answer))
            elif processed_data[image_path]["api"] == 2:
                question = processed_data[image_path]["question"]
                answer = processed_data[image_path]["answer"]
                grade_queue_2.put((image_path, question, answer))
            elif processed_data[image_path]["api"] == 3:
                question = processed_data[image_path]["question"]
                answer = processed_data[image_path]["answer"]
                grade_queue_3.put((image_path, question, answer))
        else:
            print(f"Warning: image_path '{image_path}' not found in processed_data")  
    
def add_image_to_queue(image_path, use_api):
    """Adds an image to the queue and specifies which API to use."""
    if use_api == 0:
        image_queue_1.put(image_path)
        print(f"Adding {image_path} to queue for API 1")
        # Call API 1 processing function
    elif use_api == 1:
        image_queue_2.put(image_path)
        print(f"Adding {image_path} to queue for API 2")
        # Call API 2 processing function
    else:
        image_queue_3.put(image_path)
        print(f"Adding {image_path} to queue for API 3")
        # Call API 3 processing function

def update_ui(image_path, update_only=False):
    if image_path not in processed_data:  # Prevent adding button if removed
        return
    
    def show_text(image_path):
        def show_large_image(image_path):
            large_popup = tk.Toplevel()
            large_popup.title("Full Image View")
            large_popup.geometry("800x600")
            large_popup.configure(bg="black")

            # Create a canvas for better scaling
            canvas = tk.Canvas(large_popup, bg="black", highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)

            img = Image.open(image_path)

            # Resize image dynamically
            def resize_image(event):
                new_width, new_height = event.width, event.height
                img_resized = img.copy()
                img_resized.thumbnail((new_width, new_height))  # Maintain aspect ratio

                photo_resized = ImageTk.PhotoImage(img_resized)
                canvas.image = photo_resized  # Keep reference
                canvas.delete("all")  # Clear previous image
                canvas.create_image(new_width // 2, new_height // 2, anchor=tk.CENTER, image=photo_resized)

            large_popup.bind("<Configure>", resize_image)

        def remove_item(image_path, popup=None):
            global total_tasks, completed_tasks, graded_tasks

            if popup:
                popup.destroy()  # Close popup
            
            if image_path in processed_data:
                # Remove from data
                del processed_data[image_path]
                if image_path not in failed:
                    if total_tasks > 0:
                        total_tasks -= 1
                    if completed_tasks > 0:
                        completed_tasks -= 1
                print("deleted in processed data")

            if image_path in graded_images:
                # Remove from data
                del graded_images[image_path]
                if graded_tasks > 0:
                    graded_tasks -= 1
                print("deleted in graded images")

            if image_path in image_buttons:
                image_buttons[image_path].destroy()
                del image_buttons[image_path]
                print("deleted in image buttons")

            # Rebuild queues without removed image
            global grade_queue_1, grade_queue_2, grade_queue_3
            new_queue_1 = queue.Queue()
            while not grade_queue_1.empty():
                item = grade_queue_1.get()
                if item[0] != image_path:
                    new_queue_1.put(item)
            grade_queue_1 = new_queue_1

            new_queue_2 = queue.Queue()
            while not grade_queue_2.empty():
                item = grade_queue_2.get()
                if item[0] != image_path:
                    new_queue_2.put(item)
            grade_queue_2 = new_queue_2
            
            new_queue_3 = queue.Queue()
            while not grade_queue_3.empty():
                item = grade_queue_3.get()
                if item[0] != image_path:
                    new_queue_3.put(item)
            grade_queue_3 = new_queue_3

            # Rearrange grid & update progress
            rearrange_grid()
            grading_progress_bar()
            update_progress_bar()
        
        def toggle_edit():
            if is_editing.get():
                text_area.configure(state=tk.DISABLED)
                edit_btn.configure(text="Edit")
                save_btn.configure(state=tk.DISABLED)  # Disable save when not editing
            else:
                text_area.configure(state=tk.NORMAL)
                edit_btn.configure(text="Cancel")
                save_btn.configure(state=tk.NORMAL)  # Enable save when editing
            is_editing.set(not is_editing.get())  # Toggle state

        def save_changes(image_path):
            """Save the edited text, update processed_data, and refresh the correct grading queue based on API."""
            new_text = text_area.get("1.0", tk.END).strip()  # Get the edited text

            if image_path in processed_data:
                processed_data[image_path]["text"] = new_text  # Update full text

                def extract_field(label):
                    start = new_text.find(label)
                    if start != -1:
                        return new_text[start + len(label):].strip().split("\n", 1)[0]  # Get first line after label
                    return None

                new_name = extract_field("Name: ")
                new_student_no = extract_field("Student No: ")
                new_section = extract_field("Section: ")
                new_question = extract_field("QUESTION: ")
                new_answer = extract_field("ANSWER: ")

                # Update the processed_data dictionary
                if new_name:
                    processed_data[image_path]["name"] = new_name
                if new_student_no:
                    processed_data[image_path]["student no"] = new_student_no
                    if image_path in image_buttons:
                        display_no = new_student_no if new_student_no and new_student_no != "N/A" else "#######"
                        image_buttons[image_path].configure(text=f"ID: {display_no}")
                if new_section:
                    processed_data[image_path]["section"] = new_section
                if new_question:
                    processed_data[image_path]["question"] = new_question
                if new_answer:
                    processed_data[image_path]["answer"] = new_answer

                # Determine which queue to update based on API
                api_used = processed_data[image_path].get("api", 1)  # Default to API 1 if missing
                queue_map = {1: grade_queue_1, 2: grade_queue_2, 3: grade_queue_3}
                queue_to_update = queue_map.get(api_used)

                if queue_to_update:
                    # Remove old entry from queue and re-add updated one
                    temp_queue = queue.Queue()
                    found = False  # Track if image was found in the queue

                    while not queue_to_update.empty():
                        item = queue_to_update.get()
                        if item[0] != image_path:  # Keep other items
                            temp_queue.put(item)
                        else:
                            found = True  # Mark that we removed the old one

                    # If new data is valid, re-add it
                    if "N/A" not in (new_name, new_question, new_answer):
                        temp_queue.put((image_path, new_question, new_answer))  # Add updated entry
                        found = True  # Ensure it's in the queue

                    # Restore all queue items
                    while not temp_queue.empty():
                        queue_to_update.put(temp_queue.get())

                    # Log warning if the image wasn't found in queue (debugging)
                    if not found:
                        print(f"[WARNING] {image_path} was not found in the grading queue {api_used}. It was added manually.")

                text_area.configure(state=tk.DISABLED)  # Lock the textbox after saving
                save_btn.configure(state=tk.DISABLED)  # Disable save button after saving
                edit_btn.configure(text="Edit")  # Reset button text
                is_editing.set(False)  # Reset editing state

        popup = tk.Toplevel()
        student_no = processed_data.get(image_path, {}).get("student no", "#######")
        if student_no == "N/A":
           student_no = "#######"
        popup.title(student_no)
        popup.configure(bg=white)

        img = Image.open(image_path)
        img.thumbnail((500, 500))  # Small preview
        photo = ImageTk.PhotoImage(img)

        content_frame = tk.Frame(popup, bg=white)
        content_frame.pack(padx=10, pady=10)

        img_label = tk.Label(content_frame, image=photo, bg=white)
        img_label.image = photo
        img_label.grid(row=0, rowspan=2, column=0, padx=10)
        img_label.bind("<Button-1>", lambda e: show_large_image(image_path))  # Open full-size view

        is_editing = tk.BooleanVar(value=False)  # Tracks if the text is editable

        textArea = tk.Frame(content_frame, bg=white)
        textArea.grid(row=0, column=1, padx=10)

        text_area = scrolledtext.ScrolledText(textArea, wrap=tk.WORD, width=50, height=15, font=("Arial", 12))
        extracted_text = processed_data.get(image_path, {}).get("text", "No text extracted")
        text_area.insert(tk.INSERT, extracted_text)
        text_area.configure(state=tk.DISABLED)
        text_area.grid(row=0, column=0, padx=10)

        score_area = scrolledtext.ScrolledText(textArea, wrap=tk.WORD, width=50, height=5, font=("Arial", 12))
        extracted_grade = processed_data.get(image_path, {}).get("grade", "No grade assigned")
        extracted_feedback = processed_data.get(image_path, {}).get("feedback", "No feedback given")
        score_text = f"Grade: {extracted_grade}\nFeedback: {extracted_feedback}"
        score_area.insert(tk.INSERT, score_text)
        score_area.configure(state=tk.DISABLED)
        score_area.grid(row=1, column=0, padx=10)

        btn_frame = tk.Frame(content_frame, bg=white)
        btn_frame.grid(row=1, column=1, padx=10)

        # Edit Button
        edit_btn = ctk.CTkButton(
            btn_frame, text="Edit", command=toggle_edit,
            text_color=white, fg_color=grey, hover_color=grey_hover,
            font=("Segoe UI", 12, "bold"), corner_radius=10
        )
        edit_btn.pack(pady=(10,0))

        # Save Button (Initially Disabled)
        save_btn = ctk.CTkButton(
            btn_frame, text="Save", command= lambda: save_changes(image_path),
            text_color=white, fg_color=green, hover_color=green_hover,
            font=("Segoe UI", 12, "bold"), corner_radius=10
        )
        save_btn.pack(pady=10)
        save_btn.configure(state=tk.DISABLED)  # Disabled until Edit is clicked

        # Remove Button with Styling
        remove_btn = ctk.CTkButton(
            btn_frame, text="Remove", command=lambda: remove_item(image_path, popup),
            text_color=white, fg_color=red, hover_color=red_hover,
            font=("Segoe UI", 12, "bold"), corner_radius=20
        )
        remove_btn.pack(pady=(0,10))
        
    if update_only and image_path in image_buttons:
        btn = image_buttons[image_path]
        btn.configure(command=lambda p=image_path: show_text(p))

        # Mark green if graded
        if image_path in graded_images:
            btn.configure(fg_color=green, hover_color=green_hover, text_color=white)

        # Mark red if any field contains "N/A"
        extracted_data = processed_data.get(image_path, {})
        if "N/A" in (extracted_data["name"], extracted_data["question"], extracted_data["answer"]):
            btn.configure(fg_color=red, hover_color=red_hover, text_color=white)

        return
    
    if image_path in image_buttons:  # Prevent duplicate buttons
        return

    img = Image.open(image_path)
    img.thumbnail((100, 100))
    photo = ImageTk.PhotoImage(img)
    student_no = processed_data.get(image_path, {}).get("student no", "#######")
    if student_no == 0:
        student_no = "#######"
    # Image Button
    img_button = ctk.CTkButton(
        frame, image=photo, text=f"ID: {student_no}", compound="top", 
        command=lambda p=image_path: show_text(p), width=175, 
        height=175, border_width=2, fg_color=white, text_color=	black,
        hover_color="#E0E0E0", corner_radius=20
    )
    img_button.image = photo  # Keep reference
    img_button.configure(font=("Segoe UI", 14, "bold"), anchor="center")

    # Mark green if graded
    if image_path in graded_images:
        img_button.configure(fg_color=green, hover_color=green_hover, text_color=white)

    # Mark red if any field contains "N/A"
    extracted_data = processed_data.get(image_path, {})
    if "N/A" in (extracted_data["name"], extracted_data["question"], extracted_data["answer"]):
        img_button.configure(fg_color=red, hover_color=red_hover, text_color=white)

    # Store reference
    image_buttons[image_path] = img_button

    # Get position in grid
    row, col = divmod(len(image_buttons) - 1, MAX_COLUMNS)
    img_button.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

def rearrange_grid():
    """Rearrange UI after an item is removed."""
    for widget in frame.winfo_children():
        widget.grid_forget()  # Clear grid layout
    
    for index, (image_path, widget) in enumerate(image_buttons.items()):
        row, col = divmod(index, MAX_COLUMNS)
        widget.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

def start_monitoring():
    """Continuously monitors the directory for new images and processes them."""
    global total_tasks
    
    print(f"Monitoring directory: {monitored_directory}")
    processed_images = set()  # Store already processed images to avoid duplication

    while True:  # Continuously check for new files
        image_files = [
            os.path.join(monitored_directory, file)
            for file in os.listdir(monitored_directory)
            if os.path.isfile(os.path.join(monitored_directory, file)) and file.lower().endswith((".png", ".jpg", ".jpeg"))
        ]

        for image_path in image_files:
            if image_path not in processed_images:  # Process only new images
                use_api = len(processed_images) % 3
                add_image_to_queue(image_path, use_api)
                processed_images.add(image_path)  # Mark file as processed
                total_tasks += 1  # Dynamically update total tasks
                update_progress_bar()

        time.sleep(2)  # Check for new files every 2 seconds (adjustable)

def start_grading():
    global stop_grading_1, stop_grading_2, stop_grading_3
    print("Starting grading process...")

    check_graded()
    
    grade_button.configure(state="disabled")  # Disable grading while in progress
    export_button.configure(state="disabled")

    stop_grading_1 = False
    stop_grading_2 = False
    stop_grading_3 = False
    # Start grading threads
    threading.Thread(target=process_grades_1, daemon=True).start()
    threading.Thread(target=process_grades_2, daemon=True).start()
    threading.Thread(target=process_grades_3, daemon=True).start()
    grading_progress_bar()

def update_directory_text(new_path):
    directory_textbox.configure(state="normal")  # Enable editing to update text
    directory_textbox.delete("1.0", tk.END)  # Clear previous text
    directory_textbox.insert("1.0", new_path)  # Insert new path
    directory_textbox.configure(state="disabled")  # Disable editing

def _on_mouse_scroll(event):
    if canvas.winfo_containing(event.x_root, event.y_root) == canvas:
        canvas.yview_scroll(-1 * (event.delta // 120), "units")

def _on_shift_mouse_scroll(event):
    if canvas.winfo_containing(event.x_root, event.y_root) == canvas:
        canvas.xview_scroll(-1 * (event.delta // 120), "units")

def update_scroll_region(event):
    frame.update_idletasks()  # Ensure layout updates before calculating bbox
    bbox = canvas.bbox("all")

    if bbox:
        x1, y1, x2, y2 = bbox  # Get bounding box
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()

        # Prevent excessive scrolling when content fits inside
        if x2 - x1 < canvas_width:
            x2 = x1 + canvas_width
        if y2 - y1 < canvas_height:
            y2 = y1 + canvas_height

        canvas.configure(scrollregion=(x1, y1, x2, y2))

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",  # Change this if your username is different
            password="",  # Add your password here if you set one
            database="essay_checker"
        )
        return connection
    except mysql.connector.Error as e:
        messagebox.showerror("Database Error", f"Failed to connect: {e}")
        return None

def save_to_database():
    if not processed_data:  # Assuming processed_data is your data dictionary
        messagebox.showwarning("Nothing to Save", "No data to save.")
        return

    # Save a JSON file on your desktop
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(sessions_directory, f"grades_{timestamp}.json")
    entries = []
    for image_path, data in processed_data.items():
        entries.append({"image_path": image_path, "data": data})

    try:
        with open(save_path, "w") as f:
            json.dump(entries, f, indent=2)
    except Exception as e:
        messagebox.showerror("Save Error", f"Failed to save JSON:\n{e}")
        return

    # Save to database
    connection = get_db_connection()
    if not connection:
        return

    cursor = connection.cursor()
    insert_query = """
    INSERT INTO grades (image_path, student_no, name, section, question, answer, grade, feedback, api)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    try:
        for entry in entries:
            image_path = entry["image_path"]
            data = entry["data"]
            try:
                student_no_int = int(data.get("student no"))
            except (ValueError, TypeError):
                raise ValueError(f"Invalid student number '{data.get('student no')}' for image {image_path}. Must be an integer.")
            try:
                api_int = int(data.get("api", 1))
            except (ValueError, TypeError):
                api_int = 1  # Default if invalid
            cursor.execute(insert_query, (
                image_path,
                student_no_int,
                data.get("name", "N/A"),
                data.get("section", "N/A"),
                data.get("question", "N/A"),
                data.get("answer", "N/A"),
                data.get("grade", None),
                data.get("feedback", None),
                api_int
            ))
        connection.commit()
        messagebox.showinfo("Success", f"Data saved to database and JSON file:\n{save_path}")
    except mysql.connector.Error as e:
        messagebox.showerror("Database Error", f"Failed to save:\n{e}")
    except ValueError as ve:
        messagebox.showerror("Input Error", str(ve))
    finally:
        cursor.close()
        connection.close()

class SearchCriteriaDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, fields):
        super().__init__(parent)
        self.title(title)
        self.fields = fields
        self.entries = {}
        self.result = None
        self.geometry("700x400")  # Set to 700x400 as requested
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - 600) // 2
        y = (screen_height - 400) // 2
        self.geometry(f"600x400+{x}+{y}")
        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        # Main frame to hold the grid layout
        main_frame = ctk.CTkFrame(self, fg_color=background)
        main_frame.pack(padx=0, pady=0, fill="both", expand=True)

        # Row 1: Student number and Name
        student_no_label = ctk.CTkLabel(main_frame, text="Student number:", text_color=black, font=font)
        student_no_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        student_no_entry = ctk.CTkEntry(main_frame, width=150, fg_color=white, text_color=black, font=font)
        student_no_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.entries["Student number"] = student_no_entry

        name_label = ctk.CTkLabel(main_frame, text="Name:", text_color=black, font=font)
        name_label.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        name_entry = ctk.CTkEntry(main_frame, width=150, fg_color=white, text_color=black, font=font)
        name_entry.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.entries["Name"] = name_entry

        # Row 2: Section and Question
        section_label = ctk.CTkLabel(main_frame, text="Section:", text_color=black, font=font)
        section_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        section_entry = ctk.CTkEntry(main_frame, width=150, fg_color=white, text_color=black, font=font)
        section_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.entries["Section"] = section_entry

        question_label = ctk.CTkLabel(main_frame, text="Question:", text_color=black, font=font)
        question_label.grid(row=1, column=2, padx=5, pady=5, sticky="e")
        question_entry = ctk.CTkEntry(main_frame, width=150, fg_color=white, text_color=black, font=font)
        question_entry.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        self.entries["Question"] = question_entry

        # Row 3: Year, Month, Day
        year_label = ctk.CTkLabel(main_frame, text="Year:", text_color=black, font=font)
        year_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
        year_entry = ctk.CTkEntry(main_frame, width=100, fg_color=white, text_color=black, font=font)
        year_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.entries["Year"] = year_entry

        month_label = ctk.CTkLabel(main_frame, text="Month:", text_color=black, font=font)
        month_label.grid(row=2, column=2, padx=5, pady=5, sticky="e")
        month_entry = ctk.CTkEntry(main_frame, width=80, fg_color=white, text_color=black, font=font)
        month_entry.grid(row=2, column=3, padx=5, pady=5, sticky="w")
        self.entries["Month"] = month_entry

        day_label = ctk.CTkLabel(main_frame, text="Day:", text_color=black, font=font)
        day_label.grid(row=3, column=2, padx=5, pady=5, sticky="e")
        day_entry = ctk.CTkEntry(main_frame, width=80, fg_color=white, text_color=black, font=font)
        day_entry.grid(row=3, column=3, padx=5, pady=5, sticky="w")
        self.entries["Day"] = day_entry

        # Row 4: Time (Beside label)
        time_label = ctk.CTkLabel(main_frame, text="Time:", text_color=black, font=font)
        time_label.grid(row=3, column=0, padx=5, pady=5, sticky="e")
        time_entry = ctk.CTkEntry(main_frame, width=100, fg_color=white, text_color=black, font=font)
        time_entry.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        self.entries["Time"] = time_entry

        # Buttons
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=4, column=0, columnspan=6, pady=20)

        load_button = ctk.CTkButton(button_frame, text="Load", command=self.on_load, font=font, fg_color=grey, hover_color=grey_hover, text_color=white, width=100)
        load_button.pack(side="left", padx=10)

        cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self.on_cancel, font=font, fg_color=grey, hover_color=grey_hover, text_color=white, width=100)
        cancel_button.pack(side="left", padx=10)

        # Configure grid weights for better spacing
        main_frame.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        main_frame.rowconfigure((0, 1, 2, 3, 4), weight=1)

    def on_load(self):
        criteria = {field: entry.get().strip() for field, entry in self.entries.items()}
        if any(criteria.values()):
            self.result = criteria
            self.destroy()
        else:
            messagebox.showerror("Input Error", "At least one search criterion is required.")

    def on_cancel(self):
        self.result = None
        self.destroy()

    def on_close(self):
        self.result = None
        self.destroy()

def load_from_database():
    global processed_data, graded_images, failed, failed_grading
    global total_tasks, completed_tasks, graded_tasks

    connection = get_db_connection()
    if not connection:
        return

    fields = ["Student number", "Name", "Section", "Question", "Year", "Month", "Day", "Time"]
    field_mapping = {
        "Student number": "student_no",
        "Name": "name",
        "Section": "section",
        "Question": "question",
        "Year": "year",
        "Month": "month",
        "Day": "day",
        "Time": "time"
    }

    dialog = SearchCriteriaDialog(root, title="Search Database", fields=fields)
    dialog.grab_set()
    root.wait_window(dialog)

    if dialog.result is None:
        return  # Canceled

    criteria = dialog.result

    # Build SQL query
    query = "SELECT * FROM grades WHERE 1=1"
    params = []

    for field, value in criteria.items():
        if value:
            if field == "Student number":
                try:
                    student_no_int = int(value)
                    query += " AND student_no = %s"
                    params.append(student_no_int)
                except ValueError:
                    messagebox.showerror("Input Error", "Student number must be an integer.")
                    return
            elif field == "Name":
                query += " AND name LIKE %s"
                params.append(f"%{value}%")
            elif field == "Section":
                query += " AND section LIKE %s"
                params.append(f"%{value}%")
            elif field == "Question":
                query += " AND question LIKE %s"
                params.append(f"%{value}%")
            elif field == "Year":
                try:
                    year = int(value)
                    query += " AND YEAR(created_at) = %s"
                    params.append(year)
                except ValueError:
                    messagebox.showerror("Input Error", "Year must be an integer.")
                    return
            elif field == "Month":
                try:
                    month = int(value)
                    if month < 1 or month > 12:
                        raise ValueError("Month must be between 1 and 12.")
                    query += " AND MONTH(created_at) = %s"
                    params.append(month)
                except ValueError as e:
                    messagebox.showerror("Input Error", str(e))
                    return
            elif field == "Day":
                try:
                    day = int(value)
                    if day < 1 or day > 31:
                        raise ValueError("Day must be between 1 and 31.")
                    query += " AND DAY(created_at) = %s"
                    params.append(day)
                except ValueError as e:
                    messagebox.showerror("Input Error", str(e))
                    return
            elif field == "Time":
                try:
                    # Assuming time is in HH:MM:SS format
                    datetime.strptime(value, "%H:%M:%S")
                    query += " AND TIME(created_at) = %s"
                    params.append(value)
                except ValueError:
                    messagebox.showerror("Input Error", "Time must be in HH:MM:SS format.")
                    return

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query, tuple(params))
        records = cursor.fetchall()
        if not records:
            messagebox.showinfo("No Data", "No data found for the given criteria.")
            return

        # Track new entries to avoid duplicates
        new_entries = 0
        existing_image_paths = set(processed_data.keys())  # Track existing image paths

        for record in records:
            image_path = record["image_path"]
            # Skip if this image_path is already in processed_data
            if image_path in existing_image_paths:
                print(f"[SKIPPED] {image_path} already loaded in UI.")
                continue

            if not os.path.exists(image_path):
                archive_path = os.path.join(archive_directory, os.path.basename(image_path))
                if os.path.exists(archive_path):
                    image_path = archive_path
                else:
                    print(f"[SKIPPED] Image file not found: {image_path}")
                    continue

            name = record["name"] or "N/A"
            student_no = str(record["student_no"]) or "N/A"
            section = record["section"] or "N/A"
            question = record["question"] or "N/A"
            answer = record["answer"] or "N/A"
            processed_data[image_path] = {
                "text": f"\nName: {name}\nStudent No: {student_no}\nSection: {section}\n\nQUESTION: {question}\n\nANSWER: {answer}",
                "student no": student_no,
                "name": name,
                "section": section,
                "question": question,
                "answer": answer,
                "grade": record["grade"],
                "feedback": record["feedback"],
                "api": record["api"]
            }
            total_tasks += 1
            new_entries += 1
            if "N/A" not in (name, question, answer):
                completed_tasks += 1
            else:
                failed[image_path] = "invalid"
            if record["grade"] is not None:
                graded_tasks += 1
                graded_images[image_path] = "graded"
            update_ui(image_path)

        grading_progress_bar()
        update_progress_bar()
        time.sleep(0.1)
        grading_progress_bar()
        update_progress_bar()
        frame.update_idletasks()
        update_scroll_region(None)
        messagebox.showinfo("Success", f"{new_entries} new entries loaded. Total entries in UI: {len(processed_data)}.")

    except mysql.connector.Error as e:
        messagebox.showerror("Database Error", f"Failed to load:\n{e}")
    finally:
        cursor.close()
        connection.close()

#====TKINTER SETUP====#

#====ICONS====#
folder = Image.open(folder_path)  # Load PNG image
control = Image.open(control_path)  # Load PNG image
images = Image.open(images_path)  # Load PNG image

folder_ctk = ctk.CTkImage(folder)
control_ctk = ctk.CTkImage(control)
images_ctk = ctk.CTkImage(images)
# Root Window Setup
root = ctk.CTk(fg_color=background)
root.title("Gemini API Automatic Essay Checker")
# Get screen width and height
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

# Set window size to match the screen
root.geometry(f"{screen_width}x{screen_height}+0+0")  # Fullscreen window

# Configure Grid Layout for Root
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)

# === Scrollable Image Display ===
canvas = tk.Canvas(root, bg=background, highlightthickness=0)
scroll_y = tk.Scrollbar(root, orient="vertical", command=canvas.yview,
                        bg=background, troughcolor="#000000")
scroll_x = tk.Scrollbar(root, orient="horizontal", command=canvas.xview,
                        bg=background, troughcolor="#000000")

# Configure Grid Layout for Canvas and Scrollbars
canvas.grid(row=1, column=0, sticky="nsew", padx=(10,0), pady=(0,10))
scroll_y.grid(row=1, column=1, sticky="nsew")
scroll_x.grid(row=2, column=0, sticky="nsew")

# Allow Canvas to Expand
root.rowconfigure(0, weight=0)
root.rowconfigure(1, weight=1)

processed_label = ctk.CTkLabel(root,image=images_ctk, text=" PROCESSED IMAGES", compound="left", font=font, text_color=black)
processed_label.grid(row=0, column=0, sticky="sw", padx=10, pady=10)

# Frame Inside Canvas for Content
frame = ctk.CTkFrame(canvas, fg_color="transparent")
canvas.create_window((0, 0), window=frame, anchor="nw")

canvas.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
canvas.configure(yscrollincrement=20, xscrollincrement=20)

frame.bind("<Configure>", update_scroll_region)
frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"), width=frame.winfo_reqwidth()))


canvas.bind("<Enter>", lambda event: canvas.bind("<MouseWheel>", _on_mouse_scroll))
canvas.bind("<Leave>", lambda event: canvas.unbind("<MouseWheel>"))

canvas.bind("<Enter>", lambda event: canvas.bind("<Shift-MouseWheel>", _on_shift_mouse_scroll))
canvas.bind("<Leave>", lambda event: canvas.unbind("<Shift-MouseWheel>"))

# === Right Panel: Fixed Size ===
right_panel = ctk.CTkFrame(root, width=350, fg_color=green)
right_panel.grid(row=0, rowspan=3, column=2, sticky="nsew")

controls_label = ctk.CTkLabel(right_panel, image=control_ctk, text=" CONTROL PANEL", compound="left", font=font, text_color=white)
controls_label.pack(pady=10, padx=10, anchor="w")

# Ensure Right Panel Stays Fixed
root.columnconfigure(2, minsize=350, weight=0)

# Progress Elements
progress_label = ctk.CTkLabel(right_panel, text="Processing...", font=font, text_color=white)
progress_bar = ctk.CTkProgressBar(right_panel, mode="indeterminate", width=300, height=8, fg_color=white, progress_color=grey)
progress_label.pack(pady=5)
progress_bar.pack(pady=5)
progress_bar.start()
progress_bar.pack_forget()
progress_label.pack_forget()

directory_frame = ctk.CTkFrame(right_panel, fg_color=white, corner_radius=10)
directory_frame.pack(padx=10, fill="x")

# Directory Monitoring Label (Scrollable)
directory_label = ctk.CTkLabel(directory_frame, image=folder_ctk, text=" Directory Monitored:", compound="left", font=font, text_color=black)
directory_label.pack(pady=(10,0))

directory_textbox = ctk.CTkTextbox(directory_frame, font=font, text_color=black,
                                   width=300, height=40, wrap="none", fg_color=white)
directory_textbox.pack(pady=10)

# Set Initial Directory
update_directory_text(monitored_directory)

directory_button = ctk.CTkButton(directory_frame, text="Change Directory", command=change_directory, 
                                 font=font, fg_color=grey, hover_color=grey_hover, text_color=white, 
                                 corner_radius=10, width=200, height=40)
directory_button.pack(pady=(0,10))

buttons_frame = ctk.CTkFrame(right_panel, fg_color=white, corner_radius=10)
buttons_frame.pack(pady=10, padx=10, fill="x")

grade_button = ctk.CTkButton(buttons_frame, text="Start Grading", command=start_grading, state="disabled",
                             font=font, fg_color=grey, hover_color=grey_hover, text_color=white, 
                             corner_radius=10, width=200, height=40)
grade_button.pack(pady=(10,0))

export_button = ctk.CTkButton(buttons_frame, text="Export to Excel", command=export_to_excel, state="disabled",
                              font=font, fg_color=grey, hover_color=grey_hover, text_color=white, 
                              corner_radius=10, width=200, height=40)
export_button.pack(pady=10)

save_db_button = ctk.CTkButton(buttons_frame, text="Save to Database", command=save_to_database, state="disabled",
                               font=font, fg_color=grey, hover_color=grey_hover, text_color=white,
                               corner_radius=10, width=200, height=40)
save_db_button.pack(pady=(0,10))

load_db_button = ctk.CTkButton(buttons_frame, text="Load from Database", command=load_from_database,
                               font=font, fg_color=grey, hover_color=grey_hover, text_color=white,
                               corner_radius=10, width=200, height=40)
load_db_button.pack(pady=(0,10))

reset_button = ctk.CTkButton(buttons_frame, text="Reset", command=reset_all, 
                             font=font, fg_color=grey, hover_color=grey_hover, text_color=white, 
                             corner_radius=10, width=200, height=40)

reset_button = ctk.CTkButton(buttons_frame, text="Reset", command=reset_all, 
                             font=font, fg_color=grey, hover_color=grey_hover, text_color=white, 
                             corner_radius=10, width=200, height=40)
reset_button.pack(pady=(0,10))
reset_button.configure(state="disabled")

status_label = ctk.CTkLabel(right_panel, text="ALL APIS ACTIVE", font=font, text_color=white)
status_label.pack(pady=(20,10))


threading.Thread(target=process_images_1, daemon=True).start()
threading.Thread(target=process_images_2, daemon=True).start()
threading.Thread(target=process_images_3, daemon=True).start()
threading.Thread(target=start_monitoring, daemon=True).start()

root.mainloop()
